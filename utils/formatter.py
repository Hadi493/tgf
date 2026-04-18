import hashlib
import re
from datetime import timedelta
from telethon.tl.types import Message, Chat, Channel

def format_header(chat: Chat | Channel, source_url: str) -> str:
    """Formats the header for a forwarded message."""
    name = getattr(chat, 'title', getattr(chat, 'first_name', 'Unknown'))
    return f"**{name}** ([Source]({source_url}))"

def get_content_hash(message: Message) -> str:
    """Generates a hash of the message content to detect duplicates."""
    text = message.text or ""
    media = str(message.media) if message.media else ""
    reply = str(message.reply_to_msg_id) if message.reply_to_msg_id else ""
    
    # We include chat_id and message_id to ensure uniqueness for each message
    data = f"{message.chat_id}{message.id}{text}{media}{reply}"
    return hashlib.sha256(data.encode()).hexdigest()

def parse_duration(duration_str: str) -> timedelta | None:
    """Parses a duration string like '1d', '2h', '30m', '10s' into a timedelta."""
    match = re.match(r"(\d+)([smhd])", duration_str.lower())
    if not match:
        return None
        
    value, unit = match.groups()
    value = int(value)
    
    if unit == 's':
        return timedelta(seconds=value)
    if unit == 'm':
        return timedelta(minutes=value)
    if unit == 'h':
        return timedelta(hours=value)
    if unit == 'd':
        return timedelta(days=value)
        
    return None
