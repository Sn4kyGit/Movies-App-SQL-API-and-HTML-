"""
Persistence layer for the Movies app.

- Speichert IMMER neben dieser Datei (modulrelativ): data.json
- Legt data.json automatisch an
- Robust gegen leere/kaputte JSON
- Atomare Saves (erst .tmp, dann os.replace)
"""

from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Dict, Any

# Datei IMMER neben movie_storage.py ablegen
BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data.json"


def _ensure_file() -> None:
    """Erstellt die Datei, wenn sie fehlt oder leer ist."""
    if not DATA_FILE.exists() or DATA_FILE.stat().st_size == 0:
        DATA_FILE.write_text("{}", encoding="utf-8")


def get_movies() -> Dict[str, Dict[str, Any]]:
    """Liest alle Movies (immer ein Dict)."""
    _ensure_file()
    try:
        with DATA_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        DATA_FILE.write_text("{}", encoding="utf-8")
        return {}


def save_movies(movies: Dict[str, Dict[str, Any]]) -> None:
    """Speichert atomar."""
    _ensure_file()
    tmp = DATA_FILE.with_suffix(DATA_FILE.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(movies, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())  # sicherheitshalber auf Platte schreiben
    os.replace(tmp, DATA_FILE)  # atomar austauschen


def add_movie(title: str, year: int, rating: float, **extra_props: Any) -> None:
    """Fügt neuen Film hinzu (Fehler, wenn schon vorhanden)."""
    movies = get_movies()
    if title in movies:
        raise ValueError(f"Movie '{title}' already exists.")
    props: Dict[str, Any] = {"year": year, "rating": rating}
    if extra_props:
        props.update(extra_props)
    movies[title] = props
    save_movies(movies)


def delete_movie(title: str) -> None:
    """Löscht Film (Fehler, wenn nicht vorhanden)."""
    movies = get_movies()
    if title not in movies:
        raise KeyError(f"Movie '{title}' not found.")
    del movies[title]
    save_movies(movies)


def update_movie(
    title: str,
    *,
    year: int | None = None,
    rating: float | None = None,
    **extra_updates: Any,
) -> None:
    """Aktualisiert Felder eines Films (Fehler, wenn nicht vorhanden)."""
    movies = get_movies()
    if title not in movies:
        raise KeyError(f"Movie '{title}' not found.")

    if year is not None:
        movies[title]["year"] = year
    if rating is not None:
        movies[title]["rating"] = rating
    if extra_updates:
        movies[title].update(extra_updates)

    save_movies(movies)
