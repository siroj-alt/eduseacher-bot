"""EduSearcher Telegram boti — edusearcher.uz saytining imkoniyatlari bot ichida.

Asosiy qism: kontekst, majburiy obuna, qidiruv, kartochka, ariza, sharh, profil.
Qo'shimcha imkoniyatlar (sinov darsi, daraja testi, ota-ona, markaz egasi, inline, taqqoslash, til)
features.py da; ular app.py orqali shu dispetcherga ulanadi.
"""
import logging
import os
import re
import time
from typing import Awaitable, Callable, Optional

from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
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
import i18n
import kb
from db import DB, DBError
from fmt import esc
from i18n import t
from kb import BOT_USERNAME, WEB_APP_URL

log = logging.getLogger("bot")

ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "").strip()
# Majburiy obuna: foydalanuvchi shu kanalga a'zo bo'lmaguncha bot ishlamaydi.
# Bot kanalda ADMIN bo'lishi shart (aks holda a'zolikni tekshirib bo'lmaydi; u holda bot bloklamaydi).
CHANNEL = os.getenv("CHANNEL_USERNAME", "@edusearcher").strip()
CHANNEL_URL = os.getenv("CHANNEL_URL", "https://t.me/edusearcher").strip()
REQUIRE_SUB = os.getenv("REQUIRE_SUBSCRIPTION", "1").strip() not in ("0", "false", "no", "")
SUB_TTL = 60 * 60  # tasdiqlangan obuna 1 soat davomida qayta tekshirilmaydi
MEMBER_OK = ("member", "administrator", "creator")
STEP_TTL = 30 * 60  # bajarilmay qolgan qadam 30 daqiqadan keyin eskiradi
UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
FLOW_KEYS = ("step", "step_ts", "pending", "lead", "rv", "tr", "lt", "fam_pick")

LAST_ERRORS: list = []  # selftest uchun
ERROR_COUNT = {"n": 0}

# Qadam bo'yicha kontakt (telefon) qabul qiluvchilar: features.py to'ldiradi
HOOKS: dict = {}

dp = Dispatcher()
fallback = Router(name="fallback")  # eng oxirida ulanadi (app.py)


def all_texts(key: str) -> set:
    return i18n.all_texts(key)


# =====================================================================
# Kontekst (har bir update uchun foydalanuvchi + seans + til)
# =====================================================================
class CtxMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Update, data: dict):
        db: Optional[DB] = data.get("db")
        user = data.get("event_from_user")
        u = {"session": {}, "tg_id": user.id if user else 0}
        inline = bool(event.inline_query or event.chosen_inline_result)
        if db and user and not user.is_bot and not inline:
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
        s = sess(u)
        if "lang" not in s:
            code = ((user.language_code if user else "") or "").lower()
            s["lang"] = "ru" if code.startswith("ru") else "uz"
        i18n.set_ctx(s.get("lang", "uz"), s.get("role", ""))
        data["u"] = u
        if db and user and not user.is_bot and REQUIRE_SUB and not inline:
            if not await subscription_gate(event, data, db, u, user):
                return None
        return await handler(event, data)


dp.update.outer_middleware(CtxMiddleware())


# =====================================================================
# Majburiy obuna (kanal)
# =====================================================================
async def is_subscribed(bot: Bot, user_id: int) -> Optional[bool]:
    """True/False — a'zolik; None — tekshirib bo'lmadi (bot kanalda admin emas yoki Telegram xatosi)."""
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL, user_id=user_id)
    except Exception as exc:  # noqa: BLE001
        log.warning("Obunani tekshirib bo'lmadi: %r", exc)
        return None
    status = getattr(member, "status", None)
    if status in MEMBER_OK:
        return True
    if status == "restricted":
        return bool(getattr(member, "is_member", False))
    return False


