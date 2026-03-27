import os
import asyncio
from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaWebPage, Channel, Chat
from telethon.errors import MessageNotModifiedError, FloodWaitError, MessageIdInvalidError
from loguru import logger
from db.storage import Database
from utils.formatter import get_content_hash, format_header

TEXT_LIMIT = 4096
CAPTION_LIMIT = 1024
send_lock = asyncio.Lock()

def get_aggregator_id():
    val = os.getenv("TELEGRAM_AGGREGATOR_CHANNEL")
    if not val:
        return None
    # If it's a numeric ID (like -100123 or 123), convert to int
    if val.startswith('-') and val[1:].isdigit():
        return int(val)
    if val.isdigit():
        return int(val)
    return val

async def get_chat_link(client: TelegramClient, chat_id: int, message_id: int) -> str:
    try:
        entity = await client.get_entity(chat_id)
        if isinstance(entity, (Channel, Chat)) and getattr(entity, 'username', None):
            return f"https://t.me/{entity.username}/{message_id}"
        clean_id = str(chat_id).replace("-100", "")
        return f"https://t.me/c/{clean_id}/{message_id}"
    except:
        return f"https://t.me/c/{str(chat_id).replace('-100', '')}/{message_id}"

async def split_and_send(client, aggregator, text, reply_to=None):
    chunks = [text[i:i + TEXT_LIMIT] for i in range(0, len(text), TEXT_LIMIT)]
    last_sent = None
    for chunk in chunks:
        last_sent = await client.send_message(aggregator, chunk, reply_to=reply_to or last_sent, link_preview=False)
        reply_to = last_sent.id
        await asyncio.sleep(1)
    return last_sent

async def send_to_aggregator(client, aggregator, text, media=None, reply_to=None, buttons=None, is_album=False, messages=None):
    async with send_lock:
        try:
            if is_album:
                caption = text if len(text) <= CAPTION_LIMIT else text[:1021] + "..."
                sent = await client.send_file(aggregator, messages, caption=caption, reply_to=reply_to)
                main_msg = sent[0] if isinstance(sent, list) else sent
                if len(text) > CAPTION_LIMIT:
                    await asyncio.sleep(1)
                    await split_and_send(client, aggregator, text, reply_to=main_msg.id)
                return sent

            has_media = media and not isinstance(media, MessageMediaWebPage)
            limit = CAPTION_LIMIT if has_media else TEXT_LIMIT
            
            if len(text) > limit:
                truncated = text[:limit-3] + "..."
                sent = await client.send_message(aggregator, truncated, file=media if has_media else None, reply_to=reply_to, buttons=buttons, link_preview=False)
                await asyncio.sleep(1)
                await split_and_send(client, aggregator, text, reply_to=sent.id)
                return sent
            
            sent = await client.send_message(aggregator, text, file=media if has_media else None, reply_to=reply_to, buttons=buttons, link_preview=False)
            await asyncio.sleep(3)
            return sent
        except FloodWaitError as e:
            logger.warning(f"Flood wait: {e.seconds}s")
            await asyncio.sleep(e.seconds)
            return await send_to_aggregator(client, aggregator, text, media, reply_to, buttons, is_album, messages)

async def process_message(client, db, aggregator, chat_id, messages, is_album=False, chat=None):
    try:
        if not messages: return
        main_msg = messages[0]
        
        # Check if any message in the album/set is a duplicate
        # For simplicity, we check the first one, but we will mark all as seen
        content_hash = get_content_hash(main_msg)
        if await db.is_duplicate(content_hash): return

        if not chat:
            chat = await client.get_entity(chat_id)
        
        link = await get_chat_link(client, chat_id, main_msg.id)
        text = f"{format_header(chat, link)}\n\n{main_msg.text or ''}"
        
        reply_to = None
        if main_msg.reply_to_msg_id:
            reply_to = await db.get_mapping(chat_id, main_msg.reply_to_msg_id)

        sent_result = await send_to_aggregator(
            client, aggregator, text, 
            media=main_msg.media, 
            reply_to=reply_to, 
            buttons=main_msg.reply_markup, 
            is_album=is_album, 
            messages=messages
        )

        if sent_result:
            await db.mark_as_seen(content_hash)
            
            if is_album and isinstance(sent_result, list):
                for i in range(min(len(messages), len(sent_result))):
                    await db.save_mapping(chat_id, messages[i].id, sent_result[i].id)
            else:
                sent_msg = sent_result[0] if isinstance(sent_result, list) else sent_result
                await db.save_mapping(chat_id, main_msg.id, sent_msg.id)
            
            logger.success(f"Forwarded from {getattr(chat, 'title', 'Unknown')}")
    except Exception as e:
        logger.error(f"Processing error: {e}")

