# TgF — My Telegram Feed

I built `tgf` because I was tired of jumping between dozens of Telegram channels to stay updated. This is a simple tool that watches the channels i care about and forwards everything into one single "feed" channel/bot for me.

Think of it as an RSS reader, but for Telegram.

## Quick Start

   ```bash
   git clone https://github.com/Hadi493/tgf.git
   cd tgf
   ```

   Copy `.env.example` to `.env` and add your Telegram API details (you get these from [my.telegram.org](https://my.telegram.org)).

   Copy `config.toml.example` to `config.toml` and list the channels you want to follow.

## How to use it

If you have [uv](https://github.com/astral-sh/uv) installed (which I recommend), it's super easy:

- **Start the feed**: `uv run main.py run`
- **Add a channel**: `uv run main.py add channelsusername`
- **Remove a channel**: `uv run main.py remove channelsusername`
- **See what's being tracked**: `uv run main.py list`

## A few notes

- **Privacy**: Keep your `.env` file to yourself. It contains your login session.
- **Safety**: This uses your actual Telegram account (as a "userbot"). Don't go overboard with hundreds of channels or you might trigger Telegram's flood limits.
- **Logs**: If something goes wrong, check `bot.log`. It cleans itself up after 10MB.

*This is a personal project I use daily. Feel free to use it, but remember it's provided "as-is"!*
