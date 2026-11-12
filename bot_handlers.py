"""EduSearcher Telegram boti — edusearcher.uz saytining imkoniyatlari bot ichida.

Qidiruv, yaqin markazlar, markaz kartochkasi, ariza, sharh, saqlanganlar, profil, referal.
Ma'lumotlar sayt bilan bir xil Supabase bazasidan olinadi (db.py).
"""
import logging
import os
import re
import time
from typing import Optional

from aiogram import BaseMiddleware, Bot, Dispatcher, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    CallbackQuery,
    ErrorEvent,
    InlineKeyboardMarkup,
    Message,
    Update,
)

import fmt
import kb
from db import DB, DBError
from fmt import esc
from kb import BOT_USERNAME, WEB_APP_URL

log = logging.getLogger("bot")

ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "").strip()
STEP_TTL = 30 * 60  # bajarilmay qolgan qadam 30 daqiqadan keyin eskiradi
UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

LAST_ERRORS: list = []  # selftest uchun
ERROR_COUNT = {"n": 0}

dp = Dispatcher()


# =====================================================================
# Kontekst (har bir update uchun foydalanuvchi + seans)
# =====================================================================
class CtxMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Update, data: dict):
        db: Optional[DB] = data.get("db")
        user = data.get("event_from_user")
        u = {"session": {}, "tg_id": user.id if user else 0}
        if db and user and not user.is_bot:
            ref = None
            msg = event.message
            if msg and msg.text and msg.text.startswith("/start"):
                parts = msg.text.split(maxsplit=1)
                if len(parts) == 2 and parts[1].startswith("ref_") and parts[1][4:].isdigit():
                    ref = int(parts[1][4:])
            try:
                u = await db.ctx(user.id, user.first_name, user.username, ref)
            except DBError:
                log.exception("Foydalanuvchi kontekstini olib bo'lmadi")
        data["u"] = u
        return await handler(event, data)


dp.update.outer_middleware(CtxMiddleware())


# =====================================================================
# Yordamchilar
# =====================================================================
def sess(u: dict) -> dict:
    s = u.get("session")
    if not isinstance(s, dict):
        s = {}
        u["session"] = s
    return s


def set_step(u: dict, step: Optional[str]) -> None:
    s = sess(u)
    s["step"] = step
    s["step_ts"] = int(time.time())


def current_step(u: dict) -> Optional[str]:
    s = sess(u)
    step = s.get("step")
    if step and int(time.time()) - int(s.get("step_ts") or 0) > STEP_TTL:
        return None
    return step


def reset_flow(u: dict) -> None:
    s = sess(u)
    for key in ("step", "step_ts", "pending", "lead", "rv"):
        s.pop(key, None)


async def save(db: DB, u: dict) -> None:
    try:
        await db.set_session(u["tg_id"], sess(u))
    except DBError:
        log.exception("Seansni saqlab bo'lmadi")


async def reply(event, text: str, markup=None) -> None:
    """Yangi xabar yuboradi. Message ham, CallbackQuery ham (eski/kirish imkonsiz xabar bo'lsa ham) ishlaydi."""
    if isinstance(event, CallbackQuery):
        await event.bot.send_message(chat_id=event.from_user.id, text=text, reply_markup=markup,
                                     parse_mode="HTML", disable_web_page_preview=True)
    else:
        await event.answer(text, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)


async def respond(event, text: str, markup=None, edit: bool = True) -> None:
    """Callbackdan kelsa xabarni tahrirlaydi (iloji bo'lmasa yangisini yuboradi), aks holda yangi xabar yuboradi."""
    if (isinstance(event, CallbackQuery) and edit and isinstance(event.message, Message)
            and (markup is None or isinstance(markup, InlineKeyboardMarkup))):
        try:
            await event.message.edit_text(text, reply_markup=markup, parse_mode="HTML",
                                          disable_web_page_preview=True)
            return
        except TelegramBadRequest as exc:
            if "not modified" in str(exc):
                return
    await reply(event, text, markup)


async def send(event, text: str, markup=None) -> None:
    """Doim yangi xabar yuboradi."""
    await reply(event, text, markup)


async def safe_send(bot: Bot, chat_id, text: str) -> None:
    try:
        await bot.send_message(chat_id, text, parse_mode="HTML")
    except Exception:  # bloklagan foydalanuvchi va h.k.
        log.warning("Xabar yuborilmadi: %s", chat_id)


def menu_text() -> str:
    return "🏠 <b>Bosh menyu</b>\n\nPastdagi tugmalardan tanlang yoki markaz nomini yozib qidiring."


