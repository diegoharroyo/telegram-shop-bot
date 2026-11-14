"""Fill an empty Google Sheet with the demo bakery's data (all fictional).
Run once: uv run --env-file .env seed.py
It wipes the Products, FAQ and Orders tabs, so it refuses if Orders already has orders;
pass --force to wipe anyway."""

import os
import sys

import gspread

from sheet import ORDER_COLUMNS

TABS = {
    "Products": [
        ["name", "price", "stock"],
        ["Sourdough loaf", 6.50, 12],
        ["Baguette", 3.00, 20],
        ["Butter croissant", 2.50, 30],
        ["Cinnamon roll", 3.50, 15],
        ["Gluten-free loaf", 7.00, 4],
    ],
    "FAQ": [
        ["question", "answer", "keywords"],
        ["Opening hours", "We're open Mon–Sat 7:00–19:00, Sun 8:00–13:00.", "hour, open, close, sunday, open today"],
        ["Delivery", "Pickup only for now: order here and we'll tell you when it's ready.", "deliver, delivery, ship"],
        ["Allergens", ("Everything is baked in one kitchen. Our gluten-free loaf is made first thing "
                       "in the morning, but we can't guarantee zero traces."), "gluten, celiac, allergen, nut, vegan, dairy"],
        ["Payment", "Cash or card at pickup.", "pay, card, cash, payment"],
        # ties go to the first row, so order status sits above "where are you"
        ["Order status", ("We'll message you here the moment it's ready. If it's been a while, "
                          "type your question and the team will check."), "my order, order status, ready yet"],
        ["Thanks", "You're welcome! 🙂", "thank, thx"],
        ["Greeting", "Hi! Tap /menu to order, or ask me anything.", "hello, hey, good morning"],
        ["Location", "123 Example Street (this is a demo shop).", "address, location, find you, where are you"],
    ],
    "Orders": [ORDER_COLUMNS],
}

book = gspread.service_account(filename=os.environ["GOOGLE_CREDENTIALS"]).open_by_key(os.environ["SHEET_ID"])
titles = [ws.title for ws in book.worksheets()]
if "Orders" in titles and len(book.worksheet("Orders").col_values(1)) > 1 and "--force" not in sys.argv:
    sys.exit("Orders already has data; refusing to wipe this sheet. Use --force if you mean it.")
for title, rows in TABS.items():
    try:
        ws = book.worksheet(title)
        ws.clear()
    except gspread.WorksheetNotFound:
        ws = book.add_worksheet(title, rows=200, cols=len(rows[0]))
    ws.update(rows, "A1")
    ws.format("1:1", {"textFormat": {"bold": True}})
    ws.freeze(rows=1)
for ws in book.worksheets():
    if ws.title not in TABS:
        book.del_worksheet(ws)
print("Seeded", book.url)
