from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from sqlalchemy import create_engine, text

# Define the database URL
DB_URL = "sqlite:///movies.db"

# Create the engine (echo=True prints all SQL for debugging)
engine = create_engine(DB_URL, echo=True)

# ──────────────────────────────────────────────────────────────────────────────
# Schema setup & migrations
# ──────────────────────────────────────────────────────────────────────────────
with engine.connect() as connection:
    # 1) Users table
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    """))

    # 2) Movies table (includes note)
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            year INTEGER NOT NULL,
            rating REAL NOT NULL,
            poster_url TEXT,
            user_id INTEGER NOT NULL,
            note TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """))

    # 3) Upgrades for existing DBs (ignore if already there)
    for col_sql in (
        "ALTER TABLE movies ADD COLUMN poster_url TEXT",
        "ALTER TABLE movies ADD COLUMN user_id INTEGER",
        "ALTER TABLE movies ADD COLUMN note TEXT",
    ):
        try:
            connection.execute(text(col_sql))
        except Exception:
            pass

    # 4) Ensure default user & backfill user_id when missing
    connection.execute(
        text("INSERT OR IGNORE INTO users(name) VALUES (:n)"),
        {"n": "Default"},
    )
    default_user_id = connection.execute(
        text("SELECT id FROM users WHERE name = :n"), {"n": "Default"}
    ).scalar()

    connection.execute(
        text("UPDATE movies SET user_id = :uid WHERE user_id IS NULL"),
        {"uid": default_user_id},
    )

    connection.commit()

# ──────────────────────────────────────────────────────────────────────────────
# User helpers
# ──────────────────────────────────────────────────────────────────────────────
def list_users() -> List[Tuple[int, str]]:
    with engine.connect() as connection:
        res = connection.execute(
            text("SELECT id, name FROM users ORDER BY name ASC")
        )
        return list(res.fetchall())


def get_user_by_name(name: str) -> Optional[Tuple[int, str]]:
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT id, name FROM users WHERE name = :n"),
            {"n": name},
        ).fetchone()
        return (row[0], row[1]) if row else None


def get_or_create_user(name: str) -> Tuple[int, str]:
    with engine.connect() as connection:
        connection.execute(
            text("INSERT OR IGNORE INTO users(name) VALUES (:n)"),
            {"n": name},
        )
        row = connection.execute(
            text("SELECT id, name FROM users WHERE name = :n"),
            {"n": name},
        ).fetchone()
        connection.commit()
        return (row[0], row[1])

# ──────────────────────────────────────────────────────────────────────────────
# Movie operations (scoped by user_id)
# ──────────────────────────────────────────────────────────────────────────────
def list_movies(user_id: int) -> Dict[str, Dict]:
    """Retrieve all movies for a given user_id."""
    with engine.connect() as connection:
        result = connection.execute(
            text("""
                SELECT title, year, rating, poster_url, note
                FROM movies
                WHERE user_id = :uid
                ORDER BY title COLLATE NOCASE ASC
            """),
            {"uid": user_id},
        )
        rows = result.fetchall()

    return {
        r[0]: {"year": r[1], "rating": r[2], "poster_url": r[3], "note": r[4]}
        for r in rows
    }


def add_movie(
    title: str,
    year: int,
    rating: float,
    poster_url: Optional[str],
    user_id: int,
) -> None:
    """Add a new movie for the user. Enforce per-user title uniqueness in code."""
    with engine.connect() as connection:
        exists = connection.execute(
            text("SELECT 1 FROM movies WHERE user_id = :uid AND title = :t"),
            {"uid": user_id, "t": title},
        ).fetchone()
        if exists:
            raise ValueError(f"Movie '{title}' already exists for this user.")

        connection.execute(
            text("""
                INSERT INTO movies (title, year, rating, poster_url, user_id, note)
                VALUES (:title, :year, :rating, :poster_url, :uid, NULL)
            """),
            {
                "title": title,
                "year": year,
                "rating": rating,
                "poster_url": poster_url,
                "uid": user_id,
            },
        )
        connection.commit()
        print(f"Movie '{title}' added successfully.")


def delete_movie(title: str, user_id: int) -> None:
    """Delete a movie for the user."""
    with engine.connect() as connection:
        result = connection.execute(
            text("DELETE FROM movies WHERE title = :t AND user_id = :uid"),
            {"t": title, "uid": user_id},
        )
        connection.commit()
        if result.rowcount == 0:
            raise KeyError(f"Movie '{title}' not found for this user.")
        print(f"Movie '{title}' deleted successfully.")


def update_movie(
    title: str,
    user_id: int,
    *,
    rating: Optional[float] = None,
    year: Optional[int] = None,
    poster_url: Optional[str] = None,
    note: Optional[str] = None,
) -> None:
    """Update provided fields for a user's movie."""
    set_parts = []
    params = {"t": title, "uid": user_id}

    if rating is not None:
        set_parts.append("rating = :rating")
        params["rating"] = rating
    if year is not None:
        set_parts.append("year = :year")
        params["year"] = year
    if poster_url is not None:
        set_parts.append("poster_url = :poster_url")
        params["poster_url"] = poster_url
    if note is not None:
        set_parts.append("note = :note")
        params["note"] = note

    if not set_parts:
        return

    set_clause = ", ".join(set_parts)
    with engine.connect() as connection:
        result = connection.execute(
            text(f"UPDATE movies SET {set_clause} "
                 f"WHERE title = :t AND user_id = :uid"),
            params,
        )
        connection.commit()
        if result.rowcount == 0:
            raise KeyError(f"Movie '{title}' not found for this user.")
        print(f"Movie '{title}' updated.")