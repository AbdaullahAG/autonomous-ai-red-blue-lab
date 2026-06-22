from flask import Flask, request, render_template_string
import sqlite3, os

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
# ⚠️  ثغرة SQL Injection متعمدة
# ==========================================
@app.route("/login", methods=["GET","POST"])
def login():
    result = ""
    if request.method == "POST":
        user = request.form.get("username","")
        pwd  = request.form.get("password","")
        con  = sqlite3.connect(DB)
        cur  = con.cursor()
        # خطأ متعمد: إدخال المستخدم مباشرة في الاستعلام
        query = f"SELECT * FROM users WHERE username='{user}' AND password='{pwd}'"
        cur.execute(query)
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
# ⚠️  ثغرة Stored XSS متعمدة
# ==========================================
@app.route("/comments", methods=["GET","POST"])
def comments():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    if request.method == "POST":
        content = request.form.get("comment","")
        # خطأ متعمد: حفظ وعرض المدخلات بدون تعقيم
        cur.execute("INSERT INTO comments (content) VALUES (?)", (content,))
        con.commit()
    cur.execute("SELECT content FROM comments")
    rows = cur.fetchall()
    con.close()
    # خطأ متعمد: |safe يعطّل الـ escaping
    comments_html = "".join(f"<p>{r[0]}</p>" for r in rows)
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
