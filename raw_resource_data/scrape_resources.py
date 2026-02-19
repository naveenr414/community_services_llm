import openai
from utils import call_chatgpt_api, BASE_DIR
from googlesearch import search
import requests
from bs4 import BeautifulSoup
import cloudscraper
import os
import pandas as pd
import argparse
import time
import concurrent.futures
from threading import Lock

openai.api_key = os.environ.get("SECRET_KEY")

parser = argparse.ArgumentParser()
parser.add_argument('--location', '-l', help='location', type=str, default="New Jersey")
parser.add_argument('--org_name', '-o', help='organization', type=str, default="cspnj")
args = parser.parse_args()
location = args.location
org_name = args.org_name

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'
}
scraper = cloudscraper.create_scraper()
lock = Lock()
csv_path = f"C:/Users/KARAN/Desktop/AISOC/community_services_llm/community_services_llm/backend/data/{org_name}.csv"

def get_text_from_url(url):
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code != 200:
            response = scraper.get(url, timeout=5)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            return soup.get_text(separator='\n', strip=True)[:100000]
    except Exception:
        pass
    return "Error"

def retry_gpt(prompt, content, max_retries=20):
    for attempt in range(max_retries):
        try:
            return call_chatgpt_api(prompt, content, stream=False)
        except Exception as e:
            print(f"Retrying GPT... attempt {attempt+1}/20 due to error: {e}")
            time.sleep(2 * (attempt + 1))
    return ""

def process_entry(name):
    print(f"Processing: {name}")
    row = {
        'service': name,
        'description': '',
        'url': '',
        'phone': '',
        'url_phone': '',
        'address': '',
        'action': ''
    }

    # Phone
    try:
        phone_url = next(search(f"{name} Phone Number {location}", num=1, stop=1))
        phone_text = get_text_from_url(phone_url)
        if phone_text != "Error":
            row['phone'] = retry_gpt(
                "You are a helpful assistant. Return only the phone number (no dashes/spaces), else return an empty string.",
                f"Extract the phone number from this text: {phone_text}"
            )
            row['url_phone'] = phone_url
    except Exception as e:
        print(f"Phone search error for {name}: {e}")

    # Description, Address, Action
    try:
        desc_url = next(search(f"{name} {location}", num=1, stop=1))
        desc_text = get_text_from_url(desc_url)
        if desc_text != "Error":
            row['description'] = retry_gpt(
                "You are a helpful assistant. Summarize the resource. Mention location, hours, and any requirements. Return only the summary.",
                f"Summarize this website: {desc_text}"
            )
            row['address'] = retry_gpt(
                "You are a helpful assistant. Extract the full physical address from the following website text. Return only the address or an empty string.",
                f"Extract the address: {desc_text}"
            )
            row['action'] = retry_gpt(
                "You are a helpful assistant. Suggest a single clear next action a user can take for the resource below. Return only the action.",
                f"What is one actionable step a person should take for this resource: {desc_text}"
            )
            row['url'] = desc_url
    except Exception as e:
        print(f"Desc/address/action error for {name}: {e}")

    # Save row immediately with thread-safe lock
    with lock:
        df = pd.DataFrame([row])
        if not os.path.exists(csv_path):
            df.to_csv(csv_path, index=False)
        else:
            df.to_csv(csv_path, mode='a', header=False, index=False)

    return row

if __name__ == "__main__":
    all_entries = open(BASE_DIR / "data/{org_name}_resources.txt", "r").read().strip().split("\n")
    print(f"There are {len(all_entries)} entries")

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        executor.map(process_entry, all_entries)
