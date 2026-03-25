# tgf — Telegram Feed

A Telegram userbot that aggregates messages from multiple channels into a single target channel in real time.

> ⚠️ **Personal Project** — This is built for personal use. Use it responsibly and at your own risk.

## How it works

tgf logs into your Telegram account using [Telethon](https://github.com/LonamiWebs/Telethon) (MTProto), listens to new messages from your configured source channels, and forwards them to one aggregator channel/bot — giving you a single feed for everything.

## Requirements

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- A Telegram account with `api_id` and `api_hash` from [my.telegram.org](https://my.telegram.org)

## Setup

```bash
git clone https://github.com/Hadi493/tgf.git
cd tgf

cp .env.example .env
# Fill in your TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE

cp config.toml.example config.toml
# Add your source channels
```

## Usage

```bash
# Run the userbot
uv run main.py run

# Manage channels
uv run main.py add @channelusername
uv run main.py remove @channelusername
uv run main.py list
```
## Config example

```toml
[source_channels]
channels = ["@channel1", "@channel2"]
```

## Notes

- Keep your `.env` file private and never push it to GitHub.
- Logs are written to `bot.log` with rotation at 10 MB.
