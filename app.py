import os
import csv
import io
import secrets
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, Response, abort
)
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# -------------------------
# Config (env-driven, with safe local defaults)
# -------------------------
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config["DEBUG"] = os.environ.get("FLASK_DEBUG", "0") == "1"

DATABASE = os.environ.get("DATABASE_PATH", "students.db")

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
# Default password hash corresponds to "admin123" — override in production via env var.
ADMIN_PASSWORD_HASH = os.environ.get(
    "ADMIN_PASSWORD_HASH",
    generate_password_hash("admin123")
)

PER_PAGE = 10


# -------------------------
# Database Connection
# -------------------------
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# -------------------------
# Grade Calculator
# -------------------------
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


# -------------------------
# Validation Helpers
# -------------------------
def validate_student_form(form):
    """Returns (data_dict, errors_list)."""
    errors = []

    name = form.get("name", "").strip()
    email = form.get("email", "").strip()
    age_raw = form.get("age", "").strip()
    course = form.get("course", "").strip()
    marks_raw = form.get("marks", "").strip()

    if not name:
        errors.append("Name is required.")
    if not email or "@" not in email or "." not in email.split("@")[-1]:
        errors.append("A valid email is required.")
    if not course:
        errors.append("Course is required.")

    age = None
    if age_raw:
        try:
            age = int(age_raw)
            if age < 0 or age > 120:
                errors.append("Age must be between 0 and 120.")
        except ValueError:
            errors.append("Age must be a whole number.")
    else:
        errors.append("Age is required.")

    marks = None
    if marks_raw:
        try:
            marks = int(marks_raw)
            if marks < 0 or marks > 100:
                errors.append("Marks must be between 0 and 100.")
        except ValueError:
            errors.append("Marks must be a whole number.")
    else:
        errors.append("Marks is required.")

    return {
        "name": name,
        "email": email,
        "age": age,
        "course": course,
        "marks": marks,
    }, errors


def email_exists(conn, email, exclude_id=None):
    if exclude_id:
        row = conn.execute(
            "SELECT id FROM students WHERE email=? AND id<>?",
            (email, exclude_id)
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT id FROM students WHERE email=?",
            (email,)
        ).fetchone()
    return row is not None


