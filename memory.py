
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).with_name("bud.sqlite3")


def setup():
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fact TEXT NOT NULL UNIQUE
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                chat_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS away_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                sender TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        db.execute("""
            INSERT OR IGNORE INTO settings (key, value)
            VALUES ('auto_reply', '0')
        """)
        db.execute("""
            INSERT OR IGNORE INTO settings (key, value)
            VALUES ('away', '0')
        """)


def set_setting(key, value):
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, str(value)))


def get_setting(key, default="0"):
    with sqlite3.connect(DB_PATH) as db:
        row = db.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
    return row[0] if row else default


def remember(fact):
    fact = fact.strip()[:500]
    if fact:
        with sqlite3.connect(DB_PATH) as db:
            db.execute(
                "INSERT OR IGNORE INTO memories (fact) VALUES (?)",
                (fact,),
            )


def get_memories():
    with sqlite3.connect(DB_PATH) as db:
        return [
            row[0] for row in db.execute(
                "SELECT fact FROM memories ORDER BY id DESC LIMIT 80"
            ).fetchall()
        ]


def save_chat(chat_id, role, content):
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""
            INSERT INTO chats (chat_id, role, content)
            VALUES (?, ?, ?)
        """, (chat_id, role, content[:2000]))

        db.execute("""
            DELETE FROM chats
            WHERE chat_id = ? AND rowid NOT IN (
                SELECT rowid FROM chats
                WHERE chat_id = ?
                ORDER BY rowid DESC LIMIT 20
            )
        """, (chat_id, chat_id))


def get_chat(chat_id):
    with sqlite3.connect(DB_PATH) as db:
        rows = db.execute("""
            SELECT role, content FROM chats
            WHERE chat_id = ?
            ORDER BY rowid DESC LIMIT 12
        """, (chat_id,)).fetchall()

    return [
        {"role": role, "content": content}
        for role, content in reversed(rows)
    ]


def log_away_message(chat_id, sender, content):
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""
            INSERT INTO away_messages
                (chat_id, sender, content, created_at)
            VALUES (?, ?, ?, ?)
        """, (
            chat_id,
            sender[:100],
            content[:2000],
            datetime.now(timezone.utc).isoformat(),
        ))


def get_away_messages():
    with sqlite3.connect(DB_PATH) as db:
        return db.execute("""
            SELECT chat_id, sender, content, created_at
            FROM away_messages ORDER BY id
        """).fetchall()


def clear_away_messages():
    with sqlite3.connect(DB_PATH) as db:
        db.execute("DELETE FROM away_messages")