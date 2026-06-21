import os
import csv
import io
import secrets
from collections import Counter
from datetime import date, datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, Response, abort
)
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash

from models import db, Student, Attendance

app = Flask(__name__)

# -------------------------
# Config (env-driven, with safe local defaults)
# -------------------------
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config["DEBUG"] = os.environ.get("FLASK_DEBUG", "0") == "1"

DATABASE = os.environ.get("DATABASE_PATH", "students.db")
if not os.path.isabs(DATABASE):
    # Resolve relative to the app's root directory (not Flask's instance/
    # folder) so any existing students.db from the previous sqlite3-only
    # version of this app is picked up automatically after upgrading.
    DATABASE = os.path.join(app.root_path, DATABASE)

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", f"sqlite:///{DATABASE}"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
# Default password hash corresponds to "admin123" — override in production via env var.
ADMIN_PASSWORD_HASH = os.environ.get(
    "ADMIN_PASSWORD_HASH",
    generate_password_hash("admin123")
)

PER_PAGE = 10


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


def email_exists(email, exclude_id=None):
    query = Student.query.filter(Student.email == email)
    if exclude_id:
        query = query.filter(Student.id != exclude_id)
    return query.first() is not None


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
    order = order.lower() if order.lower() in ("asc", "desc") else "desc"

    sort_col = getattr(Student, sort)
    sort_col = sort_col.asc() if order == "asc" else sort_col.desc()

    total_students = Student.query.count()
    avg_marks = db.session.query(func.avg(Student.marks)).scalar() or 0

    pagination = Student.query.order_by(sort_col).paginate(
        page=page, per_page=PER_PAGE, error_out=False
    )
    students = pagination.items
    total_pages = max(1, pagination.pages)

    return render_template(
        "index.html",
        students=students,
        total_students=total_students,
        avg_marks=round(avg_marks, 2),
        page=page,
        total_pages=total_pages,
        sort=sort,
        order=order
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

        if not errors and email_exists(data["email"]):
            errors.append("A student with this email already exists.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("add_student.html", form=request.form)

        student = Student(
            name=data["name"], email=data["email"], age=data["age"],
            course=data["course"], marks=data["marks"]
        )
        student.refresh_grade()

        try:
            db.session.add(student)
            db.session.commit()
            flash("Student Added Successfully", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Database error: {e}", "danger")

        return redirect(url_for("dashboard"))

    return render_template("add_student.html", form={})


# -------------------------
# Edit Student
# -------------------------
@app.route("/edit/<int:id>", methods=["GET", "POST"])
@login_required
@csrf_protect
def edit_student(id):
    student = Student.query.get(id)

    if student is None:
        flash("Student not found.", "danger")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        data, errors = validate_student_form(request.form)

        if not errors and email_exists(data["email"], exclude_id=id):
            errors.append("Another student already uses this email.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("edit_student.html", student=student)

        student.name = data["name"]
        student.email = data["email"]
        student.age = data["age"]
        student.course = data["course"]
        student.marks = data["marks"]
        student.refresh_grade()

        try:
            db.session.commit()
            flash("Student Updated Successfully", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Database error: {e}", "danger")

        return redirect(url_for("dashboard"))

    return render_template("edit_student.html", student=student)


# -------------------------
# Delete Student (POST only, CSRF protected)
# -------------------------
@app.route("/delete/<int:id>", methods=["POST"])
@login_required
@csrf_protect
def delete_student(id):
    student = Student.query.get(id)
    try:
        if student:
            db.session.delete(student)
            db.session.commit()
            flash("Student Deleted Successfully", "warning")
        else:
            flash("Student not found.", "danger")
    except Exception as e:
        db.session.rollback()
        flash(f"Database error: {e}", "danger")

    return redirect(url_for("dashboard"))


# -------------------------
# Search Student
# -------------------------
@app.route("/search")
@login_required
def search_student():
    query = request.args.get("query", "").strip()
    like = f"%{query}%"

    students = Student.query.filter(
        db.or_(
            Student.name.ilike(like),
            Student.email.ilike(like),
            Student.course.ilike(like),
        )
    ).order_by(Student.id.desc()).all()

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
    students = Student.query.order_by(Student.id).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Name", "Email", "Age", "Course", "Marks", "Grade"])
    for s in students:
        writer.writerow([s.id, s.name, s.email, s.age, s.course, s.marks, s.grade])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=students.csv"}
    )


# -------------------------
# Export to PDF
# -------------------------
@app.route("/export/pdf")
@login_required
def export_pdf():
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    )
    from reportlab.lib.styles import getSampleStyleSheet

    students = Student.query.order_by(Student.id).all()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        topMargin=15 * mm, bottomMargin=15 * mm,
        leftMargin=12 * mm, rightMargin=12 * mm,
    )
    styles = getSampleStyleSheet()
    elements = [
        Paragraph("Student Management System &mdash; Student Records", styles["Title"]),
        Paragraph(
            f"Generated on {datetime.now().strftime('%d %b %Y, %I:%M %p')} "
            f"&middot; Total Students: {len(students)}",
            styles["Normal"],
        ),
        Spacer(1, 10),
    ]

    table_data = [["ID", "Name", "Email", "Age", "Course", "Marks", "Grade"]]
    for s in students:
        table_data.append([s.id, s.name, s.email, s.age, s.course, s.marks, s.grade])

    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4f46e5")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6fb")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(table)
    doc.build(elements)
    buf.seek(0)

    return Response(
        buf.read(),
        mimetype="application/pdf",
        headers={"Content-Disposition": "attachment; filename=students.pdf"}
    )


# -------------------------
# Analytics Dashboard (charts)
# -------------------------
@app.route("/analytics")
@login_required
def analytics():
    students = Student.query.all()

    grade_counts = Counter(s.grade for s in students)
    grade_labels = ["A+", "A", "B", "C", "D", "F"]
    grade_data = [grade_counts.get(g, 0) for g in grade_labels]

    course_counts = Counter(s.course for s in students)
    course_labels = list(course_counts.keys())
    course_data = [course_counts[c] for c in course_labels]

    bins = ["0-49", "50-59", "60-69", "70-79", "80-89", "90-100"]
    bin_data = [0] * 6
    for s in students:
        m = s.marks or 0
        if m < 50:
            bin_data[0] += 1
        elif m < 60:
            bin_data[1] += 1
        elif m < 70:
            bin_data[2] += 1
        elif m < 80:
            bin_data[3] += 1
        elif m < 90:
            bin_data[4] += 1
        else:
            bin_data[5] += 1

    avg_marks = round((sum(s.marks or 0 for s in students) / len(students)), 2) if students else 0
    top_student = max(students, key=lambda s: s.marks or 0, default=None)

    return render_template(
        "analytics.html",
        total_students=len(students),
        avg_marks=avg_marks,
        top_student=top_student,
        grade_labels=grade_labels,
        grade_data=grade_data,
        course_labels=course_labels,
        course_data=course_data,
        bin_labels=bins,
        bin_data=bin_data,
    )


# -------------------------
# Attendance
# -------------------------
@app.route("/attendance", methods=["GET", "POST"])
@login_required
@csrf_protect
def attendance():
    selected_date_raw = request.args.get("date") or request.form.get("date")
    try:
        selected_date = (
            datetime.strptime(selected_date_raw, "%Y-%m-%d").date()
            if selected_date_raw else date.today()
        )
    except ValueError:
        selected_date = date.today()

    if request.method == "POST":
        students = Student.query.all()
        for student in students:
            status = request.form.get(f"status_{student.id}", "Absent")
            record = Attendance.query.filter_by(
                student_id=student.id, date=selected_date
            ).first()
            if record:
                record.status = status
            else:
                db.session.add(Attendance(
                    student_id=student.id, date=selected_date, status=status
                ))
        try:
            db.session.commit()
            flash(f"Attendance saved for {selected_date.strftime('%d %b %Y')}", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Database error: {e}", "danger")
        return redirect(url_for("attendance", date=selected_date.isoformat()))

    students = Student.query.order_by(Student.name).all()
    existing = {
        a.student_id: a.status
        for a in Attendance.query.filter_by(date=selected_date).all()
    }

    return render_template(
        "attendance.html",
        students=students,
        existing=existing,
        selected_date=selected_date,
    )


@app.route("/attendance/<int:student_id>")
@login_required
def attendance_history(student_id):
    student = Student.query.get(student_id)
    if student is None:
        flash("Student not found.", "danger")
        return redirect(url_for("dashboard"))

    records = Attendance.query.filter_by(student_id=student_id).order_by(
        Attendance.date.desc()
    ).all()
    present, total, pct = student.attendance_summary()

    return render_template(
        "attendance_history.html",
        student=student,
        records=records,
        present=present,
        total=total,
        pct=pct,
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
# DB init
# -------------------------
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=app.config["DEBUG"])
