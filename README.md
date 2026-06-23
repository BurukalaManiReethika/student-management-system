# 🎓 Student Management System

A modern and responsive Student Management System built with Flask, SQLite, HTML, CSS, and JavaScript

## 🚀 Features

### 👨‍🎓 Student Management
- Add Students
- Edit Students
- Delete Students
- View Student Details
- Search Students
- Export Student Data to CSV

### 📊 Dashboard
- Total Students
- Average Marks
- Pass Percentage
- Top Performer
- Grade Distribution
- Course Statistics

### 📅 Attendance Management
- Mark Attendance
- View Attendance Records
- Attendance Reports
- Present / Absent Statistics

### 📢 Notice Board
- Create Notices
- View Notices
- Delete Notices
- Notice Categories

### 🔐 Authentication
- Admin Login
- Teacher Login
- Student Login
- Role-Based Access Control

### 📈 Reports
- Student Performance Reports
- Course Analytics
- Grade Distribution
- Statistics Dashboard

---

## 🛠️ Tech Stack

### Backend
- Flask
- SQLite
- Python

### Frontend
- HTML5
- CSS3
- JavaScript
- Bootstrap

### Deployment
- Render
- Gunicorn

---

## 📂 Project Structure

```text
student-management-system/
│
├── app.py
├── students.db
├── requirements.txt
├── render.yaml
│
├── static/
│   ├── css/
│   │   └── style.css
│   │
│   └── js/
│       └── script.js
│
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── index.html
│   ├── students.html
│   ├── student_form.html
│   ├── student_detail.html
│   ├── attendance.html
│   ├── reports.html
│   └── notices.html
│
└── README.md
```

---

## ⚡ Installation

### Clone Repository

```bash
git clone https://github.com/yourusername/student-management-system.git
```

### Move Into Folder

```bash
cd student-management-system
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run Application

```bash
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

---

## 🔑 Demo Credentials

### Admin

```text
Username: admin
Password: admin123
```

### Teacher

```text
Username: teacher
Password: teach123
```

### Student

```text
Username: student
Password: stu123
```

---

## 📊 Dashboard Modules

- Student Overview
- Attendance Overview
- Notices
- Reports
- Analytics
- Export Data

---

## 🌐 Deployment on Render

### Build Command

```bash
pip install -r requirements.txt
```

### Start Command

```bash
gunicorn app:app
```

---

## 🎯 Future Improvements

- Email Notifications
- Parent Portal
- Fee Management
- Online Exams
- AI Analytics
- PDF Report Generation
- Multi-School Support

---

## 👨‍💻 Author

BURUKALA MANI REETHIKA

---

## ⭐ Support

If you found this project useful:

⭐ Star the repository

🍴 Fork the project

🚀 Deploy your own version

Happy Coding!
