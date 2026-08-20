import os
import aiosqlite
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_no TEXT UNIQUE NOT NULL,
    buyer_chat_id INTEGER NOT NULL,
    target_user_id INTEGER NOT NULL,
    target_username TEXT NOT NULL,
    target_display_name TEXT,
    months INTEGER NOT NULL,
    price_usdt REAL NOT NULL,
    star_count INTEGER NOT NULL,
    status TEXT NOT NULL,
    txid TEXT UNIQUE,
    paid_from TEXT,
    created_at INTEGER NOT NULL,
    paid_at INTEGER,
    gifted_at INTEGER,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_buyer ON orders(buyer_chat_id);
"""

async def init_db(path: str):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    async with aiosqlite.connect(path) as db:
        await db.executescript(SCHEMA)
        await db.commit()

async def create_order(
    path: str,
    order_no: str,
    buyer_chat_id: int,
    target_user_id: int,
    target_username: str,
    target_display_name: str,
    months: int,
    price_usdt: float,
    star_count: int,
):
    now = int(datetime.now(timezone.utc).timestamp())
    async with aiosqlite.connect(path) as db:
        await db.execute(
            """
            INSERT INTO orders
            (order_no,buyer_chat_id,target_user_id,target_username,
             target_display_name,months,price_usdt,star_count,status,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                order_no, buyer_chat_id, target_user_id, target_username,
                target_display_name, months, price_usdt, star_count,
                "pending", now
            ),
        )
        await db.commit()

async def get_order(path: str, order_no: str):
    async with aiosqlite.connect(path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM orders WHERE order_no=?", (order_no,))
        return await cur.fetchone()

async def get_pending_orders(path: str):
    async with aiosqlite.connect(path) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM orders WHERE status='pending' ORDER BY created_at ASC"
        )
        return await cur.fetchall()

async def mark_paid(path: str, order_no: str, txid: str, paid_from: str):
    now = int(datetime.now(timezone.utc).timestamp())
    async with aiosqlite.connect(path) as db:
        cur = await db.execute(
            """
            UPDATE orders
            SET status='paid', txid=?, paid_from=?, paid_at=?
            WHERE order_no=? AND status='pending'
            """,
            (txid, paid_from, now, order_no),
        )
        await db.commit()
        return cur.rowcount == 1

async def mark_gifted(path: str, order_no: str):
    now = int(datetime.now(timezone.utc).timestamp())
    async with aiosqlite.connect(path) as db:
        await db.execute(
            "UPDATE orders SET status='gifted', gifted_at=?, error=NULL WHERE order_no=?",
            (now, order_no),
        )
        await db.commit()

async def mark_error(path: str, order_no: str, error: str, status="paid"):
    async with aiosqlite.connect(path) as db:
        await db.execute(
            "UPDATE orders SET status=?, error=? WHERE order_no=?",
            (status, error[:1000], order_no),
        )
        await db.commit()

async def tx_already_used(path: str, txid: str) -> bool:
    async with aiosqlite.connect(path) as db:
        cur = await db.execute("SELECT 1 FROM orders WHERE txid=?", (txid,))
        return await cur.fetchone() is not None
