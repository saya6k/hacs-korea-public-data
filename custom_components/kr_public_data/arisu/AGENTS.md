# `arisu` (서울 상수도 요금·사용량)

No public API — `arisu/api.py` scrapes the Arisu website with `BeautifulSoup` (`aiohttp` + HTML parsing, not `curl_cffi`; this endpoint hasn't needed browser-TLS impersonation so far). Auth is by customer number + customer name, not a service key. Single coordinator per entry, no regions/subentries — one customer's account per entry.
