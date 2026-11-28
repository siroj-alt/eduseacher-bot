"""Botning qo'shimcha imkoniyatlari: til, sinov darsi, daraja testi, taklif, taqqoslash, narx/saralash,
ota-ona rejimi, markaz egasi paneli va inline rejim. app.py orqali asosiy dispetcherga ulanadi."""
import logging
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import BaseFilter, Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResultArticle,
    InlineQueryResultsButton,
    InputTextMessageContent,
    Message,
)

import fmt
import i18n
import kb
import leveltest
from bot_handlers import (
    ADMIN_CHAT_ID, HOOKS, UUID_RE, all_texts, ask_location, card_markup, current_step, go_home, reply,
    reset_flow, respond, save, send, safe_send, sess, set_step, show_list, show_card,
)
from db import DB, DBError
from fmt import esc
from i18n import t
from kb import BOT_USERNAME, WEB_APP_URL

log = logging.getLogger("bot.features")
router = Router(name="features")


class StepIs(BaseFilter):
    """Filtr: foydalanuvchi shu qadamlardan birida (matn xabarlari uchun)."""

    def __init__(self, *steps: str):
        self.steps = set(steps)

    async def __call__(self, message: Message, u: dict) -> bool:
        return current_step(u) in self.steps


def err_text(exc: DBError, fallback_key: str = "error_retry") -> str:
    return f"⚠️ {esc(str(exc))}" if exc.user_visible else t(fallback_key)


# =====================================================================
# Til
# =====================================================================
@router.message(Command("lang"))
async def cmd_lang(message: Message, db: DB, u: dict):
    await message.answer(t("lang_prompt"), reply_markup=kb.lang_menu())


@router.callback_query(F.data == "lang:menu")
async def cb_lang_menu(cb: CallbackQuery):
    await cb.answer()
    await respond(cb, t("lang_prompt"), kb.lang_menu())


@router.callback_query(F.data.in_({"lang:uz", "lang:ru"}))
async def cb_lang_set(cb: CallbackQuery, db: DB, u: dict):
    code = cb.data.split(":")[1]
    s = sess(u)
    s["lang"] = code
    i18n.set_ctx(code, s.get("role", ""))
    reset_flow(u)
    await save(db, u)
    await cb.answer("✅")
    await send(cb, t("lang_changed"), kb.main_menu())


# =====================================================================
# Sayt kabineti bilan bog'lanish, "Mening o'qishim"
# =====================================================================
def how_to_link_markup() -> InlineKeyboardMarkup:
    return kb.markup([[kb.ub(t("b_open_cabinet_site"), WEB_APP_URL.rstrip("/") + "/kabinet")], kb.home_row()])


@router.callback_query(F.data == "acc:how")
async def cb_link_how(cb: CallbackQuery):
    await cb.answer()
    await respond(cb, t("link_how"), how_to_link_markup())


@router.callback_query(F.data == "acc:unlink")
async def cb_unlink(cb: CallbackQuery):
    await cb.answer()
    await respond(cb, t("unlink_confirm"), kb.confirm_unlink())


