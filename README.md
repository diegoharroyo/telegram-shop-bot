# Telegram shop bot

[![ci](https://github.com/diegoharroyo/telegram-shop-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/diegoharroyo/telegram-shop-bot/actions/workflows/ci.yml)

A Telegram bot for a small shop. Customers browse the menu, order for pickup and ask questions.
The owner runs everything from a Google Sheet and their own Telegram: no admin panel, no database, no server to expose.

![Demo: ordering, marking the order ready, and a FAQ answer](docs/demo.gif)

*Demo shop "Crumb & Co." is fictional. In the recording one account plays both customer and owner.*

## What it does

**For customers**
- `/menu` shows what's in stock, with prices. Tap an item, tap a quantity, done.
- They get a message when their order is ready.
- Questions like "are you open Sunday?" or "can I pay by card?" are answered from the FAQ tab.
- Anything the bot can't answer is forwarded to the owner, and the owner's reply comes back in the same chat.

**For the owner**
- A Telegram message for every new order, with a **Ready** button that notifies the customer.
- `/orders` lists what's left to prepare, `/stats` gives today's orders, revenue and best seller.
- `/add Cinnamon roll 3.50 15` adds a product without opening the sheet.
- Prices, stock, products and FAQ answers are edited directly in the sheet. The bot reads it live, no restart.

## The sheet

Three tabs. The bot creates them with `seed.py`; after that the owner edits them like any spreadsheet.

| Tab | Columns | Who writes it |
|---|---|---|
| Products | name, price, stock | owner (stock goes down with each order) |
| FAQ | question, answer, keywords | owner |
| Orders | id, created_at, chat_id, customer, product, qty, unit_price, total, status | bot (status → ready) |

A FAQ row answers when its keywords appear in the message, e.g. `hour, open, close, sunday`.

## Run it

You need [uv](https://docs.astral.sh/uv/), a Telegram bot token and a Google service account.

1. **Bot**: talk to [@BotFather](https://t.me/BotFather), `/newbot`, copy the token.
2. **Your chat id**: send `/start` to your new bot, open `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy `message.chat.id`.
3. **Google**: in Google Cloud, enable the Google Sheets API, create a service account and download its JSON key.
   Create an empty Google Sheet and share it (Editor) with the service account's email.
4. Copy `.env.example` to `.env` and fill it in.

Then:

```sh
uv sync
uv run --env-file .env seed.py   # fills the sheet with the demo bakery
uv run --env-file .env bot.py
```

The bot uses long polling, so it runs on any always-on machine (a VPS, a Raspberry Pi, a cheap cloud instance) without a public URL.

## Adapt it to your business

- Shop name and messages: the top of `bot.py`.
- Quantities offered: `QTYS` in `bot.py`.
- Menu, prices, stock and FAQ: just edit the sheet.

## Limits

- One product per order (no cart) and no online payment: customers pay at pickup.
- The FAQ is keyword matching, not AI. It only answers what's in the FAQ tab; everything else goes to the owner.
- Product names up to about 55 characters (Telegram limits button data to 64 bytes).
- Google Sheets allows about 60 reads per minute. That's plenty for a small shop; a busy one would want a cache or a real database.
- One owner account.

## Tests

```sh
uv run pytest
uv run ruff check .
```

The shop logic (FAQ matching, `/add` parsing, daily stats, hand-off routing) lives in `shop.py`, with no Telegram or Google calls, and is unit-tested. CI runs both commands on every push.

---

MIT license.
