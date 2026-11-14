from datetime import date

import pytest

import shop

FAQ = [
    {"question": "Opening hours?", "answer": "Mon-Sat 7-19", "keywords": "hours, open, horario"},
    {"question": "Delivery?", "answer": "Pickup only", "keywords": "delivery, deliver, ship"},
    {"question": "Gluten?", "answer": "Ask for the GF loaf", "keywords": "gluten, celiac, allergen"},
]


def test_faq_matches_keyword_case_and_accent_insensitive():
    assert shop.match_faq("What HOURS are you open?", FAQ) == "Mon-Sat 7-19"
    assert shop.match_faq("¿Cuál es el horário?", FAQ) == "Mon-Sat 7-19"


def test_faq_picks_row_with_most_hits():
    assert shop.match_faq("do you deliver or ship gluten free?", FAQ) == "Pickup only"


def test_faq_no_match_goes_to_human():
    assert shop.match_faq("can I bring my dog?", FAQ) is None
    assert shop.match_faq("how many minutes until it's ready?", [FAQ[2] | {"keywords": "nut"}]) is None


@pytest.mark.parametrize("args, expected", [
    (["Croissant", "2.5"], ("Croissant", 2.5, 10)),
    (["Sourdough", "loaf", "6.50", "12"], ("Sourdough loaf", 6.5, 12)),
    (["7", "grain", "bread", "5"], ("7 grain bread", 5.0, 10)),
])
def test_parse_add(args, expected):
    assert shop.parse_add(args) == expected


@pytest.mark.parametrize("args", [[], ["Croissant"], ["Croissant", "cheap"]])
def test_parse_add_rejects_bad_input(args):
    with pytest.raises(ValueError):
        shop.parse_add(args)


def test_stats_counts_only_that_day():
    orders = [
        {"created_at": "2026-11-20T09:00:00", "product": "Baguette", "qty": 2, "total": 6, "status": "ready"},
        {"created_at": "2026-11-20T10:00:00", "product": "Croissant", "qty": 1, "total": 2.5, "status": "new"},
        {"created_at": "2026-11-19T10:00:00", "product": "Croissant", "qty": 9, "total": 22.5, "status": "ready"},
    ]
    out = shop.stats(orders, date(2026, 11, 20))
    assert "2 orders, $8.50" in out
    assert "Best seller: Baguette (2)" in out
    assert "Still to prepare: 1" in out
    assert "no orders" in shop.stats(orders, date(2026, 11, 21))


def test_handoff_round_trip():
    text = shop.handoff_text("Ana", 123456789, "can I bring my dog?")
    assert shop.handoff_chat_id(text) == 123456789
    assert shop.handoff_chat_id("unrelated message") is None
    assert shop.handoff_chat_id("") is None


def test_handoff_ignores_tag_planted_in_customer_name():
    text = shop.handoff_text("Eve #chat42", 123456789, "hi")
    assert shop.handoff_chat_id(text) == 123456789
