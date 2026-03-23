# Telegram Channel Aggregator

A professional Telegram userbot built with [Telethon](https://github.com/LonamiWebs/Telethon) to aggregate messages from multiple source channels into a single private aggregator channel in real-time.

## Features

- 🚀 **Real-time Aggregation**: Listens to `NewMessage` events across multiple channels.
- 🛡️ **Ad Filtering**: Automatically filters out messages with inline buttons or forwards.
- 👯 **Deduplication**: Uses SQLite and SHA-256 hashing to prevent duplicate posts.
- 🏷️ **Smart Labeling**: Appends source channel names and timestamps to every message.
- 📁 **Media Support**: Handles photos, videos, documents, and polls seamlessly.
- 💻 **CLI Management**: Easily add, remove, or list source channels via the command line.
- 🛠️ **Systemd Integration**: Includes a service unit for reliable 24/7 operation on Linux.

## Project Structure

```text
telegram-aggregator/
├── main.py           # CLI entry point & bot logic
├── config.toml       # Source channels configuration
├── db/
│   └── storage.py    # SQLite deduplication handler
├── handlers/
│   └── message.py    # Core message processing & filtering
├── utils/
│   └── formatter.py  # Message styling & hashing
└── .env.example      # Environment variable template
```

## Setup & Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/telegram-aggregator.git
   cd telegram-aggregator
   ```

2. **Install dependencies (using `uv` or `pip`):**
   ```bash
   uv pip install -r requirements.txt
   # OR
   pip install -r requirements.txt
   ```

3. **Configure Environment:**
   Copy `.env.example` to `.env` and fill in your details:
   - `TELEGRAM_API_ID`: Get from [my.telegram.org](https://my.telegram.org)
   - `TELEGRAM_API_HASH`: Get from [my.telegram.org](https://my.telegram.org)
   - `TELEGRAM_PHONE`: Your international phone number (e.g., +123456789)
   - `TELEGRAM_AGGREGATOR_CHANNEL`: Target channel username or ID

4. **Manage Channels:**
   ```bash
   python main.py add <channel_username>
   python main.py list
   ```

5. **Run the Aggregator:**
   ```bash
   python main.py run
   ```

## Deployment

A `telegram-aggregator.service` file is provided for deployment as a systemd service. Update the `User` and `WorkingDirectory` paths in the file before enabling:

```bash
sudo cp telegram-aggregator.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now telegram-aggregator
```

## License
MIT
