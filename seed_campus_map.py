import sqlite3

def seed_map_data():
    """
    Seeds the campus map with your exact coordinates for all nodes.
    """
    conn = sqlite3.connect('campus_navigation.db')
    cursor = conn.cursor()

    print("Dropping old table structures...")
    cursor.execute("DROP TABLE IF EXISTS nodes")
    cursor.execute("DROP TABLE IF EXISTS edges")

    cursor.execute('''
        CREATE TABLE nodes (
            name TEXT PRIMARY KEY,
            floor INTEGER DEFAULT 1,
            description TEXT,
            lat REAL DEFAULT 0.0,
            lng REAL DEFAULT 0.0,
            occupancy_status TEXT DEFAULT 'UNVERIFIED',
            last_verified TEXT DEFAULT 'Never',
            image_url TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE edges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_from TEXT,
            node_to TEXT,
            distance_meters REAL,
            direction_hint TEXT,
            FOREIGN KEY(node_from) REFERENCES nodes(name),
            FOREIGN KEY(node_to) REFERENCES nodes(name)
        )
    ''')

    # 3. YOUR EXACT NODES
    campus_nodes = [
        ("Forensic laboratory", -1.045600, 37.012300, 1, "Main laboratory complex area"),
        ("Vice chancellors office", -1.046100, 37.012800, 1, "Administration Block"),
        ("BS/2", -0.092969, 37.989887, 1, "Common Group Hub Point"),
        ("Main Gate Junction", -1.045000, 37.011500, 1, "Pedestrian Pathway split entry point"),
        ("UTC 9", -0.090023, 37.987475, 1, "Common Group"),
        ("STB 2", -0.090755, 37.989205, 1, "Common Group"),
        ("ED 7", -0.090617, 37.989997, 1, "Common Group"),
        ("TC 1", -0.092325, 37.989829, 1, "Common Group"),
        ("Bs/1", -0.092576, 37.990462, 1, "Common Group"),
        ("Hospitality lab", -0.092770, 37.991091, 1, "Common Group"),
        ("Forensic laboratory (Old Location)", -0.092555, 37.990695, 1, "Common Group"),
        ("Bs/3", -0.093857, 37.991478, 1, "Common Group"),
        ("UTC 7", -0.090071, 37.987236, 1, "Common Group"),
        ("UTC 4", -0.090135, 37.986793, 1, "Common Group"),
        ("UTC 5", -0.089972, 37.986814, 1, "Common Group"),
        ("UTC 6", -0.089910, 37.987072, 1, "Common Group"),
        ("UTC 3", -0.090330, 37.986788, 1, "Common Group"),
        ("UTC 2", -0.090278, 37.986831, 1, "Common Group"),
        ("STB", -0.090889, 37.989139, 1, "Common Group"),
        ("CHEM LAB", -0.090763, 37.989195, 1, "Common Group"),
        ("UTC 14", -0.090825, 37.987438, 1, "Common Group"),
        ("UTC 1", -0.090371, 37.987353, 1, "Common Group"),
        ("ODEL CENTER", -0.090169, 37.987256, 1, "Common Group"),
        ("UTC", -0.090089, 37.987632, 1, "Common Group"),
        ("DEAN FBURST", -0.090161, 37.987279, 1, "Common Group"),
        ("DIRECTOR ODEL", -0.090345, 37.987340, 1, "Common Group"),
        ("BIO LAB", -0.090500, 37.989500, 1, "Biology Laboratory"),
        ("PHYSICS LAB", -0.090400, 37.989600, 1, "Physics Laboratory"),
    ]

    print(f"Inserting {len(campus_nodes)} campus nodes...")
    for name, lat, lng, floor, desc in campus_nodes:
        cursor.execute('''
            INSERT INTO nodes (name, floor, description, lat, lng, occupancy_status, last_verified)
            VALUES (?, ?, ?, ?, ?, 'UNVERIFIED', 'Never')
        ''', (name, floor, desc, lat, lng))

    # 4. EDGES connecting nearby nodes
    campus_edges = [
        # --- THARAKA CAMPUS CLUSTER (~ -0.090 to -0.094) ---
        # UTC cluster
        ("UTC 9", "UTC 7", 30.0, "adjacent UTC buildings"),
        ("UTC 7", "UTC 6", 25.0, "along UTC block row"),
        ("UTC 6", "UTC 5", 20.0, "adjacent UTC buildings"),
        ("UTC 5", "UTC 4", 25.0, "along UTC block row"),
        ("UTC 4", "UTC 3", 30.0, "adjacent UTC buildings"),
        ("UTC 3", "UTC 2", 15.0, "adjacent UTC buildings"),
        ("UTC 2", "UTC 1", 20.0, "along UTC block row"),
        ("UTC 1", "UTC", 15.0, "adjacent UTC buildings"),
        ("UTC", "ODEL CENTER", 15.0, "adjacent buildings"),
        ("ODEL CENTER", "DEAN FBURST", 10.0, "adjacent offices"),
        ("DEAN FBURST", "DIRECTOR ODEL", 20.0, "along office row"),
        ("DIRECTOR ODEL", "UTC 14", 50.0, "cross campus path"),
        ("UTC 14", "UTC 9", 60.0, "around UTC block perimeter"),
        
        # STB / Chemistry Lab cluster
        ("STB 2", "STB", 20.0, "adjacent STB buildings"),
        ("STB", "CHEM LAB", 15.0, "adjacent buildings"),
        ("CHEM LAB", "PHYSICS LAB", 15.0, "adjacent lab buildings"),
        ("PHYSICS LAB", "BIO LAB", 15.0, "adjacent lab buildings"),
        ("BIO LAB", "STB 2", 20.0, "around lab complex"),
        
        # Central campus connections
        ("STB 2", "ED 7", 90.0, "past the central pavilion corridor"),
        ("ED 7", "Bs/1", 210.2, "down the eastern academic block lane"),
        ("STB 2", "UTC 9", 180.5, "straight along the northern perimeter walkway"),
        ("STB 2", "UTC 14", 150.0, "cross campus pathway"),
        ("Bs/1", "Forensic laboratory (Old Location)", 45.0, "directly across the walkway deck"),
        ("Forensic laboratory (Old Location)", "Hospitality lab", 50.0, "adjacent facility service path"),
        ("Bs/1", "TC 1", 75.8, "heading west towards the science block corner"),
        ("TC 1", "BS/2", 80.4, "straight access sidewalk down the line"),
        ("BS/2", "Bs/3", 205.0, "southern link route heading towards the field gate"),
        ("Forensic laboratory (Old Location)", "Vice chancellors office", 120.0, "administration avenue corridor link"),
        
        # --- MAIN CAMPUS CLUSTER (~ -1.045 to -1.046) ---
        ("Main Gate Junction", "Forensic laboratory", 95.5, "main access entry road path segment"),
        ("Forensic laboratory", "Vice chancellors office", 120.0, "administration avenue corridor link"),
        ("Main Gate Junction", "Vice chancellors office", 150.0, "campus ring road path"),
    ]

    print(f"Connecting {len(campus_edges)} pathway edges...")
    for node_from, node_to, dist, hint in campus_edges:
        cursor.execute('''
            INSERT INTO edges (node_from, node_to, distance_meters, direction_hint)
            VALUES (?, ?, ?, ?)
        ''', (node_from, node_to, dist, hint))

    conn.commit()
    conn.close()
    print(f"✅ Database updated with {len(campus_nodes)} nodes and {len(campus_edges)} edges!")
    print(f"   See your campus nodes on the Map Routes tab in app.html")

if __name__ == '__main__':
    seed_map_data()