async def subscription_gate(event: Update, data: dict, db: DB, u: dict, user) -> bool:
    """True — foydalanuvchi o'tkazilsin; False — obuna so'raldi, handler chaqirilmaydi."""
    msg, cb = event.message, event.callback_query
    if not msg and not cb:
        return True
    if msg and msg.chat.type != "private":
        return True
    # Sayt kabinetini ulash, o'qishni tasdiqlash va markaz egasining ariza tugmalari obunasiz ishlaydi
    if msg and msg.text and msg.text.startswith("/start link_"):
        return True
    if cb and cb.data and cb.data.startswith(("enc:", "apo:")):
        return True
    bot: Bot = data["bot"]
    s = sess(u)
    now = int(time.time())
    is_check = bool(cb and cb.data == "chk_sub")

    if not is_check and now - int(s.get("sub_ts") or 0) < SUB_TTL:
        return True

    ok = await is_subscribed(bot, user.id)
    if ok is None:  # tekshirib bo'lmadi — foydalanuvchini bloklamaymiz
        if is_check:
            await cb.answer(t("sub_cant_check"), show_alert=True)
            return False
        return True

    if ok:
        s["sub_ts"] = now
        if not is_check:
            s.pop("gated", None)
            await save(db, u)
            return True
        # «Obunani tekshirish» bosildi va obuna tasdiqlandi — botni to'liq ishga tushiramiz
        s.pop("gated", None)
        pending = s.pop("pending_start", None) or ""
        ref_by = s.pop("pending_ref", None)
        name = user.first_name or t("friend")
        await cb.answer(t("sub_ok"))
        if isinstance(cb.message, Message):
            try:
                await cb.message.delete()
            except Exception:  # noqa: BLE001
                pass
        reset_flow(u)
        await save(db, u)
        await send_welcome(bot, db, u, user.id, name, pending, ref_by)
        return False

    # a'zo emas
    s["sub_ts"] = 0
    if is_check:
        await cb.answer(t("sub_not_yet"), show_alert=True)
        return False
    if msg and msg.text and msg.text.startswith("/start"):
        parts = msg.text.split(maxsplit=1)
        if len(parts) == 2:
            s["pending_start"] = parts[1][:80]
        if u.get("is_new") and u.get("referred_by"):
            s["pending_ref"] = u["referred_by"]
    s["gated"] = True
    await save(db, u)
    if cb:
        await cb.answer(t("sub_first"), show_alert=True)
    await bot.send_message(chat_id=user.id, text=t("gate_text"), parse_mode="HTML",
                           reply_markup=kb.subscribe(CHANNEL_URL), disable_web_page_preview=True)
    return False


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
    for key in FLOW_KEYS:
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
    return t("menu_text")


def text_step(u: dict, *steps: str) -> bool:
    return current_step(u) in steps


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
        limit=fmt.PAGE_SIZE, max_price=qd.get("maxp") or None, sort=qd.get("sort") or None,
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
    await respond(event, text, kb.results(data["items"], page, data["total"], qd, len(s.get("cmp") or [])))


def card_markup(u: dict, card: dict) -> InlineKeyboardMarkup:
    cmp = sess(u).get("cmp") or []
    return kb.card(card, bool(card.get("fav")), card["id"] in cmp, len(cmp))


async def show_card(event, db: DB, u: dict, center_id: str) -> None:
    card = await db.center_card(u["tg_id"], center_id)
    if not card:
        await respond(event, t("center_not_found"), kb.menu_only())
        return
    await respond(event, fmt.render_card(card, u.get("lat"), u.get("lng")), card_markup(u, card))


async def ask_location(event, db: DB, u: dict, pending: dict) -> None:
    set_step(u, "await_loc")
    sess(u)["pending"] = pending
    await save(db, u)
    await send(event, t("ask_location"), kb.location_request())


async def go_home(event, u: dict, db: DB, text: Optional[str] = None) -> None:
    reset_flow(u)
    await save(db, u)
    await send(event, text or menu_text(), kb.main_menu())


# =====================================================================
# Buyruqlar va menyu
# =====================================================================
async def send_welcome(bot: Bot, db: DB, u: dict, chat_id: int, name: str, args: str = "",
                       referred_by: Optional[int] = None) -> None:
    """/start javobi (to'g'ridan-to'g'ri yoki obuna tasdiqlangach)."""
    if referred_by:
        await safe_send(bot, referred_by, t("ref_joined", name=esc(name)))

    if args.startswith("c_") and UUID_RE.match(args[2:]):
        await bot.send_message(chat_id=chat_id, text=t("welcome_short"), reply_markup=kb.main_menu())
        card = await db.center_card(u["tg_id"], args[2:])
        if card:
            await bot.send_message(chat_id=chat_id, text=fmt.render_card(card, u.get("lat"), u.get("lng")),
                                   parse_mode="HTML", disable_web_page_preview=True,
                                   reply_markup=card_markup(u, card))
        else:
            await bot.send_message(chat_id=chat_id, text=t("center_not_found"))
        return

    text = t("welcome", name=esc(name))
    if args.startswith("ref_"):
        text += "\n\n" + t("welcome_ref")
    await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML", reply_markup=kb.main_menu())


