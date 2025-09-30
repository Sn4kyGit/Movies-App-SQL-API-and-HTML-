from __future__ import annotations

import random
import difflib
import matplotlib.pyplot as plt
import json
import urllib.request, urllib.parse
from urllib.error import URLError, HTTPError
from pathlib import Path
import html
import shutil
from typing import Dict, Optional

import movie_storage_sql as storage  # persistence layer (SQLAlchemy)

# ANSI color codes
COLOR_RESET = "\033[0m"
COLOR_ERROR = "\033[91m"
COLOR_MENU = "\033[92m"     # grün – Menüoptionen
COLOR_INPUT = "\033[0m"
COLOR_OUTPUT = "\033[33m"   # gelb – normale Ausgaben
COLOR_HEADER = "\033[96m"   # CYAN – auffällige Überschriften

# Active user state
ACTIVE_USER: Optional[Dict] = None  # {"id": int, "name": str}


# ──────────────────────────────────────────────────────────────────────────────
# UI Basics
# ──────────────────────────────────────────────────────────────────────────────
def print_title():
    print(f"{COLOR_MENU}********** My Movies Database **********{COLOR_RESET}\n")


def print_menu():
    uname = ACTIVE_USER["name"] if ACTIVE_USER else "—"

    # Headline „-- Ronnys Menü --“ (deutsche Form ohne Apostroph)
    headline = f"-- {uname}s Menü --"

    # Box dynamisch breit machen
    inner_width = max(len(headline) + 2, 55)
    top    = "┌" + "─" * inner_width + "┐"
    middle = "│" + headline.center(inner_width) + "│"
    bottom = "└" + "─" * inner_width + "┘"

    print()
    print(f"{COLOR_HEADER}{top}{COLOR_RESET}")
    print(f"{COLOR_HEADER}{middle}{COLOR_RESET}")
    print(f"{COLOR_HEADER}{bottom}{COLOR_RESET}")

    # Menüeinträge in GRÜN (klare Trennung zum Cyan-Header)
    print(f"\n   {COLOR_MENU}Menu:{COLOR_RESET}")
    print(f"{COLOR_MENU}   0. Exit{COLOR_RESET}")
    print(f"{COLOR_MENU}   1. Show all Movies sorted by rating{COLOR_RESET}")
    print(f"{COLOR_MENU}   2. Show all Movies sorted by year (chronological){COLOR_RESET}")
    print(f"{COLOR_MENU}   3. List all movies{COLOR_RESET}")
    print(f"{COLOR_MENU}   4. Add a new movie{COLOR_RESET}")
    print(f"{COLOR_MENU}   5. Delete a movie{COLOR_RESET}")
    print(f"{COLOR_MENU}   6. Update a movie (rating/year){COLOR_RESET}")
    print(f"{COLOR_MENU}   7. Database Overview (Stats){COLOR_RESET}")
    print(f"{COLOR_MENU}   8. List a random movie{COLOR_RESET}")
    print(f"{COLOR_MENU}   9. Search for a movie{COLOR_RESET}")
    print(f"{COLOR_MENU}   10. Create a Rating Histogram{COLOR_RESET}")
    print(f"{COLOR_MENU}   11. Filter Movies{COLOR_RESET}")
    print(f"{COLOR_MENU}   12. Generate website{COLOR_RESET}")
    print(f"{COLOR_MENU}   13. Switch user{COLOR_RESET}")
    print()


# ──────────────────────────────────────────────────────────────────────────────
# Input Helpers
# ──────────────────────────────────────────────────────────────────────────────
def require_user() -> bool:
    """Ensure a user is selected before executing actions."""
    if ACTIVE_USER is None:
        print(f"   {COLOR_ERROR}No user selected. Please choose a user first.{COLOR_RESET}")
        return False
    return True


def input_nonempty_string(prompt: str) -> str:
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print(f"   {COLOR_ERROR}Input cannot be empty. Please try again.{COLOR_RESET}")


