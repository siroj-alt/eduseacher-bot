import os

from aiogram import Dispatcher, types
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

WEB_APP_URL = os.getenv("WEB_APP_URL", "https://edusearcher.uz")

dp = Dispatcher()

# WebApp tugmasi
web_app_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔍 Platformani ochish",
                web_app=WebAppInfo(url=WEB_APP_URL),
            )
        ]
    ]
)


@dp.message(CommandStart())
async def start_command(message: types.Message):
    user_name = message.from_user.first_name if message.from_user else "do'st"
    text = (
        f"👋 Salom, <b>{user_name}</b>!\n\n"
        f"<b>EduSearcher.uz</b> rasmiy botiga xush kelibsiz! 🎓\n\n"
        f"Oʻzbekistondagi eng mos oʻquv markazlari va kurslarni topish uchun pastdagi tugmani bosing 👇"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=web_app_keyboard)


@dp.message(Command("help"))
async def help_command(message: types.Message):
    text = (
        "❓ <b>Yordam boʻlimi</b>\n\n"
        "EduSearcher platformasidan foydalanish uchun «🔍 Platformani ochish» tugmasini bosing.\n"
        "Muammo yoki takliflar bo'lsa: @sirojshukrullayev bilan bog'laning."
    )
    await message.answer(text, parse_mode="HTML", reply_markup=web_app_keyboard)


@dp.message(Command("about"))
async def about_command(message: types.Message):
    text = (
        "ℹ️ <b>EduSearcher.uz haqida</b>\n\n"
        "EduSearcher — ta'lim muassasalarini tez va qulay izlab topish platformasi."
    )
    await message.answer(text, parse_mode="HTML", reply_markup=web_app_keyboard)