LINK_RE = re.compile(r"^link_([A-Za-z0-9_-]{16,80})$")


async def link_account(message: Message, db: DB, u: dict, token: str) -> None:
    """Saytdagi kabinet (markaz yoki o'quvchi) shu Telegram akkauntiga ulanadi."""
    try:
        res = await db.link_account(message.from_user.id, token)
    except DBError:
        log.exception("Kabinetni ulab bo'lmadi")
        await message.answer(t("link_fail"))
        return
    if not res.get("ok"):
        await message.answer(t("link_expired"))
        return
    role = res.get("role") or "user"
    who = esc(res.get("name") or "")
    s = sess(u)
    is_owner = role == "center_owner" or bool(res.get("centers"))
    s["role"] = "owner" if is_owner else ""
    await save(db, u)
    i18n.set_ctx(s.get("lang", "uz"), s.get("role", ""))
    if is_owner:
        centers = esc(res.get("centers") or "")
        text = t("link_ok_owner", who=(" — " + who) if who else "",
                 centers=(("🏢 " + centers + "\n\n") if centers else ""))
    else:
        text = t("link_ok_user", who=(" — " + who) if who else "")
    await message.answer(text, parse_mode="HTML", reply_markup=kb.main_menu())


@dp.callback_query(F.data.startswith("enc:"))
async def cb_enrollment(cb: CallbackQuery, db: DB, u: dict):
    parts = cb.data.split(":")
    if len(parts) != 3 or not parts[1].isdigit() or parts[2] not in ("0", "1"):
        await cb.answer()
        return
    ok = parts[2] == "1"
    try:
        res = await db.confirm_enrollment(cb.from_user.id, int(parts[1]), ok)
    except DBError:
        await cb.answer(t("save_fail_alert"), show_alert=True)
        return
    if not res.get("ok"):
        await cb.answer(t("req_not_found"), show_alert=True)
        return
    await cb.answer(t("thanks_saved"))
    center = esc(res.get("center") or t("center_word"))
    text = t("enc_yes", center=center) if ok else t("enc_no", center=center)
    if isinstance(cb.message, Message):
        try:
            await cb.message.edit_text(text, parse_mode="HTML")
            return
        except TelegramBadRequest:
            pass
    await cb.bot.send_message(cb.from_user.id, text, parse_mode="HTML")


@dp.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, db: DB, u: dict, bot: Bot):
    name = message.from_user.first_name if message.from_user else t("friend")
    args = (command.args or "").strip()
    m = LINK_RE.match(args)
    if m:
        await link_account(message, db, u, m.group(1))
        return
    reset_flow(u)
    await save(db, u)
    referred = u["referred_by"] if u.get("is_new") and u.get("referred_by") else None
    await send_welcome(bot, db, u, message.chat.id, name, args, referred)


@dp.message(Command("menu"))
async def cmd_menu(message: Message, db: DB, u: dict):
    await go_home(message, u, db)


@dp.message(Command("cancel"))
@dp.message(F.text.in_(all_texts("btn_cancel")))
async def cmd_cancel(message: Message, db: DB, u: dict):
    await go_home(message, u, db, t("cancelled_home"))


@dp.message(Command("help"))
async def cmd_help(message: Message, db: DB, u: dict):
    await message.answer(t("help_text"), parse_mode="HTML", reply_markup=kb.main_menu())


@dp.message(Command("about"))
@dp.message(F.text.in_(all_texts("btn_about")))
async def cmd_about(message: Message, db: DB, u: dict):
    reset_flow(u)
    await save(db, u)
    try:
        st = await db.stats()
    except DBError:
        st = {}
    stats_line = ""
    if st:
        stats_line = "\n\n" + t("about_stats", centers=st.get("centers", 0), branches=st.get("branches", 0),
                                courses=st.get("courses", 0), regions=st.get("regions", 0),
                                categories=st.get("categories", 0))
    await message.answer(
        t("about_head") + stats_line + "\n\n" + t("about_tail") + "\n\n" + t("help_text").split("\n\n", 1)[1],
        parse_mode="HTML", reply_markup=kb.open_site(),
    )


