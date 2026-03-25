from telethon import TelegramClient, events
from loguru import logger
from db.storage import Database
from utils.formatter import format_message, get_content_hash
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
            logger.debug(f"Received new message from {event.chat_id}")
            if event.message.reply_markup:
                logger.debug(f"Filtered message with inline buttons from {event.chat_id}")
                return

            if event.message.fwd_from:
                logger.info(f"Filtered forwarded message from {event.chat_id}")
                return
            content_hash = get_content_hash(event.message)
            if await db.is_duplicate(content_hash):
                logger.debug(f"Skipping duplicate message from {event.chat_id}")
                return
            chat = await event.get_chat()
            caption = format_message(event.message, chat)

            logger.info(f"Forwarding message from {chat.title}")
            if event.message.media:
                await client.send_message(
                    aggregator,
                    caption,
                    file=event.message.media
                )
            else:
                await client.send_message(
                    aggregator,
                    caption
                )

            await db.mark_as_seen(content_hash)
            logger.success(f"Forwarded message from {chat.title}")

        except Exception as e:
            logger.error(f"Error handling message: {e}")

