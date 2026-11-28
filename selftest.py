"""Botning o'z-o'zini tekshirishi (dry-run).

Haqiqiy Supabase bazasi bilan barcha tugma va oqimlarni yurgizadi, lekin Telegram'ga hech narsa
yubormaydi (API chaqiruvlari yozib olinadi). Ariza/sharh yuboruvchi oxirgi qadamlar ATAYLAB o'tkazib yuboriladi.

Ishga tushirish: GET /api/setup?key=<WEBHOOK_SECRET>&selftest=1
"""
import time

from aiogram.client.session.base import BaseSession
from aiogram.types import InlineKeyboardMarkup, Message, ReplyKeyboardMarkup, Update

import app
import bot_handlers
import daily
import i18n
import kb
from db import DB, DBError

TEST_ID = 900000001


class DryRunSession(BaseSession):
    def __init__(self, calls: list):
        super().__init__()
        self.calls = calls
        self.member_status = "member"  # GetChatMember javobi (obuna testlari uchun)

    async def close(self) -> None:
        return None

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        if type(method).__name__ == "GetChatMember":
            from aiogram.types import ChatMemberLeft, ChatMemberMember
            u = {"id": TEST_ID, "is_bot": False, "first_name": "Selftest"}
            if self.member_status == "member":
                return ChatMemberMember(status="member", user=u)
            return ChatMemberLeft(status="left", user=u)
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
    bot = app.make_bot("123456:SELFTEST-token", session=DryRunSession(calls))
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

    def cbq(data: str, old: bool = False) -> dict:
        # date=0 — Telegram 48 soatdan eski xabarlarni shunday yuboradi (InaccessibleMessage)
        return {"update_id": nxt(), "callback_query": {
            "id": str(nxt()), "from": user, "chat_instance": "ci", "data": data,
            "message": {"message_id": 99, "date": 0 if old else 1700000000, "chat": chat, "text": "old",
                        "from": {"id": 1, "is_bot": True, "first_name": "bot"}},
        }}

    async def step(label: str, payload: dict, expect_calls: bool = True):
        nonlocal failures
        calls.clear()
        errors_before = bot_handlers.ERROR_COUNT["n"]
        t0 = time.time()
        try:
            update = Update.model_validate(payload, context={"bot": bot})
            await app.dp.feed_update(bot, update, db=db)
        except Exception as exc:  # noqa: BLE001
            failures += 1
            lines.append(f"[FAIL] {label}: ISTISNO {exc!r}")
            return
        n_new = bot_handlers.ERROR_COUNT["n"] - errors_before
        new_errors = bot_handlers.LAST_ERRORS[-n_new:] if n_new > 0 else []
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

    # ---- majburiy obuna (kanal) ----
    sub_calls_ok = True
    session = bot.session
    await db.ctx(TEST_ID, "Selftest", "selftest_user", None)
    await db.set_session(TEST_ID, {})
    session.member_status = "left"
    await step("obuna: /start (a'zo emas -> kanal so'raladi)", msg("/start"))
    gate = [c for c in calls if type(c).__name__ == "SendMessage"]
    if not gate or "obuna" not in (gate[-1].text or "").lower() or not isinstance(gate[-1].reply_markup, InlineKeyboardMarkup):
        failures += 1
        lines.append("[FAIL] obuna: kanalga obuna taklifi chiqmadi")
    await step("obuna: menyu bosilsa ham bloklanadi", msg(kb.BTN_FIND))
    await step("obuna: tugma bosilsa bloklanadi", cbq("cat:3"))
    await step("obuna: «tekshirish» (hali a'zo emas)", cbq("chk_sub"))
    session.member_status = "member"
    await step("obuna: «tekshirish» (a'zo bo'ldi -> bot ishga tushadi)", cbq("chk_sub"))
    welcome = [c for c in calls if type(c).__name__ == "SendMessage"]
    if not welcome or "xush kelibsiz" not in (welcome[-1].text or "").lower():
        failures += 1
        lines.append("[FAIL] obuna: tasdiqlangach xush kelibsiz xabari chiqmadi")
    await step("obuna: tasdiqlangach bot ishlaydi", msg(kb.BTN_FIND))
    # chuqur havola obunadan keyin ham saqlanadi
    await db.set_session(TEST_ID, {})
    session.member_status = "left"
    await step("obuna: /start c_<id> (a'zo emas)", msg(f"/start c_{cid}"))
    session.member_status = "member"
    await step("obuna: tasdiqlangach markaz kartochkasi ochiladi", cbq("chk_sub"))
    if not any(type(c).__name__ == "SendMessage" and "reply_markup" in dir(c) and isinstance(c.reply_markup, InlineKeyboardMarkup)
               for c in calls):
        failures += 1
        lines.append("[FAIL] obuna: chuqur havola kartochkasi yuborilmadi")
    await db.set_session(TEST_ID, {})

    # ---- eski (kirish imkonsiz) xabardagi tugmalar ----
    await step("cb cat:3 (eski xabar, InaccessibleMessage)", cbq("cat:3", old=True))
    await step("cb c:<id> (eski xabar)", cbq(f"c:{cid}", old=True))
    await step("cb fv:<id> (eski xabar)", cbq(f"fv:{cid}", old=True))
    await step("cb fv:<id> (eski xabar, qaytarish)", cbq(f"fv:{cid}", old=True))
    await step("cb rt:<id> (eski xabar)", cbq(f"rt:{cid}", old=True), expect_calls=False)

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

    # ================= YANGI IMKONIYATLAR =================
    def inline_q(text: str) -> dict:
        return {"update_id": nxt(), "inline_query": {"id": str(nxt()), "from": user, "query": text, "offset": "", "chat_type": "sender"}}

    await db.set_session(TEST_ID, {})
    # ---- til almashtirish
    await step("/lang", msg("/lang"))
    await step("cb lang:ru", cbq("lang:ru"))
    await step("ru: menyu «Найти центр»", msg(i18n.S["btn_find"][1]))
    await step("ru: cb cat:3", cbq("cat:3"))
    await step("ru: cb lvl:3:x", cbq("lvl:3:x"))
    await step("ru: cb fr:3:x:1", cbq("fr:3:x:1"))
    await step("ru: cb c:<id>", cbq(f"c:{cid}"))
    await step("ru: profil", msg(i18n.S["btn_profile"][1]))
    await step("ru: /help", msg("/help"))
    await step("cb lang:uz", cbq("lang:uz"))

    # ---- qidiruv: narx, saralash, deep link
    await step("matn: 'ingliz tili 1 mln gacha'", msg("ingliz tili 1 mln gacha"))
    await step("cb prcm", cbq("prcm"))
    await step("cb prc:500000", cbq("prc:500000"))
    await step("cb srtm", cbq("srtm"))
    await step("cb srt:cheap", cbq("srt:cheap"))
    await step("cb srt:rating", cbq("srt:rating"))
    await step("matn: 'arzon matematika'", msg("arzon matematika"))
    await step("matn: 'reyting IELTS'", msg("reyting IELTS"))

    # ---- taqqoslash
    try:
        two = await db.list_centers(category=1, limit=3)
        ids = [x["id"] for x in two["items"]][:3]
    except DBError:
        ids = [cid]
    for i, c in enumerate(ids):
        await step(f"cb cmp:{i + 1}-markaz", cbq(f"cmp:{c}"))
    await step("cb cmps (taqqoslash)", cbq("cmps"))
    await step("cb cmpx (tozalash)", cbq("cmpx"))

    # ---- sinov darsi (yuborilmaydi)
    await step("cb tr:<id> (sinov darsi)", cbq(f"tr:{cid}"))
    await step("cb trd:0", cbq("trd:0"))
    await step("cb trb", cbq("trb"))
    await step("cb trd:0 (qayta)", cbq("trd:0"))
    await step("cb trt:0", cbq("trt:0"))
    await step("cb trc:-1", cbq("trc:-1"))
    await step("matn: sinov ismi", msg("Selftest Sinov"))
    await step("matn: noto'g'ri telefon", msg("12"))
    await step("cancel (sinov darsini to'xtatish)", msg("/cancel"))

    # ---- daraja testi
    await step("menyu: Daraja testi", msg(kb.BTN_TEST))
    await step("cb lt:s", cbq("lt:s"))
    for qi in range(15):
        await step(f"cb lt:a:{qi}:0", cbq(f"lt:a:{qi}:0"))
    await step("cb lt:c (mos markazlar)", cbq("lt:c"))
    await step("cb lt:i (IELTS)", cbq("lt:i"))
    await step("cb lt:s + lt:x", cbq("lt:s"))
    await step("cb lt:x", cbq("lt:x"))

    # ---- farzandim uchun
    await step("menyu: Farzandim uchun", msg(kb.BTN_FAMILY))
    await step("cb fam:add", cbq("fam:add"))
    await step("matn: noto'g'ri kod", msg("12"))
    await step("matn: mavjud bo'lmagan kod", msg("000000"))
    await step("cancel (farzand)", msg("/cancel"))
    await step("cb fam:list", cbq("fam:list"))

    # ---- markaz egasi
    await step("menyu: /owner", msg("/owner"))
    await step("cb own:new", cbq("own:new"), expect_calls=False)
    await step("cb own:all", cbq("own:all"), expect_calls=False)
    await step("cb own:r:7", cbq("own:r:7"), expect_calls=False)
    await step("cb apo:0:ok (begona ariza)", cbq("apo:0:ok"))

    # ---- hisob, taklif
    await step("cb acc:how", cbq("acc:how"))
    await step("cb my:study", cbq("my:study"))
    await step("cb acc:unlink", cbq("acc:unlink"))
    await step("menyu: ulashish + takliflar", msg(kb.BTN_SHARE))
    await step("cb ref:code", cbq("ref:code"))
    await step("matn: noto'g'ri kod", msg("!!"))
    await step("matn: mavjud bo'lmagan taklif kodi", msg("ZZZZ9999"))
    await step("cancel (kod)", msg("/cancel"))

    # ---- inline rejim
    await step("inline: 'ingliz tili'", inline_q("ingliz tili"))
    await step("inline: bo'sh so'rov", inline_q(""))
    await step("inline: 'IELTS 1 mln gacha'", inline_q("IELTS 1 mln gacha"))

    # ---- kanal posti (yubormaydi)
    try:
        post, markup = daily.build_post(await db.daily_digest(), daily.today())
        if post and markup:
            lines.append(f"[ OK ] kunlik post matni tayyor ({len(post)} belgi)")
        else:
            lines.append("[WARN] kunlik post: kun markazi topilmadi")
    except Exception as exc:  # noqa: BLE001
        failures += 1
        lines.append(f"[FAIL] kunlik post: {exc!r}")
    await step("yakuniy: /start", msg("/start"))

    summary = f"JAMI: {len([l for l in lines if l.startswith('[')])} tekshiruv, xatolar: {failures}"
    return summary + "\n" + "\n".join(lines)
