import sqlite3

venues=[
 ('10-11',1,'Lecture room 10-11',-1.2921,36.8219),
 ('Main Hall',1,'Main lecture hall',-1.2925,36.8220),
 ('PHIL 210 TC 11',2,'Philosophy building room 210',-1.2930,36.8225),
 ('ECON 443 STB 1',3,'Economics block 443',-1.2935,36.8230)
]

conn=sqlite3.connect('campus_navigation.db')
cur=conn.cursor()
for name,floor,desc,lat,lng in venues:
    cur.execute("SELECT 1 FROM nodes WHERE name=?",(name,))
    if cur.fetchone():
        print('exists',name)
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
