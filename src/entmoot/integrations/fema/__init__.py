"""
FEMA National Flood Hazard Layer (NFHL) API integration.

This module provides integration with FEMA's flood map service to fetch
floodplain data and determine if properties are in flood hazard areas.
"""

from .client import FEMAClient
from .parser import FEMAResponseParser

__all__ = ["FEMAClient", "FEMAResponseParser"]
