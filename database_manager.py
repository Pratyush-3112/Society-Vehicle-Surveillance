"""
Database Manager for Parking System

This module handles all database operations for a residential parking management system.
It uses SQLite3 for data storage and manages residents, parking logs, and violations.

SQLite3 is a lightweight, file-based database that doesn't require a separate server.
It's perfect for small to medium applications and stores all data in a single file.

Datetime module is used for handling timestamps when logging entries, exits, and violations.
"""

import sqlite3
from datetime import datetime

DB_NAME = "parking.db"

# ─────────────────────────────────────────
# SETUP
# ─────────────────────────────────────────

def create_tables():
    """
    Creates the necessary database tables if they don't already exist.
    
    Tables:
    - Residents: Stores information about registered residents and their vehicles
    - Log: Tracks vehicle entries, exits, and parking status
    - Violations: Records parking violations with timestamps
    """
    conn = sqlite3.connect(DB_NAME)  # Connect to the SQLite database file
    cursor = conn.cursor()  # Create a cursor to execute SQL commands

    # Create Residents table
    # PRIMARY KEY ensures each plate_number is unique
    # TEXT is SQLite's string type, NOT NULL means required field
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Residents (
            plate_number TEXT PRIMARY KEY,
            owner_name   TEXT NOT NULL,
            email        TEXT NOT NULL,
            flat_number  TEXT NOT NULL,
            vehicle_type TEXT NOT NULL
        )
    """)

    # Create Log table
    # INTEGER PRIMARY KEY AUTOINCREMENT creates auto-incrementing IDs
    # timestamp_out can be NULL for vehicles still inside
    # status tracks whether vehicle is entering, parked, or exited
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Log (
            log_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            plate_number TEXT NOT NULL,
            timestamp_in TEXT NOT NULL,
            timestamp_out TEXT,
            status       TEXT DEFAULT 'In-Transit'
        )
    """)

    # Create Violations table
    # Tracks violations like unauthorized parking, speeding, etc.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Violations (
            violation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate_number TEXT NOT NULL,
            type         TEXT NOT NULL,
            timestamp    TEXT NOT NULL,
            count        INTEGER DEFAULT 1
        )
    """)

    conn.commit()  # Save all changes to the database
    conn.close()   # Close the connection
    print("Tables created successfully.")


# ─────────────────────────────────────────
# RESIDENTS
# ─────────────────────────────────────────

def add_resident(plate_number, owner_name, email, flat_number, vehicle_type):
    """
    Adds or updates a resident in the database.
    Uses INSERT OR REPLACE to update existing residents or add new ones.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # INSERT OR REPLACE will update if plate_number exists, or insert if new
    # ? are placeholders to prevent SQL injection attacks
    cursor.execute("""
        INSERT OR REPLACE INTO Residents 
        (plate_number, owner_name, email, flat_number, vehicle_type)
        VALUES (?, ?, ?, ?, ?)
    """, (plate_number, owner_name, email, flat_number, vehicle_type))

    conn.commit()
    conn.close()
    print(f"Resident {owner_name} added.")