async def catch_up(client: TelegramClient, db: Database, channels: list):
    aggregator = await client.get_entity(get_aggregator_id())
    for chat_id in channels:
        last_id = await db.get_last_message_id(chat_id)
        limit = 10 if last_id == 0 else None
        min_id = last_id if last_id > 0 else None
        
        current_album = []
        current_gid = None
        
        async for msg in client.iter_messages(chat_id, limit=limit, min_id=min_id, reverse=True):
            if msg.grouped_id:
                if current_gid and msg.grouped_id == current_gid:
                    current_album.append(msg)
                else:
                    if current_album:
                        await process_message(client, db, aggregator, chat_id, current_album, is_album=True)
                        await asyncio.sleep(2)
                    current_album = [msg]
                    current_gid = msg.grouped_id
            else:
                if current_album:
                    await process_message(client, db, aggregator, chat_id, current_album, is_album=True)
                    await asyncio.sleep(2)
                    current_album = []
                    current_gid = None
                await process_message(client, db, aggregator, chat_id, [msg])
                await asyncio.sleep(2)
        
        if current_album:
            await process_message(client, db, aggregator, chat_id, current_album, is_album=True)
            await asyncio.sleep(2)

async def register_handlers(client: TelegramClient, db: Database, active_ids: list, inactive_names: list):
    aggregator = await client.get_entity(get_aggregator_id())

    @client.on(events.NewMessage(pattern=r'(?i)^/status', outgoing=True))
    async def status_handler(event):
        try:
            stats = await db.get_stats()
            text = (
                f"📊 **System Status**\n\n"
                f"✅ **Active Sources:** `{len(active_ids)}` channels\n"
                f"❌ **Inactive/Failed:** `{len(inactive_names)}` sources\n"
                f"📤 **Total Forwarded:** `{stats['total_forwarded']}` messages\n"
                f"🔍 **Duplicate Check:** `{stats['total_seen']}` total posts seen"
            )
            if inactive_names:
                text += f"\n\n⚠️ **Failed to resolve:**\n" + "\n".join([f"- `{n}`" for n in inactive_names[:5]])
                if len(inactive_names) > 5: text += f"\n... and {len(inactive_names)-5} more."
            await event.edit(text)
        except Exception as e: logger.error(f"Status error: {e}")

    @client.on(events.Album(chats=active_ids))
    async def album_handler(event):
        await process_message(client, db, aggregator, event.chat_id, event.messages, is_album=True, chat=await event.get_chat())

    @client.on(events.NewMessage(chats=active_ids, func=lambda e: e.grouped_id is None))
    async def message_handler(event):
        if event.out and event.text.startswith('/status'): return
        await process_message(client, db, aggregator, event.chat_id, [event.message], chat=await event.get_chat())

    @client.on(events.MessageEdited(chats=active_ids))
    async def edit_handler(event):
        try:
            agg_id = await db.get_mapping(event.chat_id, event.id)
            if not agg_id: return
            chat = await client.get_entity(event.chat_id)
            link = await get_chat_link(client, event.chat_id, event.id)
            text = f"{format_header(chat, link)}\n\n{event.text or ''}"
            has_media = event.media and not isinstance(event.media, MessageMediaWebPage)
            limit = CAPTION_LIMIT if has_media else TEXT_LIMIT
            safe_text = text if len(text) <= limit else text[:limit-3] + "..."
            async with send_lock:
                await client.edit_message(aggregator, agg_id, text=safe_text, link_preview=False)
                await asyncio.sleep(1)
        except MessageNotModifiedError: pass
        except MessageIdInvalidError:
            logger.warning(f"Message {event.id} in {event.chat_id} not found in aggregator. Removing stale mapping.")
            await db.delete_mapping(event.chat_id, event.id)
        except FloodWaitError as e: await asyncio.sleep(e.seconds)
        except Exception as e: logger.error(f"Edit error: {e}")

    @client.on(events.MessageDeleted())
    async def delete_handler(event):
        for msg_id in event.deleted_ids:
            agg_id = await db.get_mapping(event.chat_id, msg_id)
            if agg_id:
                try: 
                    async with send_lock:
                        await client.delete_messages(aggregator, agg_id)
                        await asyncio.sleep(1)
                except: pass
                await db.delete_mapping(event.chat_id, msg_id)
