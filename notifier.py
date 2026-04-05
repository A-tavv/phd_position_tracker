import logging

import requests


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{token}/sendMessage" if token else ""

    def send_message(self, message: str):
        if not self.token or not self.chat_id:
            logging.warning("Telegram token or chat ID not set. Skipping notification.")
            return

        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "disable_web_page_preview": True,
        }

        try:
            response = requests.post(self.api_url, json=payload, timeout=30)
            response.raise_for_status()
            logging.info("Notification sent successfully.")
        except requests.exceptions.RequestException as exc:
            logging.error("Failed to send Telegram notification: %s", exc)

    def format_job_message(self, job: dict) -> str:
        return (
            "New PhD vacancy found\n\n"
            f"Title: {job['title']}\n"
            f"Location: {job['location']}\n"
            f"Source: {job.get('source', 'Unknown')}\n"
            f"Link: {job['url']}"
        )
