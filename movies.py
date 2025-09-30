from __future__ import annotations

"""
CLI Movie App with user profiles, OMDb integration, SQLite/SQLAlchemy storage,
and static website generation per user.
Update feature: adds/edits a free-text NOTE per movie.
Poster is clickable and opens IMDb.
'Add a new movie' now supports adding multiple movies in one go (type 'done' to stop).
"""

from pathlib import Path
from typing import Dict, Optional

import difflib
import html
import json
import random
import shutil
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError

import matplotlib.pyplot as plt

import movie_storage_sql as storage  # persistence layer (SQLAlchemy)

# ──────────────────────────────────────────────────────────────────────────────
# Constants & Settings
# ──────────────────────────────────────────────────────────────────────────────
APP_TITLE = "My Movies Database"
PAGE_TITLE = "My Movie App"

OMDB_API_KEY = "8496f341"
OMDB_TIMEOUT_SEC = 8
OMDB_BASE_URL = "http://www.omdbapi.com/"

# Console colors
COLOR_RESET = "\033[0m"
COLOR_ERROR = "\033[91m"   # red
COLOR_MENU = "\033[92m"    # green  - menu options
COLOR_INPUT = "\033[0m"    # default
COLOR_OUTPUT = "\033[33m"  # yellow  - normal output
COLOR_HEADER = "\033[96m"  # cyan    - headers

# Active user (set via choose_user)
ACTIVE_USER: Optional[Dict[str, object]] = None  # {"id": int, "name": str}

# ──────────────────────────────────────────────────────────────────────────────
# UI
# ──────────────────────────────────────────────────────────────────────────────
def print_title() -> None:
    print(f"{COLOR_MENU}********** {APP_TITLE} **********{COLOR_RESET}\n")


def print_menu() -> None:
    uname = ACTIVE_USER["name"] if ACTIVE_USER else "—"
    headline = f"-- {uname}s Menü --"
    inner_width = max(len(headline) + 2, 55)
    top = "┌" + "─" * inner_width + "┐"
    middle = "│" + headline.center(inner_width) + "│"
    bottom = "└" + "─" * inner_width + "┘"

    print()
    print(f"{COLOR_HEADER}{top}{COLOR_RESET}")
    print(f"{COLOR_HEADER}{middle}{COLOR_RESET}")
    print(f"{COLOR_HEADER}{bottom}{COLOR_RESET}")

    print(f"\n   {COLOR_MENU}Menu:{COLOR_RESET}")
    print(f"{COLOR_MENU}   0. Exit{COLOR_RESET}")
    print(f"{COLOR_MENU}   1. Show all Movies sorted by rating{COLOR_RESET}")
    print(f"{COLOR_MENU}   2. Show all Movies sorted by year (chronological){COLOR_RESET}")
    print(f"{COLOR_MENU}   3. List all movies{COLOR_RESET}")
    print(f"{COLOR_MENU}   4. Add a new movie{COLOR_RESET}")
    print(f"{COLOR_MENU}   5. Delete a movie{COLOR_RESET}")
    print(f"{COLOR_MENU}   6. Update movie (add/edit note){COLOR_RESET}")
    print(f"{COLOR_MENU}   7. Database Overview (Stats){COLOR_RESET}")
    print(f"{COLOR_MENU}   8. List a random movie{COLOR_RESET}")
    print(f"{COLOR_MENU}   9. Search for a movie{COLOR_RESET}")
    print(f"{COLOR_MENU}   10. Create a Rating Histogram{COLOR_RESET}")
    print(f"{COLOR_MENU}   11. Filter Movies{COLOR_RESET}")
    print(f"{COLOR_MENU}   12. Generate website{COLOR_RESET}")
    print(f"{COLOR_MENU}   13. Switch user{COLOR_RESET}")
    print()

