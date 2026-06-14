import sqlite3
import os
import pytesseract
from PIL import Image

def parse_image_timetable(image_path):
    # Requires Tesseract-OCR installed on your OS
    text = pytesseract.image_to_string(Image.open(image_path))
    
    conn = sqlite3.connect('campus_navigation.db')
    cursor = conn.cursor()
    
    # Simplified example: Looking for course codes in the OCR text
    # You would use regex here to find times and venues
    print("Extracted Text Sample:", text[:100])
    
    # Logic for inserting into 'timetable' table goes here...
    conn.close()

if __name__ == "__main__":
    parse_image_timetable("static/uploads/timetable_photo.jpg")