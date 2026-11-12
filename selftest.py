"""Botning o'z-o'zini tekshirishi (dry-run).

Haqiqiy Supabase bazasi bilan barcha tugma va oqimlarni yurgizadi, lekin Telegram'ga hech narsa
yubormaydi (API chaqiruvlari yozib olinadi). Ariza/sharh yuboruvchi oxirgi qadamlar ATAYLAB o'tkazib yuboriladi.

Ishga tushirish: GET /api/setup?key=<WEBHOOK_SECRET>&selftest=1
"""
import time

from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.types import InlineKeyboardMarkup, Message, ReplyKeyboardMarkup, Update

import bot_handlers
import kb
from db import DB, DBError

TEST_ID = 900000001


class DryRunSession(BaseSession):
    def __init__(self, calls: list):
        super().__init__()
        self.calls = calls

    async def close(self) -> None:
        return None

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        if type(method).__name__ in ("SendMessage", "SendLocation"):
            return Message.model_validate({
                "message_id": len(self.calls), "date": 0,
                "chat": {"id": TEST_ID, "type": "private"}, "text": "x",
            })
        return True

    def stream_content(self, url, headers=None, timeout=30, chunk_size=65536, raise_for_status=True):
        async def gen():
            if False:
                yield b""
        return gen()


def _describe(method) -> str:
    name = type(method).__name__
    text = getattr(method, "text", None) or getattr(method, "caption", None) or ""
    markup = getattr(method, "reply_markup", None)
    btns = ""
    if isinstance(markup, InlineKeyboardMarkup):
        btns = f" inline={sum(len(r) for r in markup.inline_keyboard)}"
    elif isinstance(markup, ReplyKeyboardMarkup):
        btns = f" reply={sum(len(r) for r in markup.keyboard)}"
    if name == "AnswerCallbackQuery":
        text = getattr(method, "text", None) or ""
    one_line = " ".join(str(text).split())[:70]
    return f"{name}{btns} {one_line!r}"


