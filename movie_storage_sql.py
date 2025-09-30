from sqlalchemy import create_engine, text

# Define the database URL
DB_URL = "sqlite:///movies.db"

# Create the engine (echo=True prints all SQL for debugging)
engine = create_engine(DB_URL, echo=True)

# Create/upgrade the movies table
with engine.connect() as connection:
    # Create with poster_url column for fresh databases
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT UNIQUE NOT NULL,
            year INTEGER NOT NULL,
            rating REAL NOT NULL,
            poster_url TEXT
        )
    """))

    # Upgrade path for existing DBs: add poster_url if it doesn't exist
    try:
        connection.execute(text("ALTER TABLE movies ADD COLUMN poster_url TEXT"))
    except Exception:
        # Column likely already exists; ignore
        pass

    connection.commit()


def list_movies():
    """Retrieve all movies from the database."""
    with engine.connect() as connection:
        result = connection.execute(text("SELECT title, year, rating, poster_url FROM movies"))
        movies = result.fetchall()

    return {
        row[0]: {"year": row[1], "rating": row[2], "poster_url": row[3]}
        for row in movies
    }


def add_movie(title: str, year: int, rating: float, poster_url: str | None = None):
    """Add a new movie to the database."""
    with engine.connect() as connection:
        try:
            connection.execute(
                text("""
                    INSERT INTO movies (title, year, rating, poster_url)
                    VALUES (:title, :year, :rating, :poster_url)
                """),
                {"title": title, "year": year, "rating": rating, "poster_url": poster_url}
            )
            connection.commit()
            print(f"Movie '{title}' added successfully.")
        except Exception as e:
            print(f"Error: {e}")


def delete_movie(title: str):
    """Delete a movie from the database."""
    with engine.connect() as connection:
        result = connection.execute(
            text("DELETE FROM movies WHERE title = :title"),
            {"title": title}
        )
        connection.commit()
        if result.rowcount == 0:
            print(f"No movie found with title '{title}'.")
        else:
            print(f"Movie '{title}' deleted successfully.")


def update_movie(
    title: str,
    rating: float | None = None,
    year: int | None = None,
    poster_url: str | None = None
):
    """Update a movie's rating and/or year and/or poster URL in the database."""
    if rating is None and year is None and poster_url is None:
        print("No updates provided.")
        return

    set_parts = []
    params = {"title": title}

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
            text(f"UPDATE movies SET {set_clause} WHERE title = :title"),
            params
        )
        connection.commit()
        if result.rowcount == 0:
            print(f"No movie found with title '{title}'.")
        else:
            changed = []
            if rating is not None:
                changed.append(f"rating to {rating}")
            if year is not None:
                changed.append(f"year to {year}")
            if poster_url is not None:
                changed.append("poster_url updated")
            print(f"Movie '{title}' updated: " + ", ".join(changed) + ".")