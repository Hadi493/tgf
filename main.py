import asyncio
import os
import sys
import tomllib
from dotenv import load_dotenv

load_dotenv()

from telethon import TelegramClient
from loguru import logger
import click

logger.add("bot.log", rotation="10 MB", level="DEBUG")

from db.storage import Database
from handlers.message import register_handlers, catch_up
from utils.folder import get_channels_from_folder

CONFIG_FILE = "config.toml"
SESSION_NAME = "session"

API_ID = os.getenv("TELEGRAM_API_ID") or sys.exit("Missing TELEGRAM_API_ID in .env")
API_HASH = os.getenv("TELEGRAM_API_HASH") or sys.exit("Missing TELEGRAM_API_HASH in .env")
PHONE = os.getenv("TELEGRAM_PHONE") or sys.exit("Missing TELEGRAM_PHONE in .env")

db = Database()

def load_config() -> dict:
    with open(CONFIG_FILE, "rb") as f:
        return tomllib.load(f)

def save_config(config: dict) -> None:
    import tomli_w
    with open(CONFIG_FILE, "wb") as f:
        tomli_w.dump(config, f)


@click.group()
def cli():
    pass

@cli.command(help="Add a source channel (username or ID).")
@click.argument("channel")
def add(channel: str) -> None:
    config = load_config()
    if channel not in config["source_channels"]["channels"]:
        config["source_channels"]["channels"].append(channel)
        save_config(config)
        click.echo(f"Added {channel} to source channels.")
    else:
        click.echo(f"{channel} is already in the list.")

@cli.command(help="Remove a source channel.")
@click.argument("channel")
def remove(channel: str) -> None:
    config = load_config()
    if channel in config["source_channels"]["channels"]:
        config["source_channels"]["channels"].remove(channel)
        save_config(config)
        click.echo(f"Removed {channel} from source channels.")
    else:
        click.echo(f"{channel} not found in the list.")

@cli.command(name="list", help="List all source channels.")
def list_channels() -> None:
    config = load_config()
    channels = config["source_channels"]["channels"]
    if not channels:
        click.echo("No source channels configured.")
    else:
        click.echo("Source Channels:")
        for c in channels:
            click.echo(f"  - {c}")

@cli.command(help="Start the Telegram aggregator userbot.")
def run() -> None:
    asyncio.run(main())

async def start_client() -> TelegramClient | None:
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start(phone=PHONE)

    me = await client.get_me()
    logger.info(f"Authorized as: {me.username or me.first_name} (ID: {me.id}, Bot: {me.bot})")

    if me.bot:
        logger.error("Logged in as a BOT. Userbots must use a user account. Delete session.session and retry.")
        return None

    return client

async def resolve_channels(client: TelegramClient, channels: list[str]) -> tuple[list[int], list[str]]:
    resolved: list[int] = []
    inactive: list[str] = []

    for channel in channels:
        try:
            entity = await client.get_entity(channel)
            resolved.append(entity.id)
        except Exception as e:
            logger.error(f"Could not resolve channel '{channel}': {e}")
            inactive.append(str(channel))

    return resolved, inactive


async def main() -> None:
    logger.info("Starting Telegram Aggregator...")

    await db.initialize()

    config = load_config()

    client = await start_client()
    if not client:
        return

    folder_input = config.get("source", {}).get("folder")
    
    resolved_channels: list[int] = []
    inactive_channels: list[str] = []

    if folder_input:
        target_folders = folder_input if isinstance(folder_input, list) else [folder_input]
        logger.info(f"Using Telegram folder(s): {target_folders}")
        
        for name in target_folders:
            try:
                channels = await get_channels_from_folder(client, name)
                if channels:
                    resolved_channels.extend(channels)
                    logger.info(f"Added {len(channels)} channels from folder: '{name}'")
                else:
                    logger.warning(f"No channels found in folder: '{name}'")
            except Exception as e:
                logger.error(f"Error processing folder '{name}': {e}")
        
        resolved_channels = list(set(resolved_channels))
        
    else:
        source_channels: list[str] = config.get("source_channels", {}).get("channels", [])
        if not source_channels:
            logger.warning("No source channels configured. Use 'add <channel>' or set a folder in config.toml.")
        
        resolved_channels, inactive_channels = await resolve_channels(client, source_channels)

    if not resolved_channels:
        logger.error("No active channels to listen to. Exiting.")
        return

    await catch_up(client, db, resolved_channels)
    await register_handlers(client, db, resolved_channels, resolved_channels, inactive_channels)

    logger.success(f"Userbot is running and listening to {len(resolved_channels)} channels.")
    await client.run_until_disconnected()


if __name__ == "__main__":
    try:
        import tomli_w
    except ImportError:
        logger.error("Missing dependency 'tomli_w'. Install it with: uv add tomli-w")
        sys.exit(1)

    cli()
