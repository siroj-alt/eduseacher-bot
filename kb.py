"""Tugmalar (klaviaturalar)."""
import os
from typing import Optional
from urllib.parse import quote

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

import fmt

WEB_APP_URL = os.getenv("WEB_APP_URL", "https://edusearcher.uz")
BOT_USERNAME = (os.getenv("BOT_USERNAME") or "edusearcherbot").lstrip("@")

BTN_FIND = "🔍 Markaz topish"
BTN_NEAR = "📍 Yaqin markazlar"
BTN_REGIONS = "🏢 Markazlar"
BTN_CATS = "📚 Yo'nalishlar"
BTN_FAV = "⭐ Saqlanganlar"
BTN_LEADS = "📝 Arizalarim"
BTN_SHARE = "📤 Do'stlarga ulashish"
BTN_PROFILE = "👤 Profil"
BTN_SITE = "🌐 Saytni ochish"
BTN_ABOUT = "ℹ️ Sayt haqida"
BTN_CANCEL = "❌ Bekor qilish"

MENU_BUTTONS = {BTN_FIND, BTN_NEAR, BTN_REGIONS, BTN_CATS, BTN_FAV, BTN_LEADS,
                BTN_SHARE, BTN_PROFILE, BTN_ABOUT, BTN_CANCEL}


def ib(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def rows_of(buttons: list, per_row: int) -> list:
    return [buttons[i:i + per_row] for i in range(0, len(buttons), per_row)]


# ---------- asosiy menyu ----------
def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_FIND), KeyboardButton(text=BTN_NEAR)],
            [KeyboardButton(text=BTN_REGIONS), KeyboardButton(text=BTN_CATS)],
            [KeyboardButton(text=BTN_FAV), KeyboardButton(text=BTN_LEADS)],
            [KeyboardButton(text=BTN_SHARE), KeyboardButton(text=BTN_PROFILE)],
            [KeyboardButton(text=BTN_SITE, web_app=WebAppInfo(url=WEB_APP_URL)),
             KeyboardButton(text=BTN_ABOUT)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Markaz nomini yozing yoki menyudan tanlang…",
    )


def location_request() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Joylashuvni yuborish", request_location=True)],
            [KeyboardButton(text=BTN_CANCEL)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def phone_request(saved: Optional[str] = None) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text="📞 Raqamimni yuborish", request_contact=True)]]
    if saved:
        rows.insert(0, [KeyboardButton(text=f"✅ {saved}")])
    rows.append([KeyboardButton(text=BTN_CANCEL)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, one_time_keyboard=True)


def cancel_only() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=BTN_CANCEL)]], resize_keyboard=True)