def input_float(prompt: str, min_val=None, max_val=None) -> float:
    while True:
        try:
            raw = input(prompt)
            value = float(raw)
            if (min_val is not None and value < min_val) or (max_val is not None and value > max_val):
                print(f"   {COLOR_ERROR}Please enter a number between {min_val} and {max_val}.{COLOR_RESET}")
                continue
            return value
        except ValueError:
            print(f"   {COLOR_ERROR}Invalid number. Please try again.{COLOR_RESET}")


def input_int(prompt: str, min_val=None, max_val=None) -> int:
    while True:
        try:
            raw = input(prompt)
            value = int(raw)
            if (min_val is not None and value < min_val) or (max_val is not None and value > max_val):
                print(f"   {COLOR_ERROR}Please enter an integer between {min_val} and {max_val}.{COLOR_RESET}")
                continue
            return value
        except ValueError:
            print(f"   {COLOR_ERROR}Invalid integer. Please try again.{COLOR_RESET}")


def input_menu_choice(prompt: str, allowed: set[str]) -> str:
    while True:
        choice = input(prompt).strip()
        if choice in allowed:
            return choice
        print(f"   {COLOR_ERROR}Invalid choice. Allowed: {', '.join(sorted(allowed))}.{COLOR_RESET}")


def input_existing_title(prompt: str) -> str | None:
    if not require_user():
        return None
    movies = storage.list_movies(ACTIVE_USER["id"])
    if not movies:
        print(f"   {COLOR_ERROR}No movies in database yet for {ACTIVE_USER['name']}.{COLOR_RESET}")
        return None

    while True:
        title = input_nonempty_string(prompt)
        if title.lower() == "cancel":
            return None
        movies = storage.list_movies(ACTIVE_USER["id"])
        if title in movies:
            return title
        print(f"   {COLOR_ERROR}Movie '{title}' not found for {ACTIVE_USER['name']}. Type 'cancel' to abort or try again.{COLOR_RESET}")


def print_movie_line(idx, title, props):
    rating = props.get("rating", "N/A")
    year = props.get("year", "N/A")
    print(f"      {idx}. {title} ({year}): {rating}/10")


# ──────────────────────────────────────────────────────────────────────────────
# User selection
# ──────────────────────────────────────────────────────────────────────────────
def choose_user():
    """Select or create a user profile at app start."""
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
        # No users yet
        print("No users yet. Let's create one.")
        name = input_nonempty_string("Enter new user name: ").strip()
        uid, uname = storage.get_or_create_user(name)
        ACTIVE_USER = {"id": uid, "name": uname}
        print(f"\nWelcome, {uname}! 🎬\n")


def switch_user():
    choose_user()


# ──────────────────────────────────────────────────────────────────────────────
# Actions (all scoped to ACTIVE_USER)
# ──────────────────────────────────────────────────────────────────────────────
def list_movies():
    if not require_user():
        return
    try:
        movies = storage.list_movies(ACTIVE_USER["id"])
    except Exception as e:
        print(f"   {COLOR_ERROR}DB error while listing movies: {e}{COLOR_RESET}")
        return

    if not movies:
        print(f"   {COLOR_OUTPUT}{ACTIVE_USER['name']}, your movie collection is empty. Add some movies!{COLOR_RESET}")
    else:
        print(f"   {COLOR_OUTPUT}Movies for {ACTIVE_USER['name']}:{COLOR_RESET}")
        for idx, (title, props) in enumerate(movies.items(), 1):
            print_movie_line(idx, title, props)
        print(f"   {COLOR_OUTPUT}Total movies: {len(movies)}{COLOR_RESET}")