# ──────────────────────────────────────────────────────────────────────────────
# Input helpers
# ──────────────────────────────────────────────────────────────────────────────
def require_user() -> bool:
    if ACTIVE_USER is None:
        print(f"   {COLOR_ERROR}No user selected. Choose a user first.{COLOR_RESET}")
        return False
    return True


def input_nonempty_string(prompt: str) -> str:
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print(f"   {COLOR_ERROR}Input cannot be empty. Try again.{COLOR_RESET}")


def input_float(prompt: str, min_val: float | None = None,
                max_val: float | None = None) -> float:
    while True:
        try:
            value = float(input(prompt))
            if (min_val is not None and value < min_val) or (
                max_val is not None and value > max_val
            ):
                print(
                    f"   {COLOR_ERROR}Enter a number between {min_val} and "
                    f"{max_val}.{COLOR_RESET}"
                )
                continue
            return value
        except ValueError:
            print(f"   {COLOR_ERROR}Invalid number. Try again.{COLOR_RESET}")


def input_int(prompt: str, min_val: int | None = None,
              max_val: int | None = None) -> int:
    while True:
        try:
            value = int(input(prompt))
            if (min_val is not None and value < min_val) or (
                max_val is not None and value > max_val
            ):
                print(
                    f"   {COLOR_ERROR}Enter an integer between {min_val} and "
                    f"{max_val}.{COLOR_RESET}"
                )
                continue
            return value
        except ValueError:
            print(f"   {COLOR_ERROR}Invalid integer. Try again.{COLOR_RESET}")


def input_menu_choice(prompt: str, allowed: set[str]) -> str:
    while True:
        choice = input(prompt).strip()
        if choice in allowed:
            return choice
        opts = ", ".join(sorted(allowed))
        print(f"   {COLOR_ERROR}Invalid choice. Allowed: {opts}.{COLOR_RESET}")


def safe_list_movies() -> Dict[str, Dict[str, object]]:
    assert ACTIVE_USER is not None
    try:
        return storage.list_movies(ACTIVE_USER["id"])  # type: ignore[index]
    except Exception as exc:
        print(f"   {COLOR_ERROR}DB error while listing movies: {exc}{COLOR_RESET}")
        return {}


def input_existing_title(prompt: str) -> str | None:
    if not require_user():
        return None

    movies = safe_list_movies()
    if not movies:
        print(f"   {COLOR_ERROR}No movies yet for {ACTIVE_USER['name']}.{COLOR_RESET}")
        return None

    while True:
        title = input_nonempty_string(prompt)
        if title.lower() == "cancel":
            return None
        if title in movies:
            return title
        print(
            f"   {COLOR_ERROR}Movie '{title}' not found for {ACTIVE_USER['name']}."
            f" Type 'cancel' to abort or try again.{COLOR_RESET}"
        )


def print_movie_line(idx: int, title: str, props: Dict[str, object]) -> None:
    rating = props.get("rating", "N/A")
    year = props.get("year", "N/A")
    note = props.get("note")
    note_part = f" | Note: {note}" if note else ""
    print(f"      {idx}. {title} ({year}): {rating}/10{note_part}")

# ──────────────────────────────────────────────────────────────────────────────
# User selection
# ──────────────────────────────────────────────────────────────────────────────
def choose_user() -> None:
    global ACTIVE_USER

    users = storage.list_users()
    print("Welcome to the Movie App! 🎬\n")
    if users:
        print("Select a user:")
        for i, (_, name) in enumerate(users, start=1):
            print(f"{i}. {name}")
        create_idx = len(users) + 1
        print(f"{create_idx}. Create new user\n")

        allowed = set(str(i) for i in range(1, create_idx + 1))
        choice = input_menu_choice("Enter choice: ", allowed)

        if int(choice) == create_idx:
            name = input_nonempty_string("Enter new user name: ").strip()
            uid, uname = storage.get_or_create_user(name)
            ACTIVE_USER = {"id": uid, "name": uname}
            print(f"\nWelcome, {uname}! 🎬\n")
        else:
            idx = int(choice) - 1
            uid, uname = users[idx]
            ACTIVE_USER = {"id": uid, "name": uname}
            print(f"\nWelcome back, {uname}! 🎬\n")
    else:
        print("No users yet. Let's create one.")
        name = input_nonempty_string("Enter new user name: ").strip()
        uid, uname = storage.get_or_create_user(name)
        ACTIVE_USER = {"id": uid, "name": uname}
        print(f"\nWelcome, {uname}! 🎬\n")


