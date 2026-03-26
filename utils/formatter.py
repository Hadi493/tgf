import hashlib
from telethon.tl.types import Message, Chat, Channel
from datetime import datetime

def format_header(chat: Chat | Channel, source_url: str) -> str:
    name = getattr(chat, 'title', getattr(chat, 'first_name', 'Unknown'))
    return f"**{name}** ([Source]({source_url}))"

def get_content_hash(message: Message) -> str:
    text = message.text or ""
    media = str(message.media) if message.media else ""
    reply = str(message.reply_to_msg_id) if message.reply_to_msg_id else ""
    data = f"{message.chat_id}{message.id}{text}{media}{reply}"
    return hashlib.sha256(data.encode()).hexdigest()
