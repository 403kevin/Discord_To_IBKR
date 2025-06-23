import logging
import requests
from config import TELEGRAM_ENABLED, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

def send_telegram_message(text: str):
    """
    Send a text message via Telegram bot.
    """
    # Abort if notifications are disabled or config is incomplete
    if not TELEGRAM_ENABLED or not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        resp = requests.post(url, data=payload, timeout=5)
        resp.raise_for_status()
        logging.debug(f"[Telegram] Message sent successfully.")
    except requests.RequestException as e:
        logging.error(f"[Telegram] HTTP error: {e.response.status_code} – {e.response.text}")
    except Exception as e:
        logging.error(f"[Telegram] Send failed: {e}")
