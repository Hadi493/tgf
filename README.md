# tgf — My Telegram Feed

I built `tgf` because I was tired of jumping between dozens of Telegram channels to stay updated. This is a simple tool that watches the channels i care about and forwards everything into one single "feed" channel/bot for me.

Think of it as an RSS reader, but for Telegram.

## Quick Start

```bash
git clone https://github.com/Hadi493/tgf.git
cd tgf
```

   Copy `.env.example` to `.env` and add your Telegram API details (you get these from [my.telegram.org](https://my.telegram.org)).
```bash
cp .env.example .env
```
Copy `config.toml.example` to `config.toml` and list the channels you want to follow.
```bash
cp config.toml.example config.toml
```

## How to use it

If you have [uv](https://github.com/astral-sh/uv) installed (which I recommend), it's super easy:

- **Start the feed**: 
```bash
uv run main.py run
```
- **Add a channel**: 
```bash
uv run main.py add channelsusername
```
- **Remove a channel**: 
```bash
uv run main.py remove channelsusername
```
- **See what's being tracked**: 
```bash
uv run main.py list
```

*This is a personal project I use daily. Feel free to use it, but remember it's provided "as-is"!*
