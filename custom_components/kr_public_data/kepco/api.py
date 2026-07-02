"""KEPCO API client - NO module-level curl_cffi import."""
from __future__ import annotations
import json
import logging

from .exceptions import KepcoAuthError

_LOGGER = logging.getLogger(__name__)

_LOGIN_OK_URL_MARKERS = ("confirmInfo.do",)
_LOGIN_FAIL_BODY_MARKERS = (
    "비밀번호가 일치하지 않습니다",
    "존재하지 않는 아이디",
    "로그인에 실패",
    "아이디 또는 비밀번호",
)


def _get_rsa_key():
    """Lazy import RSAKey to avoid triggering utils import chain."""
    from ..utils import RSAKey
    return RSAKey


class KepcoApiClient:
    def __init__(self, session):
        self._session = session
        self._username = None
        self._password = None

    def set_credentials(self, username, password):
        self._username = username
        self._password = password

    async def async_get_session_and_rsa_key(self):
        from bs4 import BeautifulSoup  # lazy import
        url = "https://pp.kepco.co.kr:8030/intro.do"
        result = await self._session.get(url=url)
        result.raise_for_status()
        html_text = result.text
        soup = BeautifulSoup(html_text, "html.parser")
        rsa_modulus_tag = soup.find("input", {"id": "RSAModulus"})
        rsa_exponent_tag = soup.find("input", {"id": "RSAExponent"})
        sessid_tag = soup.find("input", {"id": "SESSID"})
        if not rsa_modulus_tag or not rsa_exponent_tag or not sessid_tag:
            raise KepcoAuthError("Failed to get RSA keys from intro page")
        return (rsa_modulus_tag.get("value").strip(),
                rsa_exponent_tag.get("value").strip(),
                sessid_tag.get("value").strip())

    async def async_login(self, username, password):
        self.set_credentials(username, password)
        try:
            rsa_modulus, rsa_exponent, sessid = await self.async_get_session_and_rsa_key()
        except KepcoAuthError:
            return False
        RSAKey = _get_rsa_key()
        try:
            rsa_key = RSAKey()
            rsa_key.set_public(rsa_modulus, rsa_exponent)
            enc_user = rsa_key.encrypt(username)
            enc_pass = rsa_key.encrypt(password)
            if not enc_user or not enc_pass:
                raise ValueError("RSA encryption failed")
        except Exception as e:
            _LOGGER.error("RSA encryption failed: %s", e)
            return False
        user_id = f"{sessid}_{enc_user}"
        user_pw = f"{sessid}_{enc_pass}"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "https://pp.kepco.co.kr:8030/intro.do",
            "Cookie": f"JSESSIONID={sessid}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
        }
        try:
            response = await self._session.post(
                "https://pp.kepco.co.kr:8030/login",
                data={"USER_ID": user_id, "USER_PW": user_pw},
                headers=headers, allow_redirects=True)
            if response.status_code != 200:
                _LOGGER.warning("KEPCO login returned HTTP %s", response.status_code)
                return False
            body = response.text or ""
            if any(marker in body for marker in _LOGIN_FAIL_BODY_MARKERS):
                # Definite credential rejection — distinct from network flakiness
                # so callers can trigger a reauth flow instead of retrying.
                raise KepcoAuthError("KEPCO rejected the username/password")
            if any(marker in str(response.url) for marker in _LOGIN_OK_URL_MARKERS):
                return True
            _LOGGER.warning("Unknown KEPCO login response: %s", body[:200])
            return False
        except KepcoAuthError:
            raise
        except Exception as e:
            _LOGGER.error("Login failed: %s", e)
            return False

    async def _request(self, method, url, **kwargs):
        try:
            response = await self._session.request(method, url, **kwargs)
            return json.loads(response.text)
        except Exception:
            if await self.async_login(self._username, self._password):
                try:
                    response = await self._session.request(method, url, **kwargs)
                    return json.loads(response.text)
                except Exception as retry_err:
                    _LOGGER.debug("KEPCO retry failed: %s", retry_err)
            raise

    async def async_get_recent_usage(self):
        return await self._request("POST", "https://pp.kepco.co.kr:8030/low/main/recent_usage.do", json={})

    async def async_get_usage_info(self):
        return await self._request("POST", "https://pp.kepco.co.kr:8030/low/main/usage_info.do", json={"tou": "N"})
