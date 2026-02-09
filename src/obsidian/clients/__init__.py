"""API client layer for OBSIDIAN MM.

Async HTTP clients for fetching market microstructure data from:
- Unusual Whales: Dark pool flow, options Greeks
- Polygon.io: Price bars, quotes
- Financial Modeling Prep: Fundamentals, index weights
- FRED: Macro release dates (CPI, NFP)
"""

from obsidian.clients.base import BaseAsyncClient, RateLimiter, APIProviderError
from obsidian.clients.unusual_whales import UnusualWhalesClient
from obsidian.clients.polygon import PolygonClient
from obsidian.clients.fmp import FMPClient
from obsidian.clients.fred import FREDClient

__all__ = [
    "BaseAsyncClient",
    "RateLimiter",
    "APIProviderError",
    "UnusualWhalesClient",
    "PolygonClient",
    "FMPClient",
    "FREDClient",
]