def switch_user() -> None:
    choose_user()

# ──────────────────────────────────────────────────────────────────────────────
# Actions (scoped to ACTIVE_USER)
# ──────────────────────────────────────────────────────────────────────────────
def list_movies() -> None:
    if not require_user():
        return
    movies = safe_list_movies()
    if not movies:
        print(
            f"   {COLOR_OUTPUT}{ACTIVE_USER['name']}, your movie collection is "
            f"empty. Add some movies!{COLOR_RESET}"
        )
        return

    print(f"   {COLOR_OUTPUT}Movies for {ACTIVE_USER['name']}:{COLOR_RESET}")
    for idx, (title, props) in enumerate(movies.items(), 1):
        print_movie_line(idx, title, props)
    print(f"   {COLOR_OUTPUT}Total movies: {len(movies)}{COLOR_RESET}")


def sort_by_rating() -> None:
    if not require_user():
        return
    movies = safe_list_movies()
    if not movies:
        print(f"   {COLOR_ERROR}No movies to sort.{COLOR_RESET}")
        return

    sorted_movies = sorted(
        movies.items(),
        key=lambda kv: (kv[1].get("rating", float("-inf")), kv[0]),
        reverse=True,
    )
    print(f"   {COLOR_OUTPUT}Movies sorted by rating:{COLOR_RESET}")
    for idx, (title, props) in enumerate(sorted_movies, 1):
        print(
            f"   {idx}. {title} ({props.get('year','N/A')}): "
            f"{props.get('rating','N/A')}/10"
        )
    print()


def sort_by_year() -> None:
    if not require_user():
        return
    movies = safe_list_movies()
    if not movies:
        print(f"   {COLOR_ERROR}No movies to sort.{COLOR_RESET}")
        return

    print(f"   {COLOR_MENU}How do you want to order them?{COLOR_RESET}")
    print("   1. Latest first")
    print("   2. Latest last")
    choice = input_menu_choice(
        f"   {COLOR_INPUT}Enter choice (1-2): {COLOR_RESET}", {"1", "2"}
    )

    if choice == "1":
        sorted_movies = sorted(
            movies.items(),
            key=lambda kv: (kv[1].get("year", float("-inf")), kv[0]),
            reverse=True,
        )
    else:
        sorted_movies = sorted(
            movies.items(),
            key=lambda kv: (kv[1].get("year", float("inf")), kv[0]),
            reverse=False,
        )

    print(f"   {COLOR_OUTPUT}Movies sorted by year:{COLOR_RESET}")
    for idx, (title, props) in enumerate(sorted_movies, 1):
        year = props.get("year", "N/A")
        rating = props.get("rating", "N/A")
        print(f"   {idx}. {title} ({year}): {rating}/10")
    print()


