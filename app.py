from flask import Flask, render_template, request, redirect, session, flash
import sqlite3
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "hopeconnect_secret"

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# DATABASE CONNECTION
def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn


# CREATE TABLES
def create_tables():

    conn = get_db()

    conn.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT,
        password TEXT,
        role TEXT
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS complaints(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        description TEXT,
        category TEXT,
        priority TEXT,
        image TEXT,
        after_image TEXT,
        status TEXT,
        user_id INTEGER,
        ngo_id INTEGER,
        latitude TEXT,
        longitude TEXT
    )
    """)

    conn.commit()
    conn.close()


create_tables()


# HOME PAGE
@app.route("/")
def home():
    return render_template("home.html")


# REGISTER
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        role = request.form["role"]

        conn = get_db()

        conn.execute(
            "INSERT INTO users (name,email,password,role) VALUES (?,?,?,?)",
            (name, email, password, role)
        )

        conn.commit()
        conn.close()

        flash("Registration successful! Please login.")
        return redirect("/login")

    return render_template("register.html")


# LOGIN
@app.route("/login", methods=["GET", "POST"])
def login():

    if session.get("user_id"):

        if session.get("role") == "admin":
            return redirect("/admin_dashboard")

        elif session.get("role") == "ngo":
            return redirect("/ngo_dashboard")

        elif session.get("role") == "user":
            return redirect("/user_dashboard")

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        # ADMIN LOGIN
        if email == "admin@hope.com" and password == "123":

            session.clear()
            session["user_id"] = 0
            session["role"] = "admin"

            flash("Welcome Admin!")
            return redirect("/admin_dashboard")

        conn = get_db()

        user = conn.execute(
            "SELECT * FROM users WHERE email=? AND password=?",
            (email, password)
        ).fetchone()

        conn.close()

        if user:

            session.clear()
            session["user_id"] = user["id"]
            session["role"] = user["role"]

            flash("Login successful!")

            if user["role"] == "user":
                return redirect("/user_dashboard")

            elif user["role"] == "ngo":
                return redirect("/ngo_dashboard")

        flash("Invalid login details")

    return render_template("login.html")


# LOGOUT
@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully")
    return redirect("/")


# USER DASHBOARD  ✅ UPDATED HERE
@app.route("/user_dashboard", methods=["GET", "POST"])
def user_dashboard():

    if session.get("role") != "user":
        return redirect("/login")

    conn = get_db()

    if request.method == "POST":

        title = request.form["title"]
        description = request.form["description"]
        category = request.form["category"]
        priority = request.form["priority"]
        image = request.files["image"]

        # ✅ NEW LOCATION DATA
        latitude = request.form.get("latitude")
        longitude = request.form.get("longitude")

        filename = None

        if image and image.filename != "":
            filename = secure_filename(image.filename)
            image.save(os.path.join(UPLOAD_FOLDER, filename))

        conn.execute(
            """INSERT INTO complaints
            (title,description,category,priority,image,status,user_id,latitude,longitude)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (title, description, category, priority,
             filename, "Pending", session["user_id"],
             latitude, longitude)
        )

        conn.commit()
        flash("Complaint submitted successfully!")

    complaints = conn.execute(
        "SELECT * FROM complaints WHERE user_id=?",
        (session["user_id"],)
    ).fetchall()

    conn.close()

    return render_template("user_dashboard.html", complaints=complaints)


# ADMIN DASHBOARD
@app.route("/admin_dashboard")
def admin_dashboard():

    if session.get("role") != "admin":
        return redirect("/login")

    conn = get_db()

    complaints = conn.execute("""
        SELECT complaints.*, users.name as ngo_name
        FROM complaints
        LEFT JOIN users
        ON complaints.ngo_id = users.id
    """).fetchall()

    ngos = conn.execute(
        "SELECT * FROM users WHERE role='ngo'"
    ).fetchall()

    total = conn.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM complaints WHERE status='Pending'").fetchone()[0]
    assigned = conn.execute("SELECT COUNT(*) FROM complaints WHERE status='Assigned'").fetchone()[0]
    resolved = conn.execute("SELECT COUNT(*) FROM complaints WHERE status='Resolved'").fetchone()[0]

    dog_count = conn.execute("SELECT COUNT(*) FROM complaints WHERE category='Dog'").fetchone()[0]
    cat_count = conn.execute("SELECT COUNT(*) FROM complaints WHERE category='Cat'").fetchone()[0]
    human_count = conn.execute("SELECT COUNT(*) FROM complaints WHERE category='Homeless Person'").fetchone()[0]

    high_priority = conn.execute("SELECT COUNT(*) FROM complaints WHERE priority='High'").fetchone()[0]
    medium_priority = conn.execute("SELECT COUNT(*) FROM complaints WHERE priority='Medium'").fetchone()[0]
    low_priority = conn.execute("SELECT COUNT(*) FROM complaints WHERE priority='Low'").fetchone()[0]

    conn.close()

    return render_template(
        "admin_dashboard.html",
        complaints=complaints,
        ngos=ngos,
        total=total,
        pending=pending,
        assigned=assigned,
        resolved=resolved,
        dog_count=dog_count,
        cat_count=cat_count,
        human_count=human_count,
        high_priority=high_priority,
        medium_priority=medium_priority,
        low_priority=low_priority
    )


# ASSIGN NGO
@app.route("/assign_ngo/<int:complaint_id>", methods=["POST"])
def assign_ngo(complaint_id):

    ngo_id = request.form["ngo_id"]

    conn = get_db()

    conn.execute(
        "UPDATE complaints SET ngo_id=?, status='Assigned' WHERE id=?",
        (ngo_id, complaint_id)
    )

    conn.commit()
    conn.close()

    flash("NGO assigned successfully!")
    return redirect("/admin_dashboard")


# NGO DASHBOARD
@app.route("/ngo_dashboard")
def ngo_dashboard():

    if session.get("role") != "ngo":
        return redirect("/login")

    conn = get_db()

    complaints = conn.execute(
        "SELECT * FROM complaints WHERE ngo_id=?",
        (session["user_id"],)
    ).fetchall()

    assigned_count = conn.execute(
        "SELECT COUNT(*) FROM complaints WHERE ngo_id=? AND status='Assigned'",
        (session["user_id"],)
    ).fetchone()[0]

    pending_count = conn.execute(
        "SELECT COUNT(*) FROM complaints WHERE ngo_id=? AND status='Pending'",
        (session["user_id"],)
    ).fetchone()[0]

    resolved_count = conn.execute(
        "SELECT COUNT(*) FROM complaints WHERE ngo_id=? AND status='Resolved'",
        (session["user_id"],)
    ).fetchone()[0]

    conn.close()

    return render_template(
        "ngo_dashboard.html",
        complaints=complaints,
        assigned_count=assigned_count,
        pending_count=pending_count,
        resolved_count=resolved_count
    )


# RESOLVE CASE
@app.route("/resolve_case/<int:complaint_id>", methods=["POST"])
def resolve_case(complaint_id):

    if session.get("role") != "ngo":
        return redirect("/login")

    after_image = request.files["after_image"]
    filename = None

    if after_image and after_image.filename != "":
        filename = secure_filename(after_image.filename)
        after_image.save(os.path.join(UPLOAD_FOLDER, filename))

    conn = get_db()

    conn.execute(
        "UPDATE complaints SET status=?, after_image=? WHERE id=?",
        ("Resolved", filename, complaint_id)
    )

    conn.commit()
    conn.close()

    flash("Case resolved with after image!")
    return redirect("/ngo_dashboard")


if __name__ == "__main__":
    app.run(debug=True)
