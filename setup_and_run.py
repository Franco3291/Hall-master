import sqlite3, os, sys, subprocess

# 1. Initialize database tables
print("=== Setting up database ===")
conn = sqlite3.connect('campus_navigation.db')
cur = conn.cursor()

# Create tables if not exist
cur.execute('''CREATE TABLE IF NOT EXISTS nodes (
    name TEXT PRIMARY KEY, floor INTEGER DEFAULT 1, description TEXT,
    lat REAL DEFAULT 0.0, lng REAL DEFAULT 0.0,
    occupancy_status TEXT DEFAULT 'UNVERIFIED',
    last_verified TEXT DEFAULT 'Never', image_url TEXT,
    camera_url TEXT DEFAULT NULL)''')

cur.execute('''CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_from TEXT, node_to TEXT, distance_meters REAL,
    FOREIGN KEY(node_from) REFERENCES nodes(name),
    FOREIGN KEY(node_to) REFERENCES nodes(name))''')

cur.execute('''CREATE TABLE IF NOT EXISTS timetable (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_code TEXT, course_name TEXT, day_of_week TEXT,
    start_time TEXT, end_time TEXT, venue TEXT)''')

cur.execute('''CREATE TABLE IF NOT EXISTS students (
    reg_no TEXT PRIMARY KEY, password TEXT NOT NULL,
    course TEXT NOT NULL, year INTEGER NOT NULL,
    semester INTEGER NOT NULL, units TEXT NOT NULL)''')

conn.commit()

# 2. Check if nodes exist, if not seed them
count = cur.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
if count == 0:
    print("Seeding campus map nodes...")
    campus_nodes = [
        ("Forensic laboratory", -1.045600, 37.012300, 1, "Main laboratory"),
        ("Vice chancellors office", -1.046100, 37.012800, 1, "Admin Block"),
        ("BS/2", -0.092969, 37.989887, 1, "Common Hub"),
        ("Main Gate Junction", -1.045000, 37.011500, 1, "Main Entry"),
        ("UTC 9", -0.090023, 37.987475, 1, "Lecture"),
        ("STB 2", -0.090755, 37.989205, 1, "Lecture"),
        ("ED 7", -0.090617, 37.989997, 1, "Lecture"),
        ("TC 1", -0.092325, 37.989829, 1, "Lecture"),
        ("Bs/1", -0.092576, 37.990462, 1, "Lecture"),
        ("Hospitality lab", -0.092770, 37.991091, 1, "Lab"),
        ("Forensic laboratory (Old Location)", -0.092555, 37.990695, 1, "Lab"),
        ("Bs/3", -0.093857, 37.991478, 1, "Lecture"),
    ]
    for name, lat, lng, floor, desc in campus_nodes:
        cur.execute("INSERT OR IGNORE INTO nodes (name, floor, description, lat, lng, occupancy_status, last_verified) VALUES (?,?,?,?,?,'UNVERIFIED','Never')", 
                   (name, floor, desc, lat, lng))
    conn.commit()
    print(f"  Added {len(campus_nodes)} nodes")

# 3. Check if timetable exists
tt_count = cur.execute("SELECT COUNT(*) FROM timetable").fetchone()[0]
print(f"Timetable entries: {tt_count}")
print(f"Nodes: {cur.execute('SELECT COUNT(*) FROM nodes').fetchone()[0]}")
print(f"Edges: {cur.execute('SELECT COUNT(*) FROM edges').fetchone()[0]}")

conn.close()
print("\n=== Database ready! ===")

# 4. Start server
print("\nStarting FastAPI server...")
os.environ['ADMIN_PASSWORD'] = 'Campus@123'
subprocess.run([sys.executable, '-m', 'uvicorn', 'main:app', '--reload', '--host', '127.0.0.1', '--port', '8000'])