async def run_selftest(db: DB) -> str:
    calls: list = []
    bot = Bot(token="123456:SELFTEST-token", session=DryRunSession(calls))
    lines: list = []
    counter = {"n": 1000}
    failures = 0

    def nxt() -> int:
        counter["n"] += 1
        return counter["n"]

    user = {"id": TEST_ID, "is_bot": False, "first_name": "Selftest", "username": "selftest_user"}
    chat = {"id": TEST_ID, "type": "private"}

    def msg(text=None, **extra) -> dict:
        m = {"message_id": nxt(), "date": 0, "chat": chat, "from": user, **extra}
        if text is not None:
            m["text"] = text
        return {"update_id": nxt(), "message": m}

    def cbq(data: str) -> dict:
        return {"update_id": nxt(), "callback_query": {
            "id": str(nxt()), "from": user, "chat_instance": "ci", "data": data,
            "message": {"message_id": 99, "date": 0, "chat": chat, "text": "old",
                        "from": {"id": 1, "is_bot": True, "first_name": "bot"}},
        }}

    async def step(label: str, payload: dict, expect_calls: bool = True):
        nonlocal failures
        calls.clear()
        errors_before = len(bot_handlers.LAST_ERRORS)
        t0 = time.time()
        try:
            update = Update.model_validate(payload, context={"bot": bot})
            await bot_handlers.dp.feed_update(bot, update, db=db)
        except Exception as exc:  # noqa: BLE001
            failures += 1
            lines.append(f"[FAIL] {label}: ISTISNO {exc!r}")
            return
        new_errors = bot_handlers.LAST_ERRORS[errors_before:]
        ms = int((time.time() - t0) * 1000)
        if new_errors or (expect_calls and not calls):
            failures += 1
            lines.append(f"[FAIL] {label} ({ms} ms): {new_errors or 'javob yuborilmadi'}")
        else:
            lines.append(f"[ OK ] {label} ({ms} ms)")
        for c in calls[:4]:
            lines.append(f"         -> {_describe(c)}")

    # ---- baza qatlami ----
    try:
        cats, regs, st = await db.categories(), await db.regions(), await db.stats()
        lines.append(f"[ OK ] baza: {len(cats)} yo'nalish, {len(regs)} viloyat, stats={st}")
        found = await db.list_centers(category=3, limit=1)
        cid = found["items"][0]["id"]
        lines.append(f"[ OK ] namunaviy markaz: {found['items'][0]['name']} ({cid})")
    except DBError as exc:
        return f"[FAIL] baza qatlami: {exc}"

    # ---- boshlash ----
    await step("/start", msg("/start"))
    await step("/start c_<id> (chuqur havola)", msg(f"/start c_{cid}"))
    await step("/help", msg("/help"))
    await step("/menu", msg("/menu"))

    # ---- wizard ----
    await step("menyu: Markaz topish", msg(kb.BTN_FIND))
    await step("cb cat:3", cbq("cat:3"))
    await step("cb lvl:3:b", cbq("lvl:3:b"))
    await step("cb fr:3:b:1 (Toshkent shahri)", cbq("fr:3:b:1"))
    await step("cb pg:1", cbq("pg:1"))
    await step("cb c:<id> (kartochka)", cbq(f"c:{cid}"))
    await step("cb fv:<id> (saqlash)", cbq(f"fv:{cid}"))
    await step("menyu: Saqlanganlar", msg(kb.BTN_FAV))
    await step("cb fv:<id> (olib tashlash)", cbq(f"fv:{cid}"))
    await step("cb rt:<id> (yo'nalish)", cbq(f"rt:{cid}"), expect_calls=False)
    await step("cb bk", cbq("bk"))
    await step("cb new", cbq("new"))
    await step("cb lvl:3:x", cbq("lvl:3:x"))
    await step("cb fr:3:x:0 (butun O'zbekiston)", cbq("fr:3:x:0"))

    # ---- joylashuv ----
    await step("cb fl:3:b (joylashuvsiz -> so'raydi)", cbq("fl:3:b"))
    await step("location xabari (kutilgan oqim)", msg(location={"latitude": 41.3111, "longitude": 69.2797}))
    await step("menyu: Yaqin markazlar", msg(kb.BTN_NEAR))
    await step("cb nccat", cbq("nccat"))
    await step("cb nc:5", cbq("nc:5"))
    await step("cb nc:0", cbq("nc:0"))
    await step("cb updloc", cbq("updloc"))
    await step("location xabari (yangilash)", msg(location={"latitude": 39.6542, "longitude": 66.9597}))

    # ---- ko'rish menyulari ----
    await step("menyu: Markazlar", msg(kb.BTN_REGIONS))
    await step("cb rg:1", cbq("rg:1"))
    await step("cb rg:0", cbq("rg:0"))
    await step("menyu: Yo'nalishlar", msg(kb.BTN_CATS))
    await step("cb bc:5", cbq("bc:5"))
    await step("matn: nom bo'yicha qidiruv 'it'", msg("it"))
    await step("matn: topilmaydigan qidiruv", msg("zzzqqxx"))
    await step("matn: bir belgi", msg("a"))

    # ---- ariza oqimi (yuborilmaydi) ----
    await step("cb ap:<id>", cbq(f"ap:{cid}"))
    await step("cb apc:0", cbq("apc:0"))
    await step("matn: ism", msg("Selftest Ism"))
    await step("matn: noto'g'ri telefon", msg("123"))
    await step("matn: to'g'ri telefon", msg("+998901234567"))
    await step("cancel (arizani to'xtatish)", msg("/cancel"))

    # ---- sharh oqimi (yuborilmaydi) ----
    await step("cb rv:<id>", cbq(f"rv:{cid}"))
    await step("cb st:5", cbq("st:5"))
    await step("cancel (sharhni to'xtatish)", msg(kb.BTN_CANCEL))

    # ---- profil ----
    await step("menyu: Profil", msg(kb.BTN_PROFILE))
    await step("cb pe:name", cbq("pe:name"))
    await step("matn: yangi ism", msg("Selftest Nom"))
    await step("cb pe:phone", cbq("pe:phone"))
    await step("matn: telefon", msg("90 123 45 67"))
    await step("cb pe:loc", cbq("pe:loc"))
    await step("cb pe:delloc", cbq("pe:delloc"))

    # ---- boshqalar ----
    await step("menyu: Arizalarim", msg(kb.BTN_LEADS))
    await step("menyu: Do'stlarga ulashish", msg(kb.BTN_SHARE))
    await step("menyu: Sayt haqida", msg(kb.BTN_ABOUT))
    await step("tushunarsiz kontent (dice)", msg(dice={"emoji": "🎲", "value": 3}))
    await step("eskirgan callback", cbq("zzz:1"))
    await step("noto'g'ri markaz id (cb c:xxx)", cbq("c:not-a-uuid"), expect_calls=False)

    summary = f"JAMI: {len([l for l in lines if l.startswith('[')])} tekshiruv, xatolar: {failures}"
    return summary + "\n" + "\n".join(lines)