def sort_by_rating():
    if not require_user():
        return
    try:
        movies = storage.list_movies(ACTIVE_USER["id"])
    except Exception as e:
        print(f"   {COLOR_ERROR}DB error while sorting by rating: {e}{COLOR_RESET}")
        return

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
        print(f"   {idx}. {title} ({props.get('year','N/A')}): {props.get('rating','N/A')}/10")
    print()


def sort_by_year():
    if not require_user():
        return
    try:
        movies = storage.list_movies(ACTIVE_USER["id"])
    except Exception as e:
        print(f"   {COLOR_ERROR}DB error while sorting by year: {e}{COLOR_RESET}")
        return

    if not movies:
        print(f"   {COLOR_ERROR}No movies to sort.{COLOR_RESET}")
        return

    print(f"   {COLOR_MENU}How do you want to order them?{COLOR_RESET}")
    print("   1. Latest first")
    print("   2. Latest last")
    choice = input_menu_choice(f"   {COLOR_INPUT}Enter choice (1-2): {COLOR_RESET}", {"1", "2"})

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


def add_movie():
    if not require_user():
        return
    title_input = input_nonempty_string(f"   {COLOR_INPUT}Enter movie title: {COLOR_RESET}")

    # Fetch from OMDb
    api_key = "8496f341"
    query = urllib.parse.urlencode({"t": title_input, "apikey": api_key})
    url = f"http://www.omdbapi.com/?{query}"

    try:
        with urllib.request.urlopen(url, timeout=8) as resp:
            if resp.status != 200:
                print(f"   {COLOR_ERROR}OMDb HTTP error: {resp.status}{COLOR_RESET}")
                return
            raw = resp.read()
        try:
            data = json.loads(raw.decode())
        except json.JSONDecodeError:
            print(f"   {COLOR_ERROR}OMDb returned invalid JSON.{COLOR_RESET}")
            return
    except HTTPError as e:
        print(f"   {COLOR_ERROR}OMDb HTTP error: {e.code} {e.reason}{COLOR_RESET}")
        return
    except URLError as e:
        print(f"   {COLOR_ERROR}Network error reaching OMDb: {e.reason}{COLOR_RESET}")
        return
    except TimeoutError:
        print(f"   {COLOR_ERROR}OMDb request timed out.{COLOR_RESET}")
        return
    except Exception as e:
        print(f"   {COLOR_ERROR}Unexpected error contacting OMDb: {e}{COLOR_RESET}")
        return

    if data.get("Response") != "True":
        err_msg = data.get("Error", "Unknown error")
        print(f"   {COLOR_ERROR}OMDb error: {err_msg}{COLOR_RESET}")
        return

    # Parse fields
    title = data.get("Title") or title_input

    year_str = data.get("Year", "")
    year = None
    if year_str and year_str[:4].isdigit():
        year = int(year_str[:4])

    rating = None
    rating_str = data.get("imdbRating")
    if rating_str and rating_str != "N/A":
        try:
            rating = float(rating_str)
        except ValueError:
            rating = None

    poster_url = data.get("Poster") if data.get("Poster") not in (None, "N/A") else None

    if year is None or rating is None:
        print(f"   {COLOR_ERROR}Could not parse year/rating from OMDb for '{title}'.{COLOR_RESET}")
        return

    # Save to DB (per-user uniqueness enforced im Storage)
    try:
        storage.add_movie(title, year, rating, poster_url, ACTIVE_USER["id"])
        print(f"   {COLOR_OUTPUT}Movie '{title}' added to {ACTIVE_USER['name']}'s collection!{COLOR_RESET}")
        if poster_url:
            print(f"   {COLOR_OUTPUT}Poster: {poster_url}{COLOR_RESET}")
    except ValueError as e:
        print(f"   {COLOR_ERROR}{e}{COLOR_RESET}")
    except Exception as e:
        print(f"   {COLOR_ERROR}DB error while saving movie: {e}{COLOR_RESET}")


