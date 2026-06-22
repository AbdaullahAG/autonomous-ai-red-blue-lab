import os
import sqlite3
import hmac
import secrets
import hashlib
from flask import Flask, request, render_template_string, session, redirect, url_for, abort, g

app = Flask(__name__)

DB = os.environ.get("FLASK_DB_PATH", "users.db")


def _env_truthy(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


app.config.update(
    SECRET_KEY=os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=_env_truthy("FLASK_SESSION_COOKIE_SECURE", default=False),
    MAX_CONTENT_LENGTH=64 * 1024,  # request-size guardrail
)


def get_db():
    if "db" not in g:
        con = sqlite3.connect(DB)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        con.execute("PRAGMA journal_mode = WAL")
        g.db = con
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    con = g.pop("db", None)
    if con is not None:
        con.close()


def _hash_password(password: str, salt: bytes | None = None) -> str:
    if salt is None:
        salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return "pbkdf2_sha256$200000$" + salt.hex() + "$" + dk.hex()


def _verify_password(stored: str, password: str) -> bool:
    try:
        algo, iters, salt_hex, hash_hex = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        salt = bytes.fromhex(salt_hex)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iters))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


def init_db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY,
            content TEXT NOT NULL,
            user_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
        )
        """
    )

    # Demo users (stored securely; prevent duplicates)
    demo = [(1, "admin", "secret123"), (2, "alice", "pass456")]
    for uid, username, pwd in demo:
        cur.execute("SELECT password FROM users WHERE id=? OR username=?", (uid, username))
        row = cur.fetchone()
        if row is None:
            cur.execute(
                "INSERT INTO users (id, username, password) VALUES (?,?,?)",
                (uid, username, _hash_password(pwd)),
            )
        else:
            # If legacy plaintext exists, upgrade on startup
            existing = row["password"]
            if not isinstance(existing, str) or not existing.startswith("pbkdf2_sha256$"):
                cur.execute(
                    "UPDATE users SET password=? WHERE username=?",
                    (_hash_password(pwd), username),
                )

    con.commit()
    con.close()


@app.after_request
def set_security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    resp.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    resp.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'; "
        "object-src 'none'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "upgrade-insecure-requests"
    )
    return resp


def _csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_hex(32)
        session["csrf_token"] = token
    return token


def validate_csrf():
    if request.method == "POST":
        sent = request.form.get("csrf_token", "")
        token = session.get("csrf_token", "")
        if not sent or not token or not hmac.compare_digest(sent, token):
            abort(400)


def login_required():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return None


@app.route("/", methods=["GET"])
def index():
    return redirect(url_for("login"))


@app.route("/logout", methods=["POST"])
def logout():
    validate_csrf()
    session.clear()
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    validate_csrf()
    result = ""
    if request.method == "POST":
        user = request.form.get("username", "").strip()
        pwd = request.form.get("password", "")

        if not user or not pwd or len(user) > 150 or len(pwd) > 150:
            result = "❌ Invalid credentials"
        else:
            con = get_db()
            cur = con.cursor()
            cur.execute("SELECT id, username, password FROM users WHERE username=?", (user,))
            row = cur.fetchone()

            if row and _verify_password(row["password"], pwd):
                session.clear()
                session["user_id"] = int(row["id"])
                session["username"] = row["username"]
                session["csrf_token"] = secrets.token_hex(32)
                result = f"✅ Welcome {row['username']}!"
            else:
                result = "❌ Invalid credentials"

    return render_template_string(
        """
        <!doctype html>
        <html>
        <head><meta charset="utf-8"><title>Login</title></head>
        <body>
            <h2>Login</h2>
            <form method="post" autocomplete="off">
                <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                Username: <input name="username" maxlength="150" required><br>
                Password: <input name="password" type="password" maxlength="150" required><br>
                <input type="submit" value="Login">
            </form>
            <p>{{ result }}</p>
            <a href="{{ url_for('comments') }}">Go to Comments</a>
        </body>
        </html>
        """,
        result=result,
        csrf_token=_csrf_token(),
    )


@app.route("/comments", methods=["GET", "POST"])
def comments():
    validate_csrf()
    gate = login_required()
    if gate is not None:
        return gate

    con = get_db()
    cur = con.cursor()

    if request.method == "POST":
        content = (request.form.get("comment", "") or "").strip()
        if content:
            if len(content) > 2000:
                abort(413)
            cur.execute(
                "INSERT INTO comments (content, user_id) VALUES (?, ?)",
                (content, int(session["user_id"])),
            )
            con.commit()

    cur.execute(
        """
        SELECT c.content, c.created_at, u.username
        FROM comments c
        LEFT JOIN users u ON u.id = c.user_id
        ORDER BY c.id DESC
        LIMIT 200
        """
    )
    rows = cur.fetchall()

    return render_template_string(
        """
        <!doctype html>
        <html>
        <head><meta charset="utf-8"><title>Comments</title></head>
        <body>
            <h2>Comments</h2>

            <form method="post">
                <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                <textarea name="comment" maxlength="2000" required></textarea><br>
                <input type="submit" value="Post">
            </form>

            <form method="post" action="{{ url_for('logout') }}">
                <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
                <input type="submit" value="Logout">
            </form>

            <hr>
            {% for r in rows %}
                <p>
                    <strong>{{ r['username'] or 'anonymous' }}</strong>
                    <em>{{ r['created_at'] }}</em><br>
                    {{ r['content'] }}
                </p>
            {% endfor %}
            <hr>
            <a href="{{ url_for('login