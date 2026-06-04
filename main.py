"""
Telegram personal account auto-reply userbot (Telethon).

Replies once per user in private DMs with a video file, then a text message.
"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, RPCError
from telethon.tl.types import DocumentAttributeVideo, TypeDocumentAttribute
from telethon.utils import get_attributes

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
REPLIED_USERS_FILE = BASE_DIR / "replied_users.json"
VIDEO_FILE = BASE_DIR / "video.mp4"

# Custom emoji document IDs (Telegram Premium required to send)
EMOJI_TICK = "5212932275376759608"
EMOJI_DOWN = "5406745015365943482"
EMOJI_FIRE = "6186050278421174022"
EMOJI_ROCKET = "6147654280112248427"
EMOJI_MONEY = "5039789890133296083"
EMOJI_CAMERA = "5235837920081887219"
EMOJI_RED_TICK = "6073204973406000341"
EMOJI_ON_BUTTON = "6111493206690499107"

REGISTER_LINK = (
    "https://u3.shortink.io/register?utm_campaign=841927&utm_source=affiliate"
    "&utm_medium=sr&a=sXY5N4PY66xd77&al=1744620&ac=starting&cid=949169&code=WELCOME50"
)


def _ce(emoji_id: str, fallback: str) -> str:
    """Wrap a fallback character as a Telegram custom emoji."""
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


def build_reply_text() -> str:
    tick = _ce(EMOJI_TICK, "✅")
    down = _ce(EMOJI_DOWN, "⬇️")
    fire = _ce(EMOJI_FIRE, "🔥")
    rocket = _ce(EMOJI_ROCKET, "🚀")
    money = _ce(EMOJI_MONEY, "💰")
    camera = _ce(EMOJI_CAMERA, "📸")
    on_button = _ce(EMOJI_ON_BUTTON, "🔘")

    return (
        f"FULL PROCESS {tick}\n\n\n"
        f"{on_button}<b>How To START TRADING ?</b>\n (Trading kaise Start kare ?){tick}\n"
        f"{down * 10}\n\n\n"
        f"{on_button}Step:1- {fire}Make Your Trading ID Now with Tradexkrish {tick}"
        f"{rocket}{down}( Apni Trading Account iss Verified Link se Banao )\n"
        f"{tick} Trading ID Register Link - \n\n"
        f"{REGISTER_LINK}\n\n"
        f"{on_button}Step:2- {money}Minimum Deposit "
        f"(Itna Paisa se trading Start kar skte ho ): ₹1500 Only{tick}\n\n"
        f"{on_button}Step:3- {camera}Send Us Your Trader UID Screenshot After Registration "
        f"(Account Banane ke baad yaha apni id number vejdo)\n\n"
        f"{tick}@teamtradexkrish{tick}\n\n"
        f"Step:4- {rocket}Join the live session and Follow The trades {fire}"
    )


REPLY_TEXT = build_reply_text()

MSG_DELAY_SECONDS = 1  # wait 1 sec after video, then send text


@dataclass(frozen=True)
class VideoInfo:
    width: int
    height: int
    duration: int  # seconds


# Loaded at startup from video.mp4 metadata
VIDEO_INFO: Optional[VideoInfo] = None
VIDEO_THUMB: Optional[Path] = None

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Replied-users persistence (JSON)
# ---------------------------------------------------------------------------


def load_replied_users() -> set[int]:
    """Load user IDs that have already received an auto-reply."""
    if not REPLIED_USERS_FILE.exists():
        return set()

    try:
        with REPLIED_USERS_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, list):
            logger.warning("Invalid replied_users.json format; starting fresh.")
            return set()
        return {int(user_id) for user_id in data}
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        logger.error("Could not read replied_users.json: %s", exc)
        return set()


def save_replied_user(user_id: int, replied_users: set[int]) -> None:
    """Append a user ID and persist to disk."""
    replied_users.add(user_id)
    try:
        with REPLIED_USERS_FILE.open("w", encoding="utf-8") as file:
            json.dump(sorted(replied_users), file, indent=2)
        logger.info("Saved user %s to replied_users.json", user_id)
    except OSError as exc:
        logger.error("Failed to save replied_users.json: %s", exc)


# ---------------------------------------------------------------------------
# Environment & client setup
# ---------------------------------------------------------------------------


def load_config() -> tuple[int, str, str]:
    """Load API credentials from .env."""
    load_dotenv(BASE_DIR / ".env")

    api_id_raw = os.getenv("API_ID", "").strip()
    api_hash = os.getenv("API_HASH", "").strip()
    session_name = os.getenv("SESSION_NAME", "sameer_session").strip()

    if not api_id_raw or not api_hash:
        raise ValueError(
            "API_ID and API_HASH must be set in .env "
            "(copy .env.example to .env and fill in your values)."
        )

    try:
        api_id = int(api_id_raw)
    except ValueError as exc:
        raise ValueError("API_ID must be a number.") from exc

    return api_id, api_hash, session_name


def validate_files() -> None:
    """Ensure required media file exists before starting."""
    if not VIDEO_FILE.is_file():
        raise FileNotFoundError(
            f"Video file not found: {VIDEO_FILE}\n"
            "Place your video.mp4 in the project folder."
        )


def _probe_with_ffprobe(path: Path) -> Optional[VideoInfo]:
    """Read width, height, duration using ffprobe (best for VPS)."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height,duration",
                "-show_entries",
                "stream_tags=rotate",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        payload = json.loads(result.stdout)
        stream = payload["streams"][0]
        width = int(stream["width"])
        height = int(stream["height"])
        tags = stream.get("tags") or {}
        rotation = int(tags.get("rotate", 0) or 0)
        if rotation in (90, 270):
            width, height = height, width

        duration_raw = stream.get("duration")
        if duration_raw is None:
            format_duration = json.loads(
                subprocess.run(
                    [
                        "ffprobe",
                        "-v",
                        "error",
                        "-show_entries",
                        "format=duration",
                        "-of",
                        "json",
                        str(path),
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=30,
                ).stdout
            )
            duration_raw = format_duration["format"]["duration"]

        duration = max(1, int(float(duration_raw)))
        return VideoInfo(width=width, height=height, duration=duration)
    except (FileNotFoundError, subprocess.SubprocessError, KeyError, ValueError, json.JSONDecodeError):
        return None


def _probe_with_mdls(path: Path) -> Optional[VideoInfo]:
    """macOS fallback when ffprobe is not installed."""
    if sys.platform != "darwin":
        return None

    try:
        result = subprocess.run(
            [
                "mdls",
                "-name",
                "kMDItemPixelWidth",
                "-name",
                "kMDItemPixelHeight",
                "-name",
                "kMDItemDurationSeconds",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
        values: dict[str, float] = {}
        for line in result.stdout.splitlines():
            if "=" not in line:
                continue
            key, raw_value = line.split("=", 1)
            raw_value = raw_value.strip()
            if raw_value == "(null)":
                continue
            values[key.strip()] = float(raw_value)

        width = int(values["kMDItemPixelWidth"])
        height = int(values["kMDItemPixelHeight"])
        duration = max(1, int(values["kMDItemDurationSeconds"]))
        return VideoInfo(width=width, height=height, duration=duration)
    except (subprocess.SubprocessError, KeyError, ValueError):
        return None


def _probe_with_telethon(path: Path) -> Optional[VideoInfo]:
    """Read video metadata via Telethon (uses hachoir, no ffprobe needed)."""
    try:
        attrs, _ = get_attributes(str(path), supports_streaming=True)
        for attr in attrs:
            if isinstance(attr, DocumentAttributeVideo) and attr.w > 1 and attr.h > 1:
                return VideoInfo(
                    width=int(attr.w),
                    height=int(attr.h),
                    duration=max(1, int(attr.duration)),
                )
    except Exception as exc:
        logger.warning("Telethon/hachoir metadata read failed: %s", exc)
    return None


def _probe_from_env() -> Optional[VideoInfo]:
    """Optional manual override via .env if auto-detect fails."""
    load_dotenv(BASE_DIR / ".env")
    width_raw = os.getenv("VIDEO_WIDTH", "").strip()
    height_raw = os.getenv("VIDEO_HEIGHT", "").strip()
    duration_raw = os.getenv("VIDEO_DURATION", "").strip()

    if not width_raw or not height_raw:
        return None

    try:
        return VideoInfo(
            width=int(width_raw),
            height=int(height_raw),
            duration=max(1, int(duration_raw or "1")),
        )
    except ValueError:
        return None


def load_video_info() -> VideoInfo:
    """Detect portrait/landscape video metadata for correct Telegram playback."""
    load_dotenv(BASE_DIR / ".env")

    def _log_and_return(source: str, info: VideoInfo) -> VideoInfo:
        logger.info(
            "Video metadata (%s): %sx%s, %ss",
            source,
            info.width,
            info.height,
            info.duration,
        )
        return info

    try:
        info = _probe_from_env()
        if info is not None:
            return _log_and_return("env", info)
    except Exception as exc:
        logger.warning("env video probe failed: %s", exc)

    if shutil.which("ffprobe"):
        try:
            info = _probe_with_ffprobe(VIDEO_FILE)
            if info is not None:
                return _log_and_return("ffprobe", info)
        except Exception as exc:
            logger.warning("ffprobe failed: %s", exc)
    else:
        logger.warning("ffprobe not found — run: sudo apt install ffmpeg -y")

    try:
        info = _probe_with_mdls(VIDEO_FILE)
        if info is not None:
            return _log_and_return("mdls", info)
    except Exception as exc:
        logger.warning("mdls probe failed: %s", exc)

    try:
        info = _probe_with_telethon(VIDEO_FILE)
        if info is not None:
            return _log_and_return("telethon", info)
    except Exception as exc:
        logger.warning("telethon probe failed: %s", exc)

    logger.warning(
        "Could not detect video metadata. Add VIDEO_WIDTH/HEIGHT to .env "
        "or install ffmpeg. Using safe portrait default 1080x1920."
    )
    return VideoInfo(width=1080, height=1920, duration=60)


def build_video_attributes() -> List[TypeDocumentAttribute]:
    """Build Telegram upload attributes for the video file."""
    attrs, _ = get_attributes(str(VIDEO_FILE), supports_streaming=True)
    if VIDEO_INFO is None:
        return attrs

    filtered = [a for a in attrs if not isinstance(a, DocumentAttributeVideo)]
    filtered.append(
        DocumentAttributeVideo(
            duration=VIDEO_INFO.duration,
            w=VIDEO_INFO.width,
            h=VIDEO_INFO.height,
            supports_streaming=True,
            round_message=False,
        )
    )
    return filtered


def prepare_video_thumb(video_info: VideoInfo) -> Optional[Path]:
    """Create a JPEG thumbnail so Telegram shows correct 9:16 preview."""
    thumb_path = BASE_DIR / "video_thumb.jpg"
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(VIDEO_FILE),
                "-ss",
                "00:00:01",
                "-vframes",
                "1",
                "-vf",
                f"scale={video_info.width}:{video_info.height}",
                str(thumb_path),
            ],
            capture_output=True,
            check=True,
            timeout=60,
        )
        if thumb_path.is_file():
            logger.info("Created video thumbnail: %s", thumb_path.name)
            return thumb_path
    except (FileNotFoundError, subprocess.SubprocessError):
        logger.info("ffmpeg not found; sending video without custom thumbnail.")
    return None


# ---------------------------------------------------------------------------
# Auto-reply logic
# ---------------------------------------------------------------------------


async def send_auto_reply(client: TelegramClient, user_id: int) -> None:
    """Send video first (9:16 portrait), then text message after 1 second."""
    send_kwargs: Dict = {
        "supports_streaming": True,
        "force_document": False,
        "attributes": build_video_attributes(),
    }
    if VIDEO_THUMB is not None:
        send_kwargs["thumb"] = str(VIDEO_THUMB)

    await client.send_file(user_id, str(VIDEO_FILE), **send_kwargs)
    if VIDEO_INFO:
        logger.info(
            "Sent video to user %s (%sx%s)",
            user_id,
            VIDEO_INFO.width,
            VIDEO_INFO.height,
        )
    else:
        logger.info("Sent video to user %s", user_id)

    await asyncio.sleep(MSG_DELAY_SECONDS)

    await client.send_message(user_id, REPLY_TEXT, parse_mode="html")
    logger.info("Sent text message to user %s", user_id)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    global VIDEO_INFO, VIDEO_THUMB

    validate_files()
    try:
        VIDEO_INFO = load_video_info()
    except Exception as exc:
        logger.exception("Video metadata failed, using defaults: %s", exc)
        VIDEO_INFO = VideoInfo(width=1080, height=1920, duration=60)
    VIDEO_THUMB = prepare_video_thumb(VIDEO_INFO)

    api_id, api_hash, session_name = load_config()
    session_path = str(BASE_DIR / session_name)

    replied_users = load_replied_users()
    pending_users: set[int] = set()  # prevents duplicate replies during delay
    logger.info("Loaded %s previously replied user(s).", len(replied_users))

    client = TelegramClient(session_path, api_id, api_hash)

    @client.on(events.NewMessage(incoming=True))
    async def handle_new_message(event: events.NewMessage.Event) -> None:
        # Only private DMs (not groups/channels)
        if not event.is_private:
            return

        sender = await event.get_sender()
        if sender is None:
            return

        # Ignore bots and own messages
        if getattr(sender, "bot", False):
            return
        if event.out:
            return

        user_id = sender.id

        if user_id in replied_users or user_id in pending_users:
            logger.debug("User %s already replied or pending; skipping.", user_id)
            return

        pending_users.add(user_id)
        logger.info(
            "New DM from user %s (@%s); preparing auto-reply.",
            user_id,
            getattr(sender, "username", None) or "no_username",
        )

        try:
            await send_auto_reply(client, user_id)
            save_replied_user(user_id, replied_users)
        except FloodWaitError as exc:
            logger.warning(
                "Flood wait: Telegram asked to wait %s seconds. Skipping this reply.",
                exc.seconds,
            )
            pending_users.discard(user_id)
        except RPCError as exc:
            logger.error("Telegram API error for user %s: %s", user_id, exc)
            pending_users.discard(user_id)
        except Exception as exc:
            logger.exception("Unexpected error while replying to user %s: %s", user_id, exc)
            pending_users.discard(user_id)
        else:
            pending_users.discard(user_id)

    logger.info("Starting Telegram userbot...")
    await client.start()
    me = await client.get_me()
    logger.info(
        "Logged in as %s (@%s). Listening for private messages...",
        me.first_name,
        me.username or "no_username",
    )
    logger.info("Press Ctrl+C to stop.")

    await client.run_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopped by user.")
    except ValueError as exc:
        logger.error("Configuration error: %s", exc)
        raise SystemExit(1) from exc
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        raise SystemExit(1) from exc
