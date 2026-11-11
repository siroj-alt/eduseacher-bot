import os
from urllib.parse import quote

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

WEB_APP_URL = os.getenv("WEB_APP_URL", "https://edusearcher.uz")
# Ixtiyoriy: bot username (@siz). Bo'lmasa Telegram'dan avtomatik olinadi.
BOT_USERNAME = os.getenv("BOT_USERNAME", "").lstrip("@")

SHARE_CALLBACK = "share_friends"

dp = Dispatcher()


def main_keyboard() -> InlineKeyboardMarkup:
    """Asosiy tugmalar: Web App + do'stlarga ulashish."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔍 Platformani ochish",
                    web_app=WebAppInfo(url=WEB_APP_URL),
                )
            ],
            [
                InlineKeyboardButton(
                    text="📤 Do'stlarga ulashish",
                    callback_data=SHARE_CALLBACK,
                )
            ],
        ]
    )


async def get_bot_username(bot: Bot) -> str:
    if BOT_USERNAME:
        return BOT_USERNAME
    me = await bot.me()
    return me.username or ""


def referral_link(username: str, user_id: int) -> str:
    return f"https://t.me/{username}?start=ref_{user_id}"


def share_announcement() -> str:
    return (
        "🎓 EduSearcher.uz — Oʻzbekistondagi oʻquv markazlari va kurslarni "
        "bir joyda topishning qulay usuli!\n\n"
        "📍 Kurs, daraja va joylashuv boʻyicha eng mos markazni tanlang.\n"
        "👇 Botni ochish uchun havolani bosing:"
    )


@dp.message(CommandStart())
async def start_command(message: types.Message, command: CommandObject):
    user_name = message.from_user.first_name if message.from_user else "do'st"
    invited = bool(command.args and command.args.startswith("ref_"))
    text = (
        f"👋 Salom, <b>{user_name}</b>!\n\n"
        f"<b>EduSearcher.uz</b> rasmiy botiga xush kelibsiz! 🎓\n\n"
        f"Oʻzbekistondagi eng mos oʻquv markazlari va kurslarni topish uchun pastdagi tugmani bosing 👇"
    )
    if invited:
        text += "\n\n🤝 Sizni doʻstingiz taklif qildi — xush kelibsiz!"
    await message.answer(text, parse_mode="HTML", reply_markup=main_keyboard())


@dp.message(Command("help"))
async def help_command(message: types.Message):
    text = (
        "❓ <b>Yordam boʻlimi</b>\n\n"
        "EduSearcher platformasidan foydalanish uchun «🔍 Platformani ochish» tugmasini bosing.\n"
        "Doʻstlaringizga ulashish uchun «📤 Do'stlarga ulashish» tugmasidan foydalaning.\n"
        "Muammo yoki takliflar bo'lsa: @sirojshukrullayev bilan bog'laning."
    )
    await message.answer(text, parse_mode="HTML", reply_markup=main_keyboard())


@dp.message(Command("about"))
async def about_command(message: types.Message):
    text = (
        "ℹ️ <b>EduSearcher.uz haqida</b>\n\n"
        "EduSearcher — ta'lim muassasalarini tez va qulay izlab topish platformasi."
    )
    await message.answer(text, parse_mode="HTML", reply_markup=main_keyboard())


async def send_share(message: types.Message, user_id: int, bot: Bot) -> None:
    username = await get_bot_username(bot)
    link = referral_link(username, user_id)
    announcement = share_announcement()
    share_url = f"https://t.me/share/url?url={quote(link, safe='')}&text={quote(announcement, safe='')}"

    # Foydalanuvchi shu xabarni oʻzi ham koʻrib, boshqalarga yubora oladi
    await message.answer(
        f"{announcement}\n{link}",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📨 Doʻstga yuborish", url=share_url)]
            ]
        ),
        disable_web_page_preview=True,
    )
    await message.answer(
        "☝️ Shu eʼlonni doʻstlaringizga yuboring yoki «📨 Doʻstga yuborish» tugmasini bosing. "
        "Ular sizning havolangiz orqali botga qoʻshiladi."
    )


@dp.callback_query(F.data == SHARE_CALLBACK)
async def share_callback(callback: types.CallbackQuery, bot: Bot):
    await callback.answer()
    if callback.message:
        await send_share(callback.message, callback.from_user.id, bot)


@dp.message(Command("share"))
async def share_command(message: types.Message, bot: Bot):
    if message.from_user:
        await send_share(message, message.from_user.id, bot)
