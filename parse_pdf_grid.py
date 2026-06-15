import sqlite3
import os

try:
    import pdfplumber
except ImportError:
    print("⏳ Installing pdfplumber library...")
    os.system("pip install pdfplumber")
    import pdfplumber

def parse_and_load_pdf(pdf_path):
    if not os.path.exists(pdf_path):
        current_dir = os.getcwd()
        print(f"DEBUG: Looking in folder: {current_dir}")
        all_files = os.listdir(current_dir)
        pdf_files = [f for f in all_files if f.lower().endswith('.pdf')]
        
        if pdf_files:
            print(f"⚠️ '{pdf_path}' not found, but I found: {pdf_files}")
            pdf_path = pdf_files[0]
            print(f"✅ Auto-switching to use: '{pdf_path}'")
        else:
            print(f"❌ Error: No PDF files found in {current_dir}. Please ensure your timetable is here.")
            return

    print(f"⏳ Opening {pdf_path} and extracting table grids...")
    conn = sqlite3.connect('campus_navigation.db')
    cursor = conn.cursor()

    # Ensure the table exists before attempting to clear it
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS timetable (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_code TEXT, course_name TEXT, 
            day_of_week TEXT, start_time TEXT, 
            end_time TEXT, venue TEXT
        )
    ''')

    # Clear any previous prototype timetable records
    cursor.execute("DELETE FROM timetable")
    
    classes_saved = 0

    with pdfplumber.open(pdf_path) as pdf:
        # Loop through every single page of your university master timetable
        for page_num, page in enumerate(pdf.pages, start=1):
            table = page.extract_table()
            
            if not table:
                continue  # Skip pages without clear structural tables
                
            # Debug: Print the first row of each page to verify column layout
            print(f"📋 Page {page_num} detected columns: {table[0]}")
            print(f"⏳ Processing rows...")
            
            # Loop through rows (skipping the first row if it's just headers like Day/Time)
            for row in table[1:]:
                # Filter out empty rows
                if not row or len(row) < 5:
                    continue
                
                # Adjust these index mappings based on your school's exact column layout:
                # Example assumption: Col 0=Day, Col 1=Time, Col 2=Course, Col 3=Unit Name, Col 4=Venue
                try:
                    day = str(row[0]).strip() if row[0] else "Monday"
                    time_slot = str(row[1]).strip() if row[1] else "08:00-11:00"
                    course_code = str(row[2]).strip() if row[2] else "UNKNOWN"
                    course_name = str(row[3]).strip() if row[3] else "General Lecture"
                    venue = str(row[4]).strip() if row[4] else "Main Hall"

                    # Split time slot (e.g., "08:00-11:00" or "08:00 - 11:00") into start and end
                    if "-" in time_slot:
                        start_time, end_time = time_slot.split("-")
                    else:
                        start_time, end_time = "08:00", "11:00"

                    # Clean up strings
                    start_time = start_time.strip()
                    end_time = end_time.strip()

                    # Insert row directly into your system's timetable architecture
                    cursor.execute('''
                        INSERT INTO timetable (course_code, course_name, day_of_week, start_time, end_time, venue)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (course_code, course_name, day, start_time, end_time, venue))
                    
                    classes_saved += 1
                except Exception as e:
                    # Skip rows that don't match the standard structural format perfectly
                    continue

    conn.commit()
    conn.close()
    print(f"🎉 Success! Extracted and loaded {classes_saved} active class schedules into your system.")

if __name__ == "__main__":
    # Change this name if your actual document file has a different name
    timetable_filename = "timetable.pdf" 
    parse_and_load_pdf(timetable_filename)