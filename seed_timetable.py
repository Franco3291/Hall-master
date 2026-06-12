import sqlite3
from datetime import datetime

def seed_timetable_with_today():
    """Insert sample timetable data with classes for TODAY"""
    conn = sqlite3.connect('campus_navigation.db')
    cursor = conn.cursor()
    
    # Clear existing timetable
    cursor.execute("DELETE FROM timetable")
    
    # Get current day name
    today = datetime.now().strftime('%A')
    
    # Sample classes - include today's day with various times
    classes = [
        # Today's classes with spread times
        ('COSC 101', 'Introduction to Programming', today, '10:00', '11:00', '10-11'),
        ('BCS 201', 'Data Structures', today, '11:30', '12:30', 'Main Hall'),
        ('MATH 110', 'Calculus I', today, '13:00', '14:00', 'PHIL 210 TC 11'),
        ('PHYS 150', 'Physics for Engineers', today, '14:30', '16:00', 'ECON 443 STB 1'),
        ('ENG 101', 'English Composition', today, '16:00', '17:00', 'Main Hall'),
        
        # Regular weekday classes
        ('COSC 101', 'Introduction to Programming', 'Monday', '08:00', '09:00', '10-11'),
        ('BCS 201', 'Data Structures', 'Tuesday', '10:00', '11:00', 'Main Hall'),
        ('MATH 110', 'Calculus I', 'Monday', '13:00', '14:00', 'PHIL 210 TC 11'),
        ('PHYS 150', 'Physics for Engineers', 'Thursday', '10:00', '12:00', 'ECON 443 STB 1'),
        ('ENG 101', 'English Composition', 'Monday', '14:00', '15:00', 'Main Hall'),
    ]
    
    for course_code, course_name, day, start_time, end_time, venue in classes:
        cursor.execute('''
            INSERT INTO timetable (course_code, course_name, day_of_week, start_time, end_time, venue)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (course_code, course_name, day, start_time, end_time, venue))
    
    conn.commit()
    
    # Show what was inserted
    cursor.execute("SELECT COUNT(*) FROM timetable")
    count = cursor.fetchone()[0]
    
    cursor.execute(f"SELECT * FROM timetable WHERE day_of_week = '{today}'")
    todays_classes = cursor.fetchall()
    
    conn.close()
    
    print(f"✅ Timetable seeded with {count} classes!")
    print(f"📅 Today ({today}) has {len(todays_classes)} classes:")
    for cls in todays_classes:
        print(f"   - {cls[1]} ({cls[2]}) from {cls[4]} to {cls[5]} in {cls[6]}")

if __name__ == "__main__":
    seed_timetable_with_today()
