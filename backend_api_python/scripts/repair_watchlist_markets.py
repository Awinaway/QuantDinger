"""
Repair legacy qd_watchlist rows whose stored market does not match the symbol.

Safe behavior:
- canonicalize each row with app.services.market_identity
- if the canonical row already exists for the same user, delete the bad duplicate
- otherwise update the row in place
"""

from __future__ import annotations

from app.data.market_symbols_seed import get_symbol_name as seed_get_symbol_name
from app.services.market_identity import canonicalize_market_symbol
from app.services.symbol_name import resolve_symbol_name
from app.utils.db import get_db_connection


def main() -> int:
    updated = 0
    deleted = 0

    with get_db_connection() as db:
        cur = db.cursor()
        cur.execute(
            """
            SELECT id, user_id, market, symbol, name
            FROM qd_watchlist
            ORDER BY user_id, id
            """
        )
        rows = cur.fetchall() or []

        for row in rows:
            row_id = row.get("id")
            user_id = row.get("user_id")
            market = row.get("market")
            symbol = row.get("symbol")
            if not row_id or not user_id or not market or not symbol:
                continue

            canonical = canonicalize_market_symbol(market, symbol)
            if canonical.market == market and canonical.symbol == symbol:
                continue

            cur.execute(
                """
                SELECT id
                FROM qd_watchlist
                WHERE user_id = ? AND market = ? AND symbol = ? AND id <> ?
                LIMIT 1
                """,
                (user_id, canonical.market, canonical.symbol, row_id),
            )
            existing = cur.fetchone()
            if existing:
                cur.execute("DELETE FROM qd_watchlist WHERE id = ?", (row_id,))
                deleted += 1
                continue

            resolved = (
                resolve_symbol_name(canonical.market, canonical.symbol)
                or seed_get_symbol_name(canonical.market, canonical.symbol)
                or row.get("name")
                or canonical.symbol
            )
            cur.execute(
                """
                UPDATE qd_watchlist
                SET market = ?, symbol = ?, name = ?, updated_at = NOW()
                WHERE id = ?
                """,
                (canonical.market, canonical.symbol, resolved, row_id),
            )
            updated += 1

        db.commit()
        cur.close()

    print(f"watchlist_repair updated={updated} deleted={deleted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
