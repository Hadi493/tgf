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
        caption = f"{header}\n\n{body}"
        
        has_real_media = main_msg.media and not isinstance(main_msg.media, MessageMediaWebPage)
        
        if is_album:
            sent_msgs = await client.send_file(
                aggregator,
                messages,
                caption=caption if len(caption) <= 1024 else caption[:1021] + "...",
                reply_to=reply_to
            )
            sent_msg = sent_msgs[0] if isinstance(sent_msgs, list) else sent_msgs
            
            if len(caption) > 1024:
                await client.send_message(aggregator, caption, reply_to=sent_msg.id, link_preview=False)
        else:
            if has_real_media and len(caption) > 1024:
                sent_msg = await client.send_message(
                    aggregator,
                    caption[:1021] + "...",
                    file=main_msg.media,
                    reply_to=reply_to,
                    buttons=main_msg.reply_markup,
                    link_preview=False
                )
                await client.send_message(aggregator, caption, reply_to=sent_msg.id, link_preview=False)
            else:
                sent_msg = await client.send_message(
                    aggregator,
                    caption,
                    file=main_msg.media if has_real_media else None,
                    reply_to=reply_to,
                    buttons=main_msg.reply_markup,
                    link_preview=False
                )

        await db.mark_as_seen(content_hash)
        await db.save_mapping(chat_id, main_msg.id, sent_msg.id)
        logger.success(f"Forwarded from {name}")

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
        logger.info(f"Resolved aggregator channel: {getattr(aggregator, 'title', aggregator_channel)}")
    except Exception as e:
        logger.error(f"Could not resolve aggregator channel '{aggregator_channel}': {e}")
        return

    @client.on(events.NewMessage(pattern='/status', outgoing=True))
    async def handle_status(event):
        try:
            stats = await db.get_stats()
            total_config = len(config_channels)
            total_active = len(resolved_channels)
            total_inactive = len(inactive_channels)
            
            status_msg = (
                "📊 **Bot Status**\n\n"
                f"✅ **Total Configured:** `{total_config}`\n"
                f"🟢 **Active (Listening):** `{total_active}`\n"
                f"🔴 **Inactive:** `{total_inactive}`\n\n"
                f"📝 **Forwarded Messages:** `{stats['total_forwarded']}`\n"
                f"🔍 **Seen Unique Hashes:** `{stats['total_seen']}`\n"
            )
            
            if total_inactive > 0:
                inactive_list = "\n".join([f"- `{c}`" for c in inactive_channels])
                status_msg += f"\n❌ **Inactive Details:**\n{inactive_list}"
                
            await event.edit(status_msg)
        except Exception as e:
            logger.error(f"Error in status command: {e}")

    @client.on(events.Album(chats=resolved_channels))
    async def handle_album(event):
        await process_message(client, db, aggregator, event.chat_id, event.messages, is_album=True)

    @client.on(events.NewMessage(chats=resolved_channels, func=lambda e: e.grouped_id is None))
    async def handle_new_message(event):
        if event.message.text and event.message.text.startswith('/status') and event.message.out:
            return # Handled by Pattern handler
        await process_message(client, db, aggregator, event.chat_id, [event.message], is_album=False)

    @client.on(events.MessageEdited(chats=resolved_channels))
    async def handle_edit(event):
        try:
            aggregator_msg_id = await db.get_mapping(event.chat_id, event.id)

            if not aggregator_msg_id:
                return

            name = await get_entity_name(client, event.chat_id)
            msg_link = await get_message_link(client, event.chat_id, event.id)
            header = f"**{name}** ([Source]({msg_link}))"
            body = event.text or ""
            caption = f"{header}\n\n{body}"

            await client.edit_message(
                aggregator,
                aggregator_msg_id,
                caption if event.media else caption,
                file=event.media if event.media else None,
                link_preview=False
            )
            logger.info(f"Updated edited message from {name}")
        except MessageNotModifiedError:
            pass
        except Exception as e:
            logger.error(f"Error handling edit: {e}")

    @client.on(events.MessageDeleted())
    async def handle_delete(event):
        for msg_id in event.deleted_ids:
            try:
                aggregator_msg_id = await db.get_mapping(event.chat_id, msg_id)
                if aggregator_msg_id:
                    await client.delete_messages(aggregator, aggregator_msg_id)
                    logger.info(f"Deleted message {msg_id} from aggregator")
            except Exception as e:
                logger.error(f"Error handling delete: {e}")
