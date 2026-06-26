from flask import Flask, render_template, request, redirect, url_for
from flask import session, flash, jsonify, Response
import sqlite3
import csv
import io
import hashlib
import os
from datetime import datetime, date
from functools import wraps

app = Flask(__name__)
# ✅ FIX 1: Secret key from environment variable (security fix)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24).hex())

DB = "students.db"

COURSES = [
    "Computer Science", "Mathematics", "Physics",
    "Chemistry", "Biology", "English", "History", "Economics"
]

# --------------------------------------------------
# Database Helpers
# --------------------------------------------------
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def hash_pw(password):
    return hashlib.sha256(password.encode()).hexdigest()

def grade(marks):
    if marks >= 90: return "A+"
    elif marks >= 80: return "A"
    elif marks >= 70: return "B"
    elif marks >= 60: return "C"
    elif marks >= 50: return "D"
    return "F"

# --------------------------------------------------
# Auth Decorators
# --------------------------------------------------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login first", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if session.get("role") not in roles:
                flash("Access denied", "danger")
                return redirect(url_for("index"))
            return f(*args, **kwargs)
        return wrapper
    return decorator

# --------------------------------------------------
# Initialize Database
# --------------------------------------------------
def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT,
                name TEXT,
                role TEXT
            );
            CREATE TABLE IF NOT EXISTS students(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                email TEXT UNIQUE,
                age INTEGER,
                gender TEXT,
                course TEXT,
                marks INTEGER,
                phone TEXT,
                address TEXT,
                dob TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS attendance(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER,
                date TEXT,
                status TEXT,
                marked_by INTEGER,
                UNIQUE(student_id, date)
            );
            CREATE TABLE IF NOT EXISTS notices(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                body TEXT,
                type TEXT,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # Insert default users
        for uid, uname, pw, name, role in [
            (1, "admin",   "admin123", "Admin User", "admin"),
            (2, "teacher", "teach123", "Teacher",    "teacher"),
            (3, "student", "stu123",   "Student",    "student"),
        ]:
            conn.execute(
                "INSERT OR IGNORE INTO users (id,username,password,name,role) VALUES (?,?,?,?,?)",
                (uid, uname, hash_pw(pw), name, role)
            )
        conn.commit()

init_db()

# --------------------------------------------------
# Login / Logout
# --------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form["username"]
        password = hash_pw(request.form["password"])
        with get_db() as conn:
            user = conn.execute(
                "SELECT * FROM users WHERE username=? AND password=?",
                (username, password)
            ).fetchone()
        if user:
            session.update({
                "user_id": user["id"],
                "username": user["username"],
                "name": user["name"],
                "role": user["role"]
            })
            flash("Login successful!", "success")
            return redirect(url_for("index"))
        flash("Invalid username or password", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully", "info")
    return redirect(url_for("login"))

# --------------------------------------------------
# Dashboard
# --------------------------------------------------
@app.route("/")
@login_required
def index():
    with get_db() as conn:
        students = conn.execute("SELECT * FROM students").fetchall()
        notices  = conn.execute(
            "SELECT * FROM notices ORDER BY created_at DESC LIMIT 5"
        ).fetchall()

    total    = len(students)
    avg      = round(sum(s["marks"] for s in students) / total, 1) if total else 0
    passing  = sum(1 for s in students if s["marks"] >= 50)
    top      = max(students, key=lambda x: x["marks"], default=None)

    grade_dist  = {"A+": 0, "A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    course_dist = {}
    for s in students:
        grade_dist[grade(s["marks"])] += 1
        course_dist[s["course"]] = course_dist.get(s["course"], 0) + 1

    top5 = sorted(students, key=lambda x: x["marks"], reverse=True)[:5]

    return render_template(
        "index.html",
        total=total, avg=avg, passing=passing, top=top,
        grade_dist=grade_dist, course_dist=course_dist,
        top5=top5, notices=notices, grade_fn=grade
    )

# --------------------------------------------------
# Students List
# --------------------------------------------------
@app.route("/students")
@login_required
def students():
    search          = request.args.get("search", "")
    selected_course = request.args.get("course", "")

    query  = "SELECT * FROM students WHERE 1=1"
    params = []
    if search:
        query += " AND (name LIKE ? OR email LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    if selected_course:
        query += " AND course=?"
        params.append(selected_course)
    query += " ORDER BY name"

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()

    return render_template(
        "students.html",
        students=rows, total=len(rows),
        courses=COURSES, selected_course=selected_course,
        grade_fn=grade
    )

# --------------------------------------------------
# Add Student
# --------------------------------------------------
@app.route("/students/add", methods=["GET", "POST"])
@login_required
@role_required("admin", "teacher")
def add_student():
    if request.method == "POST":
        try:
            with get_db() as conn:
                conn.execute(
                    """INSERT INTO students
                       (name,email,age,gender,course,marks,phone,address,dob)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        request.form["name"], request.form["email"],
                        request.form.get("age", 0),
                        request.form.get("gender", "Male"),
                        request.form["course"], request.form["marks"],
                        request.form.get("phone", ""),
                        request.form.get("address", ""),
                        request.form.get("dob", "")
                    )
                )
                conn.commit()
            flash("Student added successfully!", "success")
            return redirect(url_for("students"))
        except sqlite3.IntegrityError:
            flash("Email already exists!", "danger")
    return render_template("student_form.html", student=None, courses=COURSES, action="Add")

# --------------------------------------------------
# Edit Student
# --------------------------------------------------
@app.route("/students/edit/<int:sid>", methods=["GET", "POST"])
@login_required
@role_required("admin", "teacher")
def edit_student(sid):
    with get_db() as conn:
        student = conn.execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
    if not student:
        flash("Student not found", "danger")
        return redirect(url_for("students"))

    if request.method == "POST":
        try:
            with get_db() as conn:
                conn.execute(
                    """UPDATE students SET
                       name=?,email=?,age=?,gender=?,course=?,marks=?,
                       phone=?,address=?,dob=? WHERE id=?""",
                    (
                        request.form["name"], request.form["email"],
                        request.form.get("age", 0),
                        request.form.get("gender", "Male"),
                        request.form["course"], request.form["marks"],
                        request.form.get("phone", ""),
                        request.form.get("address", ""),
                        request.form.get("dob", ""), sid
                    )
                )
                conn.commit()
            flash("Student updated successfully!", "success")
            return redirect(url_for("students"))
        except sqlite3.IntegrityError:
            flash("Email already exists!", "danger")
    return render_template("student_form.html", student=student, courses=COURSES, action="Edit")

# --------------------------------------------------
# Delete Student
# --------------------------------------------------
@app.route("/students/delete/<int:sid>", methods=["POST"])
@login_required
@role_required("admin")
def delete_student(sid):
    with get_db() as conn:
        conn.execute("DELETE FROM students WHERE id=?", (sid,))
        # ✅ FIX 2: Also delete attendance records
        conn.execute("DELETE FROM attendance WHERE student_id=?", (sid,))
        conn.commit()
    flash("Student deleted successfully", "info")
    return redirect(url_for("students"))

# --------------------------------------------------
# Student Detail
# --------------------------------------------------
@app.route("/students/<int:sid>")
@login_required
def student_detail(sid):
    with get_db() as conn:
        student = conn.execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
        att_records = conn.execute(
            "SELECT * FROM attendance WHERE student_id=? ORDER BY date DESC LIMIT 30",
            (sid,)
        ).fetchall()

    if not student:
        flash("Student not found", "danger")
        return redirect(url_for("students"))

    att_total   = len(att_records)
    att_present = sum(1 for a in att_records if a["status"] == "P")
    att_pct     = round((att_present / att_total) * 100, 1) if att_total else 0

    return render_template(
        "student_detail.html",
        student=student, grade=grade(student["marks"]),
        att_records=att_records, att_pct=att_pct,
        att_present=att_present, att_total=att_total
    )

# --------------------------------------------------
# ✅ NEW: Student Self-View (student role fix)
# --------------------------------------------------
@app.route("/my-profile")
@login_required
def my_profile():
    if session.get("role") != "student":
        return redirect(url_for("index"))

    # Link student user to student record by name match
    with get_db() as conn:
        student = conn.execute(
            "SELECT * FROM students WHERE name LIKE ?",
            (f"%{session['name']}%",)
        ).fetchone()

    if not student:
        flash("No student record linked to your account. Contact admin.", "warning")
        return redirect(url_for("index"))

    return redirect(url_for("student_detail", sid=student["id"]))

# --------------------------------------------------
# Export CSV
# --------------------------------------------------
@app.route("/students/export")
@login_required
def export_students():
    with get_db() as conn:
        students = conn.execute("SELECT * FROM students ORDER BY name").fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID","Name","Email","Age","Gender","Course","Marks","Grade","Phone","Address","DOB"])
    for s in students:
        writer.writerow([
            s["id"], s["name"], s["email"], s["age"], s["gender"],
            s["course"], s["marks"], grade(s["marks"]),
            s["phone"], s["address"], s["dob"]
        ])
    output.seek(0)
    return Response(
        output.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=students.csv"}
    )

# --------------------------------------------------
# Attendance — ✅ FIX 3: Duplicate prevention with INSERT OR REPLACE
# --------------------------------------------------
@app.route("/attendance", methods=["GET", "POST"])
@login_required
def attendance():
    sel_date = request.args.get("date", date.today().isoformat())

    if request.method == "POST" and session.get("role") in ["admin", "teacher"]:
        with get_db() as conn:
            students_list = conn.execute("SELECT id FROM students").fetchall()
            for s in students_list:
                status = request.form.get(f"status_{s['id']}", "P")
                # ✅ INSERT OR REPLACE prevents duplicates (UNIQUE constraint on student_id + date)
                conn.execute(
                    """INSERT OR REPLACE INTO attendance
                       (student_id, date, status, marked_by)
                       VALUES (?,?,?,?)""",
                    (s["id"], sel_date, status, session["user_id"])
                )
            conn.commit()
        flash("Attendance saved successfully!", "success")
        return redirect(url_for("attendance", date=sel_date))

    with get_db() as conn:
        students_list = conn.execute("SELECT * FROM students ORDER BY name").fetchall()
        existing = {
            row["student_id"]: row["status"]
            for row in conn.execute(
                "SELECT student_id, status FROM attendance WHERE date=?", (sel_date,)
            ).fetchall()
        }

    rows = [{"student": s, "status": existing.get(s["id"], "P")} for s in students_list]
    already_marked = bool(existing)

    return render_template(
        "attendance.html",
        rows=rows, sel_date=sel_date,
        already_marked=already_marked,
        P=sum(1 for r in rows if r["status"] == "P"),
        A=sum(1 for r in rows if r["status"] == "A"),
        L=sum(1 for r in rows if r["status"] == "L"),
    )

# --------------------------------------------------
# Reports
# --------------------------------------------------
@app.route("/reports")
@login_required
@role_required("admin", "teacher")
def reports():
    with get_db() as conn:
        students = conn.execute("SELECT * FROM students ORDER BY marks DESC").fetchall()

    total   = len(students)
    avg     = round(sum(s["marks"] for s in students) / total, 1) if total else 0
    highest = max((s["marks"] for s in students), default=0)
    lowest  = min((s["marks"] for s in students), default=0)

    grade_dist  = {"A+": 0, "A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    course_avgs = {}
    for s in students:
        grade_dist[grade(s["marks"])] += 1
        course_avgs.setdefault(s["course"], []).append(s["marks"])
    course_avgs = {c: round(sum(v)/len(v), 1) for c, v in course_avgs.items()}

    students_with_grade = [(s, grade(s["marks"])) for s in students]

    return render_template(
        "reports.html",
        students=students_with_grade,
        total=total, avg=avg, highest=highest, lowest=lowest,
        grade_dist=grade_dist, course_avgs=course_avgs
    )

# --------------------------------------------------
# Notices
# --------------------------------------------------
@app.route("/notices")
@login_required
def notices():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM notices ORDER BY created_at DESC"
        ).fetchall()
    return render_template("notices.html", notices=rows)

@app.route("/notices/add", methods=["GET", "POST"])
@login_required
@role_required("admin", "teacher")
def add_notice():
    if request.method == "POST":
        with get_db() as conn:
            conn.execute(
                "INSERT INTO notices (title,body,type,created_by) VALUES (?,?,?,?)",
                (
                    request.form["title"], request.form["body"],
                    request.form.get("type", "info"), session["user_id"]
                )
            )
            conn.commit()
        flash("Notice posted!", "success")
        return redirect(url_for("notices"))
    return render_template("notice_form.html")

# --------------------------------------------------
# ✅ NEW: Analytics API (for Charts)
# --------------------------------------------------
@app.route("/api/analytics")
@login_required
def api_analytics():
    with get_db() as conn:
        students = conn.execute("SELECT * FROM students").fetchall()

    grade_dist  = {"A+": 0, "A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    course_dist = {}
    marks_range = {"0-49": 0, "50-59": 0, "60-69": 0, "70-79": 0, "80-89": 0, "90-100": 0}

    for s in students:
        m = s["marks"]
        grade_dist[grade(m)] += 1
        course_dist[s["course"]] = course_dist.get(s["course"], 0) + 1
        if m < 50:   marks_range["0-49"] += 1
        elif m < 60: marks_range["50-59"] += 1
        elif m < 70: marks_range["60-69"] += 1
        elif m < 80: marks_range["70-79"] += 1
        elif m < 90: marks_range["80-89"] += 1
        else:        marks_range["90-100"] += 1

    return jsonify({
        "grade_dist": grade_dist,
        "course_dist": course_dist,
        "marks_range": marks_range,
        "total": len(students),
        "avg": round(sum(s["marks"] for s in students) / len(students), 1) if students else 0
    })

if __name__ == "__main__":
    app.run(debug=True)