# ---------- qidiruv menyulari ----------
@dp.message(Command("find"))
@dp.message(F.text.in_(all_texts("btn_find")))
async def menu_find(message: Message, db: DB, u: dict):
    reset_flow(u)
    await save(db, u)
    cats = await db.categories()
    await message.answer(t("find_prompt"), parse_mode="HTML", reply_markup=kb.categories(cats, "cat"))


@dp.message(Command("near"))
@dp.message(F.text.in_(all_texts("btn_near")))
async def menu_near(message: Message, db: DB, u: dict):
    reset_flow(u)
    if u.get("lat") is not None and u.get("lng") is not None:
        await show_list(message, db, u, {"k": "near", "cat": None, "near": True})
    else:
        await ask_location(message, db, u, {"k": "near", "cat": None})


@dp.message(F.text.in_(all_texts("btn_regions")))
async def menu_regions(message: Message, db: DB, u: dict):
    reset_flow(u)
    await save(db, u)
    regs = await db.regions()
    await message.answer(t("regions_prompt"), parse_mode="HTML", reply_markup=kb.regions(regs))


@dp.message(F.text.in_(all_texts("btn_cats")))
async def menu_cats(message: Message, db: DB, u: dict):
    reset_flow(u)
    await save(db, u)
    cats = await db.categories()
    await message.answer(t("cats_prompt"), parse_mode="HTML", reply_markup=kb.categories(cats, "bc"))


# ---------- saqlanganlar, arizalar ----------
@dp.message(Command("saved"))
@dp.message(F.text.in_(all_texts("btn_fav")))
async def menu_fav(message: Message, db: DB, u: dict):
    reset_flow(u)
    await save(db, u)
    items = await db.favorites(u["tg_id"])
    if not items:
        await message.answer(t("fav_empty"), reply_markup=kb.main_menu())
        return
    await message.answer(t("fav_title", n=len(items)), parse_mode="HTML", reply_markup=kb.favorites(items))


@dp.message(Command("applications"))
@dp.message(F.text.in_(all_texts("btn_leads")))
async def menu_leads(message: Message, db: DB, u: dict):
    reset_flow(u)
    await save(db, u)
    items = await db.my_leads(u["tg_id"])
    if not items:
        await message.answer(t("leads_empty"), reply_markup=kb.main_menu())
        return
    lines = [t("leads_title") + "\n"]
    for it in items:
        course = f" · {esc(fmt.clip(it.get('course'), 40))}" if it.get("course") else ""
        lines.append(f"<b>{esc(fmt.clip(it.get('center'), 50))}</b>{course}\n"
                     f"{fmt.lead_status(it.get('status'))} · {fmt.short_date(it.get('created_at'))}")
    lines.append("\n" + t("leads_footer"))
    await message.answer("\n\n".join(lines), parse_mode="HTML", reply_markup=kb.my_leads(items))


# ---------- profil ----------
async def show_profile(event, db: DB, u: dict) -> None:
    loc = t("saved_yes") if u.get("lat") is not None and u.get("lng") is not None else t("no_word")
    linked, role = False, ""
    try:
        me = await db.me(u["tg_id"])
        linked = bool(me.get("linked"))
        role = "owner" if me.get("centers") else ""
        s = sess(u)
        if s.get("role", "") != role:
            s["role"] = role
            await save(db, u)
            i18n.set_ctx(s.get("lang", "uz"), role)
    except DBError:
        pass
    text = t("profile_text", name=esc(u.get("full_name") or "—"), phone=esc(u.get("phone") or "—"), loc=loc,
             favs=int(u.get("favorites") or 0), refs=int(u.get("referrals") or 0),
             lang=("Русский" if i18n.lang() == "ru" else "O'zbekcha"),
             cabinet=(t("cabinet_linked") if linked else t("cabinet_not_linked")))
    await respond(event, text, kb.profile(linked, role))


