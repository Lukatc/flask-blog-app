# სოციალური ბლოგ-პლატფორმა — Flask REST API

## გაშვება

```bash
python -m venv venv
source venv/bin/activate   # Windows-ზე: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

სერვერი გაეშვება `http://127.0.0.1:5000`-ზე. მონაცემთა ბაზა (`blog.db`, SQLite) ავტომატურად შეიქმნება პირველივე გაშვებისას.

## Auth
სესია მუშაობს cookie-ებით (`flask-login`), ასე რომ მოთხოვნების გასაგზავნად საჭიროა session cookie-ს შენარჩუნება (მაგ. Postman-ში "cookie jar" ჩართული).

- `POST /api/register` — `{username, email, password, bio?, website?}`
- `POST /api/login` — `{username, password}`
- `POST /api/logout`

## Posts
- `GET /api/posts?page=1&per_page=10`
- `GET /api/posts/<slug>`
- `POST /api/posts` — `{title, body, tags?, cover_image_url?, is_published?}`
- `PUT /api/posts/<slug>`
- `DELETE /api/posts/<slug>`
- `POST /api/posts/<slug>/like`
- `POST /api/posts/<slug>/bookmark`
- `GET /api/bookmarks`
- `GET /api/posts/trending`

## Comments
- `GET /api/posts/<slug>/comments`
- `POST /api/posts/<slug>/comments` — `{body, parent_id?}` (reply მხოლოდ 1 დონეზე)

## Follow / Feed
- `POST /api/users/<username>/follow`
- `GET /api/feed` — მხოლოდ follow-ილი ავტორების პოსტები

## Tags
- `GET /api/tags`
- `GET /api/tags/<slug>/posts`
- `POST /api/tags/<slug>/follow`
- `GET /api/tags/feed` — გამოწერილი თეგების პოსტები (მხოლოდ ავტორიზებულისთვის)

## Users
- `GET /api/users/<username>` — პროფილი + სტატისტიკა (posts_count, total_likes, followers_count, following_count)
- `GET /api/users/<username>/posts`