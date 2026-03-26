from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaWebPage
from telethon.errors import MessageNotModifiedError
from loguru import logger
from db.storage import Database
from utils.formatter import get_content_hash
import os
import asyncio

def get_aggregator_channel():
    return os.getenv("TELEGRAM_AGGREGATOR_CHANNEL")

entity_cache = {}

TEXT_LIMIT = 4096      
CAPTION_LIMIT = 1024

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

async def get_message_link(client, chat_id, message_id):
    try:
        entity = await client.get_entity(chat_id)
        if hasattr(entity, 'username') and entity.username:
            return f"https://t.me/{entity.username}/{message_id}"
        return f"https://t.me/c/{str(chat_id).replace('-100', '')}/{message_id}"
    except:
        return f"https://t.me/c/{str(chat_id).replace('-100', '')}/{message_id}"


async def process_message(client, db, aggregator, chat_id, messages, is_album=False):
    try:
        main_msg = messages[0]
        content_hash = get_content_hash(main_msg)
        
        if await db.is_duplicate(content_hash):
            return

        name = await get_entity_name(client, chat_id)
        
        reply_to = None
        if main_msg.reply_to_msg_id:
            reply_to = await db.get_mapping(chat_id, main_msg.reply_to_msg_id)

        msg_link = await get_message_link(client, chat_id, main_msg.id)
        header = f"**{name}** ([Source]({msg_link}))"
        body = main_msg.text or ""
        full_text = f"{header}\n\n{body}"
        
        has_real_media = main_msg.media and not isinstance(main_msg.media, MessageMediaWebPage)

        if is_album:
            safe_caption = full_text if len(full_text) <= CAPTION_LIMIT else full_text[:1021] + "..."
            
            sent_msgs = await client.send_file(
                aggregator,
                messages,
                caption=safe_caption,
                reply_to=reply_to
            )
            sent_msg = sent_msgs[0] if isinstance(sent_msgs, list) else sent_msgs
            
            if len(full_text) > CAPTION_LIMIT:
                await client.send_message(aggregator, full_text, reply_to=sent_msg.id, link_preview=False)

        elif has_real_media and len(full_text) > CAPTION_LIMIT:
            sent_msg = await client.send_message(
                aggregator,
                full_text[:1021] + "...",
                file=main_msg.media,
                reply_to=reply_to,
                buttons=main_msg.reply_markup,
                link_preview=False
            )
            await client.send_message(aggregator, full_text, reply_to=sent_msg.id, link_preview=False)

        else:
            final_text = full_text if len(full_text) <= TEXT_LIMIT else full_text[:4093] + "..."
            
            sent_msg = await client.send_message(
                aggregator,
                final_text,
                file=main_msg.media if has_real_media else None,
                reply_to=reply_to,
                buttons=main_msg.reply_markup,
                link_preview=False
            )

        await db.mark_as_seen(content_hash)
        await db.save_mapping(chat_id, main_msg.id, sent_msg.id)
        logger.success(f"Forwarded from {name} (Length: {len(full_text)})")

    except Exception as e:
        logger.error(f"Error handling message: {e}")

async def catch_up(client: TelegramClient, db: Database, source_channels: list):
    aggregator_channel = get_aggregator_channel()
    try:
        aggregator = await client.get_entity(aggregator_channel)
        for chat_id in source_channels:
            last_id = await db.get_last_message_id(chat_id)
            if last_id == 0:
                async for msg in client.iter_messages(chat_id, limit=5):
                    await process_message(client, db, aggregator, chat_id, [msg], is_album=False)
                continue
            async for message in client.iter_messages(chat_id, min_id=last_id, reverse=True):
                await process_message(client, db, aggregator, chat_id, [message], is_album=False)
    except Exception as e:
        logger.error(f"Error during catch up: {e}")

async def register_handlers(client: TelegramClient, db: Database, config_channels: list, resolved_channels: list, inactive_channels: list):
    aggregator_channel = get_aggregator_channel()
    try:
        aggregator = await client.get_entity(aggregator_channel)
        logger.info(f"Aggregator initialized: {getattr(aggregator, 'title', aggregator_channel)}")
    except Exception as e:
        logger.error(f"Aggregator error: {e}")
        return

    @client.on(events.NewMessage(pattern='/status', outgoing=True))
    async def handle_status(event):
        stats = await db.get_stats()
        status_msg = f"📊 **Status**\nActive: `{len(resolved_channels)}` | Forwarded: `{stats['total_forwarded']}`"
        await event.edit(status_msg)

    @client.on(events.Album(chats=resolved_channels))
    async def handle_album(event):
        await process_message(client, db, aggregator, event.chat_id, event.messages, is_album=True)

    @client.on(events.NewMessage(chats=resolved_channels, func=lambda e: e.grouped_id is None))
    async def handle_new_message(event):
        if event.message.out and event.message.text.startswith('/status'): return
        await process_message(client, db, aggregator, event.chat_id, [event.message], is_album=False)

    @client.on(events.MessageEdited(chats=resolved_channels))
    async def handle_edit(event):
        try:
            aggregator_msg_id = await db.get_mapping(event.chat_id, event.id)
            if not aggregator_msg_id: return
            
            name = await get_entity_name(client, event.chat_id)
            msg_link = await get_message_link(client, event.chat_id, event.id)
            full_text = f"**{name}** ([Source]({msg_link}))\n\n{event.text or ''}"
            
            has_media = event.media and not isinstance(event.media, MessageMediaWebPage)
            limit = CAPTION_LIMIT if has_media else TEXT_LIMIT
            safe_text = full_text if len(full_text) <= limit else full_text[:limit-3] + "..."

            await client.edit_message(aggregator, aggregator_msg_id, text=safe_text, link_preview=False)
        except MessageNotModifiedError: pass
        except Exception as e: logger.error(f"Edit error: {e}")

    @client.on(events.MessageDeleted())
    async def handle_delete(event):
        for msg_id in event.deleted_ids:
            try:
                agg_id = await db.get_mapping(event.chat_id, msg_id)
                if agg_id: await client.delete_messages(aggregator, agg_id)
            except: pass
