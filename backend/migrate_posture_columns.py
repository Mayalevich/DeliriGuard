#!/usr/bin/env python3
"""
Migration script to add posture columns to processed_samples table
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "sleep_data.db"

def migrate():
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        print("Database will be created automatically on first run.")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(processed_samples)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'posture' in columns and 'posture_confidence' in columns:
            print("✓ Posture columns already exist. No migration needed.")
            return
        
        print("Adding posture columns to processed_samples table...")
        
        # Add posture column if it doesn't exist
        if 'posture' not in columns:
            cursor.execute("ALTER TABLE processed_samples ADD COLUMN posture TEXT")
            print("  ✓ Added 'posture' column")
        
        # Add posture_confidence column if it doesn't exist
        if 'posture_confidence' not in columns:
            cursor.execute("ALTER TABLE processed_samples ADD COLUMN posture_confidence REAL")
            print("  ✓ Added 'posture_confidence' column")
        
        conn.commit()
        print("✓ Migration completed successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"✗ Migration failed: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()

