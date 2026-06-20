from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from functools import wraps

app = Flask(__name__)
app.secret_key = "student_management_secret_key"

DATABASE = "students.db"


# -------------------------
# Database Connection
# -------------------------
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn
    def calculate_grade(marks):

    marks = int(marks)

    if marks >= 90:
        return "A+"

    elif marks >= 80:
        return "A"

    elif marks >= 70:
        return "B"

    elif marks >= 60:
        return "C"

    elif marks >= 50:
        return "D"

    return "F"



   CREATE TABLE IF NOT EXISTS students(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    age INTEGER,
    course TEXT,
    marks INTEGER,
    grade TEXT
)
# -------------------------
# Login Required Decorator
# -------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "admin" not in session:
            flash("Please login first!", "danger")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


# -------------------------
# Login Page
# -------------------------
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        if username == "admin" and password == "admin123":
            session["admin"] = username
            flash("Login Successful!", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid Credentials", "danger")

    return render_template("login.html")


# -------------------------
# Logout
# -------------------------
@app.route("/logout")
def logout():
    session.clear()
    flash("Logged Out Successfully", "info")
    return redirect(url_for("login"))


# -------------------------
# Dashboard
# -------------------------
@app.route("/")
@login_required
def dashboard():

    conn = get_db_connection()

    students = conn.execute(
        "SELECT * FROM students ORDER BY id DESC"
    ).fetchall()

    total_students = conn.execute(
        "SELECT COUNT(*) FROM students"
    ).fetchone()[0]

    conn.close()

    return render_template(
        "index.html",
        students=students,
        total_students=total_students
    )


# -------------------------
# Add Student
# -------------------------
grade = calculate_grade(marks)

conn.execute("""
INSERT INTO students
(name,email,age,course,marks,grade)
VALUES (?,?,?,?,?,?)
""",(
    name,
    email,
    age,
    course,
    marks,
    grade
))    

# -------------------------
# Search Student
# -------------------------
@app.route("/search")
@login_required
def search_student():

    query = request.args.get("query", "")

    conn = get_db_connection()

    students = conn.execute("""
    SELECT * FROM students
    WHERE name LIKE ?
    OR email LIKE ?
    OR course LIKE ?
    """, (
        f"%{query}%",
        f"%{query}%",
        f"%{query}%"
    )).fetchall()

    conn.close()

    return render_template(
        "index.html",
        students=students,
        total_students=len(students)
    )
# -------------------------
# Edit Student
# -------------------------
grade = calculate_grade(marks)

conn.execute("""
UPDATE students
SET name=?,
email=?,
age=?,
course=?,
marks=?,
grade=?
WHERE id=?
""",(
    name,
    email,
    age,
    course,
    marks,
    grade,
    id
))
# -------------------------
# Delete Student
# -------------------------
@app.route("/delete/<int:id>")
@login_required
def delete_student(id):

    conn = get_db_connection()

    conn.execute(
        "DELETE FROM students WHERE id=?",
        (id,)
    )

    conn.commit()
    conn.close()

    flash("Student Deleted Successfully!", "warning")

    return redirect(url_for("dashboard"))

# -------------------------
# Run Application
# -------------------------
if __name__ == "__main__":
    init_db()
    app.run(debug=True)
