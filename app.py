from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import re
import os
import secrets
import markdown
import bleach

app = Flask(__name__)
CORS(app, supports_credentials=True)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'ragac-secret-key-12345')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'blog.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)

@login_manager.unauthorized_handler
def unauthorized():
    return jsonify({'error': 'გთხოვთ, გაიაროთ ავტორიზაცია'}), 401


# მოდელები

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    bio = db.Column(db.Text)
    avatar_url = db.Column(db.String(255))
    website = db.Column(db.String(255))

    posts = db.relationship('Post', backref='author', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        d = {
            'id': self.id,
            'username': self.username,
            'bio': self.bio,
            'avatar_url': self.avatar_url,
            'website': self.website
        }
        if current_user.is_authenticated and current_user.id != self.id:
            d['is_following'] = Follow.query.filter_by(
                follower_id=current_user.id, following_id=self.id
            ).first() is not None
        return d

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(220), unique=True, nullable=False)
    body = db.Column(db.Text, nullable=False)
    cover_image_url = db.Column(db.String(255))
    is_published = db.Column(db.Boolean, default=True)
    views = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tags = db.relationship('Tag', secondary='post_tag', backref='posts')
    comments = db.relationship('Comment', backref='post', lazy=True, cascade='all, delete-orphan')
    likes = db.relationship('Like', backref='post', lazy=True, cascade='all, delete-orphan')

    def reading_time(self):
        words = len(self.body.split())
        return round(words / 200)

    def to_dict(self, with_body=False):
        d = {
            'id': self.id,
            'title': self.title,
            'slug': self.slug,
            'cover_image_url': self.cover_image_url,
            'is_published': self.is_published,
            'views': self.views,
            'created_at': self.created_at.isoformat(),
            'reading_time': self.reading_time(),
            'author': self.author.to_dict(),
            'tags': [t.name for t in self.tags],
            'likes_count': len(self.likes),
            'comments_count': len(self.comments)
        }
        if with_body:
            d['body'] = self.body
            d['body_html'] = render_markdown_safe(self.body)
        return d


class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    slug = db.Column(db.String(60), unique=True, nullable=False)

