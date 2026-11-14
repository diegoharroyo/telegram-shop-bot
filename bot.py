"""Telegram bot for a small shop: menu and orders from a Google Sheet, FAQ answers,
hand-off to a human, and owner commands. Run: uv run --env-file .env bot.py"""

import logging
import os
from datetime import date

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import Forbidden
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

import shop
from sheet import Sheet

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger(__name__)

SHOP = "Crumb & Co."
QTYS = (1, 2, 3, 6)
OWNER = int(os.environ["OWNER_CHAT_ID"])
db = Sheet(os.environ["GOOGLE_CREDENTIALS"], os.environ["SHEET_ID"])
new_msg = filters.UpdateType.MESSAGE  # ignore edited messages, so an edit doesn't place or forward things twice
owner_only = new_msg & filters.Chat(OWNER)


def button(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, callback_data=data)  # Telegram caps data at 64 bytes, so names at ~55 chars


def menu_markup() -> InlineKeyboardMarkup | None:
    rows = [[button(f"{p['name']} · ${float(p['price']):.2f}", f"p:{p['name']}")]
            for p in db.products() if p["stock"] > 0]
    return InlineKeyboardMarkup(rows) if rows else None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        f"Hi! I'm the {SHOP} bot 🥐 (a demo bakery).\n"
        "Tap /menu to order today's bread for pickup.\n"
        'Or type a question, like "are you open Sunday?" or "can I pay by card?"'
    )
    if update.message.chat_id == OWNER:
        await update.message.reply_text(
            "Owner commands:\n"
            "/orders – what's left to prepare\n"
            "/stats – today's orders and revenue\n"
            "/add <name> <price> [stock] – new product\n"
            "To answer a customer, reply to their question message."
        )


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    markup = menu_markup()
    if not markup:
        await update.message.reply_text("We're sold out for today, sorry! Try again tomorrow.")
        return
    await update.message.reply_text("Today's menu. Tap an item to order:", reply_markup=markup)


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    kind, _, data = query.data.partition(":")

    if kind == "m":  # back to the menu
        markup = menu_markup()
        await query.edit_message_text("Today's menu. Tap an item to order:" if markup else "We're sold out, sorry!",
                                      reply_markup=markup)

    elif kind == "p":  # product picked -> ask quantity
        p = db.product(data)  # looked up by name: the owner may have edited the sheet since the menu was sent
        qtys = [n for n in QTYS if p and n <= p["stock"]]
        if not qtys:
            await query.edit_message_text("Sorry, that just sold out or changed. Tap /menu for what's left.")
            return
        await query.edit_message_text(
            f"How many {p['name']}? (${float(p['price']):.2f} each)",
            reply_markup=InlineKeyboardMarkup([[button(str(n), f"q:{n}:{p['name']}") for n in qtys],
                                               [button("« Menu", "m")]]),
        )

    elif kind == "q":  # quantity picked -> place order
        qty, _, name = data.partition(":")
        p, qty = db.product(name), int(qty)
        if qty not in QTYS:  # callback data comes from the client, don't trust it
            return
        if not p or qty > p["stock"]:
            left = p["stock"] if p else 0
            await query.edit_message_text(f"Only {left} {name} left. Tap /menu to pick again." if left else
                                          f"Sorry, {name} just sold out. Tap /menu for what's left.")
            return
        user = query.from_user
        order_id = db.place_order(user.id, user.full_name, p, qty)
        total = float(p["price"]) * qty
        await query.edit_message_text(
            f"✅ Order #{order_id} placed: {qty} × {p['name']} = ${total:.2f}\n"
            "Pay at pickup (cash or card). We'll message you here as soon as it's ready."
        )
        handle = f" (@{user.username})" if user.username else ""
        await context.bot.send_message(
            OWNER, f"🛎 New order #{order_id} from {user.full_name}{handle}: {qty} × {p['name']} (${total:.2f})",
            reply_markup=InlineKeyboardMarkup([[button("✅ Ready", f"r:{order_id}")]]),
        )

    elif kind == "r" and query.from_user.id == OWNER:  # owner marks order ready
        order = db.mark_ready(int(data))
        if order is None:
            await query.edit_message_text(query.message.text + "\n⚠️ Order not found in the sheet.")
            return
        if order["status"] == "ready":  # its other Ready button was already pressed
            await query.edit_message_text(query.message.text + "\n✅ Already marked ready.")
            return
        try:
            await context.bot.send_message(
                int(order["chat_id"]),
                f"🥖 Order #{order['id']} is ready: {order['qty']} × {order['product']}. See you soon!",
            )
            note = "✅ Ready, customer notified."
        except Forbidden:
            note = "✅ Ready, but the customer has blocked the bot, so they weren't notified."
        await query.edit_message_text(query.message.text + "\n" + note)


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.message
    if msg.chat_id == OWNER and msg.reply_to_message:  # owner answering a hand-off
        chat_id = shop.handoff_chat_id(msg.reply_to_message.text or "")
        if not chat_id:
            await msg.reply_text("To answer a customer, reply to their question message.")
            return
        try:
            await context.bot.send_message(chat_id, f"💬 {SHOP}: {msg.text}")
            await msg.reply_text("Sent ✔")
        except Forbidden:
            await msg.reply_text("Couldn't deliver: the customer has blocked the bot.")
        return

    # The owner's plain messages go through the customer flow too, so they can try the bot themselves.
    answer = shop.match_faq(msg.text, db.faq())
    if answer:
        await msg.reply_text(answer)
        return
    await context.bot.send_message(OWNER, shop.handoff_text(msg.from_user.full_name, msg.chat_id, msg.text))
    await msg.reply_text("I don't know that one yet, so I've sent it to the team. They'll reply right here in this chat.")


async def not_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("I can only read text for now. Type your question, or tap /menu to order.")


async def add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        name, price, stock = shop.parse_add(list(context.args))
    except ValueError as e:
        await update.message.reply_text(str(e))
        return
    db.add_product(name, price, stock)
    await update.message.reply_text(f"Added {name} at ${price:.2f} ({stock} in stock).")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(shop.stats(db.orders(), date.today()))


async def orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    open_ = [o for o in db.orders() if o["status"] != "ready"]
    if not open_:
        await update.message.reply_text("Nothing to prepare 🎉")
        return
    for o in open_:
        await update.message.reply_text(
            f"#{o['id']} {o['customer']}: {o['qty']} × {o['product']}",
            reply_markup=InlineKeyboardMarkup([[button("✅ Ready", f"r:{o['id']}")]]),
        )


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.error("Handler failed", exc_info=context.error)
    if isinstance(update, Update) and update.effective_chat:
        await context.bot.send_message(update.effective_chat.id, "Something went wrong on our side, please try again.")


def main() -> None:
    # Handlers run one at a time (python-telegram-bot's default), so order ids and stock can't race.
    # Don't turn on concurrent_updates without adding a lock around place_order.
    app = Application.builder().token(os.environ["TELEGRAM_BOT_TOKEN"]).build()
    app.add_handler(CommandHandler(["start", "help"], start, filters=new_msg))
    app.add_handler(CommandHandler("menu", menu, filters=new_msg))
    app.add_handler(CommandHandler("add", add, filters=owner_only))
    app.add_handler(CommandHandler("stats", stats, filters=owner_only))
    app.add_handler(CommandHandler("orders", orders, filters=owner_only))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(new_msg & filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(MessageHandler(new_msg & ~filters.TEXT & ~filters.COMMAND, not_text))
    app.add_error_handler(on_error)
    app.run_polling()


if __name__ == "__main__":
    main()
