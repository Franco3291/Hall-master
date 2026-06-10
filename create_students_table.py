import sqlite3
conn = sqlite3.connect('campus_navigation.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS students (
        reg_no TEXT PRIMARY KEY,
        password TEXT NOT NULL,
        course TEXT NOT NULL,
        year INTEGER NOT NULL,
        semester INTEGER NOT NULL,
        units TEXT NOT NULL
    )
''')
conn.commit()
conn.close()
print("Students table created successfully!")