# =====================================================================
# Ro'yxatlar va kartochka
# =====================================================================
async def show_list(event, db: DB, u: dict, qd: dict, page: int = 0) -> None:
    cats, regs = await db.categories(), await db.regions()
    lat = lng = None
    if qd.get("near"):
        lat, lng = u.get("lat"), u.get("lng")
    kwargs = dict(
        region=qd.get("reg") or None, category=qd.get("cat") or None,
        level=fmt.LEVEL_CODES.get(qd.get("lvl")), q=qd.get("q"), lat=lat, lng=lng,
        limit=fmt.PAGE_SIZE,
    )
    data = await db.list_centers(offset=page * fmt.PAGE_SIZE, **kwargs)
    if not data["items"] and page > 0:
        page = 0
        data = await db.list_centers(offset=0, **kwargs)
    qd = {**qd, "page": page}
    s = sess(u)
    s["last"] = qd
    reset_flow(u)
    await save(db, u)
    text = fmt.render_list(qd, data, page, dict(cats), dict(regs))
    await respond(event, text, kb.results(data["items"], page, data["total"], qd))


async def show_card(event, db: DB, u: dict, center_id: str) -> None:
    card = await db.center_card(u["tg_id"], center_id)
    if not card:
        await respond(event, "Markaz topilmadi. U o'chirilgan bo'lishi mumkin.",
                      InlineKeyboardMarkup(inline_keyboard=[[kb.ib("🏠 Menyu", "home")]]))
        return
    await respond(event, fmt.render_card(card, u.get("lat"), u.get("lng")),
                  kb.card(card, bool(card.get("fav"))))


async def ask_location(event, db: DB, u: dict, pending: dict) -> None:
    set_step(u, "await_loc")
    sess(u)["pending"] = pending
    await save(db, u)
    await send(
        event,
        "📍 Sizga eng yaqin markazlarni topish uchun joylashuvingizni yuboring.\n\n"
        "Pastdagi tugmani bosing. Joylashuv faqat masofani hisoblash uchun ishlatiladi va "
        "profilingizdan istalgan vaqtda o'chirib tashlanadi.",
        kb.location_request(),
    )


async def go_home(event, u: dict, db: DB, text: Optional[str] = None) -> None:
    reset_flow(u)
    await save(db, u)
    await send(event, text or menu_text(), kb.main_menu())


# =====================================================================
# Buyruqlar va menyu
# =====================================================================
@dp.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, db: DB, u: dict, bot: Bot):
    name = message.from_user.first_name if message.from_user else "do'st"
    args = (command.args or "").strip()
    reset_flow(u)
    await save(db, u)

    if u.get("is_new") and u.get("referred_by"):
        await safe_send(bot, u["referred_by"], f"🎉 Sizning havolangiz orqali <b>{esc(name)}</b> botga qo'shildi!")

    if args.startswith("c_") and UUID_RE.match(args[2:]):
        await message.answer("👋 Xush kelibsiz!", reply_markup=kb.main_menu())
        await show_card(message, db, u, args[2:])
        return

    text = (
        f"👋 Salom, <b>{esc(name)}</b>!\n\n"
        "<b>EduSearcher.uz</b> rasmiy botiga xush kelibsiz! 🎓\n"
        "O'zbekistondagi o'quv markazlari va kurslarni shu yerning o'zida toping:\n\n"
        "🔍 yo'nalish, daraja va hudud bo'yicha qidirish\n"
        "📍 sizga eng yaqin markazlar\n"
        "📝 ariza qoldirish va ⭐ saqlab qo'yish\n"
        "💬 sharh yozish\n\n"
        "Markaz nomini yozsangiz ham qidiraman."
    )
    if args.startswith("ref_"):
        text += "\n\n🤝 Sizni do'stingiz taklif qildi — xush kelibsiz!"
    await message.answer(text, parse_mode="HTML", reply_markup=kb.main_menu())


@dp.message(Command("menu"))
async def cmd_menu(message: Message, db: DB, u: dict):
    await go_home(message, u, db)


@dp.message(Command("cancel"))
@dp.message(F.text == kb.BTN_CANCEL)
async def cmd_cancel(message: Message, db: DB, u: dict):
    await go_home(message, u, db, "Bekor qilindi. 🏠 Bosh menyu")


HELP_TEXT = (
    "❓ <b>Yordam</b>\n\n"
    "🔍 <b>Markaz topish</b> — yo'nalish → daraja → hudud tanlang.\n"
    "📍 <b>Yaqin markazlar</b> — joylashuvingizga eng yaqin markazlar.\n"
    "🏢 <b>Markazlar</b> — viloyat bo'yicha ko'rish.\n"
    "📚 <b>Yo'nalishlar</b> — fan/kurs bo'yicha ko'rish.\n"
    "⭐ <b>Saqlanganlar</b> — saqlab qo'ygan markazlaringiz.\n"
    "📝 <b>Arizalarim</b> — yuborgan arizalaringiz holati.\n"
    "📤 <b>Do'stlarga ulashish</b> — taklif havolangiz.\n\n"
    "Markaz nomini yozing — men topaman. Jarayonni to'xtatish: /cancel\n"
    "Muammo yoki takliflar: @sirojshukrullayev"
)


