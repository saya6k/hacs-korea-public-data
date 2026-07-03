"""KATEC (Bessel 1841 TM) -> WGS84 conversion for Opinet's GIS_X_COOR/GIS_Y_COOR fields.

Opinet reports station coordinates in KATEC, a Bessel-ellipsoid Transverse
Mercator grid (lat0=38N, lon0=128E, k0=0.9999, false easting/northing
400000/600000) - not GPS/WGS84. Converting requires an inverse TM projection
back to Bessel lat/lon, then a 7-parameter Bursa-Wolf datum shift to WGS84.
"""
from __future__ import annotations
import math

_A = 6377397.155  # Bessel 1841 semi-major axis
_INVF = 299.1528128
_F = 1 / _INVF
_E2 = _F * (2 - _F)
_LAT0 = math.radians(38.0)
_LON0 = math.radians(128.0)
_K0 = 0.9999
_FE = 400000.0
_FN = 600000.0

# Bessel -> WGS84 seven-parameter transform (NGII values used for Korean datums)
_DX, _DY, _DZ = -115.80, 474.99, 674.11
_RX = math.radians(-1.16 / 3600)
_RY = math.radians(2.31 / 3600)
_RZ = math.radians(1.63 / 3600)
_DS = 6.43e-6

_WGS84_A = 6378137.0
_WGS84_F = 1 / 298.257223563
_WGS84_E2 = _WGS84_F * (2 - _WGS84_F)


def _meridian_arc(lat: float) -> float:
    e2 = _E2
    return _A * (
        (1 - e2 / 4 - 3 * e2**2 / 64 - 5 * e2**3 / 256) * lat
        - (3 * e2 / 8 + 3 * e2**2 / 32 + 45 * e2**3 / 1024) * math.sin(2 * lat)
        + (15 * e2**2 / 256 + 45 * e2**3 / 1024) * math.sin(4 * lat)
        - (35 * e2**3 / 3072) * math.sin(6 * lat)
    )


def _bessel_to_wgs84(lat: float, lon: float) -> tuple[float, float]:
    n = _A / math.sqrt(1 - _E2 * math.sin(lat) ** 2)
    x = n * math.cos(lat) * math.cos(lon)
    y = n * math.cos(lat) * math.sin(lon)
    z = n * (1 - _E2) * math.sin(lat)

    x2 = _DX + (1 + _DS) * (x + _RZ * y - _RY * z)
    y2 = _DY + (1 + _DS) * (-_RZ * x + y + _RX * z)
    z2 = _DZ + (1 + _DS) * (_RY * x - _RX * y + z)

    p = math.sqrt(x2**2 + y2**2)
    lon_w = math.atan2(y2, x2)
    lat_w = math.atan2(z2, p * (1 - _WGS84_E2))
    for _ in range(5):
        n_w = _WGS84_A / math.sqrt(1 - _WGS84_E2 * math.sin(lat_w) ** 2)
        h = p / math.cos(lat_w) - n_w
        lat_w = math.atan2(z2, p * (1 - _WGS84_E2 * n_w / (n_w + h)))

    return math.degrees(lat_w), math.degrees(lon_w)


def katec_to_wgs84(x: float, y: float) -> tuple[float, float]:
    """Convert a KATEC (GIS_X_COOR, GIS_Y_COOR) pair to (latitude, longitude)."""
    e2 = _E2
    ep2 = e2 / (1 - e2)
    m0 = _meridian_arc(_LAT0)
    m = m0 + (y - _FN) / _K0
    mu = m / (_A * (1 - e2 / 4 - 3 * e2**2 / 64 - 5 * e2**3 / 256))
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    lat1 = (
        mu
        + (3 * e1 / 2 - 27 * e1**3 / 32) * math.sin(2 * mu)
        + (21 * e1**2 / 16 - 55 * e1**4 / 32) * math.sin(4 * mu)
        + (151 * e1**3 / 96) * math.sin(6 * mu)
        + (1097 * e1**4 / 512) * math.sin(8 * mu)
    )

    c1 = ep2 * math.cos(lat1) ** 2
    t1 = math.tan(lat1) ** 2
    n1 = _A / math.sqrt(1 - e2 * math.sin(lat1) ** 2)
    r1 = _A * (1 - e2) / (1 - e2 * math.sin(lat1) ** 2) ** 1.5
    d = (x - _FE) / (n1 * _K0)

    lat = lat1 - (n1 * math.tan(lat1) / r1) * (
        d**2 / 2
        - (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * ep2) * d**4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1**2 - 252 * ep2 - 3 * c1**2) * d**6 / 720
    )
    lon = _LON0 + (
        d
        - (1 + 2 * t1 + c1) * d**3 / 6
        + (5 - 2 * c1 + 28 * t1 - 3 * c1**2 + 8 * ep2 + 24 * t1**2) * d**5 / 120
    ) / math.cos(lat1)

    return _bessel_to_wgs84(lat, lon)
