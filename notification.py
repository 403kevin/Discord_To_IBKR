import logging
import requests
from config import TELEGRAM_ENABLED, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

def send_telegram_message(text: str):
    """
    Send a text message via Telegram bot.
    """
    if not TELEGRAM_ENABLED:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    }
    try:
        resp = requests.post(url, data=payload, timeout=5)
        if not resp.ok:
            logging.error(f"[Telegram] HTTP {resp.status_code}: {resp.text}")
    except Exception as e:
        logging.error(f"[Telegram] send failed: {e}")