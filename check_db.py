import sqlite3, urllib.request, json

# Check database
conn = sqlite3.connect('campus_navigation.db')
cur = conn.cursor()
tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("Tables in DB:", [t[0] for t in tables])

if ('students',) in [t[0] for t in tables]:
    rows = cur.execute("SELECT * FROM students").fetchall()
    print(f"Students: {len(rows)} entries")
    for r in rows:
        print(f"  - {r}")
else:
    print("Students table NOT FOUND!")
    # Try to create it
    cur.execute('''CREATE TABLE IF NOT EXISTS students (
        reg_no TEXT PRIMARY KEY, password TEXT NOT NULL,
        course TEXT NOT NULL, year INTEGER NOT NULL,
        semester INTEGER NOT NULL, units TEXT NOT NULL)''')
    conn.commit()
    print("Created students table")

# Test timetable
count = cur.execute("SELECT COUNT(*) FROM timetable").fetchone()[0]
print(f"Timetable entries: {count}")
if count > 0:
    sample = cur.execute("SELECT * FROM timetable LIMIT 3").fetchall()
    for s in sample:
        print(f"  - {s}")

conn.close()

# Test API
print("\n--- Testing API ---")
try:
    h = json.loads(urllib.request.urlopen('http://127.0.0.1:8000/health').read())
    print(f"Health OK: {h['counts']}")
except Exception as e:
    print(f"Health FAILED: {e}")

try:
    data = json.dumps({"reg_no":"DEMO001","password":"demo","course":"CS","year":1,"semester":1,"units":"CS101"}).encode()
    req = urllib.request.Request('http://127.0.0.1:8000/students/register', data=data, headers={'Content-Type':'application/json'})
    res = json.loads(urllib.request.urlopen(req).read())
    print(f"Register: {res}")
except Exception as e:
    print(f"Register FAILED: {e}")

try:
    r = urllib.request.urlopen('http://127.0.0.1:8000/students/schedule/DEMO001')
    print(f"Schedule: {json.loads(r.read())['day']} - {len(json.loads(r.read())['schedule'])} classes")
except Exception as e:
    print(f"Schedule FAILED: {e}")