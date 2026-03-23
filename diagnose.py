import asyncio
import os
from dotenv import load_dotenv
from telethon import TelegramClient
from loguru import logger

load_dotenv()

API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
SOURCE = "Alibk3"

async def diagnose():
    client = TelegramClient("session", API_ID, API_HASH)
    await client.start()
    
    try:
        entity = await client.get_entity(SOURCE)
        logger.info(f"Connected to {SOURCE} (ID: {entity.id})")
        
        logger.info("Fetching last 5 messages to check for ads/forwards...")
        async for msg in client.iter_messages(entity, limit=5):
            has_buttons = msg.reply_markup is not None
            is_forward = msg.fwd_from is not None
            logger.info(f"Msg ID {msg.id}: Buttons={has_buttons}, Forward={is_forward}, Text={msg.text[:50] if msg.text else 'MEDIA'}")
            
    except Exception as e:
        logger.error(f"Diagnosis failed: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(diagnose())
