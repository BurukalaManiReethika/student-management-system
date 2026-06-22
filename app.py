from flask import Flask, render_template, request, redirect, url_for
from flask import session, flash, jsonify, Response
import sqlite3
import csv
import io
import hashlib
import os

from datetime import datetime, date, timedelta
from functools import wraps

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "student-management-secret"
)

DB = "students.db"

COURSES = [
    "Computer Science",
    "Mathematics",
    "Physics",
    "Chemistry",
    "Biology",
    "English",
    "History",
    "Economics"
]

# --------------------------------------------------
# Database Helpers
# --------------------------------------------------

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def hash_pw(password):
    return hashlib.sha256(
        password.encode()
    ).hexdigest()


def grade(marks):

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


# --------------------------------------------------
# Authentication
# --------------------------------------------------

def login_required(f):

    @wraps(f)
    def wrapper(*args, **kwargs):

        if "user_id" not in session:

            flash(
                "Please login first",
                "warning"
            )

            return redirect(
                url_for("login")
            )

        return f(*args, **kwargs)

    return wrapper


def role_required(*roles):

    def decorator(f):

        @wraps(f)
        def wrapper(*args, **kwargs):

            if session.get("role") not in roles:

                flash(
                    "Access denied",
                    "danger"
                )

                return redirect(
                    url_for("index")
                )

            return f(*args, **kwargs)

        return wrapper

    return decorator


# --------------------------------------------------
# Initialize Database
# --------------------------------------------------

