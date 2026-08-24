"""A minimal Telegram bot with three-turn memory."""

import os

import requests
from dotenv import load_dotenv

from processQuery import process_query


load_dotenv()

MEMORY_TURNS = 3
ROUTE_LABELS = {
    "DIRECT": "Direct answer",
    "CODE_REQUIRED": "Python code",
    "WEBSCRAPE": "Website reader",
    "COMMAND": "Bot command",
}


def add_memory(text, history):
    """Put earlier messages before the new message sent to the AI."""
    if not history:
        return text

    earlier_messages = "\n".join(
        f"User: {user}\nAssistant: {bot}"
        for user, bot in history
    )
    return f"Previous conversation:\n{earlier_messages}\n\nNew message:\n{text}"


def run_bot(token=None):
    """Read Telegram messages, answer them, and remember each chat."""
    token = token or os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing from .env")

    url = f"https://api.telegram.org/bot{token}"
    memory = {}
    offset = 0

    print("Bot started - press Ctrl+C to stop")

    while True:
        response = requests.get(
            f"{url}/getUpdates",
            params={"timeout": 100, "offset": offset},
            timeout=105,
        )
        response.raise_for_status()
        updates = response.json()["result"]

        for update in updates:
            offset = update["update_id"] + 1
            message = update.get("message")

            # Ignore photos, stickers, and other updates without text.
            if not message or not message.get("text"):
                continue

            chat_id = message["chat"]["id"]
            text = message["text"]
            command = text.strip().lower()

            if command == "/start":
                answer = "Hello! Send me a question."
                route = "COMMAND"
            elif command == "/reset":
                memory.pop(chat_id, None)
                answer = "Memory cleared."
                route = "COMMAND"
            else:
                history = memory.get(chat_id, [])
                answer, audit = process_query(add_memory(text, history))
                memory[chat_id] = (history + [(text, answer)])[-MEMORY_TURNS:]
                route = audit[0].get("route", "DIRECT") if audit else "DIRECT"

            label = ROUTE_LABELS.get(route, route)
            reply = f"Routed to: {label}\n\n{answer}"
            print(f"Chat {chat_id} - {label}")

            response = requests.post(
                f"{url}/sendMessage",
                json={"chat_id": chat_id, "text": reply},
                timeout=20,
            )
            response.raise_for_status()


if __name__ == "__main__":
    run_bot()
