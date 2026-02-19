"""Notification helpers for sending email reminders to providers.

Contains small wrappers around the Mailgun HTTP API and a scheduled
job to email providers with today's check-ins.
"""

import os
import requests
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from app.database import fetch_provider_checkins_by_date, fetch_providers_to_notify_checkins
 

def send_test_message(recipient="Olivia Cheng <ogc@andrew.cmu.edu>"):
    """Send a basic test email via Mailgun (used in development)."""
    response = requests.post(
        "https://api.mailgun.net/v3/peercopilot.com/messages",
  		auth=("api", os.getenv('MAILGUN_SENDING_KEY')),
        data={
            "from": "Test <postmaster@peercopilot.com>",
            "to": recipient,
            "subject": "Hello!",
            "text": "Test message"
        }
    )
    print(f"Status: {response.status_code}")
    
def send_message_from_peercopilot(recipient, subject, text):
    """Send a message via Mailgun using the PeerCopilot sender identity.

    Returns the `requests.Response` object for inspection by callers.
    """
    response = requests.post(
        "https://api.mailgun.net/v3/peercopilot.com/messages",
        auth=("api", os.getenv("MAILGUN_SENDING_KEY")),
        data={
            "from": "PeerCopilot <postmaster@peercopilot.com>",
            "to": recipient,
            "subject": subject,
            "text": text
        }
    )
    if response.status_code >= 400:
        print(f"[Mailgun] Send failed to {recipient}: {response.status_code} - {response.text}")
    else:
        print(f"[Mailgun] Sent to {recipient}: {response.status_code}")
    return response

def send_daily_check_ins(todays_checkins_for_provider, service_provider_email):
    opening = "Hello from PeerCopilot! \nHere is a reminder for today's check-ins: \n\n"
    body = "\n".join([f"- {d['service_user_name']}: {d['follow_up_message']}" for d in todays_checkins_for_provider])
    closing = "\n ---- \n"
    full_text = opening + body + closing
    subject = f"{date.today()} Check-In Reminders"
    response = send_message_from_peercopilot(service_provider_email, subject, full_text)
    return response

def notification_job():
    """Job run by scheduler to email providers their check-ins for the day.

    This function is scheduled periodically (e.g., every 15 minutes) and will
    send emails to providers whose notification_time falls within the current
    window (with a short tolerance).
    """
    print("Starting notification job...")
    eastern = ZoneInfo("America/New_York")
    current_time = datetime.now(eastern).replace(microsecond=0)
    tolerance = timedelta(minutes=15)
    success, providers = fetch_providers_to_notify_checkins(current_time.time(), (current_time + tolerance).time())
    count_sent = 0
    if not success:
        print(f"Error fetching providers: {providers}")
        return
    for p in providers:
        success, todays_checkins = fetch_provider_checkins_by_date(p["username"], date.today())
        if success and len(todays_checkins) > 0:
            resp = send_daily_check_ins(todays_checkins, p["email"])
            if resp is not None and getattr(resp, "status_code", 0) < 400:
                count_sent += 1
            else:
                print(f"[Notification Job] Failed to send to {p['email']}")
    print(f"Notification job finished and {count_sent} messages sent...")
    