@dp.message(Command("profile"))
@dp.message(F.text.in_(all_texts("btn_profile")))
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
    await message.answer(t("loc_saved"), reply_markup=kb.main_menu())
    kind = (pending or {}).get("k")
    if kind == "prof":
        await show_profile(message, db, u)
    elif kind == "find":
        await show_list(message, db, u, {"k": "find", "cat": pending.get("cat"), "lvl": pending.get("lvl"),
                                         "reg": None, "near": True})
    elif kind == "lvltest":
        await show_list(message, db, u, {"k": "lvltest", "cat": pending.get("cat"), "lvl": pending.get("lvl"),
                                         "clabel": pending.get("clabel"), "reg": None, "near": True})
    else:
        await show_list(message, db, u, {"k": "near", "cat": (pending or {}).get("cat"), "near": True})


@dp.message(F.contact)
async def on_contact(message: Message, db: DB, u: dict, bot: Bot):
    c = message.contact
    if c.user_id and message.from_user and c.user_id != message.from_user.id:
        await message.answer(t("only_own_number"), reply_markup=kb.main_menu())
        return
    phone = fmt.normalize_phone(c.phone_number)
    if not phone:
        await message.answer(t("phone_bad"))
        return
    step = current_step(u)
    if step == "lead_phone":
        await lead_got_phone(message, db, u, phone)
        return
    hook = HOOKS.get(step) if step else None
    if hook:
        await hook(message, db, u, phone)
        return
    u["phone"] = phone
    try:
        await db.patch_user(u["tg_id"], {"phone": phone})
    except DBError:
        log.exception("Telefonni saqlab bo'lmadi")
    reset_flow(u)
    await save(db, u)
    await message.answer(t("phone_saved", phone=esc(phone)), parse_mode="HTML", reply_markup=kb.main_menu())


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
    await cb.answer(t("cancelled"))
    await go_home(cb, u, db, t("cancelled_home"))


