import asyncio
import os
import tomllib
from dotenv import load_dotenv

load_dotenv()

from telethon import TelegramClient
from loguru import logger
import click

logger.add("bot.log", rotation="10 MB", level="DEBUG")

from db.storage import Database
from handlers.message import register_handlers, catch_up
CONFIG_FILE = "config.toml"

def load_config():
    with open(CONFIG_FILE, "rb") as f:
        return tomllib.load(f)

def save_config(config):
    import tomli_w
    with open(CONFIG_FILE, "wb") as f:
        tomli_w.dump(config, f)

API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
PHONE = os.getenv("TELEGRAM_PHONE")
SESSION_NAME = "session"

db = Database()

@click.group()
def cli():
    pass

@cli.command(help="Add a source channel (username or ID).")
@click.argument('channel')
def add(channel):
    config = load_config()
    if channel not in config['source_channels']['channels']:
        config['source_channels']['channels'].append(channel)
        save_config(config)
        click.echo(f"Added {channel} to source channels.")
    else:
        click.echo(f"{channel} is already in the list.")

@cli.command(help="Remove a source channel.")
@click.argument('channel')
def remove(channel):
    config = load_config()
    if channel in config['source_channels']['channels']:
        config['source_channels']['channels'].remove(channel)
        save_config(config)
        click.echo(f"Removed {channel} from source channels.")
    else:
        click.echo(f"{channel} not found in the list.")

@cli.command(help="List all source channels.")
def list():
    config = load_config()
    channels = config['source_channels']['channels']
    if not channels:
        click.echo("No source channels configured.")
    else:
        click.echo("Source Channels:")
        for c in channels:
            click.echo(f"- {c}")

@cli.command(help="Start the Telegram aggregator userbot.")
def run():
    asyncio.run(main())

async def initialize_database():
    await db.initialize()

def load_configuration():
    config = load_config()
    source_channels = config['source_channels']['channels']
    if not source_channels:
        logger.warning("No source channels configured. Add some using 'python main.py add <channel>'.")
    return source_channels

async def start_client():
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start(phone=PHONE)
    
    me = await client.get_me()
    logger.info(f"Authorized as: {me.username or me.first_name} (ID: {me.id}, Bot: {me.bot})")
    if me.bot:
        logger.error("Logged in as a BOT. Userbots MUST be a user account. Delete session.session and retry.")
        return None
    return client

async def resolve_channels(client, source_channels):
    resolved_channels = []
    inactive_channels = []
    for channel in source_channels:
        try:
            entity = await client.get_entity(channel)
            resolved_channels.append(entity.id)
        except Exception as e:
            logger.error(f"Could not resolve source channel '{channel}': {e}")
            inactive_channels.append(str(channel))
    return resolved_channels, inactive_channels

async def main():
    logger.info("Starting Telegram Aggregator...")
    
    await initialize_database()
    
    source_channels = load_configuration()
    
    client = await start_client()
    if not client:
        return
    
    resolved_channels, inactive_channels = await resolve_channels(client, source_channels)
    
    await catch_up(client, db, resolved_channels)
    
    await register_handlers(client, db, source_channels, resolved_channels, inactive_channels)
    
    logger.success("Userbot is running and listening for messages.")
    await client.run_until_disconnected()

if __name__ == '__main__':
    try:
        import tomli_w
    except ImportError:
        logger.error("Missing dependency 'tomli_w' for CLI config updates. Install it first.")
        exit(1)
        
    cli()
