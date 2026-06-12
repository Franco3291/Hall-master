import sqlite3

def init_database():
    conn = sqlite3.connect('campus_navigation.db')
    cursor = conn.cursor()
    
    # 1. Create Nodes Table (Locations)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS nodes (
            name TEXT PRIMARY KEY,
            floor INTEGER DEFAULT 1,
            description TEXT,
            lat REAL DEFAULT 0.0,
            lng REAL DEFAULT 0.0,
            occupancy_status TEXT DEFAULT 'UNVERIFIED',
            last_verified TEXT DEFAULT 'Never'
        )
    ''')
    
    # 2. Create Edges Table (Pathways for Dijkstra)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_from TEXT,
            node_to TEXT,
            distance_meters REAL,
            FOREIGN KEY(node_from) REFERENCES nodes(name),
            FOREIGN KEY(node_to) REFERENCES nodes(name)
        )
    ''')
    
    # 3. Create Timetable Table (Parsed Master Schedule)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS timetable (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_code TEXT,
            course_name TEXT,
            day_of_week TEXT,
            start_time TEXT,
            end_time TEXT,
            venue TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    print("📋 Database tables initialized successfully!")

if __name__ == "__main__":
    init_database()