def _fetch_from_omdb(title_query: str) -> dict | None:
    query = urllib.parse.urlencode({"t": title_query, "apikey": OMDB_API_KEY})
    url = f"{OMDB_BASE_URL}?{query}"

    try:
        with urllib.request.urlopen(url, timeout=OMDB_TIMEOUT_SEC) as resp:
            if resp.status != 200:
                print(f"   {COLOR_ERROR}OMDb HTTP error: {resp.status}{COLOR_RESET}")
                return None
            raw = resp.read()
    except HTTPError as exc:
        print(f"   {COLOR_ERROR}OMDb HTTP error: {exc.code} {exc.reason}{COLOR_RESET}")
        return None
    except URLError as exc:
        print(f"   {COLOR_ERROR}Network error reaching OMDb: {exc.reason}{COLOR_RESET}")
        return None
    except TimeoutError:
        print(f"   {COLOR_ERROR}OMDb request timed out.{COLOR_RESET}")
        return None
    except Exception as exc:
        print(f"   {COLOR_ERROR}Unexpected OMDb error: {exc}{COLOR_RESET}")
        return None

    try:
        data = json.loads(raw.decode())
    except json.JSONDecodeError:
        print(f"   {COLOR_ERROR}OMDb returned invalid JSON.{COLOR_RESET}")
        return None

    if data.get("Response") != "True":
        err_msg = data.get("Error", "Unknown error")
        print(f"   {COLOR_ERROR}OMDb error: {err_msg}{COLOR_RESET}")
        return None

    return data


def add_movie() -> None:
    """
    Add multiple movies in one go.
    Type 'done' (or 'cancel') as title to return to the main menu.
    """
    if not require_user():
        return

    print(
        f"   {COLOR_MENU}Add mode:{COLOR_RESET} "
        f"enter movie titles one by one. Type '{COLOR_OUTPUT}done{COLOR_RESET}' to finish."
    )

    while True:
        raw = input(f"   {COLOR_INPUT}Enter movie title (or 'done'): {COLOR_RESET}").strip()
        if not raw:
            print(f"   {COLOR_ERROR}Title cannot be empty.{COLOR_RESET}")
            continue
        if raw.lower() in {"done", "cancel", "exit", "quit"}:
            print(f"   {COLOR_OUTPUT}Finished adding movies.{COLOR_RESET}")
            break

        title_input = raw

        data = _fetch_from_omdb(title_input)
        if not data:
            # keep looping so the user can try another title
            continue

        title = data.get("Title") or title_input

        # Year parsing (handles ranges like "1999–2003")
        year = None
        year_str = data.get("Year", "")
        if year_str and year_str[:4].isdigit():
            year = int(year_str[:4])

        # Rating parsing
        rating = None
        rating_str = data.get("imdbRating")
        if rating_str and rating_str != "N/A":
            try:
                rating = float(rating_str)
            except ValueError:
                rating = None

        poster_url = data.get("Poster") if data.get("Poster") not in (None, "N/A") else None
        imdb_id = data.get("imdbID") or None

        if year is None or rating is None:
            print(
                f"   {COLOR_ERROR}Could not parse year/rating from OMDb for "
                f"'{title}'. Skipping.{COLOR_RESET}"
            )
            continue

        try:
            storage.add_movie(
                title=title,
                year=year,
                rating=rating,
                poster_url=poster_url,
                user_id=ACTIVE_USER["id"],  # type: ignore[index]
                imdb_id=imdb_id,
            )
            print(
                f"   {COLOR_OUTPUT}Movie '{title}' added to "
                f"{ACTIVE_USER['name']}'s collection!{COLOR_RESET}"
            )
            if poster_url:
                print(f"   {COLOR_OUTPUT}Poster: {poster_url}{COLOR_RESET}")
            if imdb_id:
                print(
                    f"   {COLOR_OUTPUT}IMDb: https://www.imdb.com/title/{imdb_id}/{COLOR_RESET}"
                )
        except ValueError as exc:
            # duplicate for this user
            print(f"   {COLOR_ERROR}{exc}{COLOR_RESET}")
        except Exception as exc:
            print(f"   {COLOR_ERROR}DB error while saving movie: {exc}{COLOR_RESET}")

    # end while


