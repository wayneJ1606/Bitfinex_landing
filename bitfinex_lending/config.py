from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    markets: tuple[str, ...] = ("fUSD", "fBTC", "fETH")
    api_base_url: str = "https://api-pub.bitfinex.com/v2"
    precision: str = "P0"
    book_length: int = 25
    timeout: float = 10.0
    database_path: Path = Path("data/bitfinex_lending.sqlite3")
    csv_directory: Path = Path("data/raw")
    market_directory: Path = Path("data/market")
    metadata_directory: Path = Path("data/metadata")

