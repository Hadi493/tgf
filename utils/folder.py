from telethon import TelegramClient
from telethon.tl.functions.messages import GetDialogFiltersRequest
from loguru import logger

async def get_channels_from_folder(client: TelegramClient, folder_name: str) -> list[int]:
    """Retrieves all channel IDs within a specific Telegram folder."""
    try:
        result = await client(GetDialogFiltersRequest())
    except Exception as e:
        logger.error(f"Failed to fetch dialog filters: {e}")
        return []

    for filter_obj in result.filters:
        # Check if the filter (folder) has the requested title
        if not hasattr(filter_obj, 'title') or filter_obj.title.text != folder_name:
            continue

        channel_ids = []
        for peer in filter_obj.include_peers:
            try:
                entity = await client.get_entity(peer)
                channel_ids.append(entity.id)
            except Exception as e:
                logger.warning(f"Failed to resolve peer {peer} in folder '{folder_name}': {e}")

        logger.info(f"Found {len(channel_ids)} channels in folder '{folder_name}'")
        return channel_ids

    logger.error(f"Folder '{folder_name}' was not found in your Telegram account.")
    return []
