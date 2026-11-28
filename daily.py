"""Kanal (@edusearcher) uchun kunlik avtomatik post: kun markazi, yangi markazlar, chegirmalar va «kunlik so'z»."""
import datetime as dt
import logging
import os

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup

import fmt
import i18n
import kb
from db import DB, DBError
from fmt import esc

log = logging.getLogger("bot.daily")
CHANNEL = os.getenv("CHANNEL_USERNAME", "@edusearcher").strip()

# (inglizcha so'z, o'zbekcha ma'nosi, misol)
WORDS = [
    ("achieve", "erishmoq", "She worked hard to achieve her goal."), ("borrow", "qarzga olmoq", "Can I borrow your pen?"),
    ("improve", "yaxshilamoq", "I want to improve my English."), ("deadline", "oxirgi muddat", "The deadline is on Friday."),
    ("knowledge", "bilim", "Knowledge is power."), ("improve", "rivojlantirmoq", "Reading helps you improve vocabulary."),
    ("opportunity", "imkoniyat", "This is a great opportunity."), ("experience", "tajriba", "He has five years of experience."),
    ("challenge", "qiyin sinov", "Learning a language is a challenge."), ("confident", "o'ziga ishongan", "She feels confident today."),
    ("skill", "ko'nikma", "Communication is a key skill."), ("career", "kasb yo'li", "He started his career as a teacher."),
    ("increase", "oshirmoq", "Prices increase every year."), ("reduce", "kamaytirmoq", "We must reduce waste."),
    ("develop", "rivojlanmoq", "Children develop quickly."), ("suggest", "taklif qilmoq", "I suggest taking a break."),
    ("decide", "qaror qilmoq", "It's time to decide."), ("believe", "ishonmoq", "I believe in you."),
    ("require", "talab qilmoq", "This job requires patience."), ("attend", "qatnashmoq", "Please attend the lesson on time."),
    ("explain", "tushuntirmoq", "Can you explain this rule?"), ("increase", "ko'paymoq", "The number of students will increase."),
    ("receive", "qabul qilmoq", "She received a certificate."), ("prepare", "tayyorlanmoq", "Prepare for the exam in advance."),
    ("beautiful", "chiroyli", "What a beautiful city!"), ("difficult", "qiyin", "The test was difficult."),
    ("important", "muhim", "Practice is important."), ("necessary", "zarur", "Is it necessary to book a seat?"),
    ("popular", "mashhur", "This course is very popular."), ("useful", "foydali", "That's a useful tip."),
    ("reliable", "ishonchli", "He is a reliable friend."), ("curious", "qiziquvchan", "Children are naturally curious."),
    ("patient", "sabrli", "A good teacher is patient."), ("honest", "halol", "Be honest with yourself."),
    ("journey", "sayohat", "Learning is a long journey."), ("goal", "maqsad", "Set a clear goal."),
    ("habit", "odat", "Reading daily is a good habit."), ("progress", "yutuq, taraqqiyot", "You are making progress!"),
    ("advice", "maslahat", "Thanks for your advice."), ("environment", "muhit", "Protect the environment."),
    ("education", "ta'lim", "Education changes lives."), ("scholarship", "stipendiya", "She won a scholarship."),
    ("graduate", "bitirmoq", "He will graduate in June."), ("research", "tadqiqot", "They do research at the university."),
    ("lecture", "ma'ruza", "The lecture starts at nine."), ("homework", "uy vazifasi", "Did you finish your homework?"),
    ("mistake", "xato", "Mistakes help us learn."), ("fluent", "ravon", "She is fluent in three languages."),
    ("vocabulary", "lug'at boyligi", "Build your vocabulary every day."), ("pronounce", "talaffuz qilmoq", "How do you pronounce this word?"),
    ("grammar", "grammatika", "Grammar is the base of a language."), ("effort", "harakat", "Success needs effort."),
    ("focus", "e'tibor qaratmoq", "Focus on one task at a time."), ("remember", "eslab qolmoq", "I can't remember his name."),
    ("discover", "kashf qilmoq", "Discover new ways to learn."), ("support", "qo'llab-quvvatlamoq", "Parents support their children."),
    ("curriculum", "o'quv dasturi", "The curriculum is updated yearly."), ("certificate", "sertifikat", "You will get a certificate."),
]