# ---------- tanlash ro'yxatlari ----------
def categories(cats: list, prefix: str, all_label: Optional[str] = None) -> InlineKeyboardMarkup:
    buttons = [ib(name, f"{prefix}:{cid}") for cid, name in cats]
    rows = [[ib(all_label, f"{prefix}:0")]] if all_label else []
    rows += rows_of(buttons, 2)
    rows.append([ib("🏠 Menyu", "home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def levels(cat: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [ib("🌱 Boshlang'ich", f"lvl:{cat}:b"), ib("📘 O'rta", f"lvl:{cat}:i")],
        [ib("🚀 Yuqori", f"lvl:{cat}:a"), ib("♾ Farqi yo'q", f"lvl:{cat}:x")],
        [ib("⬅️ Yo'nalishlar", "new"), ib("🏠 Menyu", "home")],
    ])


def places(cat: int, lvl: str, regs: list) -> InlineKeyboardMarkup:
    rows = [
        [ib("📍 Joylashuvim bo'yicha (eng yaqin)", f"fl:{cat}:{lvl}")],
        [ib("🇺🇿 Butun O'zbekiston", f"fr:{cat}:{lvl}:0")],
    ]
    rows += rows_of([ib(name, f"fr:{cat}:{lvl}:{rid}") for rid, name in regs], 2)
    rows.append([ib("⬅️ Orqaga", f"cat:{cat}"), ib("🏠 Menyu", "home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def regions(regs: list) -> InlineKeyboardMarkup:
    rows = [[ib("🇺🇿 Barcha viloyatlar", "rg:0")]]
    rows += rows_of([ib(name, f"rg:{rid}") for rid, name in regs], 2)
    rows.append([ib("🏠 Menyu", "home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------- natijalar ro'yxati ----------
def results(items: list, page: int, total: int, qd: dict) -> InlineKeyboardMarkup:
    rows = []
    for i, it in enumerate(items, start=page * fmt.PAGE_SIZE + 1):
        label = f"{i}. {fmt.clip(it.get('name'), 36)}"
        r = fmt.fmt_rating(it.get("rating"))
        if r:
            label += f" · {r}"
        rows.append([ib(label, f"c:{it['id']}")])
    pages = max(1, -(-total // fmt.PAGE_SIZE))
    if pages > 1:
        nav = []
        if page > 0:
            nav.append(ib("⬅️ Oldingi", f"pg:{page - 1}"))
        nav.append(ib(f"{page + 1}/{pages}", "noop"))
        if page < pages - 1:
            nav.append(ib("Keyingi ➡️", f"pg:{page + 1}"))
        rows.append(nav)
    extra = []
    if qd.get("k") == "near":
        extra.append(ib("📚 Yo'nalish bo'yicha", "nccat"))
        extra.append(ib("🔄 Joylashuv", "updloc"))
    else:
        extra.append(ib("🔁 Yangi qidiruv", "new"))
    rows.append(extra)
    rows.append([ib("🏠 Menyu", "home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------- markaz kartochkasi ----------
def card(card_data: dict, saved: bool) -> InlineKeyboardMarkup:
    cid = card_data["id"]
    share_link = f"https://t.me/{BOT_USERNAME}?start=c_{cid}"
    share_text = f"{card_data.get('name', 'Markaz')} — EduSearcher.uz"
    share_url = f"https://t.me/share/url?url={quote(share_link, safe='')}&text={quote(share_text, safe='')}"
    rows = [
        [ib("📝 Ariza qoldirish", f"ap:{cid}"),
         ib("✅ Saqlangan" if saved else "⭐ Saqlash", f"fv:{cid}")],
        [ib("🧭 Yo'nalish (xarita)", f"rt:{cid}"), ib("💬 Sharh yozish", f"rv:{cid}")],
    ]
    links = []
    tg = fmt.telegram_url(card_data.get("telegram"))
    web = fmt.website_url(card_data.get("website"))
    ig = fmt.instagram_url(card_data.get("instagram"))
    if tg:
        links.append(InlineKeyboardButton(text="✈️ Telegram", url=tg))
    if web:
        links.append(InlineKeyboardButton(text="🌐 Veb-sayt", url=web))
    if ig:
        links.append(InlineKeyboardButton(text="📷 Instagram", url=ig))
    if links:
        rows.append(links)
    rows.append([InlineKeyboardButton(text="📤 Ulashish", url=share_url)])
    rows.append([ib("⬅️ Natijalarga", "bk"), ib("🏠 Menyu", "home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------- ariza / sharh ----------
def lead_courses(names: list) -> InlineKeyboardMarkup:
    rows = [[ib(fmt.clip(n, 55), f"apc:{i}")] for i, n in enumerate(names)]
    rows.append([ib("📋 Umumiy ariza (kurs tanlamayman)", "apc:-1")])
    rows.append([ib("❌ Bekor qilish", "cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def use_name(name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [ib(f"✅ {fmt.clip(name, 40)}", "apn:ok")],
        [ib("❌ Bekor qilish", "cancel")],
    ])


def skip_cancel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [ib("⏭ O'tkazib yuborish", "skip")],
        [ib("❌ Bekor qilish", "cancel")],
    ])


def stars() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [ib("⭐" * n, f"st:{n}") for n in (1, 2, 3)],
        [ib("⭐" * n, f"st:{n}") for n in (4, 5)],
        [ib("❌ Bekor qilish", "cancel")],
    ])


# ---------- profil, ulashish, boshqalar ----------
def profile() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [ib("✏️ Ismni o'zgartirish", "pe:name"), ib("📞 Telefon", "pe:phone")],
        [ib("📍 Joylashuvni yangilash", "pe:loc"), ib("🗑 Joylashuvni o'chirish", "pe:delloc")],
        [ib("🏠 Menyu", "home")],
    ])


def favorites(items: list) -> InlineKeyboardMarkup:
    rows = []
    for it in items[:30]:
        label = fmt.clip(it.get("name"), 40)
        r = fmt.fmt_rating(it.get("rating"))
        rows.append([ib(f"{label}" + (f" · {r}" if r else ""), f"c:{it['id']}")])
    rows.append([ib("🏠 Menyu", "home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def my_leads(items: list) -> InlineKeyboardMarkup:
    rows = []
    seen = set()
    for it in items[:8]:
        cid = it.get("center_id")
        if cid and cid not in seen:
            seen.add(cid)
            rows.append([ib(fmt.clip(it.get("center"), 50), f"c:{cid}")])
    rows.append([ib("🏠 Menyu", "home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def share(link: str, announcement: str) -> InlineKeyboardMarkup:
    url = f"https://t.me/share/url?url={quote(link, safe='')}&text={quote(announcement, safe='')}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📨 Do'stga yuborish", url=url)],
    ])


def open_site() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Platformani ochish", web_app=WebAppInfo(url=WEB_APP_URL))],
        [ib("🔍 Markaz topish", "new")],
    ])