def get_resident(plate_number):
    """
    Retrieves resident information by plate number.
    Returns a tuple (plate_number, owner_name, email, flat_number, vehicle_type) or None if not found.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # SELECT * gets all columns for the matching plate_number
    cursor.execute("""
        SELECT * FROM Residents WHERE plate_number = ?
    """, (plate_number,))

    row = cursor.fetchone()  # fetchone() returns one row or None
    conn.close()
    return row   # Returns None if plate not found (i.e. not a resident)


# ─────────────────────────────────────────
# LOG  (entry / exit / parking status)
# ─────────────────────────────────────────

def log_entry(plate_number):
    """
    Logs when a vehicle enters the parking area.
    Creates a new log entry with current timestamp.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # datetime.now() gets current date/time, strftime formats it as string
    # Format: "2023-12-25 14:30:45"
    timestamp_in = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO Log (plate_number, timestamp_in, status)
        VALUES (?, ?, 'In-Transit')
    """, (plate_number, timestamp_in))

    conn.commit()
    conn.close()
    print(f"Entry logged for {plate_number} at {timestamp_in}")


def log_exit(plate_number):
    """
    Logs when a vehicle exits the parking area.
    Updates the most recent open entry for this plate with exit timestamp.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    timestamp_out = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Update the most recent open log entry (timestamp_out IS NULL)
    # ORDER BY log_id DESC ensures we get the latest entry
    # LIMIT 1 ensures only one row is updated
    cursor.execute("""
        UPDATE Log
        SET timestamp_out = ?, status = 'Exited'
        WHERE log_id = (
            SELECT log_id
            FROM Log
            WHERE plate_number = ?
            AND timestamp_out IS NULL
            ORDER BY log_id DESC
            LIMIT 1
        )
    """, (timestamp_out, plate_number))

    conn.commit()
    conn.close()
    print(f"Exit logged for {plate_number} at {timestamp_out}")


def mark_parked():
    """
    Updates status to 'Parked' for vehicles that have been inside for more than 10 minutes.
    This function should be called periodically (e.g., every minute) to update parking status.
    
    Uses SQLite's strftime function to calculate time difference in seconds.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # strftime('%s', 'now') converts current time to Unix timestamp (seconds since 1970)
    # Same for timestamp_in, then subtract to get seconds parked
    # 600 seconds = 10 minutes
    cursor.execute("""
        UPDATE Log
        SET status = 'Parked'
        WHERE status = 'In-Transit'
        AND timestamp_out IS NULL
        AND (strftime('%s', 'now') - strftime('%s', timestamp_in)) > 600
    """)

    conn.commit()
    conn.close()


def get_parked_count():
    """
    Returns the number of vehicles currently parked (status = 'Parked').
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*) FROM Log WHERE status = 'Parked'
    """)

    count = cursor.fetchone()[0]  # fetchone() returns a tuple, [0] gets the count
    conn.close()
    return count


# ─────────────────────────────────────────
# VIOLATIONS
# ─────────────────────────────────────────

def add_violation(plate_number, violation_type):
    """
    Records a parking violation for a vehicle.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO Violations (plate_number, type, timestamp)
        VALUES (?, ?, ?)
    """, (plate_number, violation_type, timestamp))

    conn.commit()
    conn.close()
    print(f"Violation logged: {violation_type} for {plate_number}")


def get_violation_count(plate_number):
    """
    Returns the total number of violations for a specific plate number.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*) FROM Violations WHERE plate_number = ?
    """, (plate_number,))

    count = cursor.fetchone()[0]
    conn.close()
    return count


def get_recent_violations(limit=10):
    """
    Returns the most recent violations, ordered by newest first.
    Default limit is 10, but can be changed.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # ORDER BY violation_id DESC gets newest first (higher IDs are more recent)
    # LIMIT restricts the number of results
    cursor.execute("""
        SELECT * FROM Violations ORDER BY violation_id DESC LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()  # fetchall() returns a list of tuples
    conn.close()
    return rows


# ─────────────────────────────────────────
# TEST — run: python database_manager.py
# ─────────────────────────────────────────

if __name__ == "__main__":
    # This block only runs when the file is executed directly (not imported)
    create_tables()

    # Test resident functions
    add_resident("KA01AB1234", "Ravi Kumar", "ravi@gmail.com", "A-101", "Car")
    print("Resident lookup:", get_resident("KA01AB1234"))
    print("Unknown plate:  ", get_resident("XX00XX0000"))  # Should print None

    # Test log functions
    log_entry("KA01AB1234")
    log_exit("KA01AB1234")
    print("Parked count:", get_parked_count())

    # Test violations functions
    add_violation("KA01AB1234", "Speeding")
    add_violation("KA01AB1234", "Wrong-Way")
    print("Violation count:", get_violation_count("KA01AB1234"))  # Should print 2
    print("Recent violations:", get_recent_violations())