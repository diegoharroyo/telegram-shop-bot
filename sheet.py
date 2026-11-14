"""Google Sheet as the shop's database: the owner edits products and FAQ by hand,
the bot appends orders. Three tabs: Products, FAQ, Orders."""

from datetime import datetime

import gspread
from gspread.utils import ValueRenderOption

ORDER_COLUMNS = ["id", "created_at", "chat_id", "customer", "product", "qty", "unit_price", "total", "status"]
RAW = ValueRenderOption.unformatted  # 6.5 instead of "$6.50" or "6,50", whatever the sheet's locale/format


class Sheet:
    # ponytail: every call hits the Sheets API (60 reads/min per user, retried on 429); cache if a shop outgrows that
    def __init__(self, credentials_file: str, sheet_id: str):
        book = gspread.service_account(filename=credentials_file, http_client=gspread.BackOffHTTPClient)
        self.tabs = {ws.title: ws for ws in book.open_by_key(sheet_id).worksheets()}

    def products(self) -> list[dict]:
        """Products with a name, each tagged with its sheet row; blank stock counts as 0."""
        rows = self.tabs["Products"].get_all_records(value_render_option=RAW)
        return [p | {"row": i + 2, "stock": int(p["stock"] or 0)} for i, p in enumerate(rows) if p["name"]]

    def product(self, name: str) -> dict | None:
        return next((p for p in self.products() if p["name"] == name), None)

    def faq(self) -> list[dict]:
        return self.tabs["FAQ"].get_all_records()

    def orders(self) -> list[dict]:
        return self.tabs["Orders"].get_all_records(value_render_option=RAW)

    def add_product(self, name: str, price: float, stock: int) -> None:
        self.tabs["Products"].append_row([name, price, stock])

    def place_order(self, chat_id: int, customer: str, product: dict, qty: int) -> int:
        """Append the order, take it out of stock, return its id."""
        tab = self.tabs["Orders"]
        ids = [int(v) for v in tab.col_values(1)[1:] if str(v).isdigit()]
        order_id = max(ids, default=0) + 1  # survives the owner deleting or sorting rows
        total = round(float(product["price"]) * qty, 2)
        row = [order_id, datetime.now().isoformat(timespec="seconds"), chat_id, customer,
               product["name"], qty, product["price"], total, "new"]
        tab.append_row(row)
        self.tabs["Products"].update_cell(product["row"], 3, product["stock"] - qty)
        return order_id

    def mark_ready(self, order_id: int) -> dict | None:
        """Set status to ready. Returns the order as it was before (None if not found),
        so the caller can skip re-notifying."""
        tab = self.tabs["Orders"]
        cell = tab.find(str(order_id), in_column=1)
        if cell is None:
            return None
        order = dict(zip(ORDER_COLUMNS, tab.row_values(cell.row)))
        if order["status"] != "ready":
            tab.update_cell(cell.row, ORDER_COLUMNS.index("status") + 1, "ready")
        return order