@dp.message(Command("help"))
async def cmd_help(message: Message, db: DB, u: dict):
    await message.answer(HELP_TEXT, parse_mode="HTML", reply_markup=kb.main_menu())


@dp.message(Command("about"))
@dp.message(F.text == kb.BTN_ABOUT)
async def cmd_about(message: Message, db: DB, u: dict):
    reset_flow(u)
    await save(db, u)
    try:
        st = await db.stats()
    except DBError:
        st = {}
    stats_line = ""
    if st:
        stats_line = (
            f"\n\n📊 <b>{st.get('centers', 0)}</b> ta markaz · <b>{st.get('branches', 0)}</b> ta filial · "
            f"<b>{st.get('courses', 0)}</b> ta kurs · <b>{st.get('regions', 0)}</b> ta hudud · "
            f"<b>{st.get('categories', 0)}</b> ta yo'nalish"
        )
    await message.answer(
        "ℹ️ <b>EduSearcher.uz</b> — o'quv markazlarini kurs, daraja va joylashuv bo'yicha "
        "topish platformasi." + stats_line + "\n\nSaytdagi imkoniyatlar bot ichida ham mavjud."
        "\n\n" + HELP_TEXT.split("\n\n", 1)[1],
        parse_mode="HTML", reply_markup=kb.open_site(),
    )


# ---------- qidiruv menyulari ----------
@dp.message(Command("find"))
@dp.message(F.text == kb.BTN_FIND)
async def menu_find(message: Message, db: DB, u: dict):
    reset_flow(u)
    await save(db, u)
    cats = await db.categories()
    await message.answer("🔍 <b>Markaz topish</b>\n\nQaysi yo'nalish kerak?", parse_mode="HTML",
                         reply_markup=kb.categories(cats, "cat"))


@dp.message(Command("near"))
@dp.message(F.text == kb.BTN_NEAR)
async def menu_near(message: Message, db: DB, u: dict):
    reset_flow(u)
    if u.get("lat") is not None and u.get("lng") is not None:
        await show_list(message, db, u, {"k": "near", "cat": None, "near": True})
    else:
        await ask_location(message, db, u, {"k": "near", "cat": None})


@dp.message(F.text == kb.BTN_REGIONS)
async def menu_regions(message: Message, db: DB, u: dict):
    reset_flow(u)
    await save(db, u)
    regs = await db.regions()
    await message.answer("🏢 <b>Markazlar</b>\n\nViloyatni tanlang:", parse_mode="HTML",
                         reply_markup=kb.regions(regs))


@dp.message(F.text == kb.BTN_CATS)
async def menu_cats(message: Message, db: DB, u: dict):
    reset_flow(u)
    await save(db, u)
    cats = await db.categories()
    await message.answer("📚 <b>Yo'nalishlar</b>\n\nQaysi fan yoki kurs qiziq?", parse_mode="HTML",
                         reply_markup=kb.categories(cats, "bc"))


# ---------- saqlanganlar, arizalar ----------
@dp.message(Command("saved"))
@dp.message(F.text == kb.BTN_FAV)
async def menu_fav(message: Message, db: DB, u: dict):
    reset_flow(u)
    await save(db, u)
    items = await db.favorites(u["tg_id"])
    if not items:
        await message.answer("⭐ Hali hech narsa saqlamagansiz.\n\nMarkaz kartochkasidagi «⭐ Saqlash» "
                             "tugmasini bosing.", reply_markup=kb.main_menu())
        return
    await message.answer(f"⭐ <b>Saqlanganlar</b> ({len(items)})", parse_mode="HTML",
                         reply_markup=kb.favorites(items))


@dp.message(Command("applications"))
@dp.message(F.text == kb.BTN_LEADS)
async def menu_leads(message: Message, db: DB, u: dict):
    reset_flow(u)
    await save(db, u)
    items = await db.my_leads(u["tg_id"])
    if not items:
        await message.answer("📝 Hali ariza yubormagansiz.\n\nMarkaz kartochkasidagi «📝 Ariza qoldirish» "
                             "tugmasini bosing.", reply_markup=kb.main_menu())
        return
    lines = ["📝 <b>Arizalarim</b>\n"]
    for it in items:
        course = f" · {esc(fmt.clip(it.get('course'), 40))}" if it.get("course") else ""
        lines.append(f"<b>{esc(fmt.clip(it.get('center'), 50))}</b>{course}\n"
                     f"{fmt.lead_status(it.get('status'))} · {fmt.short_date(it.get('created_at'))}")
    lines.append("\nMarkaz sizga yuborgan raqamingiz orqali bog'lanadi.")
    await message.answer("\n\n".join(lines), parse_mode="HTML", reply_markup=kb.my_leads(items))


