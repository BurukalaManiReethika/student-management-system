from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response
import sqlite3, csv, io, hashlib, os
from datetime import datetime, date, timedelta
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-this-in-production-xyz123')

DB = 'students.db'

# ── helpers ──────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def grade(marks):
    if marks >= 90: return 'A+'
    if marks >= 80: return 'A'
    if marks >= 70: return 'B'
    if marks >= 60: return 'C'
    if marks >= 50: return 'D'
    return 'F'

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if session.get('role') not in roles:
                flash('Access denied.', 'danger')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated
    return decorator

# ── init db ──────────────────────────────────────────────────────────────────

def init_db():
    with get_db() as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                name TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'student'
            );

            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                age INTEGER,
                gender TEXT DEFAULT 'Male',
                course TEXT NOT NULL,
                marks INTEGER NOT NULL DEFAULT 0,
                phone TEXT,
                address TEXT,
                dob TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'P',
                marked_by INTEGER,
                UNIQUE(student_id, date),
                FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
                FOREIGN KEY(marked_by) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS notices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                body TEXT,
                type TEXT DEFAULT 'info',
                created_by INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(created_by) REFERENCES users(id)
            );
        ''')

        users = [
            ('admin', hash_pw('admin123'), 'Admin User', 'admin'),
            ('teacher', hash_pw('teach123'), 'Ms. Priya Sharma', 'teacher'),
            ('student', hash_pw('stu123'), 'Ravi Kumar', 'student'),
        ]

        for u in users:
            conn.execute(
                'INSERT OR IGNORE INTO users(username,password,name,role) VALUES(?,?,?,?)',
                u
            )

        sample = [
            ('Aanya Singh','aanya@example.com',19,'Female','Computer Science',92,'9876543210','Chennai','2005-03-12'),
            ('Ravi Kumar','ravi@example.com',20,'Male','Mathematics',78,'9876543211','Mumbai','2004-07-22'),
            ('Priya Nair','priya@example.com',18,'Female','Physics',85,'9876543212','Bangalore','2006-01-05'),
            ('Arjun Mehta','arjun@example.com',21,'Male','Chemistry',55,'9876543213','Delhi','2003-11-18'),
            ('Sneha Reddy','sneha@example.com',19,'Female','Biology',67,'9876543214','Hyderabad','2005-05-30'),
            ('Karthik Raj','karthik@example.com',20,'Male','English',43,'9876543215','Coimbatore','2004-09-14'),
            ('Meena Iyer','meena@example.com',18,'Female','History',88,'9876543216','Pune','2006-02-28'),
            ('Vikram Das','vikram@example.com',22,'Male','Economics',71,'9876543217','Kolkata','2002-12-01'),
        ]

        for s in sample:
            conn.execute('''
                INSERT OR IGNORE INTO students
                (name,email,age,gender,course,marks,phone,address,dob)
                VALUES(?,?,?,?,?,?,?,?,?)
            ''', s)

        notices = [
            ('Semester exams schedule released',
             'Final exams will be held from July 10–20. Check the timetable on the portal.',
             'exam', 1),

            ('Annual sports day — June 30',
             'All students are encouraged to participate. Registration open now.',
             'event', 1),

            ('Library closed June 25',
             'The library will be closed for maintenance on June 25th.',
             'info', 1),
        ]

        for n in notices:
            conn.execute(
                'INSERT OR IGNORE INTO notices(title,body,type,created_by) VALUES(?,?,?,?)',
                n
            )

        import random
        students = conn.execute('SELECT id FROM students').fetchall()

        today = date.today()
        days = []
        d = today

        while len(days) < 5:
            if d.weekday() < 5:
                days.append(d.isoformat())
            d -= timedelta(days=1)

        for s in students:
            for day in days:
                st = random.choice(['P','P','P','A','L'])
                conn.execute(
                    'INSERT OR IGNORE INTO attendance(student_id,date,status) VALUES(?,?,?)',
                    (s['id'], day, st)
                )

init_db()

# ── auth ─────────────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET','POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username'].strip()
        password = hash_pw(request.form['password'])

        with get_db() as conn:
            user = conn.execute(
                'SELECT * FROM users WHERE username=? AND password=?',
                (username, password)
            ).fetchone()

        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['name'] = user['name']
            session['role'] = user['role']

            flash(f'Welcome back, {user["name"]}!', 'success')
            return redirect(url_for('index'))

        flash('Invalid username or password.', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))

# ── dashboard ────────────────────────────────────────────────────────────────

@app.route('/')
@login_required
def index():
    with get_db() as conn:
        students = conn.execute('SELECT * FROM students').fetchall()

        notices = conn.execute(
            '''
            SELECT n.*, u.name as author
            FROM notices n
            LEFT JOIN users u ON n.created_by=u.id
            ORDER BY n.created_at DESC
            LIMIT 3
            '''
        ).fetchall()

    total = len(students)
    avg = round(sum(s['marks'] for s in students) / total, 1) if total else 0
    passing = sum(1 for s in students if s['marks'] >= 50)
    top = max(students, key=lambda s: s['marks'], default=None)

    grade_dist = {'A+':0,'A':0,'B':0,'C':0,'D':0,'F':0}
    course_dist = {}

    for s in students:
        g = grade(s['marks'])
        grade_dist[g] += 1
        course_dist[s['course']] = course_dist.get(s['course'], 0) + 1

    top5 = sorted(students, key=lambda s: s['marks'], reverse=True)[:5]

    return render_template(
        'index.html',
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
            total=len(rows)
    )

@app.route('/students/add', methods=['GET','POST'])
@login_required
@role_required('admin','teacher')
def add_student():
    if request.method == 'POST':
        try:
            with get_db() as conn:
                conn.execute('''INSERT INTO students
                    (name,email,age,gender,course,marks,phone,address,dob)
                    VALUES(?,?,?,?,?,?,?,?,?)''', (
                    request.form['name'].strip(),
                    request.form['email'].strip(),
                    int(request.form.get('age') or 0),
                    request.form.get('gender','Male'),
                    request.form['course'],
                    int(request.form['marks']),
                    request.form.get('phone','').strip(),
                    request.form.get('address','').strip(),
                    request.form.get('dob',''),
                ))
            flash('Student added successfully!', 'success')
            return redirect(url_for('students'))
        except sqlite3.IntegrityError:
            flash('Email already exists.', 'danger')
    return render_template('student_form.html', student=None, courses=COURSES, action='Add')

@app.route('/students/edit/<int:sid>', methods=['GET','POST'])
@login_required
@role_required('admin','teacher')
def edit_student(sid):
    with get_db() as conn:
        student = conn.execute('SELECT * FROM students WHERE id=?', (sid,)).fetchone()
    if not student:
        flash('Student not found.', 'danger')
        return redirect(url_for('students'))
    if request.method == 'POST':
        try:
            with get_db() as conn:
                conn.execute('''UPDATE students SET
                    name=?,email=?,age=?,gender=?,course=?,marks=?,phone=?,address=?,dob=?
                    WHERE id=?''', (
                    request.form['name'].strip(),
                    request.form['email'].strip(),
                    int(request.form.get('age') or 0),
                    request.form.get('gender','Male'),
                    request.form['course'],
                    int(request.form['marks']),
                    request.form.get('phone','').strip(),
                    request.form.get('address','').strip(),
                    request.form.get('dob',''),
                    sid
                ))
            flash('Student updated!', 'success')
            return redirect(url_for('students'))
        except sqlite3.IntegrityError:
            flash('Email already exists.', 'danger')
    return render_template('student_form.html', student=student, courses=COURSES, action='Edit')

@app.route('/students/delete/<int:sid>', methods=['POST'])
@login_required
@role_required('admin')
def delete_student(sid):
    with get_db() as conn:
        conn.execute('DELETE FROM students WHERE id=?', (sid,))
    flash('Student deleted.', 'info')
    return redirect(url_for('students'))

@app.route('/students/export')
@login_required
def export_students():
    with get_db() as conn:
        rows = conn.execute('SELECT * FROM students ORDER BY name').fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID','Name','Email','Age','Gender','Course','Marks','Grade','Phone','Address','DOB'])
    for r in rows:
        writer.writerow([r['id'],r['name'],r['email'],r['age'],r['gender'],
                         r['course'],r['marks'],grade(r['marks']),r['phone'],r['address'],r['dob']])
    output.seek(0)
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition':'attachment;filename=students.csv'})

@app.route('/students/<int:sid>')
@login_required
def student_detail(sid):
    with get_db() as conn:
        student = conn.execute('SELECT * FROM students WHERE id=?', (sid,)).fetchone()
        att_records = conn.execute(
            'SELECT * FROM attendance WHERE student_id=? ORDER BY date DESC LIMIT 30', (sid,)
        ).fetchall()
    if not student:
        flash('Student not found.', 'danger')
        return redirect(url_for('students'))
    att_total  = len(att_records)
    att_present= sum(1 for a in att_records if a['status']=='P')
    att_pct    = round(att_present/att_total*100) if att_total else 0
    return render_template('student_detail.html',
        student=student, grade=grade(student['marks']),
        att_records=att_records, att_pct=att_pct, att_present=att_present, att_total=att_total
    )

# Attendance

@app.route('/attendance', methods=['GET','POST'])
@login_required
def attendance():
    sel_date = request.args.get('date', date.today().isoformat())
    status_filter = request.args.get('status','')

    if request.method == 'POST' and session['role'] in ('admin','teacher'):
        sel_date = request.form.get('date', date.today().isoformat())
        with get_db() as conn:
            students = conn.execute('SELECT id FROM students').fetchall()
            for s in students:
                status = request.form.get(f'status_{s["id"]}', 'A')
                conn.execute('''INSERT INTO attendance(student_id,date,status,marked_by)
                    VALUES(?,?,?,?)
                    ON CONFLICT(student_id,date)
                    DO UPDATE SET status=excluded.status,
                    marked_by=excluded.marked_by''',
                    (s['id'], sel_date, status, session['user_id']))
        flash(f'Attendance saved for {sel_date}!', 'success')
        return redirect(url_for('attendance', date=sel_date))

    with get_db() as conn:
        students = conn.execute('SELECT * FROM students ORDER BY name').fetchall()
        att_map = {}

        for a in conn.execute(
            'SELECT * FROM attendance WHERE date=?',
            (sel_date,)
        ).fetchall():
            att_map[a['student_id']] = a['status']

    rows = []
    for s in students:
        st = att_map.get(s['id'], '')
        if not status_filter or st == status_filter:
            rows.append({'student': s, 'status': st})

    P = sum(1 for r in rows if r['status']=='P')
    A = sum(1 for r in rows if r['status']=='A')
    L = sum(1 for r in rows if r['status']=='L')

    dates = []
    d = date.today()
    while len(dates) < 5:
        if d.weekday() < 5:
            dates.append(d.isoformat())
        d -= timedelta(days=1)

    return render_template(
        'attendance.html',
        rows=rows,
        sel_date=sel_date,
        dates=dates,
        P=P,
        A=A,
        L=L,
        status_filter=status_filter
    )

# Reports

@app.route('/reports')
@login_required
@role_required('admin','teacher')
def reports():
    with get_db() as conn:
        students = conn.execute(
            'SELECT * FROM students ORDER BY marks DESC'
        ).fetchall()

    total = len(students)
    avg = round(sum(s['marks'] for s in students)/total,1) if total else 0
    highest = max((s['marks'] for s in students), default=0)
    lowest = min((s['marks'] for s in students), default=0)
    passing = sum(1 for s in students if s['marks'] >= 50)

    grade_dist = {'A+':0,'A':0,'B':0,'C':0,'D':0,'F':0}
    course_stats = {}

    for s in students:
        g = grade(s['marks'])
        grade_dist[g] += 1

        c = s['course']
        if c not in course_stats:
            course_stats[c] = {'total':0,'sum':0}

        course_stats[c]['total'] += 1
        course_stats[c]['sum'] += s['marks']

    course_avgs = {
        c: round(v['sum']/v['total'],1)
        for c,v in course_stats.items()
    }

    students_with_grade = [
        (s, grade(s['marks']))
        for s in students
    ]

    return render_template(
        'reports.html',
        students=students_with_grade,
        total=total,
        avg=avg,
        highest=highest,
        lowest=lowest,
        passing=passing,
        grade_dist=grade_dist,
        course_avgs=course_avgs
    )

# Notices

@app.route('/notices')
@login_required
def notices():
    with get_db() as conn:
        rows = conn.execute(
            '''
            SELECT n.*, u.name as author
            FROM notices n
            LEFT JOIN users u ON n.created_by=u.id
            ORDER BY n.created_at DESC
            '''
        ).fetchall()

    return render_template('notices.html', notices=rows)

@app.route('/notices/add', methods=['POST'])
@login_required
@role_required('admin','teacher')
def add_notice():
    title = request.form.get('title','').strip()
    body = request.form.get('body','').strip()
    ntype = request.form.get('type','info')

    if title:
        with get_db() as conn:
            conn.execute(
                'INSERT INTO notices(title,body,type,created_by) VALUES(?,?,?,?)',
                (title, body, ntype, session['user_id'])
            )

        flash('Notice posted!', 'success')

    return redirect(url_for('notices'))

@app.route('/notices/delete/<int:nid>', methods=['POST'])
@login_required
@role_required('admin')
def delete_notice(nid):
    with get_db() as conn:
        conn.execute(
            'DELETE FROM notices WHERE id=?',
            (nid,)
        )

    flash('Notice deleted.', 'info')
    return redirect(url_for('notices'))

# API

@app.route('/api/stats')
@login_required
def api_stats():
    with get_db() as conn:
        students = conn.execute(
            'SELECT marks, course FROM students'
        ).fetchall()

    grade_dist = {'A+':0,'A':0,'B':0,'C':0,'D':0,'F':0}
    course_dist = {}

    for s in students:
        grade_dist[grade(s['marks'])] += 1
        course_dist[s['course']] = course_dist.get(
            s['course'], 0
        ) + 1

    return jsonify(
        grade_dist=grade_dist,
        course_dist=course_dist
    )

if __name__ == '__main__':
    app.run(debug=True)
