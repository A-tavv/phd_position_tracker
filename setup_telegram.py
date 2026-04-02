import requests
import time
import os

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
URL = f"https://api.telegram.org/bot{TOKEN}/getUpdates"

if not TOKEN:
    raise SystemExit("Set TELEGRAM_BOT_TOKEN in your environment before running this script.")

print("Monitoring for messages to your Telegram bot...")
print("Please send 'Hello' to your bot on Telegram now.")

try:
    # Try once immediately
    r = requests.get(URL).json()
    if r['ok'] and r['result']:
        chat_id = r['result'][0]['message']['chat']['id']
        print(f"\nSUCCESS! Found Chat ID: {chat_id}")
        print("Store this value in TELEGRAM_CHAT_ID for local runs or GitHub Actions.")
        exit(0)
    else:
        print("No messages found yet. Waiting...")

except Exception as e:
    print(f"Error checking updates: {e}")

# If not found immediately, we could loop, but for this tool execution model, 
# it's better to just inform the user to run this script or that we checked and failed.
