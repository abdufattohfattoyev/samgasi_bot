import logging
from aiogram import executor

from loader import dp, user_db
import middlewares, filters, handlers
from utils.notify_admins import on_startup_notify
from utils.set_bot_commands import set_default_commands


# Logger sozlash
logging.basicConfig(level=logging.INFO)

async def on_startup(dispatcher):
    """Botni ishga tushirishda bajariladigan funksiya"""
    # Birlamchi komandalar (/start va /help)
    await set_default_commands(dispatcher)

    try:
        # Foydalanuvchilar jadvalini yaratish
        user_db.create_table_users()
        logging.info("Foydalanuvchilar jadvali yaratildi yoki allaqachon mavjud.")
    except Exception as e:
        logging.error(f"Foydalanuvchilar jadvali yaratishda xatolik: {e}")


    await on_startup_notify(dispatcher)


if __name__ == '__main__':
    # Botni boshlash
    executor.start_polling(dp, on_startup=on_startup)
