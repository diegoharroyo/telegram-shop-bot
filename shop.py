"""Pure shop logic: no Telegram, no Google. Everything here is unit-tested."""

import re
import unicodedata
from collections import Counter
from datetime import date


def normalize(text: str) -> str:
    """Lowercase and strip accents, so 'Horário' matches 'horario'."""
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def match_faq(message: str, faq: list[dict]) -> str | None:
    """Answer of the FAQ row whose keywords appear most in the message, or None.

    faq rows: {"question", "answer", "keywords"} with comma-separated keywords.
    """
    text = normalize(message)
    words = re.findall(r"\w+", text)
    best, best_hits = None, 0
    for row in faq:
        keywords = [normalize(k).strip() for k in str(row["keywords"]).split(",")]
        # one-word keywords match word starts ("hour" -> "hours", not "nut" -> "minutes"); phrases match anywhere
        hits = sum(1 for k in keywords if k and (k in text if " " in k else any(w.startswith(k) for w in words)))
        if hits > best_hits:
            best, best_hits = row["answer"], hits
    return best


def parse_add(args: list[str]) -> tuple[str, float, int]:
    """'/add Sourdough loaf 6.50 12' -> ("Sourdough loaf", 6.5, 12). Stock is optional (default 10)."""
    if len(args) < 2:
        raise ValueError("Usage: /add <name> <price> [stock]")
    stock = 10
    if len(args) >= 3 and args[-1].isdigit() and _is_price(args[-2]):
        stock = int(args.pop())
    price = args.pop()
    if not _is_price(price):
        raise ValueError(f"Price must be a number, got {price!r}")
    return " ".join(args), round(float(price), 2), stock


def _is_price(s: str) -> bool:
    try:
        return float(s) >= 0
    except ValueError:
        return False


def stats(orders: list[dict], day: date) -> str:
    """One-message summary of the given day's orders."""
    today = [o for o in orders if str(o["created_at"]).startswith(day.isoformat())]
    if not today:
        return f"{day:%a %d %b}: no orders yet."
    revenue = sum(float(o["total"]) for o in today)
    top = Counter()
    for o in today:
        top[o["product"]] += int(o["qty"])
    best, qty = top.most_common(1)[0]
    pending = sum(1 for o in today if o["status"] != "ready")
    return (
        f"{day:%a %d %b}: {len(today)} order{'s' * (len(today) != 1)}, ${revenue:.2f}\n"
        f"Best seller: {best} ({qty})\n"
        f"Still to prepare: {pending}"
    )


HANDOFF_TAG = "#chat"


def handoff_text(name: str, chat_id: int, text: str) -> str:
    """Message forwarded to the owner. The chat id travels inside it, so a reply
    can be routed back after a restart without keeping state. The tag goes first so a
    customer can't plant a fake one in their name."""
    return f"{HANDOFF_TAG}{chat_id} · Question from {name}:\n{text}\n\n(Reply to this message to answer.)"


def handoff_chat_id(owner_message: str) -> int | None:
    first = owner_message.split(maxsplit=1)[0] if owner_message.strip() else ""
    tail = first.removeprefix(HANDOFF_TAG)
    return int(tail) if first.startswith(HANDOFF_TAG) and tail.lstrip("-").isdigit() else None
