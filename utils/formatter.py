import hashlib
from telethon.tl.types import Message, Chat, Channel
from datetime import datetime

def format_message(message: Message, chat: Chat | Channel) -> str:
    source_title = getattr(chat, 'title', 'Unknown Source')
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    header = f"**{source_title}** | {timestamp}\n\n"
    original_text = message.text or ""
    
    return f"{header}{original_text}"

def get_content_hash(message: Message) -> str:
    text = message.text or ""
    media_info = str(message.media) if message.media else ""
    reply_info = str(message.reply_to_msg_id) if message.reply_to_msg_id else ""
    raw_data = f"{text}{media_info}{reply_info}"
    return hashlib.sha256(raw_data.encode()).hexdigest()
