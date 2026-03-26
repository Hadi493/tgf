from telethon import TelegramClient, events
from loguru import logger
from db.storage import Database
from utils.formatter import get_content_hash
import os

def get_aggregator_channel():
    return os.getenv("TELEGRAM_AGGREGATOR_CHANNEL")

# In-memory cache for channel titles to reduce network calls
entity_cache = {}

async def get_entity_name(client: TelegramClient, entity_id: int):
    if entity_id in entity_cache:
        return entity_cache[entity_id]
    try:
        entity = await client.get_entity(entity_id)
        name = getattr(entity, 'title', getattr(entity, 'first_name', 'Unknown'))
        entity_cache[entity_id] = name
        return name
    except Exception:
        return "Unknown"

async def register_handlers(client: TelegramClient, db: Database, source_channels: list):
    aggregator_channel = get_aggregator_channel()

    try:
        aggregator = await client.get_entity(aggregator_channel)
        logger.info(f"Resolved aggregator channel: {getattr(aggregator, 'title', aggregator_channel)}")
    except Exception as e:
        logger.error(f"Could not resolve aggregator channel '{aggregator_channel}': {e}")
        return

    async def process_message(event, messages, is_album=False):
        try:
            # Use the first message for metadata and duplicate checking
            main_msg = messages[0]
            content_hash = get_content_hash(main_msg)
            
            if await db.is_duplicate(content_hash):
                return

            name = await get_entity_name(client, event.chat_id)
            
            reply_to = None
            if main_msg.reply_to_msg_id:
                reply_to = await db.get_mapping(event.chat_id, main_msg.reply_to_msg_id)

            caption = f"**{name}**\n\n{main_msg.text or ''}"
            
            if is_album:
                # Forward as an album
                sent_msgs = await client.send_file(
                    aggregator,
                    messages,
                    caption=caption if len(caption) <= 1024 else caption[:1021] + "...",
                    reply_to=reply_to
                )
                sent_msg = sent_msgs[0] if isinstance(sent_msgs, list) else sent_msgs
                
                if len(caption) > 1024:
                    await client.send_message(aggregator, caption, reply_to=sent_msg.id)
            else:
                # Forward as a single message
                if main_msg.media and len(caption) > 1024:
                    sent_msg = await client.send_message(
                        aggregator,
                        caption[:1021] + "...",
                        file=main_msg.media,
                        reply_to=reply_to,
                        buttons=main_msg.reply_markup
                    )
                    await client.send_message(aggregator, caption, reply_to=sent_msg.id)
                else:
                    sent_msg = await client.send_message(
                        aggregator,
                        caption,
                        file=main_msg.media,
                        reply_to=reply_to,
                        buttons=main_msg.reply_markup
                    )

            await db.mark_as_seen(content_hash)
            await db.save_mapping(event.chat_id, main_msg.id, sent_msg.id)
            logger.success(f"Forwarded from {name}")

        except Exception as e:
            logger.error(f"Error handling message: {e}")

    # Handle albums (media groups)
    @client.on(events.Album(chats=source_channels))
    async def handle_album(event):
        await process_message(event, event.messages, is_album=True)

    # Handle single messages (ignore messages that are part of an album)
    @client.on(events.NewMessage(chats=source_channels, func=lambda e: e.grouped_id is None))
    async def handle_new_message(event):
        await process_message(event, [event.message], is_album=False)
