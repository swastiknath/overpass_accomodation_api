"""Data connectors for the India travel-safety pipeline.

Each connector inherits from `connectors.base.BaseConnector` and emits
records conforming to `gis.schema.IngestedRecord`.
"""

from connectors.acled_client import ACLEDClient
from connectors.crime_client import CrimeClient
from connectors.disaster_alerts_client import DisasterAlertsClient
from connectors.news_client import NewsClient
from connectors.weather_client import WeatherClient

__all__ = [
    "ACLEDClient",
    "CrimeClient",
    "DisasterAlertsClient",
    "NewsClient",
    "WeatherClient",
]