def delete_movie():
    if not require_user():
        return
    title = input_existing_title(
        f"   {COLOR_INPUT}Enter movie title to delete (or type 'cancel'): {COLOR_RESET}"
    )
    if title is None:
        print(f"   {COLOR_OUTPUT}Delete cancelled.{COLOR_RESET}")
        return
    try:
        storage.delete_movie(title, ACTIVE_USER["id"])
        print(f"   {COLOR_OUTPUT}Movie '{title}' deleted from {ACTIVE_USER['name']}'s collection.{COLOR_RESET}")
    except KeyError as e:
        print(f"   {COLOR_ERROR}{e}{COLOR_RESET}")
    except Exception as e:
        print(f"   {COLOR_ERROR}DB error while deleting movie: {e}{COLOR_RESET}")


def update_movie():
    # wie besprochen: UI beibehalten; intern nach user_id updaten
    if not require_user():
        return

    title = input_existing_title(
        f"   {COLOR_INPUT}Enter movie title to update (or type 'cancel'): {COLOR_RESET}"
    )
    if title is None:
        print(f"   {COLOR_OUTPUT}Update cancelled.{COLOR_RESET}")
        return

    print(f"   {COLOR_MENU}What do you want to update?{COLOR_RESET}")
    print("   1. Rating")
    print("   2. Year")
    print("   3. Both")
    choice = input_menu_choice(f"   {COLOR_INPUT}Enter choice (1-3): {COLOR_RESET}", {"1", "2", "3"})

    updates = {}
    if choice in {"1", "3"}:
        updates["rating"] = input_float(f"   {COLOR_INPUT}Enter new rating (0-10): {COLOR_RESET}", 0, 10)

    if choice in {"2", "3"}:
        updates["year"] = input_int(f"   {COLOR_INPUT}Enter new release year: {COLOR_RESET}", 1878, 2100)

    if updates:
        try:
            storage.update_movie(title, user_id=ACTIVE_USER["id"], **updates)
            print(f"   {COLOR_OUTPUT}Movie '{title}' updated for {ACTIVE_USER['name']}.{COLOR_RESET}")
        except KeyError as e:
            print(f"   {COLOR_ERROR}{e}{COLOR_RESET}")
        except Exception as e:
            print(f"   {COLOR_ERROR}DB error while updating movie: {e}{COLOR_RESET}")
    else:
        print(f"   {COLOR_OUTPUT}No changes applied.{COLOR_RESET}")


