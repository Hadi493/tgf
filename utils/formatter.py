import hashlib
from telethon.tl.types import Message, Chat, Channel
from datetime import datetime

def format_message(message: Message, chat: Chat | Channel) -> str:
    """Adds source channel and timestamp label to the message text."""
    source_title = getattr(chat, 'title', 'Unknown Source')
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    header = f"📢 **{source_title}** | 🕒 {timestamp}\n\n"
    original_text = message.text or ""
    
    return f"{header}{original_text}"

def get_content_hash(message: Message) -> str:
    """Generates a stable hash for a message to detect duplicates."""
    # Combine text and media info for hashing
    text = message.text or ""
    media_info = str(message.media) if message.media else ""
    raw_data = f"{text}{media_info}"
    return hashlib.sha256(raw_data.encode()).hexdigest()