TASHKENT = dt.timezone(dt.timedelta(hours=5))


def today() -> dt.date:
    return dt.datetime.now(TASHKENT).date()


def word_of_day(d: dt.date) -> tuple:
    return WORDS[d.timetuple().tm_yday % len(WORDS)]


def build_post(digest: dict, d: dt.date) -> tuple:
    """(matn, tugmalar) — kun markazi yo'q bo'lsa (None, None)."""
    i18n.set_ctx("uz")
    top = digest.get("top")
    if not top:
        return None, None
    lines = [f"🌅 <b>Kun markazi · {d.day:02d}.{d.month:02d}.{d.year}</b>", ""]
    head = f"🏫 <b>{esc(top.get('name'))}</b>" + (" ✅" if top.get("is_verified") else "")
    lines.append(head)
    bits = []
    rating = fmt.fmt_rating(top.get("rating"))
    if rating:
        bits.append(rating)
    if top.get("region"):
        bits.append("📍 " + esc(i18n.reg_name(top["region"])))
    if bits:
        lines.append(" · ".join(bits))
    price = fmt.fmt_price(top.get("min_price"))
    if price or top.get("courses"):
        row = []
        if price:
            row.append("💰 " + i18n.t("price_from", price=price))
        if top.get("courses"):
            row.append(f"📚 {int(top['courses'])} ta kurs")
        lines.append(" · ".join(row))
    if top.get("app_discount"):
        lines.append(f"🏷 Ariza qoldirganlarga −{int(top['app_discount'])}% chegirma")
    if top.get("description"):
        lines += ["", esc(fmt.clip(top["description"], 180))]

    new = digest.get("new") or []
    if new:
        lines += ["", "🆕 <b>Yangi markazlar</b>"]
        for c in new[:5]:
            extra = " · ".join(x for x in [esc(i18n.reg_name(c.get("region"))),
                                           (i18n.t("price_from", price=fmt.fmt_price(c.get("min_price")))
                                            if c.get("min_price") else "")] if x)
            lines.append(f"• {esc(fmt.clip(c.get('name'), 40))}" + (f" — {extra}" if extra else ""))
    disc = digest.get("discounts") or []
    if disc:
        lines += ["", "🏷 <b>Chegirmalar</b>"]
        for c in disc[:5]:
            lines.append(f"• {esc(fmt.clip(c.get('name'), 40))} — −{int(c.get('app_discount') or 0)}%")

    en, uz, example = word_of_day(d)
    lines += ["", f"📖 <b>Kunlik so'z:</b> <b>{esc(en)}</b> — {esc(uz)}", f"<i>{esc(example)}</i>"]
    lines += ["", f"🎓 Jami {int(digest.get('total') or 0)} ta markaz · @{kb.BOT_USERNAME}"]

    rows = [[kb.ub("🏫 Markaz haqida batafsil", f"https://t.me/{kb.BOT_USERNAME}?start=c_{top['id']}")],
            [kb.ub("🔍 Botda qidirish", f"https://t.me/{kb.BOT_USERNAME}"),
             kb.ub("🌐 Sayt", kb.WEB_APP_URL)]]
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


async def run_daily(bot: Bot, db: DB, dry: bool = False) -> str:
    """Bugungi postni kanalga yuboradi (kuniga bir marta). dry=True — faqat matnni qaytaradi, hech narsa yubormaydi."""
    d = today()
    digest = await db.daily_digest()
    text, markup = build_post(digest, d)
    if not text:
        return "skip: kun markazi yo'q"
    if dry:
        return text
    if not await db.claim_daily("channel_post"):
        return "skip: bugun allaqachon yuborilgan"
    try:
        await bot.send_message(CHANNEL, text, reply_markup=markup, disable_web_page_preview=True)
    except Exception as exc:  # noqa: BLE001
        try:
            await db.unclaim_daily("channel_post")
        except DBError:
            log.exception("unclaim ishlamadi")
        raise RuntimeError(f"Kanalga yuborib bo'lmadi: {type(exc).__name__}: {exc}") from exc
    return "posted"
