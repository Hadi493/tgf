import asyncio
import os
import sys
import platform

# Fix for Windows asyncio loop
if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import tomllib
import tomli_w
import click
from dotenv import load_dotenv
from telethon import TelegramClient
from loguru import logger
from db.storage import Database
from handlers.message import register_handlers, catch_up
from utils.folder import get_channels_from_folder

load_dotenv()

CONFIG_FILE = "config.toml"
SESSION_NAME = "session"
API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
PHONE = os.getenv("TELEGRAM_PHONE")

if not all([API_ID, API_HASH, PHONE]):
    logger.error("Missing environment variables in .env")
    sys.exit(1)

db = Database()

def load_config() -> dict:
    if not os.path.exists(CONFIG_FILE):
        return {"source": {"folder": []}, "source_channels": {"channels": []}}
    with open(CONFIG_FILE, "rb") as f:
        return tomllib.load(f)

def save_config(config: dict):
    with open(CONFIG_FILE, "wb") as f:
        tomli_w.dump(config, f)

@click.group()
def cli():
    pass

@cli.group()
def add():
    pass

@add.command(name="channel")
@click.argument("name")
def add_channel(name):
    config = load_config()
    if name not in config["source_channels"]["channels"]:
        config["source_channels"]["channels"].append(name)
        save_config(config)
        click.echo(f"Added channel: {name}")
    else:
        click.echo(f"Channel {name} already exists")

@add.command(name="folder")
@click.argument("name")
def add_folder(name):
    config = load_config()
    if "source" not in config: config["source"] = {"folder": []}
    if name not in config["source"]["folder"]:
        config["source"]["folder"].append(name)
        save_config(config)
        click.echo(f"Added folder: {name}")
    else:
        click.echo(f"Folder {name} already exists")

@cli.group()
def remove():
    pass

@remove.command(name="channel")
@click.argument("name")
def remove_channel(name):
    config = load_config()
    if name in config["source_channels"]["channels"]:
        config["source_channels"]["channels"].remove(name)
        save_config(config)
        click.echo(f"Removed channel: {name}")
    else:
        click.echo(f"Channel {name} not found")

@remove.command(name="folder")
@click.argument("name")
def remove_folder(name):
    config = load_config()
    if "source" in config and name in config["source"]["folder"]:
        config["source"]["folder"].remove(name)
        save_config(config)
        click.echo(f"Removed folder: {name}")
    else:
        click.echo(f"Folder {name} not found")

@cli.command(name="list")
def list_all():
    config = load_config()
    folders = config.get("source", {}).get("folder", [])
    channels = config.get("source_channels", {}).get("channels", [])
    click.echo("📁 Folders:")
    for f in folders: click.echo(f"  - {f}")
    if not folders: click.echo("  (none)")
    click.echo("\n📺 Channels:")
    for c in channels: click.echo(f"  - {c}")
    if not channels: click.echo("  (none)")

@cli.command(help="Start the bot")
def run():
    asyncio.run(main())

async def get_client():
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start(phone=PHONE)
    me = await client.get_me()
    if me.bot:
        logger.error("You must use a user account, not a bot token")
        return None
    logger.info(f"Logged in as {me.first_name}")
    return client

async def resolve_channels(client, channels):
    active, inactive = [], []
    for channel in channels:
        try:
            entity = await client.get_entity(channel)
            active.append(entity.id)
        except Exception as e:
            logger.error(f"Failed to resolve {channel}: {e}")
            inactive.append(str(channel))
    return active, inactive

async def main():
    logger.info("Starting Aggregator...")
    await db.connect()
    
    config = load_config()
    client = await get_client()
    if not client: return

    active_ids = []
    inactive_names = []
    
    folder_names = config.get("source", {}).get("folder", [])
    if isinstance(folder_names, str): folder_names = [folder_names]
        
    for name in folder_names:
        folder_ids = await get_channels_from_folder(client, name)
        if folder_ids:
            active_ids.extend(folder_ids)
        else:
            inactive_names.append(f"Folder: {name}")

    static_channels = config.get("source_channels", {}).get("channels", [])
    static_active, static_inactive = await resolve_channels(client, static_channels)
    
    active_ids.extend(static_active)
    inactive_names.extend(static_inactive)

    unique_active = list(set(active_ids))
    
    if not unique_active:
        logger.error("No active channels to monitor")
        return

    await register_handlers(client, db, unique_active, inactive_names)
    
    if os.getenv("CATCH_UP", "true").lower() == "true":
        await catch_up(client, db, unique_active)
    else:
        logger.info("Skipping catch-up. Monitoring only new messages.")
        from handlers.message import get_aggregators
        aggregators = get_aggregators()
        agg_id = aggregators[0] if aggregators else 0
        
        for chat_id in unique_active:
            last_id = await db.get_last_message_id(chat_id)
            if last_id == 0:
                async for msg in client.iter_messages(chat_id, limit=1):
                    await db.save_mapping(chat_id, msg.id, 0, agg_id) 

    logger.success(f"Running! Monitoring {len(unique_active)} channels")
    
    try:
        await client.run_until_disconnected()
    finally:
        await db.disconnect()

if __name__ == "__main__":
    cli()
