import sqlite3

def seed_map_data():
    conn = sqlite3.connect('campus_navigation.db')
    cursor = conn.cursor()

    # 1. CLEAN THE SLATE
    print("Dropping old table structures...")
    cursor.execute("DROP TABLE IF EXISTS nodes")
    cursor.execute("DROP TABLE IF EXISTS edges")

    # 2. CREATE SCHEMAS
    cursor.execute('''
        CREATE TABLE nodes (
            name TEXT PRIMARY KEY,
            lat REAL NOT NULL,
            lng REAL NOT NULL,
            floor INTEGER,
            description TEXT,
            occupancy_status TEXT,
            last_verified TEXT
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

    # 3. YOUR EXACT GEOGRAPHIC CAMPUS NODES
    # Format: ("Name", Latitude, Longitude, Floor, "Description")
    campus_nodes = [
        ("Forensic laboratory (Old Location)", -1.045600, 37.012300, 1, "Main laboratory complex area"),
        ("Vice chancellors office", -1.046100, 37.012800, 1, "Administration Block"),
        ("BS/2", -0.092969, 37.989887, 1, "Common Group Hub Point"),
        ("Main Gate Junction", -1.045000, 37.011500, 1, "Pedestrian Pathway split entry point"),
        ("UTC 9", -0.090055, 37.987448, 1, "Common Group Lecture Space"),
        ("STB 2", -0.090755, 37.989205, 1, "Common Group Lecture Space"),
        ("ED 7", -0.090617, 37.989997, 1, "Common Group Lecture Space"),
        ("TC 1", -0.092325, 37.989829, 1, "Common Group Lecture Space"),
        ("Bs/1", -0.092576, 37.990462, 1, "Common Group Lecture Space"),
        ("Hospitality lab", -0.092770, 37.991091, 1, "Common Group Laboratory Area"),
        ("Bs/3", -0.093857, 37.991478, 1, "Common Group Lecture Space")
    ]

    print("Inserting your updated geographic campus matrix...")
    for name, lat, lng, floor, desc in campus_nodes:
        cursor.execute('''
            INSERT INTO nodes (name, lat, lng, floor, description, occupancy_status, last_verified)
            VALUES (?, ?, ?, ?, ?, 'UNVERIFIED', 'Never')
        ''', (name, lat, lng, floor, desc))

    # 4. PATHWAY GRID LINK NETWORKS (EDGES)
    # These lines connect your specific coordinates together so Dijkstra can trace a path between them
    campus_edges = [
        ("UTC 9", "STB 2", 180.5, "straight along the northern perimeter walkway"),
        ("STB 2", "ED 7", 90.0, "past the central pavilion corridor"),
        ("ED 7", "Bs/1", 210.2, "down the eastern academic block lane"),
        ("Bs/1", "Forensic laboratory (Main Site)", 45.0, "directly across the walkway deck"),
        ("Forensic laboratory (Main Site)", "Hospitality lab", 50.0, "adjacent facility service path"),
        ("Bs/1", "TC 1", 75.8, "heading west towards the science block corner"),
        ("TC 1", "BS/2", 80.4, "straight access sidewalk down the line"),
        ("BS/2", "Bs/3", 205.0, "southern link route heading towards the field gate"),
        ("Forensic laboratory (Old Location)", "Vice chancellors office", 120.0, "administration avenue corridor link"),
        ("Main Gate Junction", "Forensic laboratory (Old Location)", 95.5, "main access entry road path segment")
    ]

    print("Connecting your physical walking path networks...")
    for node_from, node_to, dist, hint in campus_edges:
        cursor.execute('''
            INSERT INTO edges (node_from, node_to, distance_meters, direction_hint)
            VALUES (?, ?, ?, ?)
        ''', (node_from, node_to, dist, hint))

    conn.commit()
    conn.close()
    print("🚀 All custom campus nodes successfully updated in your Spatial Matrix Database!")

if __name__ == '__main__':
    seed_map_data()