@router.callback_query(F.data == "acc:unlink2")
async def cb_unlink2(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    try:
        await db.unlink_account(u["tg_id"])
    except DBError as exc:
        await send(cb, err_text(exc), kb.main_menu())
        return
    s = sess(u)
    s["role"] = ""
    i18n.set_ctx(s.get("lang", "uz"), "")
    await save(db, u)
    await send(cb, t("unlinked"), kb.main_menu())


@router.callback_query(F.data == "my:study")
async def cb_my_study(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    try:
        me = await db.me(u["tg_id"])
        if not me.get("linked"):
            await respond(cb, t("link_how"), how_to_link_markup())
            return
        enrollments = await db.my_study(u["tg_id"])
    except DBError as exc:
        await send(cb, err_text(exc), kb.menu_only())
        return
    await respond(cb, fmt.render_diary(None, enrollments, parent=False), kb.menu_only())


# =====================================================================
# Taklif va sovg'a (do'stlarga ulashish + taklif qilinganlar ro'yxati + sayt kodi)
# =====================================================================
@router.message(Command("share"))
@router.message(F.text.in_(all_texts("btn_share")))
async def menu_share(message: Message, db: DB, u: dict):
    reset_flow(u)
    await save(db, u)
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{u['tg_id']}"
    announcement = t("share_announcement")
    await message.answer(f"{announcement}\n{link}", reply_markup=kb.share(link, announcement),
                         disable_web_page_preview=True)
    try:
        data = await db.referrals(u["tg_id"])
    except DBError:
        data = {}
    n = int(data.get("bot_total") or u.get("referrals") or 0)
    lines = [t("share_howto"), "", t("share_count", n=n)]
    friends = data.get("friends") or []
    if friends:
        lines.append("")
        for f in friends[:10]:
            uname = f" (@{esc(f['username'])})" if f.get("username") else ""
            mark = " ✅" if f.get("applied") else ""
            lines.append(f"• {esc(fmt.clip(f.get('name'), 30))}{uname}{mark}")
        if n > len(friends[:10]):
            lines.append(t("share_more", n=n - 10))
        lines.append(t("share_legend"))
    if data.get("linked") and data.get("site_code"):
        lines += ["", t("share_site_code", code=esc(data["site_code"]),
                        invited=int(data.get("site_invited") or 0), enrolled=int(data.get("site_enrolled") or 0))]
    elif data and not data.get("linked"):
        lines += ["", t("share_site_hint")]
    await message.answer("\n".join(lines), parse_mode="HTML", reply_markup=kb.main_menu())


@router.callback_query(F.data == "ref:code")
async def cb_ref_code(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    set_step(u, "ref_code")
    await save(db, u)
    await send(cb, t("ref_code_prompt"), kb.cancel_only())


@router.message(StepIs("ref_code"), F.text & ~F.text.startswith("/"))
async def on_ref_code(message: Message, db: DB, u: dict):
    code = (message.text or "").strip()
    if not 4 <= len(code) <= 12 or not code.isalnum():
        await message.answer(t("ref_code_bad"))
        return
    try:
        res = await db.apply_ref(u["tg_id"], code)
    except DBError as exc:
        await message.answer(err_text(exc), reply_markup=kb.main_menu())
        return
    reset_flow(u)
    await save(db, u)
    if res.get("ok"):
        await message.answer(t("ref_code_ok"), reply_markup=kb.main_menu())
    else:
        await message.answer(t("ref_err_" + str(res.get("error") or "code")), parse_mode="HTML",
                             reply_markup=kb.main_menu())


# =====================================================================
# Taqqoslash (2–3 markaz)
# =====================================================================
def patch_cmp_markup(markup: Optional[InlineKeyboardMarkup], cid: str, in_cmp: bool, n: int) -> Optional[InlineKeyboardMarkup]:
    if not markup:
        return None
    rows, out = [list(r) for r in markup.inline_keyboard], []
    for row in rows:
        if any((b.callback_data or "") == "cmps" for b in row):
            continue  # eski «Taqqoslash (n)» qatori
        new_row = []
        for b in row:
            if (b.callback_data or "") == f"cmp:{cid}":
                b = kb.ib(t("b_cmp_remove") if in_cmp else t("b_cmp_add"), f"cmp:{cid}")
            new_row.append(b)
        out.append(new_row)
        if any((b.callback_data or "") == f"cmp:{cid}" for b in new_row) and n >= 2:
            out.append([kb.ib(t("b_compare_n", n=n), "cmps")])
    return InlineKeyboardMarkup(inline_keyboard=out)


@router.callback_query(F.data.startswith("cmp:"))
async def cb_cmp_toggle(cb: CallbackQuery, db: DB, u: dict):
    cid = cb.data[4:]
    if not UUID_RE.match(cid):
        await cb.answer()
        return
    s = sess(u)
    cmp = list(s.get("cmp") or [])
    if cid in cmp:
        cmp.remove(cid)
        await cb.answer(t("cmp_removed"))
    else:
        if len(cmp) >= 3:
            await cb.answer(t("cmp_max"), show_alert=True)
            return
        cmp.append(cid)
        await cb.answer(t("cmp_added", n=len(cmp)))
    s["cmp"] = cmp
    await save(db, u)
    if isinstance(cb.message, Message):
        markup = patch_cmp_markup(cb.message.reply_markup, cid, cid in cmp, len(cmp))
        try:
            await cb.message.edit_reply_markup(reply_markup=markup)
        except TelegramBadRequest:
            pass


@router.callback_query(F.data == "cmps")
async def cb_cmp_show(cb: CallbackQuery, db: DB, u: dict):
    ids = list(sess(u).get("cmp") or [])
    if len(ids) < 2:
        await cb.answer(t("cmp_need_two"), show_alert=True)
        return
    await cb.answer()
    try:
        items = await db.compare(ids)
    except DBError as exc:
        await send(cb, err_text(exc), kb.menu_only())
        return
    order = {cid: i for i, cid in enumerate(ids)}
    items.sort(key=lambda x: order.get(x.get("id"), 99))
    await respond(cb, fmt.render_compare(items), kb.compare_view([i["id"] for i in items]))


@router.callback_query(F.data == "cmpx")
async def cb_cmp_clear(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer(t("cmp_cleared"))
    sess(u)["cmp"] = []
    await save(db, u)
    await go_home(cb, u, db)


# =====================================================================
# Narx filtri va saralash
# =====================================================================
@router.callback_query(F.data == "prcm")
async def cb_price_menu(cb: CallbackQuery, u: dict):
    await cb.answer()
    last = sess(u).get("last") or {}
    await respond(cb, t("price_prompt"), kb.price_menu(last.get("maxp")))


@router.callback_query(F.data.startswith("prc:"))
async def cb_price_set(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    last = dict(sess(u).get("last") or {})
    if not last:
        await go_home(cb, u, db, t("search_expired"))
        return
    try:
        val = int(cb.data.split(":")[1])
    except ValueError:
        return
    last["maxp"] = val or None
    await show_list(cb, db, u, last, 0)


@router.callback_query(F.data == "srtm")
async def cb_sort_menu(cb: CallbackQuery, u: dict):
    await cb.answer()
    last = sess(u).get("last") or {}
    await respond(cb, t("sort_prompt"), kb.sort_menu(last.get("sort")))


@router.callback_query(F.data.startswith("srt:"))
async def cb_sort_set(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    last = dict(sess(u).get("last") or {})
    if not last:
        await go_home(cb, u, db, t("search_expired"))
        return
    code = cb.data.split(":")[1]
    last["sort"] = code if code in ("cheap", "rating") else None
    await show_list(cb, db, u, last, 0)


# =====================================================================
# Bepul sinov darsi
# =====================================================================
def _tr(u: dict) -> dict:
    return sess(u).get("tr") or {}


async def trial_expired(event, db: DB, u: dict) -> None:
    await go_home(event, u, db, t("tr_expired"))


@router.callback_query(F.data.startswith("tr:"))
async def cb_trial_start(cb: CallbackQuery, db: DB, u: dict):
    cid = cb.data[3:]
    if not UUID_RE.match(cid):
        await cb.answer()
        return
    try:
        card = await db.center_card(u["tg_id"], cid)
        slots = await db.trial_slots(cid) if card else []
    except DBError as exc:
        await cb.answer(err_text(exc), show_alert=True)
        return
    if not card:
        await cb.answer(t("center_nf_short"), show_alert=True)
        return
    if not slots:
        await cb.answer(t("tr_no_slots"), show_alert=True)
        return
    await cb.answer()
    reset_flow(u)
    names = [c["name"] for c in (card.get("courses") or [])][:8]
    sess(u)["tr"] = {"center": cid, "cname": card.get("name"), "courses": names, "days": slots}
    set_step(u, "tr_day")
    await save(db, u)
    await send(cb, t("tr_pick_day", name=esc(card["name"])), kb.trial_days(slots))


@router.callback_query(F.data.startswith("trd:"))
async def cb_trial_day(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    tr = _tr(u)
    if not tr or current_step(u) not in ("tr_day", "tr_time"):
        await trial_expired(cb, db, u)
        return
    i = int(cb.data.split(":")[1])
    days = tr.get("days") or []
    if not 0 <= i < len(days):
        await trial_expired(cb, db, u)
        return
    tr["di"] = i
    set_step(u, "tr_time")
    await save(db, u)
    day = days[i]
    await respond(cb, t("tr_pick_time", day=f"{t('dow_' + str(int(day.get('dow') or 1)))} {str(day['date'])[8:10]}.{str(day['date'])[5:7]}"),
                  kb.trial_times(day.get("times") or []))


@router.callback_query(F.data == "trb")
async def cb_trial_back(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    tr = _tr(u)
    if not tr:
        await trial_expired(cb, db, u)
        return
    set_step(u, "tr_day")
    await save(db, u)
    await respond(cb, t("tr_pick_day", name=esc(tr.get("cname"))), kb.trial_days(tr.get("days") or []))


@router.callback_query(F.data.startswith("trt:"))
async def cb_trial_time(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    tr = _tr(u)
    if not tr or current_step(u) != "tr_time" or tr.get("di") is None:
        await trial_expired(cb, db, u)
        return
    day = (tr.get("days") or [])[tr["di"]]
    times = day.get("times") or []
    i = int(cb.data.split(":")[1])
    if not 0 <= i < len(times):
        await trial_expired(cb, db, u)
        return
    tr["date"], tr["time"] = str(day["date"])[:10], times[i]
    if tr.get("courses"):
        set_step(u, "tr_course")
        await save(db, u)
        await respond(cb, t("tr_pick_course"), kb.trial_courses(tr["courses"]))
    else:
        await trial_ask_name(cb, db, u)


@router.callback_query(F.data.startswith("trc:"))
async def cb_trial_course(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    tr = _tr(u)
    if not tr or current_step(u) != "tr_course":
        await trial_expired(cb, db, u)
        return
    i = int(cb.data.split(":")[1])
    names = tr.get("courses") or []
    tr["course"] = names[i] if 0 <= i < len(names) else None
    await trial_ask_name(cb, db, u)


async def trial_ask_name(event, db: DB, u: dict) -> None:
    set_step(u, "tr_name")
    await save(db, u)
    name = u.get("full_name")
    if name:
        await send(event, t("ask_name_saved"), kb.trial_confirm_name(name))
    else:
        await send(event, t("ask_name"), kb.cancel_only())


@router.callback_query(F.data == "trn:ok")
async def cb_trial_name_ok(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    tr = _tr(u)
    if not tr or current_step(u) != "tr_name" or not u.get("full_name"):
        await trial_expired(cb, db, u)
        return
    tr["name"] = u["full_name"]
    await trial_ask_phone(cb, db, u)


async def trial_ask_phone(event, db: DB, u: dict) -> None:
    set_step(u, "tr_phone")
    await save(db, u)
    await send(event, t("ask_phone"), kb.phone_request(u.get("phone")))


@router.message(StepIs("tr_name"), F.text & ~F.text.startswith("/"))
async def on_trial_name(message: Message, db: DB, u: dict):
    text = (message.text or "").strip()
    if not 2 <= len(text) <= 80:
        await message.answer(t("name_len"))
        return
    tr = _tr(u)
    if not tr:
        await trial_expired(message, db, u)
        return
    tr["name"] = text
    await trial_ask_phone(message, db, u)


@router.message(StepIs("tr_phone"), F.text & ~F.text.startswith("/"))
async def on_trial_phone_text(message: Message, db: DB, u: dict, bot: Bot):
    phone = fmt.normalize_phone(message.text)
    if not phone:
        await message.answer(t("phone_bad"))
        return
    await trial_submit(message, db, u, bot, phone)


async def _trial_phone_hook(message: Message, db: DB, u: dict, phone: str) -> None:
    await trial_submit(message, db, u, message.bot, phone)


HOOKS["tr_phone"] = _trial_phone_hook


async def trial_submit(message: Message, db: DB, u: dict, bot: Bot, phone: str) -> None:
    tr = _tr(u)
    if not (tr.get("center") and tr.get("name") and tr.get("date") and tr.get("time")):
        await trial_expired(message, db, u)
        return
    try:
        await db.book_trial(u["tg_id"], tr["center"], tr["name"], phone, tr.get("course"), tr["date"], tr["time"])
    except DBError as exc:
        center = tr["center"]
        reset_flow(u)
        await save(db, u)
        await reply(message, err_text(exc), kb.main_menu())
        if exc.user_visible and center:
            await reply(message, t("continue_word"), kb.markup([[kb.ib(t("b_back_center"), f"c:{center}")]]))
        return
    patch = {}
    if not u.get("full_name"):
        patch["full_name"] = tr["name"]
    if phone != u.get("phone"):
        patch["phone"] = phone
    if patch:
        u.update(patch)
        try:
            await db.patch_user(u["tg_id"], patch)
        except DBError:
            log.exception("Profilni yangilab bo'lmadi")
    when = f"{tr['date'][8:10]}.{tr['date'][5:7]}.{tr['date'][:4]} {tr['time']}"
    text = t("tr_done", center=esc(tr.get("cname")), when=when,
             course=(f"📚 {esc(tr['course'])}\n" if tr.get("course") else ""),
             name=esc(tr["name"]), phone=esc(phone))
    if ADMIN_CHAT_ID:
        await safe_send(bot, ADMIN_CHAT_ID,
                        f"🎁 <b>Sinov darsi (bot)</b>\n🏢 {esc(tr.get('cname'))}\n🕒 {when}\n"
                        f"📚 {esc(tr.get('course') or '—')}\n👤 {esc(tr['name'])} · {esc(phone)}\n🆔 tg:{u['tg_id']}")
    center = tr["center"]
    reset_flow(u)
    await save(db, u)
    await reply(message, text, kb.main_menu())
    await reply(message, t("continue_word"), kb.markup([[kb.ib(t("b_back_center"), f"c:{center}")]]))


# =====================================================================
# Daraja testi (A1–C1)
# =====================================================================
def _render_question(i: int) -> str:
    lv, q, opts, _c = leveltest.QUESTIONS[i]
    lines = [t("lt_q_head", i=i + 1, n=leveltest.TOTAL, level=lv), "", f"<b>{esc(q)}</b>", ""]
    lines += [f"{leveltest.LETTERS[k]}) {esc(o)}" for k, o in enumerate(opts)]
    return "\n".join(lines)


@router.message(Command("test"))
@router.message(F.text.in_(all_texts("btn_test")))
async def menu_test(message: Message, db: DB, u: dict):
    reset_flow(u)
    await save(db, u)
    await message.answer(t("lt_intro", n=leveltest.TOTAL), parse_mode="HTML", reply_markup=kb.test_start())


@router.callback_query(F.data == "lt:s")
async def cb_test_start(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    reset_flow(u)
    sess(u)["lt"] = {"q": 0, "ans": []}
    set_step(u, "lt_q")
    await save(db, u)
    await respond(cb, _render_question(0), kb.test_options(0))


@router.callback_query(F.data == "lt:x")
async def cb_test_stop(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    await go_home(cb, u, db, t("lt_stopped"))


@router.callback_query(F.data.startswith("lt:a:"))
async def cb_test_answer(cb: CallbackQuery, db: DB, u: dict):
    st = sess(u).get("lt")
    parts = cb.data.split(":")
    if not st or current_step(u) != "lt_q" or len(parts) != 4 or not parts[2].isdigit() or not parts[3].isdigit():
        await cb.answer(t("step_expired"), show_alert=True)
        return
    qi, opt = int(parts[2]), int(parts[3])
    if qi != st["q"]:
        await cb.answer()  # takroriy bosish
        return
    lv, _q, opts, correct = leveltest.QUESTIONS[qi]
    if not 0 <= opt < len(opts):
        await cb.answer()
        return
    st["ans"].append(opt)
    st["q"] = qi + 1
    await cb.answer(t("lt_right") if opt == correct else t("lt_wrong", ans=f"{leveltest.LETTERS[correct]}) {opts[correct]}"))
    if st["q"] < leveltest.TOTAL:
        set_step(u, "lt_q")
        await save(db, u)
        await respond(cb, _render_question(st["q"]), kb.test_options(st["q"]))
        return
    # yakun
    level, score, per = leveltest.compute_level(st["ans"])
    sess(u).pop("lt", None)
    sess(u)["lt_res"] = {"level": level, "code": leveltest.COURSE_LEVEL[level]}
    reset_flow(u)
    await save(db, u)
    try:
        await db.save_test(u["tg_id"], level, score, leveltest.TOTAL)
    except DBError:
        log.exception("Test natijasi saqlanmadi")
    text = t("lt_result", level=level, score=score, n=leveltest.TOTAL, desc=t("lt_desc_" + level),
             breakdown=" · ".join(f"{lv_}: {per[lv_]}/3" for lv_ in leveltest.LEVELS))
    await respond(cb, text, kb.test_result(level, u.get("lat") is not None))


@router.callback_query(F.data == "lt:c")
async def cb_test_centers(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    res = sess(u).get("lt_res")
    if not res:
        await go_home(cb, u, db, t("step_expired"))
        return
    near = u.get("lat") is not None and u.get("lng") is not None
    await show_list(cb, db, u, {"k": "lvltest", "cat": 1, "lvl": res["code"], "reg": None, "near": near,
                                "clabel": res["level"]})


@router.callback_query(F.data == "lt:i")
async def cb_test_ielts(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    near = u.get("lat") is not None and u.get("lng") is not None
    await show_list(cb, db, u, {"k": "lvltest", "cat": 5, "lvl": None, "reg": None, "near": near, "clabel": "IELTS"})


# =====================================================================
# "Farzandim uchun" (ota-ona rejimi)
# =====================================================================
@router.message(Command("family"))
@router.message(F.text.in_(all_texts("btn_family")))
async def menu_family(message: Message, db: DB, u: dict):
    reset_flow(u)
    await save(db, u)
    await show_family(message, db, u)


async def show_family(event, db: DB, u: dict) -> None:
    try:
        children = await db.children(u["tg_id"])
    except DBError as exc:
        await reply(event, err_text(exc), kb.main_menu())
        return
    if not children:
        await respond(event, t("fam_intro"), kb.family_empty())
        return
    lines = [t("fam_title"), ""]
    for ch in children[:10]:
        lines.append(f"👦 <b>{esc(ch.get('name'))}</b>")
        enr = ch.get("enrollments") or []
        if not enr:
            lines.append("   " + t("fam_no_courses"))
        for e in enr[:3]:
            warn = " ⚠️" if int(e.get("absent_30") or 0) >= 3 else ""
            lines.append(f"   🏫 {esc(fmt.clip(e.get('center'), 30))} · {esc(fmt.clip(e.get('course'), 30))}{warn}")
        lines.append("")
    lines.append(t("fam_hint"))
    await respond(event, "\n".join(lines).strip(), kb.family_menu(children))


@router.callback_query(F.data == "fam:add")
async def cb_family_add(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    set_step(u, "child_code")
    await save(db, u)
    await send(cb, t("fam_code_prompt"), kb.cancel_only())


@router.message(StepIs("child_code"), F.text & ~F.text.startswith("/"))
async def on_child_code(message: Message, db: DB, u: dict):
    code = "".join(ch for ch in (message.text or "") if ch.isdigit())
    if len(code) != 6:
        await message.answer(t("fam_code_bad"))
        return
    try:
        res = await db.link_child(u["tg_id"], code)
    except DBError as exc:
        await message.answer(err_text(exc), reply_markup=kb.main_menu())
        return
    if not res.get("ok"):
        err = str(res.get("error") or "code")
        if err == "code":
            await message.answer(t("fam_err_code"))  # qadam saqlanadi: qayta urinish mumkin
            return
        reset_flow(u)
        await save(db, u)
        await message.answer(t("fam_err_" + err), reply_markup=kb.main_menu())
        return
    reset_flow(u)
    await save(db, u)
    await message.answer(t("fam_linked", name=esc(res.get("name") or "")), parse_mode="HTML", reply_markup=kb.main_menu())
    await show_family(message, db, u)


@router.callback_query(F.data.startswith("fam:v:"))
async def cb_family_view(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    try:
        children = await db.children(u["tg_id"])
    except DBError as exc:
        await send(cb, err_text(exc), kb.menu_only())
        return
    i = int(cb.data.split(":")[2])
    if not 0 <= i < len(children):
        await show_family(cb, db, u)
        return
    ch = children[i]
    await respond(cb, fmt.render_diary(ch.get("name"), ch.get("enrollments") or [], parent=True),
                  kb.markup([[kb.ib(t("b_back"), "fam:list"), kb.ib(t("b_menu"), "home")]]))


@router.callback_query(F.data == "fam:list")
async def cb_family_list(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    await show_family(cb, db, u)


@router.callback_query(F.data.startswith("fam:d:"))
async def cb_family_del(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    i = int(cb.data.split(":")[2])
    await respond(cb, t("fam_unlink_confirm"),
                  kb.markup([[kb.ib(t("b_yes_unlink"), f"fam:x:{i}"), kb.ib(t("b_no"), "fam:list")]]))


@router.callback_query(F.data.startswith("fam:x:"))
async def cb_family_unlink(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    try:
        children = await db.children(u["tg_id"])
        i = int(cb.data.split(":")[2])
        if 0 <= i < len(children):
            await db.unlink_child(u["tg_id"], children[i]["id"])
    except DBError as exc:
        await send(cb, err_text(exc), kb.menu_only())
        return
    await show_family(cb, db, u)


# =====================================================================
# Markaz egasi paneli
# =====================================================================
def app_card_text(a: dict) -> str:
    when = fmt.short_date(a.get("created_at"))
    lines = [f"📝 <b>{esc(a.get('code'))}</b> · {esc(a.get('center'))}",
             f"👤 {esc(a.get('full_name'))} · 📞 {esc(a.get('phone'))}"]
    if a.get("course_name"):
        lines.append(f"📚 {esc(a['course_name'])}")
    if a.get("note"):
        lines.append(f"💬 {esc(fmt.clip(a['note'], 200))}")
    lines.append(f"{fmt.lead_status(a.get('status'))} · {when}")
    return "\n".join(lines)


@router.message(Command("owner"))
@router.message(F.text.in_(all_texts("btn_owner")))
async def menu_owner(message: Message, db: DB, u: dict):
    reset_flow(u)
    await save(db, u)
    await show_owner(message, db, u)


async def show_owner(event, db: DB, u: dict) -> None:
    try:
        me = await db.me(u["tg_id"])
        apps = await db.owner_apps(u["tg_id"], "new", 1) if me.get("centers") else {}
    except DBError as exc:
        await reply(event, err_text(exc), kb.main_menu())
        return
    centers = me.get("centers") or []
    if not centers:
        await reply(event, t("owner_not_linked"), how_to_link_markup())
        return
    names = "\n".join("🏫 " + esc(c.get("name")) for c in centers[:8])
    await respond(event, t("owner_title", centers=names, n=int(apps.get("total_new") or 0)),
                  kb.owner_menu(int(apps.get("total_new") or 0)))


@router.callback_query(F.data == "own:new")
async def cb_owner_new(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    try:
        data = await db.owner_apps(u["tg_id"], "new", 8)
    except DBError as exc:
        await send(cb, err_text(exc), kb.menu_only())
        return
    items = data.get("items") or []
    if not items:
        await send(cb, t("owner_no_new"), kb.markup([[kb.ib(t("b_back"), "own:menu"), kb.ib(t("b_menu"), "home")]]))
        return
    for a in items:
        await send(cb, app_card_text(a), kb.app_actions(a["id"]))


@router.callback_query(F.data == "own:menu")
async def cb_owner_menu(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    await show_owner(cb, db, u)


@router.callback_query(F.data == "own:all")
async def cb_owner_all(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    try:
        data = await db.owner_apps(u["tg_id"], "all", 10)
    except DBError as exc:
        await send(cb, err_text(exc), kb.menu_only())
        return
    items = data.get("items") or []
    if not items:
        await send(cb, t("owner_no_apps"), kb.menu_only())
        return
    text = t("owner_all_title") + "\n\n" + "\n\n".join(app_card_text(a) for a in items)
    await respond(cb, text[:fmt.MAX_LEN], kb.markup([[kb.ib(t("b_back"), "own:menu"), kb.ib(t("b_menu"), "home")]]))


@router.callback_query(F.data.startswith("own:r:"))
async def cb_owner_report(cb: CallbackQuery, db: DB, u: dict):
    await cb.answer()
    try:
        days = int(cb.data.split(":")[2])
        data = await db.owner_report(u["tg_id"], days)
    except (DBError, ValueError) as exc:
        await send(cb, err_text(exc) if isinstance(exc, DBError) else t("error_retry"), kb.menu_only())
        return
    await respond(cb, fmt.render_owner_report(data),
                  kb.markup([[kb.ib(t("b_back"), "own:menu"), kb.ib(t("b_menu"), "home")]]))


@router.callback_query(F.data.startswith("apo:"))
async def cb_app_decide(cb: CallbackQuery, db: DB, u: dict):
    parts = cb.data.split(":")
    if len(parts) != 3 or not parts[1].isdigit() or parts[2] not in ("ok", "no", "ct"):
        await cb.answer()
        return
    try:
        res = await db.owner_decide(u["tg_id"], int(parts[1]), parts[2])
    except DBError as exc:
        await cb.answer(str(exc) if exc.user_visible else t("save_fail_alert"), show_alert=True)
        return
    if not res.get("ok"):
        err = res.get("error")
        if err == "done":
            await cb.answer(t("app_already", status=fmt.lead_status(res.get("status"))), show_alert=True)
            _strip_buttons = True
        else:
            await cb.answer(t("app_not_yours"), show_alert=True)
            return
    else:
        await cb.answer(t("app_done_toast"))
    status = res.get("status") if res.get("ok") else res.get("status")
    line = t("app_result", status=fmt.lead_status(status))
    if isinstance(cb.message, Message):
        try:
            base = cb.message.html_text or ""
            markup = None
            if res.get("ok") and parts[2] == "ct":
                markup = kb.markup([[kb.ib(t("b_accept"), f"apo:{parts[1]}:ok"), kb.ib(t("b_reject"), f"apo:{parts[1]}:no")]])
            await cb.message.edit_text(f"{base}\n\n{line}", parse_mode="HTML", reply_markup=markup,
                                       disable_web_page_preview=True)
            return
        except TelegramBadRequest:
            pass
    await cb.bot.send_message(cb.from_user.id, line, parse_mode="HTML")


# =====================================================================
# Inline rejim: @edusearcherbot ingliz tili
# =====================================================================
@router.inline_query()
async def on_inline(query: InlineQuery, db: DB):
    text = (query.query or "").strip()
    q, maxp, sort = fmt.parse_query(text)
    try:
        data = await db.list_centers(q=q or None, limit=12, max_price=maxp,
                                     sort=sort or ("rating" if not q and not maxp else None))
    except DBError:
        data = {"items": []}
    results = []
    for it in data.get("items") or []:
        cid = it["id"]
        rating = fmt.fmt_rating(it.get("rating"))
        where = ", ".join(x for x in [i18n.reg_name(it.get("rname")), fmt.clip(it.get("address"), 40)] if x)
        price = fmt.fmt_price(it.get("minp"))
        desc = " · ".join(x for x in [rating, where, (t("price_from", price=price) if price else "")] if x)
        body = [f"<b>{esc(it.get('name'))}</b>" + (" ✅" if it.get("is_verified") else "")]
        if rating:
            body.append(rating)
        if where:
            body.append("📍 " + esc(where))
        if it.get("cname"):
            body.append(f"📚 {esc(fmt.clip(it['cname'], 60))}" + (f" · 💰 {t('price_from', price=price)}" if price else ""))
        if it.get("app_discount"):
            body.append(f"🏷 −{int(it['app_discount'])}%")
        markup = kb.markup([
            [kb.ub(t("b_inline_open_bot"), f"https://t.me/{BOT_USERNAME}?start=c_{cid}")],
            [kb.ub(t("b_inline_site"), WEB_APP_URL)],
        ])
        results.append(InlineQueryResultArticle(
            id=str(cid), title=fmt.clip(it.get("name"), 60), description=fmt.clip(desc, 100),
            input_message_content=InputTextMessageContent(message_text="\n".join(body), parse_mode="HTML",
                                                          disable_web_page_preview=True),
            reply_markup=markup))
    await query.answer(results, cache_time=30, is_personal=False,
                       button=InlineQueryResultsButton(text=t("inline_button"), start_parameter="inline"))
