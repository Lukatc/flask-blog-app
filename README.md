# Social Blog Platform — Flask REST API

## Getting Started

```bash
# Create and activate virtual environment
python -m venv venv
# On Windows: 
.\venv\Scripts\activate
# On macOS/Linux: 
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py

```

The server will run on `[http://127.0.0.1:5000](http://127.0.0.1:5000)`. The database (`blog.db`, SQLite) will be created automatically upon the first launch.

## Authentication

Sessions are managed via cookies (`flask-login`). To make authenticated requests, you must maintain the session cookie (e.g., ensure "cookie jar" is enabled if using Postman).

* `POST /api/register` — `{username, email, password, bio?, website?}`
* `POST /api/login` — `{username, password}`
* `POST /api/logout`

## Posts

* `GET /api/posts?page=1&per_page=10`
* `GET /api/posts/<slug>`
* `POST /api/posts` — `{title, body, tags?, cover_image_url?, is_published?}`
* `PUT /api/posts/<slug>`
* `DELETE /api/posts/<slug>`
* `POST /api/posts/<slug>/like`
* `POST /api/posts/<slug>/bookmark`
* `GET /api/bookmarks`
* `GET /api/posts/trending`

## Comments

* `GET /api/posts/<slug>/comments`
* `POST /api/posts/<slug>/comments` — `{body, parent_id?}` (replies limited to 1 level deep)

## Follow / Feed

* `POST /api/users/<username>/follow`
* `GET /api/feed` — Posts from followed authors only

## Tags

* `GET /api/tags`
* `GET /api/tags/<slug>/posts`
* `POST /api/tags/<slug>/follow`
* `GET /api/tags/feed` — Posts from followed tags (authorized users only)

## Users

* `GET /api/users/<username>` — Profile + Statistics (posts_count, total_likes, followers_count, following_count)
* `GET /api/users/<username>/posts`
