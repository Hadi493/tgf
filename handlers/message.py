from telethon import TelegramClient, events
from loguru import logger
from db.storage import Database
from utils.formatter import get_content_hash
import os

def get_aggregator_channel():
    return os.getenv("TELEGRAM_AGGREGATOR_CHANNEL")

async def register_handlers(client: TelegramClient, db: Database, source_channels: list):
    aggregator_channel = get_aggregator_channel()

    try:
        aggregator = await client.get_entity(aggregator_channel)
        logger.info(f"Resolved aggregator channel: {getattr(aggregator, 'title', aggregator_channel)}")
    except Exception as e:
        logger.error(f"Could not resolve aggregator channel '{aggregator_channel}': {e}")
        return

    @client.on(events.NewMessage(chats=source_channels))
    async def handle_new_message(event):
        try:
            content_hash = get_content_hash(event.message)
            if await db.is_duplicate(content_hash):
                return

            chat = await event.get_chat()
            name = getattr(chat, 'title', 'Unknown')
            
            reply_to = None
            if event.reply_to_msg_id:
                reply_to = await db.get_mapping(event.chat_id, event.reply_to_msg_id)

            sent_msg = await client.send_message(
                aggregator,
                f"**{name}**\n\n{event.message.text or ''}",
                file=event.message.media,
                reply_to=reply_to,
                buttons=event.message.reply_markup
            )

            await db.mark_as_seen(content_hash)
            await db.save_mapping(event.chat_id, event.message.id, sent_msg.id)
            logger.success(f"Forwarded from {name}")

        except Exception as e:
            logger.error(f"Error handling message: {e}")