def init_db():

    with get_db() as conn:

        conn.executescript(
            """
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
                marked_by INTEGER
            );

            CREATE TABLE IF NOT EXISTS notices(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                body TEXT,
                type TEXT,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        conn.execute(
            """
            INSERT OR IGNORE INTO users
            (id,username,password,name,role)
            VALUES
            (1,?,?,?,?)
            """,
            (
                "admin",
                hash_pw("admin123"),
                "Admin User",
                "admin"
            )
        )

        conn.execute(
            """
            INSERT OR IGNORE INTO users
            (id,username,password,name,role)
            VALUES
            (2,?,?,?,?)
            """,
            (
                "teacher",
                hash_pw("teach123"),
                "Teacher",
                "teacher"
            )
        )

        conn.execute(
            """
            INSERT OR IGNORE INTO users
            (id,username,password,name,role)
            VALUES
            (3,?,?,?,?)
            """,
            (
                "student",
                hash_pw("stu123"),
                "Student",
                "student"
            )
        )

        conn.commit()


init_db()
# --------------------------------------------------
# Login
# --------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if "user_id" in session:
        return redirect(url_for("index"))

    if request.method == "POST":

        username = request.form["username"]
        password = hash_pw(
            request.form["password"]
        )

        with get_db() as conn:

            user = conn.execute(
                """
                SELECT * FROM users
                WHERE username=?
                AND password=?
                """,
                (username, password)
            ).fetchone()

        if user:

            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["name"] = user["name"]
            session["role"] = user["role"]

            flash(
                "
            # --------------------------------------------------
# Logout
# --------------------------------------------------

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "Logged out successfully",
        "info"
    )

    return redirect(
        url_for("login")
    )


# --------------------------------------------------
# Dashboard
# --------------------------------------------------

@app.route("/")
@login_required
def index():

    with get_db() as conn:

        students = conn.execute(
            "SELECT * FROM students"
        ).fetchall()

        notices = conn.execute(
            """
            SELECT *
            FROM notices
            ORDER BY created_at DESC
            LIMIT 5
            """
        ).fetchall()

    total = len(students)

    avg = round(
        sum(s["marks"] for s in students) / total,
        1
    ) if total else 0

    passing = sum(
        1 for s in students
        if s["marks"] >= 50
    )

    top = max(
        students,
        key=lambda x: x["marks"],
        default=None
    )

    grade_dist = {
        "A+": 0,
        "A": 0,
        "B": 0,
        "C": 0,
        "D": 0,
        "F": 0
    }

    course_dist = {}

    for s in students:

        g = grade(s["marks"])

        grade_dist[g] += 1

        course = s["course"]

        course_dist[course] = (
            course_dist.get(course, 0) + 1
        )

    top5 = sorted(
        students,
        key=lambda x: x["marks"],
        reverse=True
    )[:5]

    return render_template(
        "index.html",
        total=total,
        avg=avg,
        passing=passing,
        top=top,
        grade_dist=grade_dist,
        course_dist=course_dist,
        top5=top5,
        notices=notices,
        grade_fn=grade
    )


# --------------------------------------------------
# Students List
# --------------------------------------------------

@app.route("/students")
@login_required
def students():

    search = request.args.get(
        "search",
        ""
    )

    selected_course = request.args.get(
        "course",
        ""
    )

    query = "SELECT * FROM students WHERE 1=1"

    params = []

    if search:

        query += """
        AND (
            name LIKE ?
            OR email LIKE ?
        )
        """

        params.extend([
            f"%{search}%",
            f"%{search}%"
        ])

    if selected_course:

        query += """
        AND course = ?
        """

        params.append(
            selected_course
        )

    query += " ORDER BY name"

    with get_db() as conn:

        rows = conn.execute(
            query,
            params
        ).fetchall()

    return render_template(
        "students.html",
        students=rows,
        total=len(rows),
        courses=COURSES,
        selected_course=selected_course,
        grade_fn=grade
    )


# --------------------------------------------------
# Add Student
# --------------------------------------------------

@app.route(
    "/students/add",
    methods=["GET", "POST"]
)
@login_required
@role_required(
    "admin",
    "teacher"
)
def add_student():

    if request.method == "POST":

        try:

            with get_db() as conn:

                conn.execute(
                    """
                    INSERT INTO students
                    (
                        name,
                        email,
                        age,
                        gender,
                        course,
                        marks,
                        phone,
                        address,
                        dob
                    )
                    VALUES
                    (
                        ?,?,?,?,?,?,?,?,?
                    )
                    """,
                    (
                        request.form["name"],
                        request.form["email"],
                        request.form.get(
                            "age",
                            0
                        ),
                        request.form.get(
                            "gender",
                            "Male"
                        ),
                        request.form["course"],
                        request.form["marks"],
                        request.form.get(
                            "phone",
                            ""
                        ),
                        request.form.get(
                            "address",
                            ""
                        ),
                        request.form.get(
                            "dob",
                            ""
                        )
                    )
                )

                conn.commit()

            flash(
                "Student added successfully",
                "success"
            )

            return redirect(
                url_for("students")
            )

        except sqlite3.IntegrityError:

            flash(
                "Email already exists",
                "danger"
            )

    return render_template(
        "student_form.html",
        student=None,
        courses=COURSES,
        action="Add"
    )
            # --------------------------------------------------
# Edit Student
# --------------------------------------------------

@app.route(
    "/students/edit/<int:sid>",
    methods=["GET", "POST"]
)
@login_required
@role_required(
    "admin",
    "teacher"
)
def edit_student(sid):

    with get_db() as conn:

        student = conn.execute(
            """
            SELECT *
            FROM students
            WHERE id=?
            """,
            (sid,)
        ).fetchone()

    if not student:

        flash(
            "Student not found",
            "danger"
        )

        return redirect(
            url_for("students")
        )

    if request.method == "POST":

        try:

            with get_db() as conn:

                conn.execute(
                    """
                    UPDATE students
                    SET
                        name=?,
                        email=?,
                        age=?,
                        gender=?,
                        course=?,
                        marks=?,
                        phone=?,
                        address=?,
                        dob=?
                    WHERE id=?
                    """,
                    (
                        request.form["name"],
                        request.form["email"],
                        request.form.get("age", 0),
                        request.form.get(
                            "gender",
                            "Male"
                        ),
                        request.form["course"],
                        request.form["marks"],
                        request.form.get(
                            "phone",
                            ""
                        ),
                        request.form.get(
                            "address",
                            ""
                        ),
                        request.form.get(
                            "dob",
                            ""
                        ),
                        sid
                    )
                )

                conn.commit()

            flash(
                "Student updated successfully",
                "success"
            )

            return redirect(
                url_for("students")
            )

        except sqlite3.IntegrityError:

            flash(
                "Email already exists",
                "danger"
            )

    return render_template(
        "student_form.html",
        student=student,
        courses=COURSES,
        action="Edit"
    )


# --------------------------------------------------
# Delete Student
# --------------------------------------------------

@app.route(
    "/students/delete/<int:sid>",
    methods=["POST"]
)
@login_required
@role_required("admin")
def delete_student(sid):

    with get_db() as conn:

        conn.execute(
            """
            DELETE FROM students
            WHERE id=?
            """,
            (sid,)
        )

        conn.commit()

    flash(
        "Student deleted successfully",
        "info"
    )

    return redirect(
        url_for("students")
    )


# --------------------------------------------------
# Student Details
# --------------------------------------------------

@app.route("/students/<int:sid>")
@login_required
def student_detail(sid):

    with get_db() as conn:

        student = conn.execute(
            """
            SELECT *
            FROM students
            WHERE id=?
            """,
            (sid,)
        ).fetchone()

        att_records = conn.execute(
            """
            SELECT *
            FROM attendance
            WHERE student_id=?
            ORDER BY date DESC
            LIMIT 30
            """,
            (sid,)
        ).fetchall()

    if not student:

        flash(
            "Student not found",
            "danger"
        )

        return redirect(
            url_for("students")
        )

    att_total = len(att_records)

    att_present = sum(
        1
        for a in att_records
        if a["status"] == "P"
    )

    att_pct = round(
        (att_present / att_total) * 100,
        1
    ) if att_total else 0

    return render_template(
        "student_detail.html",
        student=student,
        grade=grade(student["marks"]),
        att_records=att_records,
        att_pct=att_pct,
        att_present=att_present,
        att_total=att_total
    )


# --------------------------------------------------
# Export Students CSV
# --------------------------------------------------

@app.route("/students/export")
@login_required
def export_students():

    with get_db() as conn:

        students = conn.execute(
            """
            SELECT *
            FROM students
            ORDER BY name
            """
        ).fetchall()

    output = io.StringIO()

    writer = csv.writer(output)

    writer.writerow([
        "ID",
        "Name",
        "Email",
        "Age",
        "Gender",
        "Course",
        "Marks",
        "Grade",
        "Phone",
        "Address",
        "DOB"
    ])

    for s in students:

        writer.writerow([
            s["id"],
            s["name"],
            s["email"],
            s["age"],
            s["gender"],
            s["course"],
            s["marks"],
            grade(s["marks"]),
            s["phone"],
            s["address"],
            s["dob"]
        ])

    output.seek(0)

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
            "attachment; filename=students.csv"
        }
    )
            # --------------------------------------------------
# Attendance
# --------------------------------------------------

@app.route(
    "/attendance",
    methods=["GET", "POST"]
)
@login_required
def attendance():

    sel_date = request.args.get(
        "date",
        date.today().isoformat()
    )

    if request.method == "POST":

        if session.get("role") in [
            "admin",
            "teacher"
        ]:

            with get_db() as conn:

                students = conn.execute(
                    "SELECT id FROM students"
                ).fetchall()

                for s in students:

                    status = request.form.get(
                        f"status_{s['id']}",
                        "P"
                    )

                    conn.execute(
                        """
                        INSERT INTO attendance
                        (
                            student_id,
                            date,
                            status,
                            marked_by
                        )
                        VALUES
                        (
                            ?,?,?,?
                        )
                        """,
                        (
                            s["id"],
                            sel_date,
                            status,
                            session["user_id"]
                        )
                    )

                conn.commit()

            flash(
                "Attendance saved successfully",
                "success"
            )

            return redirect(
                url_for("attendance")
            )

    with get_db() as conn:

        students = conn.execute(
            """
            SELECT *
            FROM students
            ORDER BY name
            """
        ).fetchall()

    rows = []

    for s in students:

        rows.append({
            "student": s,
            "status": "P"
        })

    return render_template(
        "attendance.html",
        rows=rows,
        sel_date=sel_date,
        P=len(rows),
        A=0,
        L=0,
        status_filter=""
    )


# --------------------------------------------------
# Reports
# --------------------------------------------------

@app.route("/reports")
@login_required
@role_required(
    "admin",
    "teacher"
)
def reports():

    with get_db() as conn:

        students = conn.execute(
            """
            SELECT *
            FROM students
            ORDER BY marks DESC
            """
        ).fetchall()

    total = len(students)

    avg = round(
        sum(s["marks"] for s in students) / total,
        1
    ) if total else 0

    highest = max(
        (s["marks"] for s in students),
        default=0
    )

    lowest = min(
        (s["marks"] for s in students),
        default=0
    )

    grade_dist = {
        "A+": 0,
        "A": 0,
        "B": 0,
        "C": 0,
        "D": 0,
        "F": 0
    }

    course_avgs = {}

    for s in students:

        grade_dist[
            grade(s["marks"])
        ] += 1

        course = s["course"]

        course_avgs.setdefault(
            course,
            []
        ).append(
            s["marks"]
        )

    course_avgs = {
        c: round(
            sum(v) / len(v),
            1
        )
        for c, v in course_avgs.items()
    }

    students_with_grade = [
        (
            s,
            grade(s["marks"])
        )
        for s in students
    ]

    return render_template(
        "reports.html",
        students=students_with_grade,
        total=total,
        avg=avg,
        highest=highest,
        lowest=lowest,
        grade_dist=grade_dist,
        course_avgs=course_avgs
    )


# --------------------------------------------------
# Notices
# --------------------------------------------------

@app.route("/notices")
@login_required
def notices():

    with get_db() as conn:

        rows = conn.execute(
            """
            SELECT *
            FROM notices
            ORDER BY created_at DESC
            """
        ).fetchall()

    return render_template(
        "notices.html",
        notices=rows
    )


@app.route(
    "/notices/add",
    methods=["POST"]
)
@login_required
@role_required(
    "admin",
    "teacher"
)
def add_notice():

    with get_db() as conn:

        conn.execute(
            """
            INSERT INTO notices
            (
                title,
                body,
                type,
                created_by
            )
            VALUES
            (
                ?,?,?,?
            )
            """,
            (
                request.form["title"],
                request.form["body"],
                request.form["type"],
                session["user_id"]
            )
        )

        conn.commit()

    flash(
        "Notice posted successfully",
        "success"
    )

    return redirect(
        url_for("notices")
    )


@app.route(
    "/notices/delete/<int:nid>",
    methods=["POST"]
)
@login_required
@role_required("admin")
def delete_notice(nid):

    with get_db() as conn:

        conn.execute(
            """
            DELETE FROM notices
            WHERE id=?
            """,
            (nid,)
        )

        conn.commit()

    flash(
        "Notice deleted",
        "info"
    )

    return redirect(
        url_for("notices")
    )


# --------------------------------------------------
# API
# --------------------------------------------------

@app.route("/api/stats")
@login_required
def api_stats():

    with get_db() as conn:

        students = conn.execute(
            """
            SELECT *
            FROM students
            """
        ).fetchall()

    return jsonify({
        "total_students":
            len(students),

        "average_marks":
            round(
                sum(
                    s["marks"]
                    for s in students
                ) / len(students),
                1
            ) if students else 0
    })


# --------------------------------------------------
# Main
# --------------------------------------------------

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