def delete_movie() -> None:
    if not require_user():
        return
    title = input_existing_title(
        f"   {COLOR_INPUT}Enter movie title to delete (or 'cancel'): {COLOR_RESET}"
    )
    if title is None:
        print(f"   {COLOR_OUTPUT}Delete cancelled.{COLOR_RESET}")
        return
    try:
        storage.delete_movie(title, ACTIVE_USER["id"])  # type: ignore[index]
        print(
            f"   {COLOR_OUTPUT}Movie '{title}' deleted from "
            f"{ACTIVE_USER['name']}'s collection.{COLOR_RESET}"
        )
    except KeyError as exc:
        print(f"   {COLOR_ERROR}{exc}{COLOR_RESET}")
    except Exception as exc:
        print(f"   {COLOR_ERROR}DB error while deleting movie: {exc}{COLOR_RESET}")


def update_movie() -> None:
    """Update = add/edit a NOTE for the user's movie."""
    if not require_user():
        return

    title = input_existing_title(
        f"   {COLOR_INPUT}Enter movie title to add a note (or 'cancel'): {COLOR_RESET}"
    )
    if title is None:
        print(f"   {COLOR_OUTPUT}Update cancelled.{COLOR_RESET}")
        return

    note = input_nonempty_string(f"   {COLOR_INPUT}Enter movie note: {COLOR_RESET}")

    try:
        storage.update_movie(
            title=title, user_id=ACTIVE_USER["id"], note=note  # type: ignore[index]
        )
        print(f"   {COLOR_OUTPUT}Movie '{title}' successfully updated.{COLOR_RESET}")
    except KeyError as exc:
        print(f"   {COLOR_ERROR}{exc}{COLOR_RESET}")
    except Exception as exc:
        print(f"   {COLOR_ERROR}DB error while updating movie: {exc}{COLOR_RESET}")


