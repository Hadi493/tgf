import asyncio
import os
import tomllib
from dotenv import load_dotenv

# Load config and environment first
load_dotenv()

from telethon import TelegramClient
from loguru import logger
import click

# Add file logging
logger.add("bot.log", rotation="10 MB", level="DEBUG")

from db.storage import Database
from handlers.message import register_handlers
CONFIG_FILE = "config.toml"

def load_config():
    with open(CONFIG_FILE, "rb") as f:
        return tomllib.load(f)

def save_config(config):
    import tomli_w
    with open(CONFIG_FILE, "wb") as f:
        tomli_w.dump(config, f)

# Telethon config
API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
PHONE = os.getenv("TELEGRAM_PHONE")
SESSION_NAME = "session"

db = Database()

@click.group()
def cli():
    pass

@cli.command()
@click.argument('channel')
def add(channel):
    """Add a source channel (username or ID)."""
    config = load_config()
    if channel not in config['source_channels']['channels']:
        config['source_channels']['channels'].append(channel)
        save_config(config)
        click.echo(f"Added {channel} to source channels.")
    else:
        click.echo(f"{channel} is already in the list.")

@cli.command()
@click.argument('channel')
def remove(channel):
    """Remove a source channel."""
    config = load_config()
    if channel in config['source_channels']['channels']:
        config['source_channels']['channels'].remove(channel)
        save_config(config)
        click.echo(f"Removed {channel} from source channels.")
    else:
        click.echo(f"{channel} not found in the list.")

@cli.command()
def list():
    """List all source channels."""
    config = load_config()
    channels = config['source_channels']['channels']
    if not channels:
        click.echo("No source channels configured.")
    else:
        click.echo("Source Channels:")
        for c in channels:
            click.echo(f"- {c}")

@cli.command()
def run():
    """Start the Telegram aggregator userbot."""
    asyncio.run(main())

async def main():
    logger.info("Starting Telegram Aggregator...")
    
    # 1. Initialize DB
    await db.initialize()
    
    # 2. Load Config
    config = load_config()
    source_channels = config['source_channels']['channels']
    
    if not source_channels:
        logger.warning("No source channels configured. Add some using 'python main.py add <channel>'.")

    # 3. Initialize Client
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start(phone=PHONE)
    
    # Check session type
    me = await client.get_me()
    logger.info(f"Authorized as: {me.username or me.first_name} (ID: {me.id}, Bot: {me.bot})")
    if me.bot:
        logger.error("Logged in as a BOT. Userbots MUST be a user account. Delete session.session and retry.")
        return
    
    # 4. Resolve source channels
    logger.info("Resolving source channels...")
    resolved_channels = []
    for channel in source_channels:
        try:
            entity = await client.get_entity(channel)
            resolved_channels.append(entity.id)
            logger.debug(f"Resolved source: {getattr(entity, 'title', 'Unknown')} ({entity.id})")
        except Exception as e:
            logger.error(f"Could not resolve source channel '{channel}': {e}")
    
    # 5. Register Handlers
    await register_handlers(client, db, resolved_channels)
    
    logger.success("Userbot is running and listening for messages.")
    await client.run_until_disconnected()

if __name__ == '__main__':
    # Add tomli_w to requirements if using CLI add/remove
    try:
        import tomli_w
    except ImportError:
        logger.error("Missing dependency 'tomli_w' for CLI config updates. Install it first.")
        exit(1)
        
    cli()
