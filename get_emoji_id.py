"""
Find Telegram custom emoji document IDs.

Usage:
  1. python3 get_emoji_id.py
  2. Send yourself (Saved Messages) a message with the custom emoji you want
  3. Copy the printed document_id into main.py REPLY_TEXT
"""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.tl.types import MessageEntityCustomEmoji

BASE_DIR = Path(__file__).resolve().parent


def load_config() -> tuple[int, str, str]:
    load_dotenv(BASE_DIR / ".env")
    api_id = int(os.getenv("API_ID", "").strip())
    api_hash = os.getenv("API_HASH", "").strip()
    session_name = os.getenv("SESSION_NAME", "sameer_session").strip()
    return api_id, api_hash, session_name


async def main() -> None:
    api_id, api_hash, session_name = load_config()
    client = TelegramClient(str(BASE_DIR / session_name), api_id, api_hash)

    @client.on(events.NewMessage(incoming=True, outgoing=True))
    async def on_message(event: events.NewMessage.Event) -> None:
        if not event.message.entities:
            return

        found = False
        for entity in event.message.entities:
            if isinstance(entity, MessageEntityCustomEmoji):
                found = True
                snippet = event.message.text[
                    entity.offset : entity.offset + entity.length
                ]
                print("\n--- Custom Emoji Found ---")
                print(f"document_id: {entity.document_id}")
                print(f"text snippet: {snippet!r}")
                print(
                    f'HTML: <tg-emoji emoji-id="{entity.document_id}">{snippet}</tg-emoji>'
                )
                print("--------------------------\n")

        if found:
            print("Copy the document_id into main.py REPLY_TEXT and restart the bot.")

    await client.start()
    me = await client.get_me()
    print(f"Logged in as {me.first_name}.")
    print("Send a message with custom emoji (Saved Messages works too).")
    print("Press Ctrl+C to stop.\n")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