def show_stats():
    if not require_user():
        return
    try:
        movies = storage.list_movies(ACTIVE_USER["id"])
    except Exception as e:
        print(f"   {COLOR_ERROR}DB error while computing stats: {e}{COLOR_RESET}")
        return

    if not movies:
        print(f"   {COLOR_ERROR}No movies to analyze.{COLOR_RESET}")
        return

    ratings = [p.get("rating") for p in movies.values() if isinstance(p.get("rating"), (int, float))]
    if not ratings:
        print(f"   {COLOR_ERROR}No numeric ratings available.{COLOR_RESET}")
        return

    ratings.sort()
    n = len(ratings)
    avg = sum(ratings) / n
    median = ratings[n // 2] if n % 2 == 1 else (ratings[n // 2 - 1] + ratings[n // 2]) / 2
    max_rating = max(ratings)
    min_rating = min(ratings)
    best = [t for t, p in movies.items() if p.get("rating") == max_rating]
    worst = [t for t, p in movies.items() if p.get("rating") == min_rating]

    print(
        f"   {COLOR_OUTPUT}Average: {avg:.1f} | Median: {median:.1f} | "
        f"Best: {', '.join(best)} | Worst: {', '.join(worst)}{COLOR_RESET}"
    )


def random_movie():
    if not require_user():
        return
    try:
        movies = storage.list_movies(ACTIVE_USER["id"])
    except Exception as e:
        print(f"   {COLOR_ERROR}DB error while picking random movie: {e}{COLOR_RESET}")
        return

    if movies:
        title, props = random.choice(list(movies.items()))
        print(
            f"   {COLOR_OUTPUT}Random movie: {title} ({props.get('year','N/A')}) — "
            f"{props.get('rating','N/A')}/10{COLOR_RESET}"
        )
    else:
        print(f"   {COLOR_ERROR}No movies available.{COLOR_RESET}")


def search_movie():
    if not require_user():
        return
    try:
        movies = storage.list_movies(ACTIVE_USER["id"])
    except Exception as e:
        print(f"   {COLOR_ERROR}DB error while searching: {e}{COLOR_RESET}")
        return

    if not movies:
        print(f"   {COLOR_ERROR}No movies in database.{COLOR_RESET}")
        return

    keyword = input_nonempty_string(f"   {COLOR_INPUT}Enter search keyword: {COLOR_RESET}").lower()

    found_any = False
    for title, props in movies.items():
        if keyword in title.lower():
            print(
                f"   {COLOR_OUTPUT}{title} ({props.get('year','N/A')}): "
                f"{props.get('rating','N/A')}/10{COLOR_RESET}",
                end=" | ",
            )
            found_any = True

    if not found_any:
        close_matches = difflib.get_close_matches(keyword, movies.keys(), n=5, cutoff=0.4)
        if close_matches:
            print(f"\n   {COLOR_ERROR}No exact match found. Did you mean:{COLOR_RESET} ", end="")
            for match in close_matches:
                props = movies[match]
                print(
                    f"{COLOR_OUTPUT}{match} ({props.get('year','N/A')}): "
                    f"{props.get('rating','N/A')}/10{COLOR_RESET}",
                    end=" | ",
                )
            print()
        else:
            print(f"   {COLOR_ERROR}No matching movies found.{COLOR_RESET}")
    else:
        print()


def create_histogram():
    if not require_user():
        return
    try:
        movies = storage.list_movies(ACTIVE_USER["id"])
    except Exception as e:
        print(f"   {COLOR_ERROR}DB error while creating histogram: {e}{COLOR_RESET}")
        return

    if not movies:
        print(f"   {COLOR_ERROR}No movies to analyze.{COLOR_RESET}")
        return

    ratings = [p.get("rating") for p in movies.values() if isinstance(p.get("rating"), (int, float))]
    if not ratings:
        print(f"   {COLOR_ERROR}No numeric ratings available.{COLOR_RESET}")
        return

    filename = input_nonempty_string(
        f"   {COLOR_INPUT}Enter filename to save histogram (e.g., ratings.png): {COLOR_RESET}"
    )

    plt.hist(ratings, bins=10, range=(0, 10), edgecolor="black", color="orange")
    plt.title("Movie Ratings Histogram")
    plt.xlabel("Rating")
    plt.ylabel("Count")
    plt.savefig(filename)
    plt.close()
    print(f"   {COLOR_OUTPUT}Histogram saved to {filename}{COLOR_RESET}")


def filter_movies():
    if not require_user():
        return
    try:
        movies = storage.list_movies(ACTIVE_USER["id"])
    except Exception as e:
        print(f"   {COLOR_ERROR}DB error while filtering: {e}{COLOR_RESET}")
        return

    if not movies:
        print(f"   {COLOR_ERROR}No movies available to filter.{COLOR_RESET}")
        return

    min_rating_in = input(f"   {COLOR_INPUT}Enter minimum rating (leave blank for no minimum rating): {COLOR_RESET}").strip()
    start_year_in = input(f"   {COLOR_INPUT}Enter start year (leave blank for no start year): {COLOR_RESET}").strip()
    end_year_in = input(f"   {COLOR_INPUT}Enter end year (leave blank for no end year): {COLOR_RESET}").strip()

    min_rating = float(min_rating_in) if min_rating_in else None
    start_year = int(start_year_in) if start_year_in else None
    end_year = int(end_year_in) if end_year_in else None

    filtered = []
    for title, props in movies.items():
        rating = props.get("rating")
        year = props.get("year")

        if min_rating is not None and (not isinstance(rating, (int, float)) or rating < min_rating):
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
        print(f"   {idx}. {title} ({props.get('year','N/A')}): {props.get('rating','N/A')}/10")
    print()


# ──────────────────────────────────────────────────────────────────────────────
# Website generation (per user; writes <username>.html)
# ──────────────────────────────────────────────────────────────────────────────
def generate_website():
    """Generate a static website for the active user.
    Template: _static/index_template.html
    Output:   ./<username>.html
    CSS:      ensure ./style.css exists (copied from _static/style.css)
    """
    if not require_user():
        return
    try:
        movies = storage.list_movies(ACTIVE_USER["id"])
    except Exception as e:
        print(f"   {COLOR_ERROR}DB error while generating website: {e}{COLOR_RESET}")
        return

    project_dir = Path(__file__).parent
    static_dir = project_dir / "_static"
    template_path = static_dir / "index_template.html"
    output_path = project_dir / f"{ACTIVE_USER['name']}.html"  # per-user output
    css_src = static_dir / "style.css"
    css_dst = project_dir / "style.css"

    if not template_path.exists():
        print(f"   {COLOR_ERROR}Template not found: {template_path}{COLOR_RESET}")
        return

    try:
        template = template_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"   {COLOR_ERROR}Failed to read template: {e}{COLOR_RESET}")
        return

    # Build the movie grid as <li> cards (poster, title, year)
    grid_items = []
    if movies:
        for title, props in movies.items():
            safe_title = html.escape(str(title))
            year = props.get("year")
            safe_year = html.escape(str(year)) if year is not None else "N/A"
            poster_url = props.get("poster_url") or ""
            safe_poster = html.escape(poster_url) if poster_url else ""

            grid_items.append(f"""
<li class="movie">
  <div class="poster">
    <img src="{safe_poster}" alt="{safe_title} poster" />
  </div>
  <div class="title">{safe_title}</div>
  <div class="year">{safe_year}</div>
</li>""".strip())
    else:
        grid_items.append('<li class="movie empty">No movies yet. Add some and regenerate the site.</li>')

    grid_html = "\n".join(grid_items)

    html_out = (
        template
        .replace("__TEMPLATE_TITLE__", "My Movie App")
        .replace("__TEMPLATE_MOVIE_GRID__", grid_html)
    )

    try:
        output_path.write_text(html_out, encoding="utf-8")
    except Exception as e:
        print(f"   {COLOR_ERROR}Failed to write output HTML: {e}{COLOR_RESET}")
        return

    try:
        if css_src.exists():
            shutil.copyfile(css_src, css_dst)
    except Exception as e:
        print(f"   {COLOR_ERROR}Could not copy style.css: {e}{COLOR_RESET}")

    print(f"   {COLOR_OUTPUT}Website was generated successfully for {ACTIVE_USER['name']}.{COLOR_RESET}")
    print(f"   {COLOR_OUTPUT}Open: {output_path}{COLOR_RESET}")


# ──────────────────────────────────────────────────────────────────────────────
# Main Loop
# ──────────────────────────────────────────────────────────────────────────────
def main():
    print_title()
    choose_user()  # pick or create a user before showing menu

    while True:
        print_menu()
        choice = input_menu_choice(
            f"   {COLOR_INPUT}Enter choice (0-13): {COLOR_RESET}", set(str(i) for i in range(14))
        )
        print()
        if choice == "0":
            print("   Bye!")
            break
        elif choice == "1":
            sort_by_rating()
        elif choice == "2":
            sort_by_year()
        elif choice == "3":
            list_movies()
        elif choice == "4":
            add_movie()
        elif choice == "5":
            delete_movie()
        elif choice == "6":
            update_movie()
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