class PostTag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    tag_id = db.Column(db.Integer, db.ForeignKey('tag.id'), nullable=False)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=True)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    replies = db.relationship('Comment', backref=db.backref('parent', remote_side=[id]))
    author = db.relationship('User')

    def to_dict(self):
        return {
            'id': self.id,
            'body': self.body,
            'created_at': self.created_at.isoformat(),
            'author': self.author.to_dict(),
            'parent_id': self.parent_id,
            'replies': [r.to_dict() for r in self.replies] if self.parent_id is None else []
        }

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Follow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    following_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Bookmark(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    saved_at = db.Column(db.DateTime, default=datetime.utcnow)

class TagFollow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tag_id = db.Column(db.Integer, db.ForeignKey('tag.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# დამხმარე ფუნქციები

ALLOWED_HTML_TAGS = [
    'p', 'br', 'strong', 'em', 'b', 'i', 'u', 's', 'a', 'ul', 'ol', 'li',
    'blockquote', 'code', 'pre', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'img', 'hr', 'table', 'thead', 'tbody', 'tr', 'th', 'td'
]
ALLOWED_HTML_ATTRS = {
    'a': ['href', 'title', 'rel'],
    'img': ['src', 'alt', 'title']
}

def render_markdown_safe(text):
    raw_html = markdown.markdown(text, extensions=['fenced_code', 'tables'])
    return bleach.clean(raw_html, tags=ALLOWED_HTML_TAGS, attributes=ALLOWED_HTML_ATTRS, strip=True)

def get_json_body():
    return request.get_json(silent=True)

def create_slug(text):
    t = text.strip().lower()
    t = re.sub(r'[^\w\s-]', '', t)
    t = re.sub(r'\s+', '-', t)
    if not t:
        t = secrets.token_hex(4)
    return t

def get_unique_slug(title):
    base = create_slug(title)
    s = base
    count = 1
    while Post.query.filter_by(slug=s).first():
        count += 1
        s = f"{base}-{count}"
    return s

def check_tag(name):
    t = Tag.query.filter_by(name=name).first()
    if not t:
        t = Tag(name=name, slug=create_slug(name))
        db.session.add(t)
    return t

def cleanup_orphan_tags(tags):
    changed = False
    for t in tags:
        if not t.posts:
            TagFollow.query.filter_by(tag_id=t.id).delete()
            db.session.delete(t)
            changed = True
    if changed:
        db.session.commit()


# ავტორიზაცია

@app.route('/api/register', methods=['POST'])
def register():
    req = get_json_body()
    if req is None:
        return jsonify({'error': 'მოთხოვნის ტანი JSON ფორმატში არ არის'}), 400

    u = (req.get('username') or '').strip()
    e = (req.get('email') or '').strip()
    p = req.get('password')

    if not u or not e or not p:
        return jsonify({'error': 'მონაცემები აკლია'}), 400

    if not re.match(r'^[A-Za-z0-9_.\-]{3,30}$', u):
        return jsonify({'error': 'იუზერნეიმი უნდა შეიცავდეს მხოლოდ ლათინურ ასოებს, ციფრებს, _ . -, 3-30 სიმბოლო'}), 400

    if len(p) < 6:
        return jsonify({'error': 'პაროლი უნდა იყოს მინიმუმ 6 სიმბოლო'}), 400

    if User.query.filter(db.func.lower(User.username) == u.lower()).first():
        return jsonify({'error': 'ეს იუზერნეიმი უკვე არსებობს'}), 400

    if User.query.filter(db.func.lower(User.email) == e.lower()).first():
        return jsonify({'error': 'ეს მეილი უკვე გამოყენებულია'}), 400

    new_user = User(
        username=u,
        email=e,
        bio=req.get('bio', ''),
        website=req.get('website', ''),
        avatar_url=f"https://api.dicebear.com/9.x/identicon/svg?seed={u}"
    )
    new_user.set_password(p)

    db.session.add(new_user)
    db.session.commit()

    return jsonify(new_user.to_dict()), 201

@app.route('/api/login', methods=['POST'])
def login():
    req = get_json_body()
    if req is None:
        return jsonify({'error': 'მოთხოვნის ტანი JSON ფორმატში არ არის'}), 400

    u = (req.get('username') or '').strip()
    usr = User.query.filter(db.func.lower(User.username) == u.lower()).first()

    if usr is None or not usr.check_password(req.get('password', '')):
        return jsonify({'error': 'პაროლი ან იუზერი არასწორია'}), 401

    login_user(usr)
    return jsonify(usr.to_dict())

@app.route('/api/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({'msg': 'წარმატებით გამოხვედით'})

@app.route('/api/me', methods=['GET'])
def check_auth():
    if current_user.is_authenticated:
        return jsonify(current_user.to_dict())
    return jsonify({'error': 'არაავტორიზებული'}), 401


# პოსტების CRUD

@app.route('/api/posts', methods=['GET'])
def get_posts():
    p_num = request.args.get('page', 1, type=int)
    per_p = request.args.get('per_page', 10, type=int)

    pag = Post.query.filter_by(is_published=True).order_by(Post.created_at.desc()).paginate(page=p_num, per_page=per_p, error_out=False)

    return jsonify({
        'posts': [x.to_dict(with_body=True) for x in pag.items],
        'total': pag.total,
        'page': p_num,
        'pages': pag.pages
    })

@app.route('/api/posts/<slug>', methods=['GET'])
def get_post(slug):
    p = Post.query.filter_by(slug=slug).first_or_404()

    if not p.is_published:
        if not current_user.is_authenticated or current_user.id != p.user_id:
            return jsonify({'error': 'პოსტი ვერ მოიძებნა'}), 404

    p.views += 1
    db.session.commit()
    return jsonify(p.to_dict(with_body=True))

@app.route('/api/posts', methods=['POST'])
@login_required
def create_post():
    data = get_json_body()
    if data is None:
        return jsonify({'error': 'მოთხოვნის ტანი JSON ფორმატში არ არის'}), 400

    title = data.get('title')
    body = data.get('body')

    if not title or not body:
        return jsonify({'error': 'სათაური და ტექსტი სავალდებულოა'}), 400

    new_post = Post(
        user_id=current_user.id,
        title=title,
        slug=get_unique_slug(title),
        body=body,
        cover_image_url=data.get('cover_image_url'),
        is_published=data.get('is_published', True)
    )

    tags = data.get('tags', [])
    for t_name in tags:
        new_post.tags.append(check_tag(t_name))

    db.session.add(new_post)
    db.session.commit()

    return jsonify(new_post.to_dict(with_body=True)), 201

@app.route('/api/posts/<slug>', methods=['PUT'])
@login_required
def update_post(slug):
    p = Post.query.filter_by(slug=slug).first_or_404()

    if p.user_id != current_user.id:
        return jsonify({'error': 'უფლება არ გაქვთ'}), 403

    data = request.get_json()
    if data is None:
        return jsonify({'error': 'მოთხოვნის ტანი JSON ფორმატში არ არის'}), 400

    p.title = data.get('title', p.title)
    p.body = data.get('body', p.body)
    p.cover_image_url = data.get('cover_image_url', p.cover_image_url)
    p.is_published = data.get('is_published', p.is_published)

    old_tags = list(p.tags)
    tags_changed = 'tags' in data
    if tags_changed:
        p.tags = [check_tag(name) for name in data['tags']]

    db.session.commit()

    if tags_changed:
        cleanup_orphan_tags(old_tags)

    return jsonify(p.to_dict(with_body=True))

@app.route('/api/posts/<slug>', methods=['DELETE'])
@login_required
def delete_post(slug):
    p = Post.query.filter_by(slug=slug).first_or_404()
    if p.user_id != current_user.id:
        return jsonify({'error': 'უფლება არ გაქვთ'}), 403

    old_tags = list(p.tags)

    Bookmark.query.filter_by(post_id=p.id).delete()

    db.session.delete(p)
    db.session.commit()

    cleanup_orphan_tags(old_tags)
    return jsonify({'msg': 'წაიშალა'})


# ლაიქები და შენახვა

@app.route('/api/posts/<slug>/like', methods=['POST'])
@login_required
def like_post(slug):
    p = Post.query.filter_by(slug=slug).first_or_404()
    l = Like.query.filter_by(user_id=current_user.id, post_id=p.id).first()

    if l:
        db.session.delete(l)
        db.session.commit()
        return jsonify({'liked': False, 'likes_count': len(p.likes)})

    new_like = Like(user_id=current_user.id, post_id=p.id)
    db.session.add(new_like)
    db.session.commit()

    return jsonify({'liked': True, 'likes_count': len(p.likes)})

@app.route('/api/posts/<slug>/bookmark', methods=['POST'])
@login_required
def bookmark_post(slug):
    p = Post.query.filter_by(slug=slug).first_or_404()
    b = Bookmark.query.filter_by(user_id=current_user.id, post_id=p.id).first()

    if b:
        db.session.delete(b)
        db.session.commit()
        return jsonify({'bookmarked': False})

    new_bookmark = Bookmark(user_id=current_user.id, post_id=p.id)
    db.session.add(new_bookmark)
    db.session.commit()
    return jsonify({'bookmarked': True})

@app.route('/api/bookmarks', methods=['GET'])
@login_required
def get_bookmarks():
    b_list = Bookmark.query.filter_by(user_id=current_user.id).order_by(Bookmark.saved_at.desc()).all()
    posts = [Post.query.get(b.post_id).to_dict(with_body=True) for b in b_list]
    return jsonify(posts)


# ტრენდული პოსტები

@app.route('/api/posts/trending', methods=['GET'])
def get_trending():
    last_week = datetime.utcnow() - timedelta(days=7)

    res = db.session.query(Post, db.func.count(Like.id).label('recent_likes')) \
        .join(Like, Like.post_id == Post.id) \
        .filter(Like.created_at >= last_week, Post.is_published == True) \
        .group_by(Post.id) \
        .order_by(db.desc('recent_likes')) \
        .limit(10).all()

    trending = []
    for p, count in res:
        d = p.to_dict(with_body=True)
        d['recent_likes'] = count
        trending.append(d)

    return jsonify(trending)


# კომენტარები

@app.route('/api/posts/<slug>/comments', methods=['GET'])
def get_comments(slug):
    p = Post.query.filter_by(slug=slug).first_or_404()
    comms = Comment.query.filter_by(post_id=p.id, parent_id=None).order_by(Comment.created_at.asc()).all()
    return jsonify([c.to_dict() for c in comms])

@app.route('/api/posts/<slug>/comments', methods=['POST'])
@login_required
def add_comment(slug):
    p = Post.query.filter_by(slug=slug).first_or_404()
    req = request.get_json()
    if req is None:
        return jsonify({'error': 'მოთხოვნის ტანი JSON ფორმატში არ არის'}), 400

    b = req.get('body')
    parent = req.get('parent_id')

    if not b:
        return jsonify({'error': 'კომენტარი ცარიელია'}), 400

    if parent:
        par_comm = Comment.query.get(parent)
        if not par_comm or par_comm.post_id != p.id:
            return jsonify({'error': 'არასწორი parent_id'}), 400
        if par_comm.parent_id is not None:
            return jsonify({'error': 'მხოლოდ 1 დონეზეა პასუხი დაშვებული'}), 400

    new_comm = Comment(
        post_id=p.id,
        user_id=current_user.id,
        parent_id=parent,
        body=b
    )
    db.session.add(new_comm)
    db.session.commit()

    return jsonify(new_comm.to_dict()), 201


# გამოწერა და feed

@app.route('/api/users/<username>/follow', methods=['POST'])
@login_required
def follow_user(username):
    target = User.query.filter_by(username=username).first_or_404()
    if target.id == current_user.id:
        return jsonify({'error': 'საკუთარ თავს ვერ გამოიწერთ'}), 400

    f = Follow.query.filter_by(follower_id=current_user.id, following_id=target.id).first()
    if f:
        db.session.delete(f)
        db.session.commit()
        return jsonify({'following': False})

    new_f = Follow(follower_id=current_user.id, following_id=target.id)
    db.session.add(new_f)
    db.session.commit()
    return jsonify({'following': True})

@app.route('/api/feed', methods=['GET'])
@login_required
def my_feed():
    f_ids = [x.following_id for x in Follow.query.filter_by(follower_id=current_user.id).all()]
    feed_posts = Post.query.filter(Post.user_id.in_(f_ids), Post.is_published == True).order_by(Post.created_at.desc()).all()
    return jsonify([p.to_dict(with_body=True) for p in feed_posts])


# თეგები

@app.route('/api/tags', methods=['GET'])
def all_tags():
    t = Tag.query.all()
    followed_tag_ids = set()
    if current_user.is_authenticated:
        followed_tag_ids = {tf.tag_id for tf in TagFollow.query.filter_by(user_id=current_user.id).all()}

    return jsonify([
        {'name': x.name, 'slug': x.slug, 'is_following': x.id in followed_tag_ids}
        for x in t
    ])

@app.route('/api/tags/<slug>/posts', methods=['GET'])
def tag_posts(slug):
    t = Tag.query.filter_by(slug=slug).first_or_404()
    res = [p for p in t.posts if p.is_published]
    return jsonify([p.to_dict(with_body=True) for p in res])

@app.route('/api/tags/<slug>/follow', methods=['POST'])
@login_required
def follow_tag(slug):
    t = Tag.query.filter_by(slug=slug).first_or_404()
    existing = TagFollow.query.filter_by(user_id=current_user.id, tag_id=t.id).first()

    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({'following': False})

    new_tf = TagFollow(user_id=current_user.id, tag_id=t.id)
    db.session.add(new_tf)
    db.session.commit()
    return jsonify({'following': True})

@app.route('/api/tags/feed', methods=['GET'])
@login_required
def tags_feed():
    tag_ids = [tf.tag_id for tf in TagFollow.query.filter_by(user_id=current_user.id).all()]
    if not tag_ids:
        return jsonify([])

    feed_posts = Post.query.filter(
        Post.tags.any(Tag.id.in_(tag_ids)),
        Post.is_published == True
    ).order_by(Post.created_at.desc()).all()

    return jsonify([p.to_dict(with_body=True) for p in feed_posts])


# მომხმარებლის პროფილი

@app.route('/api/users/<username>', methods=['GET'])
def user_profile(username):
    usr = User.query.filter_by(username=username).first_or_404()

    p_count = Post.query.filter_by(user_id=usr.id, is_published=True).count()
    likes_count = db.session.query(Like).join(Post).filter(Post.user_id == usr.id).count()
    followers = Follow.query.filter_by(following_id=usr.id).count()
    following = Follow.query.filter_by(follower_id=usr.id).count()

    resp = usr.to_dict()
    resp['stats'] = {
        'posts_count': p_count,
        'total_likes': likes_count,
        'followers_count': followers,
        'following_count': following
    }
    return jsonify(resp)

@app.route('/api/users/<username>/posts', methods=['GET'])
def get_users_posts(username):
    u = User.query.filter_by(username=username).first_or_404()

    is_owner = current_user.is_authenticated and current_user.id == u.id
    q = Post.query.filter_by(user_id=u.id)
    if not is_owner:
        q = q.filter_by(is_published=True)
    p = q.order_by(Post.created_at.desc()).all()
    return jsonify([x.to_dict(with_body=True) for x in p])


@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')


with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
