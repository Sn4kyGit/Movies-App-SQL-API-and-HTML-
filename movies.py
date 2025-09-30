import random
import difflib
import matplotlib.pyplot as plt
import json
import urllib.request, urllib.parse

import movie_storage_sql as storage  # persistence layer (SQLAlchemy)

# ANSI color codes
COLOR_RESET = "\033[0m"
COLOR_ERROR = "\033[91m"
COLOR_MENU = "\033[92m"
COLOR_INPUT = "\033[0m"
COLOR_OUTPUT = "\033[33m"


# ──────────────────────────────────────────────────────────────────────────────
# UI Basics
# ──────────────────────────────────────────────────────────────────────────────
def print_title():
    print(f"{COLOR_MENU}********** My Movies Database **********{COLOR_RESET}\n")


def print_menu():
    print(f"   {COLOR_MENU}Menu:")
    print("   0. Exit")
    print("   1. Show all Movies sorted by rating")
    print("   2. Show all Movies sorted by year (chronological)")
    print("   3. List all movies")
    print("   4. Add a new movie")
    print("   5. Delete a movie")
    print("   6. Update a movie (rating/year)")
    print("   7. Database Overview (Stats)")
    print("   8. List a random movie")
    print("   9. Search for a movie")
    print("   10. Create a Rating Histogram")
    print("   11. Filter Movies" + COLOR_RESET)
    print()


# ──────────────────────────────────────────────────────────────────────────────
# Input Helpers
# ──────────────────────────────────────────────────────────────────────────────
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
    while True:
        title = input_nonempty_string(prompt)
        if title.lower() == "cancel":
            return None
        movies = storage.list_movies()
        if title in movies:
            return title
        print(f"   {COLOR_ERROR}Movie '{title}' not found. Type 'cancel' to abort or try again.{COLOR_RESET}")


def print_movie_line(idx, title, props):
    rating = props.get("rating", "N/A")
    year = props.get("year", "N/A")
    print(f"      {idx}. {title} ({year}): {rating}/10")


# ──────────────────────────────────────────────────────────────────────────────
# Actions
# ──────────────────────────────────────────────────────────────────────────────
def list_movies():
    movies = storage.list_movies()
    if not movies:
        print(f"   {COLOR_ERROR}No movies found.{COLOR_RESET}")
    else:
        print(f"   {COLOR_OUTPUT}Movies:{COLOR_RESET}")
        for idx, (title, props) in enumerate(movies.items(), 1):
            print_movie_line(idx, title, props)
        print(f"   {COLOR_OUTPUT}Total movies: {len(movies)}{COLOR_RESET}")


def sort_by_rating():
    movies = storage.list_movies()
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
    movies = storage.list_movies()
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
    title_input = input_nonempty_string(f"   {COLOR_INPUT}Enter movie title: {COLOR_RESET}")

    # Fetch from OMDb
    api_key = "8496f341"
    query = urllib.parse.urlencode({"t": title_input, "apikey": api_key})
    url = f"http://www.omdbapi.com/?{query}"

    try:
        with urllib.request.urlopen(url) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        print(f"   {COLOR_ERROR}Failed to reach OMDb: {e}{COLOR_RESET}")
        return

    if data.get("Response") != "True":
        print(f"   {COLOR_ERROR}OMDb error: {data.get('Error', 'Unknown error')}{COLOR_RESET}")
        return

    # Parse fields
    title = data.get("Title") or title_input

    year_str = data.get("Year", "")
    year = None
    if year_str and year_str[:4].isdigit():  # handles ranges like "1999–2003"
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

    # Prevent obvious duplicates by title (optional UX nicety)
    existing = storage.list_movies()
    if title in existing:
        print(f"   {COLOR_ERROR}Movie '{title}' already exists in your database.{COLOR_RESET}")
        return

    # Save to DB
    try:
        storage.add_movie(title, year, rating, poster_url)
        print(f"   {COLOR_OUTPUT}Movie '{title}' ({year}) added with rating {rating:.1f}.{COLOR_RESET}")
        if poster_url:
            print(f"   {COLOR_OUTPUT}Poster: {poster_url}{COLOR_RESET}")
    except Exception as e:
        print(f"   {COLOR_ERROR}{e}{COLOR_RESET}")


def delete_movie():
    title = input_existing_title(
        f"   {COLOR_INPUT}Enter movie title to delete (or type 'cancel'): {COLOR_RESET}"
    )
    if title is None:
        print(f"   {COLOR_OUTPUT}Delete cancelled.{COLOR_RESET}")
        return
    try:
        storage.delete_movie(title)
        print(f"   {COLOR_OUTPUT}Movie '{title}' deleted.{COLOR_RESET}")
    except KeyError as e:
        print(f"   {COLOR_ERROR}{e}{COLOR_RESET}")


def update_movie():
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
            storage.update_movie(title, **updates)
            print(f"   {COLOR_OUTPUT}Movie '{title}' updated.{COLOR_RESET}")
        except KeyError as e:
            print(f"   {COLOR_ERROR}{e}{COLOR_RESET}")
    else:
        print(f"   {COLOR_OUTPUT}No changes applied.{COLOR_RESET}")


def show_stats():
    movies = storage.list_movies()
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
    best = [t for t, p in storage.list_movies().items() if p.get("rating") == max_rating]
    worst = [t for t, p in storage.list_movies().items() if p.get("rating") == min_rating]

    # → Average & Median mit nur 1 Nachkommastelle
    print(
        f"   {COLOR_OUTPUT}Average: {avg:.1f} | Median: {median:.1f} | "
        f"Best: {', '.join(best)} | Worst: {', '.join(worst)}{COLOR_RESET}"
    )


def random_movie():
    movies = storage.list_movies()
    if movies:
        title, props = random.choice(list(movies.items()))
        print(
            f"   {COLOR_OUTPUT}Random movie: {title} ({props.get('year','N/A')}) — "
            f"{props.get('rating','N/A')}/10{COLOR_RESET}"
        )
    else:
        print(f"   {COLOR_ERROR}No movies available.{COLOR_RESET}")


def search_movie():
    movies = storage.list_movies()
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
    movies = storage.list_movies()
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
    movies = storage.list_movies()
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

    print(f"   {COLOR_OUTPUT}Filtered Movies:{COLOR_RESET}")
    for idx, (title, props) in enumerate(filtered, 1):
        print(f"   {idx}. {title} ({props.get('year','N/A')}): {props.get('rating','N/A')}/10")
    print()


# ──────────────────────────────────────────────────────────────────────────────
# Main Loop
# ──────────────────────────────────────────────────────────────────────────────
def main():
    print_title()
    while True:
        print_menu()
        choice = input_menu_choice(
            f"   {COLOR_INPUT}Enter choice (0-11): {COLOR_RESET}", set(str(i) for i in range(12))
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
        print()


if __name__ == "__main__":
    main()