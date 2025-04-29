import sqlite3
import os 
import openai 
import uuid
import json 
from datetime import datetime
from app.utils import call_chatgpt_api_all_chats

DATABASE_PATH = "data/wellness_database.db"
openai.api_key = os.environ.get("SECRET_KEY")


def generate_followup_message(messages):
    """Given a set of messages, create a dictionary with recommended followups
    
    Arguments:
        messages: List of dictionaries with sender and text keys
        
    Returns: Dictionary, with two keys: follow_up_message and follow_up date"""

    all_message_list = [{'role': 'system', 'content': 'You are a Co-Pilot tool for {}, \ a peer-peer mental health organization. Please provider 1) A followup message (if applicable) and a followup date (if applicabe). Do this in a JSON format: {"follow_up_message": "Hello", "follow_up_date": "2024-01-31"}'}]
    prior_messages = []
    for m in messages:
        prior_messages.append({'role': m['sender'],'content': m['text']})
    all_message_list += prior_messages
    response = call_chatgpt_api_all_chats(all_message_list,max_tokens=750,stream=False,response_format={"type": "json_object"})
    return json.loads(response)

def load_messages_for_conversation(conversation_id):
    """Loads all messages for a given conversation_id in chronological order.

    Arguments:
        conversation_id: String, conversation_id 
    
    Returns: List of dictionaries with sender, text, and created_at

    """
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT sender, text, created_at FROM messages
        WHERE conversation_id = ?
        ORDER BY created_at ASC
    ''', (conversation_id,))

    messages = cursor.fetchall()
    conn.close()
    return [{"sender": sender, "text": text, "created_at": created_at} for sender, text, created_at in messages]



def autogenerate_conversations(username):
    """Find all conversations without corresponding outreach generated
    
    Arguments:
        username: string, provider's usernaem
    
    Returns: Nothing
    
    Side Effects: Writes new outreach events to the calendar"""

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id FROM conversations
        WHERE username = ? AND outreach_generated = 0
    ''', (username,))
    conversation_ids = cursor.fetchall()

    for conv_id in conversation_ids:
        conv_id = conv_id[0]
        messages = load_messages_for_conversation(conv_id)
        followup = generate_followup_message(messages)
        service_user_name = f"User-{uuid.uuid4().hex[:8]}"
        if followup['follow_up_date'] and followup['follow_up_message']:
            cursor.execute('''
                INSERT OR IGNORE INTO profiles (service_user_id, service_user_name, provider, location, status)
                VALUES (?, ?, ?, ?, ?)
            ''', (username, service_user_name, username, "Freehold, NJ", "Active"))
            today_str = datetime.now().strftime("%Y-%m-%d")
            cursor.execute('''
                INSERT INTO outreach_details (user_name, last_session, check_in, follow_up_message)
                VALUES (?, ?, ?, ?)
            ''', (
                service_user_name,
                today_str,
                followup['follow_up_date'],  # This will insert NULL if it's None
                followup['follow_up_message']
            ))

        cursor.execute('''
            UPDATE conversations
            SET outreach_generated = 1
            WHERE id = ?
        ''', (conv_id,))

    conn.commit()
    conn.close()