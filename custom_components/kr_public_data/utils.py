"""Utility functions - NO pytz, NO blocking imports."""
from __future__ import annotations
import random
import re
from datetime import datetime
from typing import Dict, Any, Optional
from zoneinfo import ZoneInfo

TZ_ASIA_SEOUL = ZoneInfo("Asia/Seoul")

# 전체 시도명 → 축약명 (airkorea의 STATIONS_BY_SIDO/SIDO_AREA_CODE 키).
# 나머지 시도는 앞 두 글자가 곧 축약명이다.
_SIDO_SHORT = {"충청북도": "충북", "충청남도": "충남", "전라남도": "전남",
               "경상북도": "경북", "경상남도": "경남"}


def sido_short_name(name: str) -> str:
    """'서울특별시' → '서울', '충청북도' → '충북'."""
    return _SIDO_SHORT.get(name, name[:2])


class RSAKey:
    """RSA encryption for KEPCO login (matching rsa.js)."""
    def __init__(self):
        self.n = None
        self.e = 0

    def set_public(self, modulus_hex, exponent_hex):
        if modulus_hex and exponent_hex:
            self.n = int(modulus_hex, 16)
            self.e = int(exponent_hex, 16)
        else:
            raise ValueError("Invalid RSA public key")

    def do_public(self, x):
        return pow(x, self.e, self.n)

    def encrypt(self, text):
        key_size = (self.n.bit_length() + 7) // 8
        m = _pkcs1pad2(text, key_size)
        if m is None:
            return None
        c = self.do_public(m)
        h = hex(c)[2:]
        if len(h) % 2 == 1:
            h = "0" + h
        return h


def _pkcs1pad2(s, n):
    s_bytes = s.encode("utf-8")
    s_len = len(s_bytes)
    if n < s_len + 11:
        raise ValueError("Message too long for RSA")
    ba = bytearray(n)
    ba[n - s_len:n] = s_bytes
    ba[n - s_len - 1] = 0
    for i in range(2, n - s_len - 1):
        while True:
            rand_byte = random.randint(1, 255)
            if rand_byte != 0:
                ba[i] = rand_byte
                break
    ba[0] = 0
    ba[1] = 2
    result = int.from_bytes(ba, byteorder='big')
    return result


def get_value_from_path(data: Dict[str, Any], path: str) -> Any:
    keys = path.split(".")
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return None
        if current is None:
            return None
    return current


def parse_date_value(raw_value: str, current_year: int = None) -> Optional[datetime]:
    if not raw_value:
        return None
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y.%m.%d", "%m/%d"):
        try:
            dt = datetime.strptime(raw_value.strip(), fmt)
            if current_year and dt.year == 1900:
                dt = dt.replace(year=current_year)
            return dt
        except ValueError:
            continue
    return None

