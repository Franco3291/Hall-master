import sqlite3
import csv
import os

def import_campus_data():
    db_path = 'campus_navigation.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("⏳ Clearing old prototype map layers...")
    cursor.execute("DELETE FROM edges")
    cursor.execute("DELETE FROM nodes")
    
    # 1. Import Nodes
    if os.path.exists('nodes.csv'):
        with open('nodes.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if not row.get('name'): continue
                cursor.execute('''
                    INSERT INTO nodes (name, floor, description, lat, lng, occupancy_status, last_verified)
                    VALUES (?, ?, ?, ?, ?, 'UNVERIFIED', 'Never')
                ''', (row['name'], int(row['floor'] or 1), row['description'], float(row.get('lat', 0)), float(row.get('lng', 0))))
        print("✅ Nodes table updated successfully!")
    else:
        print("❌ Error: nodes.csv not found.")

    # 2. Import Edges
    if os.path.exists('edges.csv'):
        with open('edges.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if not row.get('node_from'): continue
                cursor.execute('''
                    INSERT INTO edges (node_from, node_to, distance_meters)
                    VALUES (?, ?, ?)
                ''', (row['node_from'], row['node_to'], float(row['distance_meters'])))
        print("✅ Edges table updated successfully!")
    else:
        print("❌ Error: edges.csv not found.")
        
    conn.commit()
    conn.close()
    print("🎉 System Database updated!")

if __name__ == "__main__":
    import_campus_data()