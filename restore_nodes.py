import sqlite3

# These venues are from the timetable - using Tharaka University coordinates
# consistent with seed_campus_map.py (BS/2 center point: -0.092969, 37.989887)
venues=[
 ('10-11',1,'Lecture room 10-11',-0.091500,37.988500),
 ('Main Hall',1,'Main lecture hall',-0.092000,37.989000),
 ('PHIL 210 TC 11',2,'Philosophy building room 210',-0.092300,37.989800),
 ('ECON 443 STB 1',3,'Economics block 443',-0.090800,37.989200)
]

conn=sqlite3.connect('campus_navigation.db')
cur=conn.cursor()
for name,floor,desc,lat,lng in venues:
    cur.execute("SELECT 1 FROM nodes WHERE name=?",(name,))
    if cur.fetchone():
        # Update coordinates if node exists
        cur.execute("UPDATE nodes SET lat=?, lng=?, description=? WHERE name=?", (lat, lng, desc, name))
        print('updated',name)
    else:
        cur.execute('''INSERT INTO nodes (name,floor,description,lat,lng,occupancy_status,last_verified) VALUES (?,?,?,?,?,'UNVERIFIED','Never')''',(name,floor,desc,lat,lng))
        print('inserted',name)
conn.commit()
# Show results
rows=cur.execute("SELECT name,lat,lng,occupancy_status FROM nodes").fetchall()
print('--- nodes ---')
for r in rows:
    print(r)
conn.close()