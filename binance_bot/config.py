import os
from dataclasses import dataclass

from dotenv import load_dotenv

from .exceptions import ConfigError


TESTNET_BASE_URL = "https://testnet.binancefuture.com"


@dataclass(frozen=True)
class BinanceConfig:
    api_key: str
    api_secret: str
    base_url: str = TESTNET_BASE_URL



def load_config() -> BinanceConfig:
    load_dotenv()
    api_key = os.getenv("BINANCE_API_KEY", "").strip()
    api_secret = os.getenv("BINANCE_API_SECRET", "").strip()

    if not api_key or not api_secret:
        raise ConfigError(
            "Missing API credentials. Set BINANCE_API_KEY and BINANCE_API_SECRET."
        )

    return BinanceConfig(api_key=api_key, api_secret=api_secret)
