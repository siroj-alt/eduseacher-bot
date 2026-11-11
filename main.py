"""Lokal ishga tushirish (polling). Vercel'da esa api/webhook.py ishlaydi.

Ishlatish:
    BOT_TOKEN=... python main.py
"""
import asyncio
import logging
import os

from aiogram import Bot

from bot_handlers import dp


async def main():
    logging.basicConfig(level=logging.INFO)
    token = os.environ["BOT_TOKEN"]
    bot = Bot(token=token)
    # Webhook o'rnatilgan bo'lsa, polling ishlashi uchun uni o'chirib qo'yamiz
    await bot.delete_webhook(drop_pending_updates=True)
    print("Bot ishga tushdi (polling)...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