@dp.callback_query(F.data == "new")
async def cb_new(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    cats = await db.categories()
    await respond(cb, t("find_prompt"), kb.categories(cats, "cat"))


@dp.callback_query(F.data.startswith("cat:"))
async def cb_cat(cb: CallbackQuery, db: DB):
    await cb.answer()
    cat = int(cb.data.split(":")[1])
    name = i18n.cat_name(dict(await db.categories()).get(cat, t("direction")))
    await respond(cb, t("cat_level_prompt", name=esc(name)), kb.levels(cat))


@dp.callback_query(F.data.startswith("bc:"))
async def cb_browse_cat(cb: CallbackQuery, db: DB):
    await cb.answer()
    cat = int(cb.data.split(":")[1])
    name = i18n.cat_name(dict(await db.categories()).get(cat, t("direction")))
    regs = await db.regions()
    await respond(cb, t("cat_where_prompt", name=esc(name)), kb.places(cat, "x", regs))


@dp.callback_query(F.data.startswith("lvl:"))
async def cb_level(cb: CallbackQuery, db: DB):
    await cb.answer()
    _, cat, lvl = cb.data.split(":")
    cat = int(cat)
    name = i18n.cat_name(dict(await db.categories()).get(cat, t("direction")))
    level = fmt.level_name(lvl) if lvl in fmt.LEVEL_CODES else t("lvl_any_l")
    regs = await db.regions()
    await respond(cb, t("lvl_where_prompt", name=esc(name), level=esc(level)), kb.places(cat, lvl, regs))


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
    await respond(cb, t("near_cat_prompt"), kb.categories(cats, "nc", all_label=t("b_all_cats")))


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
        await go_home(cb, u, db, t("search_expired"))
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
        await cb.answer(str(exc) if exc.user_visible else t("error_retry_short"), show_alert=True)
        return
    await cb.answer(t("fav_saved") if saved else t("fav_removed"))
    card = await db.center_card(u["tg_id"], cid)
    if card and isinstance(cb.message, Message):
        try:
            await cb.message.edit_reply_markup(reply_markup=card_markup(u, card))
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
        await cb.answer(t("center_nf_short"), show_alert=True)
        return
    branches = [b for b in card.get("branches") or [] if b.get("lat") is not None and b.get("lng") is not None]
    if not branches:
        await cb.answer(t("no_map_address"), show_alert=True)
        return
    await cb.answer()
    best = fmt.nearest_branch(card, u.get("lat"), u.get("lng"))
    chosen = [best] if best else branches[:3]
    for b in chosen:
        await cb.bot.send_location(chat_id=cb.from_user.id, latitude=b["lat"], longitude=b["lng"])
        await cb.bot.send_message(
            chat_id=cb.from_user.id, parse_mode="HTML",
            text=f"🧭 <b>{esc(card['name'])}</b>\n{esc(i18n.reg_name(b.get('region')) or '')} {esc(b.get('address') or '')}")
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
        await send(cb, t("center_nf_short"))
        return
    names = [c["name"] for c in (card.get("courses") or [])][:8]
    sess(u)["lead"] = {"center": cid, "cname": card.get("name"), "courses": names}
    if names:
        set_step(u, "lead_course")
        await save(db, u)
        await send(cb, t("lead_course_prompt", name=esc(card["name"])), kb.lead_courses(names))
    else:
        await lead_ask_name(cb, db, u)


@dp.callback_query(F.data.startswith("apc:"))
async def cb_apply_course(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    lead = sess(u).get("lead")
    if not lead or current_step(u) != "lead_course":
        await go_home(cb, u, db, t("lead_expired"))
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
        await send(event, t("ask_name_saved"), kb.use_name(name))
    else:
        await send(event, t("ask_name"), kb.cancel_only())


@dp.callback_query(F.data == "apn:ok")
async def cb_apply_name(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    lead = sess(u).get("lead")
    if not lead or current_step(u) != "lead_name" or not u.get("full_name"):
        await go_home(cb, u, db, t("lead_expired"))
        return
    lead["name"] = u["full_name"]
    await lead_ask_phone(cb, db, u)


async def lead_ask_phone(event, db: DB, u: dict) -> None:
    set_step(u, "lead_phone")
    await save(db, u)
    await send(event, t("ask_phone"), kb.phone_request(u.get("phone")))


async def lead_got_phone(message: Message, db: DB, u: dict, phone: str) -> None:
    lead = sess(u).get("lead")
    if not lead:
        await go_home(message, u, db, t("lead_expired"))
        return
    lead["phone"] = phone
    set_step(u, "lead_note")
    await save(db, u)
    await reply(message, t("ask_note"), kb.skip_cancel())


async def lead_submit(message, db: DB, u: dict, bot: Bot, note: Optional[str]) -> None:
    lead = sess(u).get("lead") or {}
    if not (lead.get("center") and lead.get("name") and lead.get("phone")):
        await go_home(message, u, db, t("lead_expired"))
        return
    try:
        await db.submit_lead(u["tg_id"], lead["center"], lead["name"], lead["phone"], lead.get("course"), note)
    except DBError as exc:
        text = f"⚠️ {esc(str(exc))}" if exc.user_visible else t("lead_fail")
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
    summary = t("lead_sent", center=esc(lead.get("cname")),
                course=(f"📚 {esc(lead.get('course'))}\n" if lead.get("course") else ""),
                name=esc(lead["name"]), phone=esc(lead["phone"]))
    if ADMIN_CHAT_ID:
        await safe_send(bot, ADMIN_CHAT_ID,
                        f"🆕 <b>Yangi ariza (bot)</b>\n🏢 {esc(lead.get('cname'))}\n"
                        f"📚 {esc(lead.get('course') or '—')}\n👤 {esc(lead['name'])} · {esc(lead['phone'])}\n"
                        f"💬 {esc(note or '—')}\n🆔 tg:{u['tg_id']}")
    reset_flow(u)
    await save(db, u)
    await reply(message, summary, kb.main_menu())
    await reply(message, t("continue_word"), InlineKeyboardMarkup(inline_keyboard=[
        [kb.ib(t("b_back_center"), f"c:{center_id}")]]))


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
    await send(cb, t("rv_stars_prompt"), kb.stars())


@dp.callback_query(F.data.startswith("st:"))
async def cb_stars(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    rv = sess(u).get("rv")
    if not rv or current_step(u) != "rv_stars":
        await go_home(cb, u, db, t("rv_expired"))
        return
    rv["stars"] = max(1, min(5, int(cb.data.split(":")[1])))
    set_step(u, "rv_comment")
    await save(db, u)
    await respond(cb, t("rv_comment_prompt", stars="⭐" * rv["stars"]), kb.skip_cancel())


async def review_submit(message, db: DB, u: dict, comment: Optional[str]) -> None:
    rv = sess(u).get("rv") or {}
    if not (rv.get("center") and rv.get("stars")):
        await go_home(message, u, db, t("rv_expired"))
        return
    name = u.get("full_name") or t("user_word")
    center = rv["center"]
    try:
        await db.submit_review(u["tg_id"], center, name, int(rv["stars"]), comment)
    except DBError as exc:
        text = f"⚠️ {esc(str(exc))}" if exc.user_visible else t("rv_fail")
        reset_flow(u)
        await save(db, u)
        await reply(message, text, kb.main_menu())
        return
    reset_flow(u)
    await save(db, u)
    await reply(message, t("rv_thanks"), kb.main_menu())
    await reply(message, t("continue_word"), InlineKeyboardMarkup(inline_keyboard=[
        [kb.ib(t("b_back_center"), f"c:{center}")]]))


@dp.callback_query(F.data == "skip")
async def cb_skip(cb: CallbackQuery, db: DB, u: dict, bot: Bot):
    await cb.answer()
    step = current_step(u)
    if step == "lead_note":
        await lead_submit(cb, db, u, bot, None)
    elif step == "rv_comment":
        await review_submit(cb, db, u, None)
    else:
        await go_home(cb, u, db, t("step_expired"))


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
        await send(cb, t("pf_name_prompt"), kb.cancel_only())
    elif what == "phone":
        set_step(u, "pf_phone")
        await save(db, u)
        await send(cb, t("pf_phone_prompt"), kb.phone_request(u.get("phone")))
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
# Matnli xabarlar: qadamlar yoki nom bo'yicha qidiruv (features.py qadamlaridan keyin)
# =====================================================================
@fallback.message(F.text & ~F.text.startswith("/"))
async def on_text(message: Message, db: DB, u: dict, bot: Bot):
    text = (message.text or "").strip()
    step = current_step(u)

    if step == "lead_name":
        if not 2 <= len(text) <= 80:
            await message.answer(t("name_len"))
            return
        lead = sess(u).get("lead") or {}
        lead["name"] = text
        sess(u)["lead"] = lead
        await lead_ask_phone(message, db, u)
        return

    if step == "lead_phone":
        phone = fmt.normalize_phone(text)
        if not phone:
            await message.answer(t("phone_bad"))
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
            await message.answer(t("name_len"))
            return
        u["full_name"] = text
        try:
            await db.patch_user(u["tg_id"], {"full_name": text})
        except DBError:
            log.exception("Ismni saqlab bo'lmadi")
        reset_flow(u)
        await save(db, u)
        await message.answer(t("name_saved"), reply_markup=kb.main_menu())
        await show_profile(message, db, u)
        return

    if step == "pf_phone":
        phone = fmt.normalize_phone(text)
        if not phone:
            await message.answer(t("phone_bad"))
            return
        u["phone"] = phone
        try:
            await db.patch_user(u["tg_id"], {"phone": phone})
        except DBError:
            log.exception("Telefonni saqlab bo'lmadi")
        reset_flow(u)
        await save(db, u)
        await message.answer(t("phone_saved2"), reply_markup=kb.main_menu())
        await show_profile(message, db, u)
        return

    if step in ("rv_stars", "lead_course", "tr_day", "tr_time", "tr_course", "lt_q"):
        await message.answer(t("use_buttons"))
        return

    # Odatiy holat: nom/yo'nalish bo'yicha qidiruv (narx va saralash so'zlari bilan: "ingliz tili 1 mln gacha arzon")
    q, maxp, sort = fmt.parse_query(text)
    if len(q) < 2 and maxp is None and sort is None:
        await message.answer(t("search_short"), reply_markup=kb.main_menu())
        return
    if q:
        qd = {"k": "q", "q": q[:60], "maxp": maxp, "sort": sort}
    else:
        qd = {"k": "find", "cat": None, "lvl": None, "reg": None, "near": False, "maxp": maxp, "sort": sort}
    await show_list(message, db, u, qd)


@fallback.message()
async def on_other(message: Message, db: DB, u: dict):
    await message.answer(t("dont_understand"), reply_markup=kb.main_menu())


@fallback.callback_query()
async def on_stale_callback(cb: CallbackQuery):
    await cb.answer(t("stale_button"), show_alert=True)


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
            await update.callback_query.answer(t("error_alert"), show_alert=True)
        elif update.message:
            await update.message.answer(t("error_msg"))
    except Exception:
        log.warning("Xatolik haqida xabar berib bo'lmadi")
    return True
