from telethon import TelegramClient
from telethon.tl.functions.messages import GetDialogFiltersRequest
from loguru import logger

async def get_channels_from_folder(client: TelegramClient, folder_name: str) -> list[int]:
    result = await client(GetDialogFiltersRequest())

    for f in result.filters:
        if not hasattr(f, 'title') or f.title.text != folder_name:
            continue

        ids = []
        for peer in f.include_peers:
            try:
                entity = await client.get_entity(peer)
                ids.append(entity.id)
            except Exception as e:
                logger.warning(f"Could not resolve peer {peer}: {e}")

        logger.info(f"Resolved {len(ids)} channels from folder '{folder_name}'")
        return ids

    logger.error(f"Folder '{folder_name}' not found.")
    return []
