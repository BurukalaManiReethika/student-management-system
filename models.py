from datetime import date

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


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


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True)
    age = db.Column(db.Integer)
    course = db.Column(db.String(120))
    marks = db.Column(db.Integer)
    grade = db.Column(db.String(5))

    attendance_records = db.relationship(
        "Attendance",
        backref="student",
        cascade="all, delete-orphan",
        lazy=True,
    )

    def refresh_grade(self):
        self.grade = calculate_grade(self.marks)

    def attendance_summary(self):
        """Returns (present_count, total_count, percentage)."""
        total = len(self.attendance_records)
        present = sum(1 for a in self.attendance_records if a.status == "Present")
        pct = round((present / total) * 100, 1) if total else None
        return present, total, pct


class Attendance(db.Model):
    __tablename__ = "attendance"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    status = db.Column(db.String(10), nullable=False, default="Present")  # Present / Absent

    __table_args__ = (
        db.UniqueConstraint("student_id", "date", name="uq_student_date"),
    )
