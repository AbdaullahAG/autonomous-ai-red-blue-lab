from flask import Flask, request, render_template_string
import sqlite3, os
from html import escape

app = Flask(__name__)
DB = "users.db"

def init_db():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT,
        password TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY,
        content TEXT
    )""")
    cur.executemany("INSERT OR IGNORE INTO users VALUES (?,?,?)",
        [(1,"admin","secret123"),(2,"alice","pass456")])
    con.commit()
    con.close()

# ==========================================
# ✅ إصلاح SQL Injection باستخدام Parameterized Queries
# ==========================================
@app.route("/login", methods=["GET","POST"])
def login():
    result = ""
    if request.method == "POST":
        user = request.form.get("username","")
        pwd  = request.form.get("password","")
        con  = sqlite3.connect(DB)
        cur  = con.cursor()
        cur.execute("SELECT * FROM users WHERE username=? AND password=?", (user, pwd))
        row = cur.fetchone()
        con.close()
        result = f"✅ Welcome {row[1]}!" if row else "❌ Invalid credentials"
    return render_template_string("""
        <h2>Login</h2>
        <form method=post>
            Username: <input name=username><br>
            Password:  <input name=password type=password><br>
            <input type=submit value=Login>
        </form>
        <p>{{ result }}</p>
        <a href='/comments'>Go to Comments</a>
    """, result=result)

# ==========================================
# ✅ إصلاح Stored XSS باستخدام html.escape() عند العرض
# ==========================================
@app.route("/comments", methods=["GET","POST"])
def comments():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    if request.method == "POST":
        content = request.form.get("comment","")
        cur.execute("INSERT INTO comments (content) VALUES (?)", (content,))
        con.commit()
    cur.execute("SELECT content FROM comments")
    rows = cur.fetchall()
    con.close()
    comments_html = "".join(f"<p>{escape(r[0] if r[0] is not None else '')}</p>" for r in rows)
    return render_template_string("""
        <h2>Comments</h2>
        <form method=post>
            <textarea name=comment></textarea><br>
            <input type=submit value=Post>
        </form>
        <hr>
        """ + comments_html)

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)