# -------------------------
# Create Database Table
# -------------------------
def init_db():
    conn = get_db_connection()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS students(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        age INTEGER,
        course TEXT,
        marks INTEGER,
        grade TEXT
    )
    """)
    conn.commit()
    conn.close()


# -------------------------
# CSRF Protection (lightweight, no external dependency)
# -------------------------
def generate_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)
    return session["csrf_token"]


app.jinja_env.globals["csrf_token"] = generate_csrf_token


def csrf_protect(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method == "POST":
            token = session.get("csrf_token")
            form_token = request.form.get("csrf_token")
            if not token or not form_token or token != form_token:
                abort(400, description="Invalid or missing CSRF token.")
        return f(*args, **kwargs)
    return decorated_function


# -------------------------
# Login Required
# -------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "admin" not in session:
            flash("Please Login First", "danger")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


# -------------------------
# Login
# -------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
            session.clear()
            session["admin"] = username
            generate_csrf_token()
            flash("Login Successful", "success")
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
# Dashboard (with pagination + sorting)
# -------------------------
@app.route("/")
@login_required
def dashboard():
    page = request.args.get("page", 1, type=int)
    sort = request.args.get("sort", "id")
    order = request.args.get("order", "desc")

    allowed_sort = {"id", "name", "marks", "course", "age"}
    if sort not in allowed_sort:
        sort = "id"
    order = "ASC" if order.lower() == "asc" else "DESC"

    conn = get_db_connection()

    total_students = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    avg_marks = conn.execute("SELECT AVG(marks) FROM students").fetchone()[0] or 0

    offset = (page - 1) * PER_PAGE
    students = conn.execute(
        f"SELECT * FROM students ORDER BY {sort} {order} LIMIT ? OFFSET ?",
        (PER_PAGE, offset)
    ).fetchall()

    conn.close()

    total_pages = max(1, (total_students + PER_PAGE - 1) // PER_PAGE)

    return render_template(
        "index.html",
        students=students,
        total_students=total_students,
        avg_marks=round(avg_marks, 2),
        page=page,
        total_pages=total_pages,
        sort=sort,
        order=order.lower()
    )


# -------------------------
# Add Student
# -------------------------
@app.route("/add", methods=["GET", "POST"])
@login_required
@csrf_protect
def add_student():
    if request.method == "POST":
        data, errors = validate_student_form(request.form)

        conn = get_db_connection()

        if not errors and email_exists(conn, data["email"]):
            errors.append("A student with this email already exists.")

        if errors:
            conn.close()
            for e in errors:
                flash(e, "danger")
            return render_template("add_student.html", form=request.form)

        grade = calculate_grade(data["marks"])

        try:
            conn.execute("""
            INSERT INTO students (name, email, age, course, marks, grade)
            VALUES (?,?,?,?,?,?)
            """, (
                data["name"], data["email"], data["age"],
                data["course"], data["marks"], grade
            ))
            conn.commit()
            flash("Student Added Successfully", "success")
        except sqlite3.Error as e:
            flash(f"Database error: {e}", "danger")
        finally:
            conn.close()

        return redirect(url_for("dashboard"))

    return render_template("add_student.html", form={})


# -------------------------
# Edit Student
# -------------------------
@app.route("/edit/<int:id>", methods=["GET", "POST"])
@login_required
@csrf_protect
def edit_student(id):
    conn = get_db_connection()

    student = conn.execute(
        "SELECT * FROM students WHERE id=?", (id,)
    ).fetchone()

    if student is None:
        conn.close()
        flash("Student not found.", "danger")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        data, errors = validate_student_form(request.form)

        if not errors and email_exists(conn, data["email"], exclude_id=id):
            errors.append("Another student already uses this email.")

        if errors:
            conn.close()
            for e in errors:
                flash(e, "danger")
            return render_template("edit_student.html", student=student)

        grade = calculate_grade(data["marks"])

        try:
            conn.execute("""
            UPDATE students
            SET name=?, email=?, age=?, course=?, marks=?, grade=?
            WHERE id=?
            """, (
                data["name"], data["email"], data["age"],
                data["course"], data["marks"], grade, id
            ))
            conn.commit()
            flash("Student Updated Successfully", "success")
        except sqlite3.Error as e:
            flash(f"Database error: {e}", "danger")
        finally:
            conn.close()

        return redirect(url_for("dashboard"))

    conn.close()
    return render_template("edit_student.html", student=student)


# -------------------------
# Delete Student (POST only, CSRF protected)
# -------------------------
@app.route("/delete/<int:id>", methods=["POST"])
@login_required
@csrf_protect
def delete_student(id):
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM students WHERE id=?", (id,))
        conn.commit()
        flash("Student Deleted Successfully", "warning")
    except sqlite3.Error as e:
        flash(f"Database error: {e}", "danger")
    finally:
        conn.close()

    return redirect(url_for("dashboard"))


# -------------------------
# Search Student
# -------------------------
@app.route("/search")
@login_required
def search_student():
    query = request.args.get("query", "").strip()

    conn = get_db_connection()
    students = conn.execute("""
    SELECT * FROM students
    WHERE name LIKE ? OR email LIKE ? OR course LIKE ?
    ORDER BY id DESC
    """, (f"%{query}%", f"%{query}%", f"%{query}%")).fetchall()
    conn.close()

    return render_template(
        "index.html",
        students=students,
        total_students=len(students),
        avg_marks=0,
        page=1,
        total_pages=1,
        sort="id",
        order="desc"
    )


# -------------------------
# Export to CSV
# -------------------------
@app.route("/export")
@login_required
def export_csv():
    conn = get_db_connection()
    students = conn.execute("SELECT * FROM students ORDER BY id").fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Name", "Email", "Age", "Course", "Marks", "Grade"])
    for s in students:
        writer.writerow([s["id"], s["name"], s["email"], s["age"], s["course"], s["marks"], s["grade"]])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=students.csv"}
    )


# -------------------------
# Error Handlers
# -------------------------
@app.errorhandler(400)
def bad_request(e):
    return render_template("error.html", code=400, message=str(e.description)), 400


@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="Page not found."), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("error.html", code=500, message="Something went wrong."), 500


# -------------------------
# Run App
# -------------------------
init_db()

if __name__ == "__main__":
    app.run(debug=app.config["DEBUG"])
