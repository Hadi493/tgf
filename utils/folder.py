from telethon import TelegramClient
from telethon.tl.functions.messages import GetDialogFiltersRequest
from loguru import logger

async def get_channels_from_folder(client: TelegramClient, folder_name: str) -> list[int]:
    result = await client(GetDialogFiltersRequest())

    for filter_obj in result.filters:
        if not hasattr(filter_obj, 'title') or filter_obj.title.text != folder_name:
            continue

        ids = []
        for peer in filter_obj.include_peers:
            try:
                entity = await client.get_entity(peer)
                ids.append(entity.id)
            except Exception as e:
                logger.warning(f"Failed to resolve {peer}: {e}")

        logger.info(f"Found {len(ids)} channels in '{folder_name}'")
        return ids

    logger.error(f"Folder '{folder_name}' not found")
    return []
