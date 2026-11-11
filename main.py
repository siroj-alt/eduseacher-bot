import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

# BotFather'dan olingan TOKEN va Vercel/Netlify saytingiz havolasini kiriting
BOT_TOKEN = "AAF3pNMC_QJOovnA4POzx9XcP6sJI7Ye7gc"
WEB_APP_URL = "https://edusearcher.uz"  # Saytingiz manzili

bot = Bot(token=AAF3pNMC_QJOovnA4POzx9XcP6sJI7Ye7gc)
dp = Dispatcher()

# WebApp tugmasini yaratish
web_app_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(
            text="🔍 Platformani ochish", 
            web_app=WebAppInfo(url=https://edusearcher.uz)
        )
    ]
])

# /start komandasi uchun handler
@dp.message(CommandStart())
async def start_command(message: types.Message):
    user_name = message.from_user.first_name
    text = (
        f"👋 Salom, <b>{user_name}</b>!\n\n"
        f"<b>EduSearcher.uz</b> rasmiy botiga xush kelibsiz! 🎓\n\n"
        f"Oʻzbekistondagi eng mos oʻquv markazlari va kurslarni topish uchun pastdagi tugmani bosing 👇"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=web_app_keyboard)

# /help komandasi uchun handler
@dp.message(Command("help"))
async def help_command(message: types.Message):
    text = (
        "❓ <b>Yordam boʻlimi</b>\n\n"
        "EduSearcher platformasidan foydalanish uchun «🔍 Kirish» tugmasini bosing.\n"
        "Muammo yoki takliflar bo'lsa: @sirojshukrullayev bilan bog'laning."
    )
    await message.answer(text, parse_mode="HTML", reply_markup=web_app_keyboard)

# /about komandasi uchun handler
@dp.message(Command("about"))
async def about_command(message: types.Message):
    text = (
        "ℹ️ <b>EduSearcher.uz haqida</b>\n\n"
        "EduSearcher — ta'lim muassasalarini tez va qulay izlab topish platformasi."
    )
    await message.answer(text, parse_mode="HTML", reply_markup=web_app_keyboard)

async def main():
    logging.basicConfig(level=logging.INFO)
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())