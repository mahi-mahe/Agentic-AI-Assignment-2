"""Create/reset the demo college.db with student, scholarship, semester, and calendar data."""
from pathlib import Path
import sqlite3

DB_PATH = Path(__file__).with_name("college.db")

def setup_database():
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript("""
    DROP TABLE IF EXISTS audit_log;
    DROP TABLE IF EXISTS approval_requests;
    DROP TABLE IF EXISTS student_auth;
    DROP TABLE IF EXISTS tickets;
    DROP TABLE IF EXISTS calendar_events;
    DROP TABLE IF EXISTS timetable;
    DROP TABLE IF EXISTS exams;
    DROP TABLE IF EXISTS scholarships;
    DROP TABLE IF EXISTS students;

    CREATE TABLE students (
        student_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        total_fee INTEGER NOT NULL,
        paid INTEGER NOT NULL,
        due_date TEXT,
        programme TEXT NOT NULL,
        CHECK(total_fee >= 0 AND paid >= 0 AND paid <= total_fee)
    );

    CREATE TABLE scholarships (
        student_id TEXT PRIMARY KEY REFERENCES students(student_id),
        scholarship_name TEXT NOT NULL,
        amount INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL CHECK(status IN
          ('Approved','Under Review','Not Eligible','Pending Documents','Rejected')),
        academic_year TEXT NOT NULL,
        remarks TEXT
    );

    CREATE TABLE exams (
        semester TEXT NOT NULL,
        subject TEXT NOT NULL,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        venue TEXT NOT NULL
    );

    CREATE TABLE timetable (
        semester TEXT NOT NULL,
        day TEXT NOT NULL,
        period TEXT NOT NULL,
        subject TEXT NOT NULL
    );

    CREATE TABLE calendar_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        category TEXT NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT,
        start_time TEXT,
        venue TEXT,
        description TEXT,
        is_official INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL REFERENCES students(student_id),
        issue TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Open',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    students = [
        ("S1001","Aarav Sharma",223000,150000,"2026-10-15","PGDM AI & Data Science"),
        ("S1002","Diya Patel",223000,223000,None,"PGDM AI & Data Science"),
        ("S1003","Rohan Mehta",223000,100000,"2026-10-15","PGDM AI & Data Science"),
        ("S1004","Mahi",223000,150000,"2026-10-15","PGDM AI & Data Science"),
        ("S1005","Ishita Shah",223000,223000,None,"PGDM AI & Data Science"),
        ("S1006","Kabir Desai",223000,175000,"2026-11-15","PGDM AI & Data Science"),
        ("S1007","Ananya Rao",223000,125000,"2026-11-15","PGDM AI & Data Science"),
        ("S1008","Vivaan Joshi",223000,223000,None,"PGDM AI & Data Science"),
        ("S1009","Sara Khan",223000,80000,"2026-12-01","PGDM AI & Data Science"),
        ("S1010","Arjun Nair",223000,200000,"2026-11-30","PGDM AI & Data Science"),
    ]
    con.executemany("INSERT INTO students VALUES (?,?,?,?,?,?)", students)

    scholarship_rows = [
        ("S1001","Merit Scholarship",25000,"Approved","2026-27","Demo award; subject to institutional verification"),
        ("S1002","Need-Based Scholarship",30000,"Under Review","2026-27","Income documents under review"),
        ("S1003","Merit Scholarship",0,"Pending Documents","2026-27","Marksheets pending"),
        ("S1004","Merit-cum-Means Scholarship",20000,"Under Review","2026-27","Illustrative status; submit income and academic documents"),
        ("S1005","Institutional Merit Scholarship",25000,"Approved","2026-27","Demo award; subject to institutional verification"),
        ("S1006","Need-Based Scholarship",15000,"Pending Documents","2026-27","Bank details pending"),
        ("S1007","Institutional Merit Scholarship",0,"Not Eligible","2026-27","Illustrative eligibility outcome"),
        ("S1008","Merit Scholarship",30000,"Approved","2026-27","Demo award; subject to institutional verification"),
        ("S1009","Need-Based Scholarship",0,"Rejected","2026-27","Illustrative outcome; contact scholarship office for appeal rules"),
        ("S1010","Merit-cum-Means Scholarship",10000,"Under Review","2026-27","Verification in progress"),
    ]
    con.executemany("INSERT INTO scholarships VALUES (?,?,?,?,?,?)", scholarship_rows)

    exams = [
        ("semester 1","Python Programming","2026-11-10","10:00 AM","Hall A"),
        ("semester 1","Statistics","2026-11-13","10:00 AM","Hall B"),
        ("semester 1","Database Management","2026-11-17","02:00 PM","Hall A"),
        ("semester 2","Machine Learning","2027-04-08","10:00 AM","Hall C"),
        ("semester 2","Data Visualization","2027-04-12","02:00 PM","Hall A"),
    ]
    con.executemany("INSERT INTO exams VALUES (?,?,?,?,?)", exams)

    # Separate semester-specific weekly timetables; illustrative academic schedule.
    timetable = [
        ("semester 1","monday","09:00-10:00","Python Programming"),
        ("semester 1","monday","10:15-11:15","Statistics"),
        ("semester 1","monday","11:30-12:30","DBMS Lab"),
        ("semester 1","tuesday","09:00-10:00","Database Management"),
        ("semester 1","tuesday","10:15-11:15","Python Programming Lab"),
        ("semester 1","wednesday","09:00-10:00","Statistics"),
        ("semester 1","wednesday","10:15-11:15","Communication Skills"),
        ("semester 1","thursday","09:00-10:00","Database Management"),
        ("semester 1","thursday","10:15-11:15","Library / Tutorial"),
        ("semester 1","friday","09:00-10:00","Python Programming"),
        ("semester 1","friday","10:15-11:15","Statistics Tutorial"),
        ("semester 2","monday","09:00-10:00","Machine Learning"),
        ("semester 2","monday","10:15-11:15","Data Visualization"),
        ("semester 2","monday","11:30-12:30","ML Lab"),
        ("semester 2","tuesday","09:00-10:00","Deep Learning"),
        ("semester 2","tuesday","10:15-11:15","Data Engineering"),
        ("semester 2","wednesday","09:00-10:00","Machine Learning"),
        ("semester 2","wednesday","10:15-11:15","Research Methods"),
        ("semester 2","thursday","09:00-10:00","Data Visualization"),
        ("semester 2","thursday","10:15-11:15","Cloud Computing"),
        ("semester 2","friday","09:00-10:00","Deep Learning Lab"),
        ("semester 2","friday","10:15-11:15","Project / Seminar"),
    ]
    con.executemany("INSERT INTO timetable VALUES (?,?,?,?)", timetable)

    # Dates below are sample/demo calendar entries, not an official institutional calendar.
    events = [
        ("Founders' Day (sample)","Academic Holiday","2026-11-01",None,None,"Campus","Sample holiday entry; verify with official notice",0),
        ("Library Orientation","Co-curricular","2026-11-05",None,"11:00 AM","Central Library","Research and digital library orientation",0),
        ("Semester I Examination Window","Academic","2026-11-10","2026-11-17",None,"Examination Halls","See the exam schedule for subject-wise dates",0),
        ("Innovation & AI Fest (sample)","Fest","2026-11-21","2026-11-22",None,"Main Campus","Student projects, demos and competitions; sample event",0),
        ("Constitution Day Activities","Co-curricular","2026-11-26",None,"10:00 AM","Auditorium","Debate, reading and civic engagement activities; sample listing",0),
        ("Winter Break (sample)","Academic Holiday","2026-12-24","2027-01-02",None,"Campus","Provisional demo dates; verify official calendar",0),
        ("Data Science Guest Lecture","Co-curricular","2027-02-12",None,"02:00 PM","Seminar Hall","Industry talk; sample event",0),
        ("Annual Cultural Fest (sample)","Fest","2027-03-05","2027-03-07",None,"Main Campus","Music, dance and cultural performances; sample event",0),
        ("Campus Music Night (sample)","Concert","2027-03-06",None,"06:30 PM","Open Air Theatre","Sample listing; not a confirmed concert",0),
        ("Semester II Examination Window","Academic","2027-04-08","2027-04-12",None,"Examination Halls","See the exam schedule for subject-wise dates",0),
    ]
    con.executemany("""INSERT INTO calendar_events
        (title,category,start_date,end_date,start_time,venue,description,is_official)
        VALUES (?,?,?,?,?,?,?,?)""", events)
    con.commit()
    con.close()
    print(f"Database created: {DB_PATH}")

if __name__ == "__main__":
    setup_database()