# ---------- ulashish ----------
def share_announcement() -> str:
    return (
        "🎓 EduSearcher.uz — O'zbekistondagi o'quv markazlari va kurslarni bir joyda topishning "
        "qulay usuli!\n\n"
        "📍 Kurs, daraja va joylashuv bo'yicha eng mos markazni tanlang.\n"
        "👇 Botni ochish uchun havolani bosing:"
    )


@dp.message(Command("share"))
@dp.message(F.text == kb.BTN_SHARE)
async def menu_share(message: Message, db: DB, u: dict):
    reset_flow(u)
    await save(db, u)
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{u['tg_id']}"
    announcement = share_announcement()
    await message.answer(f"{announcement}\n{link}", reply_markup=kb.share(link, announcement),
                         disable_web_page_preview=True)
    n = int(u.get("referrals") or 0)
    await message.answer(
        "☝️ Shu e'lonni do'stlaringizga yuboring yoki «📨 Do'stga yuborish» tugmasini bosing. "
        f"Ular sizning havolangiz orqali botga qo'shiladi.\n\n👥 Siz taklif qilganlar: <b>{n}</b>",
        parse_mode="HTML", reply_markup=kb.main_menu())


# ---------- profil ----------
async def show_profile(event, db: DB, u: dict) -> None:
    loc = "📍 saqlangan" if u.get("lat") is not None and u.get("lng") is not None else "yo'q"
    text = (
        "👤 <b>Profil</b>\n\n"
        f"Ism: <b>{esc(u.get('full_name') or '—')}</b>\n"
        f"Telefon: <b>{esc(u.get('phone') or '—')}</b>\n"
        f"Joylashuv: <b>{loc}</b>\n"
        f"Saqlangan markazlar: <b>{int(u.get('favorites') or 0)}</b>\n"
        f"Taklif qilgan do'stlar: <b>{int(u.get('referrals') or 0)}</b>\n\n"
        "Ism va telefon ariza berishda avtomatik taklif qilinadi."
    )
    await respond(event, text, kb.profile())


@dp.message(Command("profile"))
@dp.message(F.text == kb.BTN_PROFILE)
async def menu_profile(message: Message, db: DB, u: dict):
    reset_flow(u)
    await save(db, u)
    await show_profile(message, db, u)


# =====================================================================
# Joylashuv va kontakt
# =====================================================================
@dp.message(F.location)
async def on_location(message: Message, db: DB, u: dict):
    s = sess(u)
    pending = s.get("pending") if current_step(u) == "await_loc" else None
    lat, lng = message.location.latitude, message.location.longitude
    u["lat"], u["lng"] = lat, lng
    try:
        await db.patch_user(u["tg_id"], {"lat": lat, "lng": lng})
    except DBError:
        log.exception("Joylashuvni saqlab bo'lmadi")
    reset_flow(u)
    await save(db, u)
    await message.answer("📍 Joylashuvingiz saqlandi.", reply_markup=kb.main_menu())
    kind = (pending or {}).get("k")
    if kind == "prof":
        await show_profile(message, db, u)
    elif kind == "find":
        await show_list(message, db, u, {"k": "find", "cat": pending.get("cat"), "lvl": pending.get("lvl"),
                                         "reg": None, "near": True})
    else:
        await show_list(message, db, u, {"k": "near", "cat": (pending or {}).get("cat"), "near": True})


@dp.message(F.contact)
async def on_contact(message: Message, db: DB, u: dict, bot: Bot):
    c = message.contact
    if c.user_id and message.from_user and c.user_id != message.from_user.id:
        await message.answer("Iltimos, faqat o'zingizning raqamingizni yuboring.", reply_markup=kb.main_menu())
        return
    phone = fmt.normalize_phone(c.phone_number)
    if not phone:
        await message.answer("Raqam noto'g'ri. Namuna: +998901234567")
        return
    step = current_step(u)
    if step == "lead_phone":
        await lead_got_phone(message, db, u, phone)
        return
    u["phone"] = phone
    try:
        await db.patch_user(u["tg_id"], {"phone": phone})
    except DBError:
        log.exception("Telefonni saqlab bo'lmadi")
    reset_flow(u)
    await save(db, u)
    await message.answer(f"📞 Raqamingiz saqlandi: <b>{esc(phone)}</b>", parse_mode="HTML",
                         reply_markup=kb.main_menu())


# =====================================================================
# Wizard: yo'nalish → daraja → hudud
# =====================================================================
def _lvl(code: str) -> Optional[str]:
    return code if code in fmt.LEVEL_CODES else None


@dp.callback_query(F.data == "noop")
async def cb_noop(cb: CallbackQuery):
    await cb.answer()


