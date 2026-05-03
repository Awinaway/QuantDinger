"""
Canonical market/symbol helpers for native QuantDinger flows.

Purpose:
- repair legacy watchlist rows whose `market` no longer matches the symbol
- normalize user input before native price / analysis pipelines run
- keep the rules conservative so we improve correctness without changing
  product semantics more than necessary
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from app.data_sources.factory import DataSourceFactory
from app.services.mt5_trading.symbols import parse_symbol as parse_mt5_symbol
from app.utils.db import get_db_connection


_CRYPTO_MAJOR_USD = {
    "BTCUSD": "BTC/USDT",
    "ETHUSD": "ETH/USDT",
    "SOLUSD": "SOL/USDT",
    "BNBUSD": "BNB/USDT",
    "XRPUSD": "XRP/USDT",
    "DOGEUSD": "DOGE/USDT",
}

_FOREX_FORCE = {
    "XAUUSD",
    "XAGUSD",
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "AUDUSD",
    "USDCAD",
    "USDCHF",
    "NZDUSD",
    "EURJPY",
    "GBPJPY",
    "EURGBP",
}


@dataclass(frozen=True)
class CanonicalMarketSymbol:
    market: str
    symbol: str


def _normalize_symbol(symbol: str) -> str:
    return (symbol or "").strip().upper()


def _seed_market_for_symbol(symbol: str) -> Tuple[Optional[str], int]:
    """
    Return (market, count) for exact symbol matches from qd_market_symbols.
    If more than one market matches, market is None and count > 1.
    """
    sym = _normalize_symbol(symbol)
    if not sym:
        return None, 0

    try:
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                """
                SELECT market
                FROM qd_market_symbols
                WHERE UPPER(symbol) = ?
                """,
                (sym,),
            )
            rows = cur.fetchall() or []
            cur.close()
    except Exception:
        return None, 0

    markets = sorted({str(r["market"]).strip() for r in rows if r.get("market")})
    if len(markets) == 1:
        return markets[0], 1
    return None, len(markets)


def _normalize_crypto_symbol(symbol: str) -> str:
    sym = _normalize_symbol(symbol)
    if not sym:
        return sym

    if sym in _CRYPTO_MAJOR_USD:
        return _CRYPTO_MAJOR_USD[sym]

    if ":" in sym:
        sym = sym.split(":", 1)[0]

    if "/" in sym:
        base, quote = sym.split("/", 1)
        return f"{base.strip()}/{quote.strip()}"

    quotes = ("USDT", "USDC", "BUSD", "USD", "BTC", "ETH", "BNB", "EUR", "GBP")
    for quote in quotes:
        if sym.endswith(quote) and len(sym) > len(quote):
            base = sym[: -len(quote)]
            if base:
                if quote == "USD" and sym in _CRYPTO_MAJOR_USD:
                    return _CRYPTO_MAJOR_USD[sym]
                return f"{base}/{quote}"

    return f"{sym}/USDT"


def canonicalize_market_symbol(market: str, symbol: str) -> CanonicalMarketSymbol:
    """
    Normalize market aliases and repair common market/symbol mismatches.

    Rules:
    - trust exact market-symbol seed matches first
    - force common FX/metals pairs into Forex
    - map major crypto USD forms (BTCUSD, ETHUSD, ...) into canonical Crypto pairs
    - otherwise keep the existing market, only normalized
    """
    raw_market = DataSourceFactory.normalize_market(market or "")
    raw_symbol = _normalize_symbol(symbol)
    if not raw_symbol:
        return CanonicalMarketSymbol(raw_market, raw_symbol)

    seed_market, seed_count = _seed_market_for_symbol(raw_symbol)
    if seed_market:
        return CanonicalMarketSymbol(seed_market, raw_symbol)

    if raw_symbol in _FOREX_FORCE:
        return CanonicalMarketSymbol("Forex", raw_symbol)

    if raw_symbol in _CRYPTO_MAJOR_USD:
        return CanonicalMarketSymbol("Crypto", _CRYPTO_MAJOR_USD[raw_symbol])

    clean, market_type = parse_mt5_symbol(raw_symbol)
    market_type = (market_type or "").lower()

    if raw_market == "Crypto":
        return CanonicalMarketSymbol("Crypto", _normalize_crypto_symbol(raw_symbol))

    if market_type == "crypto" and raw_market in {"MOEX", "USStock", "Forex"}:
        return CanonicalMarketSymbol("Crypto", _normalize_crypto_symbol(clean))

    if market_type in {"forex", "metal"} and raw_market in {"USStock", "MOEX"}:
        return CanonicalMarketSymbol("Forex", clean)

    if seed_count == 0 and raw_market == "MOEX":
        # MOEX should be explicit; if we cannot match the symbol there, avoid
        # routing arbitrary inputs into the MOEX source.
        if market_type in {"forex", "metal"}:
            return CanonicalMarketSymbol("Forex", clean)
        if market_type == "crypto":
            return CanonicalMarketSymbol("Crypto", _normalize_crypto_symbol(clean))

    return CanonicalMarketSymbol(raw_market, raw_symbol)
