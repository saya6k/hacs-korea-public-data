# `kepco` (한전 - 한국전력공사)

Authenticates with username/password against 사이버지점 (no API key). Login can fail silently — `__init__.py` swallows the exception so the entry still loads with stale data rather than failing setup outright.
