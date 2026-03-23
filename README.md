# Telegram Channel Aggregator

A Telegram userbot built with Telethon to aggregate messages from multiple source channels into a single target channel in real-time.

## Features

- Real-time message aggregation across multiple channels.
- Automated filtering for messages with inline buttons or forwards.
- Message deduplication using SQLite and SHA-256 hashing.
- Automated labeling with source channel and timestamp.
- Support for photos, videos, documents, and polls.
- Command-line interface for managing source channels.
- Systemd service unit for background execution on Linux.

## Project Structure

- main.py: CLI entry point and bot logic.
- config.toml: Configuration for source channels.
- db/storage.py: SQLite handler for message deduplication.
- handlers/message.py: Message processing and filtering logic.
- utils/formatter.py: Message styling and content hashing.
- .env.example: Template for environment variables.

## Installation

1. Clone the repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy .env.example to .env and provide your API credentials:
   - TELEGRAM_API_ID
   - TELEGRAM_API_HASH
   - TELEGRAM_PHONE
   - TELEGRAM_AGGREGATOR_CHANNEL
4. Configure source channels:
   ```bash
   python main.py add <channel_username>
   ```
5. Start the aggregator:
   ```bash
   python main.py run
   ```

## Deployment

A systemd service file (telegram-aggregator.service) is provided. Configure the User and WorkingDirectory paths before use:

```bash
sudo cp telegram-aggregator.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now telegram-aggregator
```

## License
MIT
