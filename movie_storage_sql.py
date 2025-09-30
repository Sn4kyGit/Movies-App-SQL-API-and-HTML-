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

    # 2) Movies table (fresh shape)
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            year INTEGER NOT NULL,
            rating REAL NOT NULL,
            poster_url TEXT,
            user_id INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """))

    # 3) Upgrades for existing DBs
    # 3a) poster_url column (legacy DBs)
    try:
        connection.execute(text("ALTER TABLE movies ADD COLUMN poster_url TEXT"))
    except Exception:
        pass

    # 3b) user_id column (legacy DBs)
    added_user_id = False
    try:
        connection.execute(text("ALTER TABLE movies ADD COLUMN user_id INTEGER"))
        added_user_id = True
    except Exception:
        pass

    # 4) Ensure a default user and backfill NULL user_id rows
    # Create default user if not exists
    connection.execute(text("INSERT OR IGNORE INTO users(name) VALUES (:n)"), {"n": "Default"})
    default_user_id = connection.execute(text("SELECT id FROM users WHERE name = :n"), {"n": "Default"}).scalar()

    if added_user_id:
        # Newly added column will be NULL; backfill with default user
        connection.execute(text("UPDATE movies SET user_id = :uid WHERE user_id IS NULL"),
                           {"uid": default_user_id})

    # 5) Optional: help avoid cross-user duplicates of same title
    # (SQLite can't easily add UNIQUE(user_id, title) post-hoc without table rebuild,
    # so we skip strict constraint; we enforce uniqueness on insert in code.)

    connection.commit()

# ──────────────────────────────────────────────────────────────────────────────
# User helpers
# ──────────────────────────────────────────────────────────────────────────────
def list_users() -> List[Tuple[int, str]]:
    """Return all users as (id, name)."""
    with engine.connect() as connection:
        res = connection.execute(text("SELECT id, name FROM users ORDER BY name ASC"))
        return list(res.fetchall())


def get_user_by_name(name: str) -> Optional[Tuple[int, str]]:
    """Return (id, name) if user exists, else None."""
    with engine.connect() as connection:
        row = connection.execute(text("SELECT id, name FROM users WHERE name = :n"), {"n": name}).fetchone()
        return (row[0], row[1]) if row else None


def get_or_create_user(name: str) -> Tuple[int, str]:
    """Return (id, name); create user if it doesn't exist."""
    with engine.connect() as connection:
        connection.execute(text("INSERT OR IGNORE INTO users(name) VALUES (:n)"), {"n": name})
        row = connection.execute(text("SELECT id, name FROM users WHERE name = :n"), {"n": name}).fetchone()
        connection.commit()
        return (row[0], row[1])

# ──────────────────────────────────────────────────────────────────────────────
# Movie operations (scoped by user_id)
# ──────────────────────────────────────────────────────────────────────────────
def list_movies(user_id: int) -> Dict[str, Dict]:
    """Retrieve all movies for a given user_id."""
    with engine.connect() as connection:
        result = connection.execute(
            text("""SELECT title, year, rating, poster_url
                    FROM movies
                    WHERE user_id = :uid
                    ORDER BY title COLLATE NOCASE ASC"""),
            {"uid": user_id}
        )
        movies = result.fetchall()

    return {
        row[0]: {"year": row[1], "rating": row[2], "poster_url": row[3]}
        for row in movies
    }


def add_movie(title: str, year: int, rating: float, poster_url: Optional[str], user_id: int) -> None:
    """Add a new movie for the user. Enforce per-user title uniqueness in code."""
    with engine.connect() as connection:
        try:
            # enforce uniqueness per user
            exists = connection.execute(
                text("SELECT 1 FROM movies WHERE user_id = :uid AND title = :t"),
                {"uid": user_id, "t": title}
            ).fetchone()
            if exists:
                raise ValueError(f"Movie '{title}' already exists for this user.")

            connection.execute(
                text("""
                    INSERT INTO movies (title, year, rating, poster_url, user_id)
                    VALUES (:title, :year, :rating, :poster_url, :uid)
                """),
                {"title": title, "year": year, "rating": rating, "poster_url": poster_url, "uid": user_id}
            )
            connection.commit()
            print(f"Movie '{title}' added successfully.")
        except Exception as e:
            print(f"Error: {e}")
            raise


def delete_movie(title: str, user_id: int) -> None:
    """Delete a movie for the user.

    Raises:
        KeyError: if the movie title does not exist for that user.
    """
    with engine.connect() as connection:
        result = connection.execute(
            text("DELETE FROM movies WHERE title = :title AND user_id = :uid"),
            {"title": title, "uid": user_id}
        )
        connection.commit()
        if result.rowcount == 0:
            raise KeyError(f"Movie '{title}' not found for this user.")
        else:
            print(f"Movie '{title}' deleted successfully.")


def update_movie(
    title: str,
    user_id: int,
    rating: Optional[float] = None,
    year: Optional[int] = None,
    poster_url: Optional[str] = None
) -> None:
    """Update a movie's fields for the given user."""
    if rating is None and year is None and poster_url is None:
        print("No updates provided.")
        return

    set_parts = []
    params = {"title": title, "uid": user_id}

    if rating is not None:
        set_parts.append("rating = :rating")
        params["rating"] = rating
    if year is not None:
        set_parts.append("year = :year")
        params["year"] = year
    if poster_url is not None:
        set_parts.append("poster_url = :poster_url")
        params["poster_url"] = poster_url

    set_clause = ", ".join(set_parts)

    with engine.connect() as connection:
        result = connection.execute(
            text(f"UPDATE movies SET {set_clause} WHERE title = :title AND user_id = :uid"),
            params
        )
        connection.commit()
        if result.rowcount == 0:
            print(f"No movie found with title '{title}' for this user.")
        else:
            changed = []
            if rating is not None:
                changed.append(f"rating to {rating}")
            if year is not None:
                changed.append(f"year to {year}")
            if poster_url is not None:
                changed.append("poster_url updated")
            print(f"Movie '{title}' updated: " + ", ".join(changed) + ".")