@dp.callback_query(F.data == "home")
async def cb_home(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    await go_home(cb, u, db)


@dp.callback_query(F.data == "cancel")
async def cb_cancel(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer("Bekor qilindi")
    await go_home(cb, u, db, "Bekor qilindi. 🏠 Bosh menyu")


@dp.callback_query(F.data == "new")
async def cb_new(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    cats = await db.categories()
    await respond(cb, "🔍 <b>Markaz topish</b>\n\nQaysi yo'nalish kerak?", kb.categories(cats, "cat"))


@dp.callback_query(F.data.startswith("cat:"))
async def cb_cat(cb: CallbackQuery, db: DB):
    await cb.answer()
    cat = int(cb.data.split(":")[1])
    name = dict(await db.categories()).get(cat, "Yo'nalish")
    await respond(cb, f"📚 <b>{esc(name)}</b>\n\nQaysi darajadan boshlaysiz?", kb.levels(cat))


@dp.callback_query(F.data.startswith("bc:"))
async def cb_browse_cat(cb: CallbackQuery, db: DB):
    await cb.answer()
    cat = int(cb.data.split(":")[1])
    name = dict(await db.categories()).get(cat, "Yo'nalish")
    regs = await db.regions()
    await respond(cb, f"📚 <b>{esc(name)}</b>\n\nQayerdan qidiramiz?", kb.places(cat, "x", regs))


@dp.callback_query(F.data.startswith("lvl:"))
async def cb_level(cb: CallbackQuery, db: DB):
    await cb.answer()
    _, cat, lvl = cb.data.split(":")
    cat = int(cat)
    name = dict(await db.categories()).get(cat, "Yo'nalish")
    level = fmt.LEVEL_NAMES.get(lvl, "har qanday daraja")
    regs = await db.regions()
    await respond(cb, f"📚 <b>{esc(name)}</b> · {esc(level)}\n\nQayerdan qidiramiz?", kb.places(cat, lvl, regs))


@dp.callback_query(F.data.startswith("fr:"))
async def cb_find_region(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    _, cat, lvl, reg = cb.data.split(":")
    await show_list(cb, db, u, {"k": "find", "cat": int(cat), "lvl": _lvl(lvl), "reg": int(reg) or None,
                                "near": False})


@dp.callback_query(F.data.startswith("fl:"))
async def cb_find_near(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    _, cat, lvl = cb.data.split(":")
    if u.get("lat") is not None and u.get("lng") is not None:
        await show_list(cb, db, u, {"k": "find", "cat": int(cat), "lvl": _lvl(lvl), "reg": None, "near": True})
    else:
        await ask_location(cb, db, u, {"k": "find", "cat": int(cat), "lvl": _lvl(lvl)})


@dp.callback_query(F.data.startswith("rg:"))
async def cb_region(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    reg = int(cb.data.split(":")[1])
    await show_list(cb, db, u, {"k": "reg", "reg": reg or None})


@dp.callback_query(F.data == "nccat")
async def cb_near_cats(cb: CallbackQuery, db: DB):
    await cb.answer()
    cats = await db.categories()
    await respond(cb, "📍 <b>Yaqin markazlar</b>\n\nQaysi yo'nalish bo'yicha?",
                  kb.categories(cats, "nc", all_label="🇺🇿 Barcha yo'nalishlar"))


@dp.callback_query(F.data.startswith("nc:"))
async def cb_near_cat(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    cat = int(cb.data.split(":")[1]) or None
    if u.get("lat") is not None and u.get("lng") is not None:
        await show_list(cb, db, u, {"k": "near", "cat": cat, "near": True})
    else:
        await ask_location(cb, db, u, {"k": "near", "cat": cat})


@dp.callback_query(F.data == "updloc")
async def cb_update_location(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    last = sess(u).get("last") or {}
    await ask_location(cb, db, u, {"k": "near", "cat": last.get("cat")})


@dp.callback_query(F.data.startswith("pg:"))
async def cb_page(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    last = sess(u).get("last")
    if not last:
        await go_home(cb, u, db, "Qidiruv eskirgan. Qaytadan boshlang 👇")
        return
    await show_list(cb, db, u, last, max(0, int(cb.data.split(":")[1])))


@dp.callback_query(F.data == "bk")
async def cb_back(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    last = sess(u).get("last")
    if not last:
        await go_home(cb, u, db)
        return
    await show_list(cb, db, u, last, int(last.get("page") or 0))


# =====================================================================
# Markaz kartochkasi, saqlash, yo'nalish
# =====================================================================
@dp.callback_query(F.data.startswith("c:"))
async def cb_center(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    cid = cb.data[2:]
    if not UUID_RE.match(cid):
        return
    await show_card(cb, db, u, cid)


@dp.callback_query(F.data.startswith("fv:"))
async def cb_favorite(cb: CallbackQuery, db: DB, u: dict):
    cid = cb.data[3:]
    if not UUID_RE.match(cid):
        await cb.answer()
        return
    try:
        saved = await db.toggle_favorite(u["tg_id"], cid)
    except DBError as exc:
        await cb.answer(str(exc) if exc.user_visible else "Xatolik, qayta urinib ko'ring", show_alert=True)
        return
    await cb.answer("⭐ Saqlandi" if saved else "Saqlanganlardan olib tashlandi")
    card = await db.center_card(u["tg_id"], cid)
    if card and isinstance(cb.message, Message):
        try:
            await cb.message.edit_reply_markup(reply_markup=kb.card(card, bool(card.get("fav"))))
        except TelegramBadRequest:
            pass


@dp.callback_query(F.data.startswith("rt:"))
async def cb_route(cb: CallbackQuery, db: DB, u: dict):
    cid = cb.data[3:]
    if not UUID_RE.match(cid):
        await cb.answer()
        return
    card = await db.center_card(u["tg_id"], cid)
    if not card:
        await cb.answer("Markaz topilmadi", show_alert=True)
        return
    branches = [b for b in card.get("branches") or [] if b.get("lat") is not None and b.get("lng") is not None]
    if not branches:
        await cb.answer("Bu markaz uchun xarita manzili kiritilmagan", show_alert=True)
        return
    await cb.answer()
    best = fmt.nearest_branch(card, u.get("lat"), u.get("lng"))
    chosen = [best] if best else branches[:3]
    for b in chosen:
        await cb.bot.send_location(chat_id=cb.from_user.id, latitude=b["lat"], longitude=b["lng"])
        await cb.bot.send_message(
            chat_id=cb.from_user.id, parse_mode="HTML",
            text=f"🧭 <b>{esc(card['name'])}</b>\n{esc(b.get('region') or '')} {esc(b.get('address') or '')}")
    await db.track("route", cid, u["tg_id"])


# =====================================================================
# Ariza qoldirish (saytdagi ariza formasi bilan bir xil — admin panelida ko'rinadi)
# =====================================================================
@dp.callback_query(F.data.startswith("ap:"))
async def cb_apply(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    cid = cb.data[3:]
    if not UUID_RE.match(cid):
        return
    card = await db.center_card(u["tg_id"], cid)
    if not card:
        await send(cb, "Markaz topilmadi.")
        return
    names = [c["name"] for c in (card.get("courses") or [])][:8]
    sess(u)["lead"] = {"center": cid, "cname": card.get("name"), "courses": names}
    if names:
        set_step(u, "lead_course")
        await save(db, u)
        await send(cb, f"📝 <b>{esc(card['name'])}</b> markaziga ariza.\n\nQaysi kurs qiziq?", kb.lead_courses(names))
    else:
        await lead_ask_name(cb, db, u)


@dp.callback_query(F.data.startswith("apc:"))
async def cb_apply_course(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    lead = sess(u).get("lead")
    if not lead or current_step(u) != "lead_course":
        await go_home(cb, u, db, "Ariza jarayoni eskirgan. Markazni qaytadan oching.")
        return
    idx = int(cb.data.split(":")[1])
    names = lead.get("courses") or []
    lead["course"] = names[idx] if 0 <= idx < len(names) else None
    await lead_ask_name(cb, db, u)


async def lead_ask_name(event, db: DB, u: dict) -> None:
    set_step(u, "lead_name")
    await save(db, u)
    name = u.get("full_name")
    if name:
        await send(event, "👤 Ismingizni yozing yoki saqlangan ismni tanlang:", kb.use_name(name))
    else:
        await send(event, "👤 Ism va familiyangizni yozing:", kb.cancel_only())


@dp.callback_query(F.data == "apn:ok")
async def cb_apply_name(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    lead = sess(u).get("lead")
    if not lead or current_step(u) != "lead_name" or not u.get("full_name"):
        await go_home(cb, u, db, "Ariza jarayoni eskirgan. Markazni qaytadan oching.")
        return
    lead["name"] = u["full_name"]
    await lead_ask_phone(cb, db, u)


async def lead_ask_phone(event, db: DB, u: dict) -> None:
    set_step(u, "lead_phone")
    await save(db, u)
    await send(event, "📞 Telefon raqamingizni yuboring: tugmani bosing yoki yozing (+998901234567).",
               kb.phone_request(u.get("phone")))


async def lead_got_phone(message: Message, db: DB, u: dict, phone: str) -> None:
    lead = sess(u).get("lead")
    if not lead:
        await go_home(message, u, db, "Ariza jarayoni eskirgan. Markazni qaytadan oching.")
        return
    lead["phone"] = phone
    set_step(u, "lead_note")
    await save(db, u)
    await reply(message, "✍️ Qo'shimcha izoh yozing (masalan, qulay vaqt) yoki o'tkazib yuboring:", kb.skip_cancel())


async def lead_submit(message, db: DB, u: dict, bot: Bot, note: Optional[str]) -> None:
    lead = sess(u).get("lead") or {}
    if not (lead.get("center") and lead.get("name") and lead.get("phone")):
        await go_home(message, u, db, "Ariza jarayoni eskirgan. Markazni qaytadan oching.")
        return
    try:
        await db.submit_lead(u["tg_id"], lead["center"], lead["name"], lead["phone"], lead.get("course"), note)
    except DBError as exc:
        text = f"⚠️ {esc(str(exc))}" if exc.user_visible else "⚠️ Ariza yuborilmadi. Birozdan keyin qayta urinib ko'ring."
        center = lead.get("center")
        reset_flow(u)
        await save(db, u)
        await reply(message, text, kb.main_menu())
        if center:
            await show_card(message, db, u, center)
        return
    patch = {}
    if not u.get("full_name"):
        patch["full_name"] = lead["name"]
    if lead["phone"] != u.get("phone"):
        patch["phone"] = lead["phone"]
    if patch:
        u.update(patch)
        try:
            await db.patch_user(u["tg_id"], patch)
        except DBError:
            log.exception("Profilni yangilab bo'lmadi")
    center_id = lead["center"]
    summary = (
        f"✅ <b>Arizangiz yuborildi!</b>\n\n"
        f"🏢 {esc(lead.get('cname'))}\n"
        + (f"📚 {esc(lead.get('course'))}\n" if lead.get("course") else "")
        + f"👤 {esc(lead['name'])} · 📞 {esc(lead['phone'])}\n\n"
        "Markaz siz bilan bog'lanadi. Holatni «📝 Arizalarim» bo'limida kuzating."
    )
    if ADMIN_CHAT_ID:
        await safe_send(bot, ADMIN_CHAT_ID,
                        f"🆕 <b>Yangi ariza (bot)</b>\n🏢 {esc(lead.get('cname'))}\n"
                        f"📚 {esc(lead.get('course') or '—')}\n👤 {esc(lead['name'])} · {esc(lead['phone'])}\n"
                        f"💬 {esc(note or '—')}\n🆔 tg:{u['tg_id']}")
    reset_flow(u)
    await save(db, u)
    await reply(message, summary, kb.main_menu())
    await reply(message, "Davom etish:", InlineKeyboardMarkup(inline_keyboard=[
        [kb.ib("🏢 Markazga qaytish", f"c:{center_id}")]]))


# =====================================================================
# Sharh yozish (saytdagidek moderatsiyadan keyin ko'rinadi)
# =====================================================================
@dp.callback_query(F.data.startswith("rv:"))
async def cb_review(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    cid = cb.data[3:]
    if not UUID_RE.match(cid):
        return
    sess(u)["rv"] = {"center": cid}
    set_step(u, "rv_stars")
    await save(db, u)
    await send(cb, "💬 <b>Sharh yozish</b>\n\nMarkazga necha yulduz berasiz?", kb.stars())


@dp.callback_query(F.data.startswith("st:"))
async def cb_stars(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    rv = sess(u).get("rv")
    if not rv or current_step(u) != "rv_stars":
        await go_home(cb, u, db, "Sharh jarayoni eskirgan. Markazni qaytadan oching.")
        return
    rv["stars"] = max(1, min(5, int(cb.data.split(":")[1])))
    set_step(u, "rv_comment")
    await save(db, u)
    await respond(cb, f"{'⭐' * rv['stars']}\n\n✍️ Fikringizni yozing yoki o'tkazib yuboring:", kb.skip_cancel())


async def review_submit(message, db: DB, u: dict, comment: Optional[str]) -> None:
    rv = sess(u).get("rv") or {}
    if not (rv.get("center") and rv.get("stars")):
        await go_home(message, u, db, "Sharh jarayoni eskirgan. Markazni qaytadan oching.")
        return
    name = u.get("full_name") or "Foydalanuvchi"
    center = rv["center"]
    try:
        await db.submit_review(u["tg_id"], center, name, int(rv["stars"]), comment)
    except DBError as exc:
        text = f"⚠️ {esc(str(exc))}" if exc.user_visible else "⚠️ Sharh yuborilmadi. Birozdan keyin qayta urinib ko'ring."
        reset_flow(u)
        await save(db, u)
        await reply(message, text, kb.main_menu())
        return
    reset_flow(u)
    await save(db, u)
    await reply(message, "✅ Rahmat! Sharhingiz moderatsiyadan so'ng saytda va botda ko'rinadi.", kb.main_menu())
    await reply(message, "Davom etish:", InlineKeyboardMarkup(inline_keyboard=[
        [kb.ib("🏢 Markazga qaytish", f"c:{center}")]]))


@dp.callback_query(F.data == "skip")
async def cb_skip(cb: CallbackQuery, db: DB, u: dict, bot: Bot):
    await cb.answer()
    step = current_step(u)
    if step == "lead_note":
        await lead_submit(cb, db, u, bot, None)
    elif step == "rv_comment":
        await review_submit(cb, db, u, None)
    else:
        await go_home(cb, u, db, "Bu qadam eskirgan. 🏠 Bosh menyu")


# =====================================================================
# Profilni tahrirlash
# =====================================================================
@dp.callback_query(F.data.startswith("pe:"))
async def cb_profile_edit(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    what = cb.data[3:]
    if what == "name":
        set_step(u, "pf_name")
        await save(db, u)
        await send(cb, "✏️ Yangi ismingizni yozing:", kb.cancel_only())
    elif what == "phone":
        set_step(u, "pf_phone")
        await save(db, u)
        await send(cb, "📞 Telefon raqamingizni yuboring yoki yozing (+998901234567):",
                   kb.phone_request(u.get("phone")))
    elif what == "loc":
        await ask_location(cb, db, u, {"k": "prof"})
    elif what == "delloc":
        u["lat"] = u["lng"] = None
        try:
            await db.patch_user(u["tg_id"], {"lat": None, "lng": None})
        except DBError:
            log.exception("Joylashuvni o'chirib bo'lmadi")
        await show_profile(cb, db, u)


# =====================================================================
# Matnli xabarlar: qadamlar yoki nom bo'yicha qidiruv
# =====================================================================
@dp.message(F.text & ~F.text.startswith("/"))
async def on_text(message: Message, db: DB, u: dict, bot: Bot):
    text = (message.text or "").strip()
    step = current_step(u)

    if step == "lead_name":
        if not 2 <= len(text) <= 80:
            await message.answer("Ism 2 dan 80 gacha belgidan iborat bo'lsin.")
            return
        lead = sess(u).get("lead") or {}
        lead["name"] = text
        sess(u)["lead"] = lead
        await lead_ask_phone(message, db, u)
        return

    if step == "lead_phone":
        phone = fmt.normalize_phone(text)
        if not phone:
            await message.answer("Telefon raqam noto'g'ri. Namuna: +998901234567")
            return
        await lead_got_phone(message, db, u, phone)
        return

    if step == "lead_note":
        await lead_submit(message, db, u, bot, text[:500])
        return

    if step == "rv_comment":
        await review_submit(message, db, u, text[:1000])
        return

    if step == "pf_name":
        if not 2 <= len(text) <= 80:
            await message.answer("Ism 2 dan 80 gacha belgidan iborat bo'lsin.")
            return
        u["full_name"] = text
        try:
            await db.patch_user(u["tg_id"], {"full_name": text})
        except DBError:
            log.exception("Ismni saqlab bo'lmadi")
        reset_flow(u)
        await save(db, u)
        await message.answer("✅ Ismingiz saqlandi.", reply_markup=kb.main_menu())
        await show_profile(message, db, u)
        return

    if step == "pf_phone":
        phone = fmt.normalize_phone(text)
        if not phone:
            await message.answer("Telefon raqam noto'g'ri. Namuna: +998901234567")
            return
        u["phone"] = phone
        try:
            await db.patch_user(u["tg_id"], {"phone": phone})
        except DBError:
            log.exception("Telefonni saqlab bo'lmadi")
        reset_flow(u)
        await save(db, u)
        await message.answer("✅ Telefon raqamingiz saqlandi.", reply_markup=kb.main_menu())
        await show_profile(message, db, u)
        return

    if step in ("rv_stars", "lead_course"):
        await message.answer("Iltimos, yuqoridagi tugmalardan birini tanlang yoki /cancel bosing.")
        return

    # Odatiy holat: markaz nomi bo'yicha qidiruv
    if len(text) < 2:
        await message.answer("Qidirish uchun kamida 2 ta belgi yozing yoki menyudan tanlang.",
                             reply_markup=kb.main_menu())
        return
    await show_list(message, db, u, {"k": "q", "q": text[:60]})


@dp.message()
async def on_other(message: Message, db: DB, u: dict):
    await message.answer("Buni tushunmadim 🙈 Menyudan tanlang yoki markaz nomini yozing.",
                         reply_markup=kb.main_menu())


@dp.callback_query()
async def on_stale_callback(cb: CallbackQuery):
    await cb.answer("Bu tugma eskirgan. /menu ni bosing.", show_alert=True)


# =====================================================================
# Xatolarni ushlash
# =====================================================================
@dp.error()
async def on_error(event: ErrorEvent):
    log.error("Handlerda xatolik: %r", event.exception, exc_info=event.exception)
    ERROR_COUNT["n"] += 1
    LAST_ERRORS.append(repr(event.exception))
    del LAST_ERRORS[:-20]
    try:
        update = event.update
        if update.callback_query:
            await update.callback_query.answer("⚠️ Xatolik yuz berdi. Qayta urinib ko'ring.", show_alert=True)
        elif update.message:
            await update.message.answer("⚠️ Xatolik yuz berdi. Qayta urinib ko'ring yoki /menu ni bosing.")
    except Exception:
        log.warning("Xatolik haqida xabar berib bo'lmadi")
    return True
