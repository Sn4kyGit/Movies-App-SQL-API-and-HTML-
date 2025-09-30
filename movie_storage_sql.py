def delete_movie(title):
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

def update_movie(title, rating):
    with engine.connect() as connection:
        result = connection.execute(
            text("UPDATE movies SET rating = :rating WHERE title = :title"),
            {"rating": rating, "title": title}
        )
        connection.commit()
        if result.rowcount == 0:
            print(f"No movie found with title '{title}'.")
        else:
            print(f"Movie '{title}' updated successfully to rating {rating}.")