def show_stats() -> None:
    if not require_user():
        return
    movies = safe_list_movies()
    if not movies:
        print(f"   {COLOR_ERROR}No movies to analyze.{COLOR_RESET}")
        return

    ratings = [
        p.get("rating")
        for p in movies.values()
        if isinstance(p.get("rating"), (int, float))
    ]
    if not ratings:
        print(f"   {COLOR_ERROR}No numeric ratings available.{COLOR_RESET}")
        return

    ratings.sort()
    n = len(ratings)
    avg = sum(ratings) / n
    median = ratings[n // 2] if n % 2 == 1 else (
        ratings[n // 2 - 1] + ratings[n // 2]
    ) / 2
    max_rating = max(ratings)
    min_rating = min(ratings)
    best = [t for t, p in movies.items() if p.get("rating") == max_rating]
    worst = [t for t, p in movies.items() if p.get("rating") == min_rating]

    print(
        f"   {COLOR_OUTPUT}Average: {avg:.1f} | Median: {median:.1f} | "
        f"Best: {', '.join(best)} | Worst: {', '.join(worst)}{COLOR_RESET}"
    )


def random_movie() -> None:
    if not require_user():
        return
    movies = safe_list_movies()
    if not movies:
        print(f"   {COLOR_ERROR}No movies available.{COLOR_RESET}")
        return

    title, props = random.choice(list(movies.items()))
    print(
        f"   {COLOR_OUTPUT}Random movie: {title} "
        f"({props.get('year','N/A')}) — {props.get('rating','N/A')}/10{COLOR_RESET}"
    )


def search_movie() -> None:
    if not require_user():
        return
    movies = safe_list_movies()
    if not movies:
        print(f"   {COLOR_ERROR}No movies in database.{COLOR_RESET}")
        return

    keyword = input_nonempty_string(
        f"   {COLOR_INPUT}Enter search keyword: {COLOR_RESET}"
    ).lower()

    found_any = False
    for title, props in movies.items():
        if keyword in title.lower():
            print(
                f"   {COLOR_OUTPUT}{title} ({props.get('year','N/A')}): "
                f"{props.get('rating','N/A')}/10{COLOR_RESET}",
                end=" | ",
            )
            found_any = True

    if found_any:
        print()
        return

    close = difflib.get_close_matches(keyword, movies.keys(), n=5, cutoff=0.4)
    if close:
        print(f"\n   {COLOR_ERROR}No exact match found. Did you mean:{COLOR_RESET} ", end="")
        for match in close:
            props = movies[match]
            print(
                f"{COLOR_OUTPUT}{match} ({props.get('year','N/A')}): "
                f"{props.get('rating','N/A')}/10{COLOR_RESET}",
                end=" | ",
            )
        print()
    else:
        print(f"   {COLOR_ERROR}No matching movies found.{COLOR_RESET}")


def create_histogram() -> None:
    if not require_user():
        return
    movies = safe_list_movies()
    if not movies:
        print(f"   {COLOR_ERROR}No movies to analyze.{COLOR_RESET}")
        return

    ratings = [
        p.get("rating")
        for p in movies.values()
        if isinstance(p.get("rating"), (int, float))
    ]
    if not ratings:
        print(f"   {COLOR_ERROR}No numeric ratings available.{COLOR_RESET}")
        return

    filename = input_nonempty_string(
        f"   {COLOR_INPUT}Enter filename (e.g., ratings.png): {COLOR_RESET}"
    )

    plt.hist(ratings, bins=10, range=(0, 10), edgecolor="black", color="orange")
    plt.title("Movie Ratings Histogram")
    plt.xlabel("Rating")
    plt.ylabel("Count")
    plt.savefig(filename)
    plt.close()
    print(f"   {COLOR_OUTPUT}Histogram saved to {filename}{COLOR_RESET}")


def filter_movies() -> None:
    """Interactive filter: by min rating and optional year range."""
    if not require_user():
        return

    movies = safe_list_movies()
    if not movies:
        print(f"   {COLOR_ERROR}No movies available to filter.{COLOR_RESET}")
        return

    min_rating_in = input(
        f"   {COLOR_INPUT}Enter minimum rating (blank = none): {COLOR_RESET}"
    ).strip()
    start_year_in = input(
        f"   {COLOR_INPUT}Enter start year (blank = none): {COLOR_RESET}"
    ).strip()
    end_year_in = input(
        f"   {COLOR_INPUT}Enter end year (blank = none): {COLOR_RESET}"
    ).strip()

    min_rating = float(min_rating_in) if min_rating_in else None
    start_year = int(start_year_in) if start_year_in else None
    end_year = int(end_year_in) if end_year_in else None

    filtered: list[tuple[str, Dict[str, object]]] = []
    for title, props in movies.items():
        rating = props.get("rating")
        year = props.get("year")

        if min_rating is not None and (
            not isinstance(rating, (int, float)) or rating < min_rating
        ):
            continue
        if start_year is not None and (not isinstance(year, int) or year < start_year):
            continue
        if end_year is not None and (not isinstance(year, int) or year > end_year):
            continue

        filtered.append((title, props))

    if not filtered:
        print(f"   {COLOR_ERROR}No movies matched the given criteria.{COLOR_RESET}")
        return

    print(f"   {COLOR_OUTPUT}Filtered Movies for {ACTIVE_USER['name']}:{COLOR_RESET}")
    for idx, (title, props) in enumerate(filtered, 1):
        print(
            f"   {idx}. {title} ({props.get('year','N/A')}): "
            f"{props.get('rating','N/A')}/10"
        )
    print()

# ──────────────────────────────────────────────────────────────────────────────
# Website generation (per user; writes <username>.html)
# ──────────────────────────────────────────────────────────────────────────────
def generate_website() -> None:
    """
    Generate a static website for the active user.

    Template: _static/index_template.html
    Output:   ./<username>.html
    CSS:      ensure ./style.css exists (copied from _static/style.css)
    Hover:    show note via CSS tooltip (data-note on poster element)
    Click:    poster links to IMDb if imdb_id exists
    """
    if not require_user():
        return

    movies = safe_list_movies()
    project_dir = Path(__file__).parent
    static_dir = project_dir / "_static"
    template_path = static_dir / "index_template.html"
    output_path = project_dir / f"{ACTIVE_USER['name']}.html"
    css_src = static_dir / "style.css"
    css_dst = project_dir / "style.css"

    if not template_path.exists():
        print(f"   {COLOR_ERROR}Template not found: {template_path}{COLOR_RESET}")
        return

    try:
        template = template_path.read_text(encoding="utf-8")
    except Exception as exc:
        print(f"   {COLOR_ERROR}Failed to read template: {exc}{COLOR_RESET}")
        return

    # Build grid (NOTE via data-note; rating badge; poster is a link to IMDb)
    grid_items: list[str] = []
    if movies:
        for title, props in movies.items():
            safe_title = html.escape(str(title))
            year = props.get("year")
            safe_year = html.escape(str(year)) if year is not None else "N/A"
            poster_url = props.get("poster_url") or ""
            safe_poster = html.escape(poster_url) if poster_url else ""
            note = props.get("note") or ""
            safe_note = html.escape(str(note)) if note else ""
            rating = props.get("rating")
            rating_txt = f"{float(rating):.1f}" if isinstance(rating, (int, float)) else "–"
            imdb_id = props.get("imdb_id") or ""
            imdb_url = f"https://www.imdb.com/title/{html.escape(imdb_id)}/" if imdb_id else "#"

            # Use <a class="poster"> to keep tooltip styles and make it clickable
            grid_items.append(
                (
                    '<li class="movie">\n'
                    f'  <a class="poster" data-note="{safe_note}" href="{imdb_url}" '
                    'target="_blank" rel="noopener noreferrer">\n'
                    f'    <span class="rating-badge">{rating_txt}</span>\n'
                    f'    <img src="{safe_poster}" alt="{safe_title} poster" />\n'
                    "  </a>\n"
                    f'  <div class="title">{safe_title}</div>\n'
                    f'  <div class="year">{safe_year}</div>\n'
                    "</li>"
                )
            )
    else:
        grid_items.append(
            '<li class="movie empty">No movies yet. Add some and regenerate the site.</li>'
        )

    grid_html = "\n".join(grid_items)

    html_out = (
        template.replace("__TEMPLATE_TITLE__", PAGE_TITLE)
        .replace("__TEMPLATE_MOVIE_GRID__", grid_html)
    )

    try:
        output_path.write_text(html_out, encoding="utf-8")
    except Exception as exc:
        print(f"   {COLOR_ERROR}Failed to write output HTML: {exc}{COLOR_RESET}")
        return

    try:
        if css_src.exists():
            shutil.copyfile(css_src, css_dst)
    except Exception as exc:
        print(f"   {COLOR_ERROR}Could not copy style.css: {exc}{COLOR_RESET}")

    print(
        f"   {COLOR_OUTPUT}Website was generated successfully for "
        f"{ACTIVE_USER['name']}.{COLOR_RESET}"
    )
    print(f"   {COLOR_OUTPUT}Open: {output_path}{COLOR_RESET}")

# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────
def main() -> None:
    print_title()
    choose_user()

    while True:
        print_menu()
        allowed = set(str(i) for i in range(14))
        choice = input_menu_choice(
            f"   {COLOR_INPUT}Enter choice (0-13): {COLOR_RESET}", allowed
        )
        print()
        if choice == "0":
            print("   Bye!")
            break
        if choice == "1":
            sort_by_rating()
        elif choice == "2":
            sort_by_year()
        elif choice == "3":
            list_movies()
        elif choice == "4":
            add_movie()             # now loops until 'done'
        elif choice == "5":
            delete_movie()
        elif choice == "6":
            update_movie()          # write/edit NOTE
        elif choice == "7":
            show_stats()
        elif choice == "8":
            random_movie()
        elif choice == "9":
            search_movie()
        elif choice == "10":
            create_histogram()
        elif choice == "11":
            filter_movies()
        elif choice == "12":
            generate_website()
        elif choice == "13":
            switch_user()
        print()


if __name__ == "__main__":
    main()