import sqlite3
import csv
from pathlib import Path

DATABASE_PATH = "data/wellness_database.db"

def init_database():
    """Initialize all the tables in database
     
    Arguments: None
     
    Returns: None
    
    Side Effects: Initialize all the databases"""

    Path("data").mkdir(exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        role TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        service_user_id TEXT UNIQUE NOT NULL,
        service_user_name TEXT NOT NULL,
        provider TEXT NOT NULL,
        location TEXT,
        status TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS outreach_details (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_name TEXT NOT NULL,
        last_session TEXT,
        check_in TEXT,
        follow_up_message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_name) REFERENCES profiles(service_user_id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS conversations (
        id TEXT PRIMARY KEY,
        username TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id TEXT NOT NULL,
        sender TEXT NOT NULL,
        text TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (conversation_id) REFERENCES conversations(id),
        outreach_generated BOOLEAN,
        UNIQUE(conversation_id, sender, text)
    )
    ''')
    
    conn.commit()
    conn.close()

def migrate_data_from_csv():
    """Transfer all the data from the CSV into databases
    
    Arguments: None
    
    Returns: None
    
    Side Effects: Loops through CSV and adds the data into database"""

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    try:
        with open("data/profiles.csv", 'r') as f:
            reader = csv.DictReader(f, skipinitialspace=True)
            for row in reader:
                cursor.execute('''
                INSERT OR IGNORE INTO profiles 
                (service_user_id, service_user_name, provider, location, status)
                VALUES (?, ?, ?, ?, ?)
                ''', (row['service_user_id'], row['service_user_name'], 
                      row['provider'], row.get('location', ''), row.get('status', 'Active')))
    except FileNotFoundError:
        print("profiles.csv not found, skipping migration")
    
    try:
        with open("data/outreach_details.csv", 'r') as f:
            reader = csv.DictReader(f, skipinitialspace=True)
            for row in reader:
                cursor.execute('''
                INSERT OR IGNORE INTO outreach_details
                (user_name, last_session, check_in, follow_up_message)
                VALUES (?, ?, ?, ?)
                ''', (row['user_name'], row['last_session'], 
                      row['check_in'], row['follow_up_message']))
    except FileNotFoundError:
        print("outreach_details.csv not found, skipping migration")
    
    conn.commit()
    conn.close()

def update_conversation(metadata, previous_text):
    """
    Update the information in the conversations database
        Based on a new message

    Arguments:
        metadata: Dictionary with username and conversation_id
        previous_text: List of dictionaries with sender and text
    
    Returns: None

    Side Effects: Writes the text in previous_text to the database
    """
    username = metadata.get("username")
    conversation_id = metadata.get("conversation_id")

    if username == "" or conversation_id == "":
        return

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM conversations WHERE id = ?", (conversation_id,))
    if cursor.fetchone() is None:
        cursor.execute(
            "INSERT INTO conversations (id, username,outreach_generated) VALUES (?, ?, ?)",
            (conversation_id, username,False)
        )

    for msg in previous_text:
        sender = msg["role"]
        text = msg["content"]
        if sender and text:
            cursor.execute(
                "INSERT OR IGNORE INTO messages (conversation_id, sender, text) VALUES (?, ?, ?)",
                (conversation_id, sender, text)
            )

    conn.commit()
    conn.close()

def add_new_wellness_checkin(provider_username, patient_name, last_session, next_checkin, followup_message):
    """Create a new entry for a new provider-service user combo, along with a followup message
    
    Arguments:
        provider_username: string, username of the peer provider
        patient_name: string, username of the service user
        last_session: string, date of the last session
        next_checkin: string, date for the next recommended checkin
        followup_message: string, suggested message to send the 
            service user"""
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    try:
        service_user_id = patient_name.lower().replace(" ", "_")
        cursor.execute('''
        SELECT service_user_id FROM profiles WHERE service_user_id = ?
        ''', (service_user_id,))
        
        if not cursor.fetchone():
            cursor.execute('''
            INSERT INTO profiles (service_user_id, service_user_name, provider, location, status)
            VALUES (?, ?, ?, ?, ?)
            ''', (service_user_id, patient_name, provider_username, "Freehold, New Jersey", "Active"))
        
        cursor.execute('''
        INSERT OR REPLACE INTO outreach_details 
        (user_name, last_session, check_in, follow_up_message)
        VALUES (?, ?, ?, ?)
        ''', (service_user_id, last_session, next_checkin, followup_message))
        conn.commit()
        conn.close()
    except Exception as e:
        conn.rollback()
        conn.close()


