# Telegram Personal Auto-Reply Userbot

A Python userbot built with [Telethon](https://docs.telethon.dev/) that runs on your **personal Telegram account** (not Bot API). When someone sends you a private DM for the first time, it automatically replies once with a text message and a video.

## Features

- Runs on your personal Telegram account via Telethon session
- Auto-replies only in **private DMs** (not groups or channels)
- Replies **once per user** — never spams the same person again
- Persists replied user IDs in `replied_users.json` (survives VPS restarts)
- Ignores messages from bots and your own outgoing messages
- Sends video first, then text message after 1 second
- Basic error handling and logging

## Project Structure

```
.
├── main.py              # Main userbot script
├── .env                 # Your secrets (create from .env.example)
├── .env.example         # Template for environment variables
├── requirements.txt     # Python dependencies
├── replied_users.json   # Tracks users who already got a reply
├── video.mp4            # Video sent in auto-reply (you provide this)
└── sameer_session.session  # Created automatically on first login
```

## Prerequisites

1. **API credentials** from [my.telegram.org](https://my.telegram.org):
   - Log in with your phone number
   - Go to **API development tools**
   - Create an app and copy `api_id` and `api_hash`

2. **video.mp4** — place your video file in the project root

## Local Setup

```bash
# Clone or upload the project to your machine
cd "USER TELEGRAM BOT"

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and fill in API_ID and API_HASH

# Run the userbot (first run will ask for phone + OTP)
python3 main.py
```

On first run, Telethon will prompt you to:

1. Enter your phone number (with country code, e.g. `+91XXXXXXXXXX`)
2. Enter the OTP sent to Telegram
3. Enter your 2FA password (if enabled)

A session file (`sameer_session.session`) is saved locally so you won't need to log in again.

## VPS Setup (Ubuntu/Debian)

SSH into your VPS and run:

```bash
# Update system and install Python
sudo apt update
sudo apt install python3 python3-pip python3-venv -y

# Upload project files (scp, git, etc.) then:
cd /path/to/USER\ TELEGRAM\ BOT

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure .env
cp .env.example .env
nano .env   # Add API_ID, API_HASH, SESSION_NAME

# Add video.mp4 to the project folder

# First run — complete Telegram login
python3 main.py
```

## Keep Running with `screen`

Use `screen` so the bot keeps running after you disconnect from SSH:

```bash
# Start a named screen session
screen -S telegram_auto_reply

# Inside screen:
cd /path/to/USER\ TELEGRAM\ BOT
source venv/bin/activate
python3 main.py

# Detach (bot keeps running): Ctrl+A, then D

# Reattach later:
screen -r telegram_auto_reply

# List all screen sessions:
screen -ls
```

## Environment Variables

| Variable       | Description                          |
|----------------|--------------------------------------|
| `API_ID`       | Your Telegram API ID (number)        |
| `API_HASH`     | Your Telegram API hash (string)      |
| `SESSION_NAME` | Session file name (default: `sameer_session`) |

## How It Works

1. The script connects using your saved Telethon session.
2. It listens for **incoming private messages**.
3. For each new sender:
   - Skips if they're a bot, if the message is outgoing, or if they're already in `replied_users.json`
   - Sends `video.mp4` immediately
   - Waits 1 second
   - Sends the configured text message
   - Saves the user ID to `replied_users.json`

## Security Notes

- **Never commit `.env` or `*.session` files** — they contain secrets and login tokens
- Keep your VPS updated and restrict SSH access
- Using userbots may violate Telegram's Terms of Service; use at your own risk

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `API_ID and API_HASH must be set` | Copy `.env.example` to `.env` and fill values |
| `Video file not found` | Add `video.mp4` to the project root |
| Flood wait errors | Telegram rate-limited you; wait and retry |
| Session expired | Delete `*.session` and run again to re-login |

## License

For personal use. Use responsibly.
