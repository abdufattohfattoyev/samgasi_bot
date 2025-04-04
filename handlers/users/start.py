import asyncio
import logging
import os
import io
import pandas as pd
import matplotlib.pyplot as plt
from aiogram import types, Dispatcher
from aiogram.dispatcher.filters.builtin import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, InputFile
from aiogram.types import ChatMemberStatus, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.exceptions import ChatAdminRequired
# Qo'shimcha import qo'shing:
from aiogram.dispatcher import FSMContext

from handlers.users.reklama import check_admin_permission, check_super_admin_permission, ReklamaTuriState, \
    get_ad_type_keyboard
from loader import dp, bot, user_db
from data.config import ADMINS

# Ikkita majburiy kanal
REQUIRED_CHANNELS = ["@yosh_dasturcii", "@kino_mania_2024"]

# Foydalanuvchilarning obuna holati
user_subscription_status = {}

async def check_subscription(user_id):
    """Foydalanuvchining kanallarga obuna bo‘lganligini tekshiradi."""
    status_dict = {}
    for channel in REQUIRED_CHANNELS:
        try:
            status = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            status_dict[channel] = status.status in ["member", "administrator", "creator"]
        except ChatAdminRequired:
            status_dict[channel] = False
        except Exception as e:
            status_dict[channel] = False
            logging.error(f"Kanalni tekshirishda xatolik yuz berdi: {e}")
    return status_dict

async def ensure_subscription(message: types.Message):
    """Obuna holatini tekshiradi va tugmalar tayyorlaydi."""
    subscription_status = await check_subscription(message.from_user.id)
    markup = InlineKeyboardMarkup(row_width=1)
    all_subscribed = True
    unsubscribed_channels = []

    for idx, channel in enumerate(REQUIRED_CHANNELS, 1):
        is_subscribed = subscription_status.get(channel, False)
        if not is_subscribed:
            unsubscribed_channels.append((idx, channel))
            all_subscribed = False

    if all_subscribed:
        user_subscription_status[message.from_user.id] = True
        return True, markup, unsubscribed_channels

    for idx, channel in unsubscribed_channels:
        button_text = f"❌ Kanal {idx} - {channel}"
        button_url = f"https://t.me/{channel.lstrip('@')}"
        markup.add(InlineKeyboardButton(button_text, url=button_url))

    markup.add(InlineKeyboardButton("✅ Obunani tekshirish", callback_data="check_subscription"))
    await message.answer(
        "<b>❌ Botdan foydalanish uchun quyidagi kanallarga a'zo bo‘ling:</b>",
        parse_mode="HTML", reply_markup=markup
    )
    return False, markup, unsubscribed_channels

# Start komandasi
@dp.message_handler(CommandStart())
async def bot_start(message: types.Message):
    subscription_status, markup, unsubscribed_channels = await ensure_subscription(message)
    if not subscription_status:
        return

    user_info = {
        "user_id": message.from_user.id,
        "full_name": message.from_user.full_name,
        "username": message.from_user.username,
    }
    existing_user = user_db.get_user_by_id(user_info['user_id'])
    if not existing_user:
        user_db.add_user(user_info['user_id'], user_info['username'])
        print(f"Foydalanuvchi {message.from_user.full_name} ro'yxatga olindi.")

    await message.answer("Salom! Iltimos, ID ni kiriting.")

# Obunani tekshirish callback
@dp.callback_query_handler(lambda c: c.data == "check_subscription")
async def check_subscription_callback(query: types.CallbackQuery):
    user_id = query.from_user.id
    subscription_status = await check_subscription(user_id)
    markup = InlineKeyboardMarkup(row_width=1)
    all_subscribed = True
    unsubscribed_channels = []

    for idx, channel in enumerate(REQUIRED_CHANNELS, 1):
        is_subscribed = subscription_status.get(channel, False)
        if not is_subscribed:
            unsubscribed_channels.append((idx, channel))
            all_subscribed = False

    if all_subscribed:
        await query.message.delete()
        await bot.send_message(user_id, "✅ Barcha kanallarga a'zo bo‘ldingiz! ID kiriting.")
    else:
        await query.message.delete()
        for idx, channel in unsubscribed_channels:
            button_text = f"❌ Kanal {idx} - {channel}"
            button_url = f"https://t.me/{channel.lstrip('@')}"
            markup.add(InlineKeyboardButton(button_text, url=button_url))
        markup.add(InlineKeyboardButton("✅ Obunani tekshirish", callback_data="check_subscription"))
        await bot.send_message(
            user_id,
            "<b>❌ Quyidagi kanallarga a'zo bo‘ling:</b>",
            parse_mode="HTML", reply_markup=markup
        )
    await query.answer()

# Excel faylini o‘qish uchun sinf
class ExcelDataHandler:
    def __init__(self):
        self.excel_data = None
        self.saved_file_name = None

    def load_excel(self, file_path):
        try:
            self.excel_data = pd.read_excel(file_path, engine='openpyxl')
            if 'ID' not in self.excel_data.columns:
                return None, "'ID' ustuni mavjud emas."
            self.excel_data['ID'] = self.excel_data['ID'].astype(str).str.strip()
            return True, "Fayl muvaffaqiyatli o'qildi."
        except Exception as e:
            return None, str(e)

    def get_user_data_by_id(self, user_id):
        if self.excel_data is None:
            return None
        user_data = self.excel_data[self.excel_data['ID'].astype(str).str.strip() == user_id]
        return user_data if not user_data.empty else None

excel_data_handler = ExcelDataHandler()

# ID bo‘yicha ma’lumot qidirish
@dp.message_handler(lambda message: message.text.isdigit())
async def handle_id_input(message: types.Message):
    subscription_status, markup, unsubscribed_channels = await ensure_subscription(message)
    if not subscription_status:
        return

    user_id = message.text
    if excel_data_handler.excel_data is None:
        await message.answer("❗ Hozircha ma'lumotlar mavjud emas. Admin bilan bog‘laning: @FATTOYEVABDUFATTOH")
        return

    user_data = excel_data_handler.get_user_data_by_id(user_id)
    if user_data is None:
        await message.answer(f"❌ ID {user_id} bo‘yicha ma'lumot topilmadi.")
    else:
        await send_user_data_as_image(message, user_id)

# Ma'lumotni rasm shaklida jo'natish
async def send_user_data_as_image(message: types.Message, user_id: str):
    user_data = excel_data_handler.get_user_data_by_id(user_id)
    if not user_data.empty:
        headers = user_data.columns.to_list()
        values = [[int(val) if isinstance(val, float) and val.is_integer() else val for val in row]
                  for row in user_data.values.tolist()]

        fig, ax = plt.subplots(figsize=(10, len(user_data) * 0.6 + 1))
        ax.axis('tight')
        ax.axis('off')

        table_data = [headers] + values
        table = ax.table(cellText=table_data, cellLoc='center', loc='center')
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1.4, 1.6)
        table.auto_set_column_width(col=list(range(len(headers))))

        for (i, j), cell in table.get_celld().items():
            if i == 0:
                cell.set_fontsize(10)
                cell.set_text_props(weight='bold')
                cell.set_facecolor('#d3d3d3')

        img_stream = io.BytesIO()
        plt.savefig(img_stream, format='png', bbox_inches='tight', dpi=300)
        img_stream.seek(0)
        plt.close()

        photo = InputFile(img_stream, filename="user_data.png")
        caption = f"📊 <b>ID {user_id} bo‘yicha ma'lumot</b>\nAdmin: @FATTOYEVABDUFATTOH"
        await message.answer_photo(photo, caption=caption, parse_mode='HTML')

# Admin panel
# Admin panelini yangilang
@dp.message_handler(commands=['admin_panel'])
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMINS:
        await message.answer("❌ Siz admin emassiz!")
        return

    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        KeyboardButton('📤 Fayl yuklash'),
        KeyboardButton('🗑️ Fayl o\'chirish'),
        KeyboardButton('👥 Foydalanuvchilar soni')  # Yangi tugma
    )
    await message.answer("👨‍💻 Admin paneliga xush kelibsiz! Quyidagi amallarni tanlang:", reply_markup=keyboard)


@dp.message_handler(lambda message: message.text == '👥 Foydalanuvchilar soni')
async def show_users_count(message: types.Message):
    if message.from_user.id not in ADMINS:
        await message.answer("❌ Siz admin emassiz!")
        return

    try:
        users_count = user_db.count_users()
        await message.answer(f"👥 Botdagi jami foydalanuvchilar soni: {users_count}")
    except Exception as e:
        logging.error(f"Foydalanuvchilar sonini olishda xato: {e}")
        await message.answer("❌ Foydalanuvchilar sonini olishda xatolik yuz berdi")

# Fayl yuklash
@dp.message_handler(lambda message: message.text == '📤 Fayl yuklash')
async def cmd_upload(message: types.Message):
    if message.from_user.id not in ADMINS:
        await message.answer("❌ Siz admin emassiz!")
        return
    await message.answer("📥 Iltimos, Excel faylini yuboring (.xlsx formatida).")

# Faylni qayta ishlash
@dp.message_handler(content_types=['document'])
async def handle_document(message: types.Message):
    if message.from_user.id not in ADMINS:
        await message.answer("❌ Faqat adminlar fayl yuklashi mumkin!")
        return

    file_name = message.document.file_name
    if not file_name.endswith('.xlsx'):
        await message.answer("❌ Iltimos, faqat .xlsx formatidagi fayl yuboring!")
        return

    file_path = os.path.join('files', file_name)
    os.makedirs('files', exist_ok=True)
    await message.document.download(destination_file=file_path)

    success, error_msg = excel_data_handler.load_excel(file_path)
    if success:
        excel_data_handler.saved_file_name = file_name
        await message.answer("✅ Excel fayli muvaffaqiyatli yuklandi va qayta ishlanmoqda!")
    else:
        await message.answer(f"❌ Xatolik yuz berdi: {error_msg}")

# Fayl o'chirish
@dp.message_handler(lambda message: message.text == '🗑️ Fayl o\'chirish')
async def delete_file(message: types.Message):
    if message.from_user.id not in ADMINS:
        await message.answer("❌ Siz admin emassiz!")
        return

    if excel_data_handler.saved_file_name:
        os.remove(os.path.join('files', excel_data_handler.saved_file_name))
        excel_data_handler.excel_data = None
        excel_data_handler.saved_file_name = None
        await message.answer("✅ Fayl muvaffaqiyatli o'chirildi!")
    else:
        await message.answer("❌ O'chirish uchun fayl topilmadi!")

@dp.message_handler(commands=['reklama'], state="*")
@dp.message_handler(text="📣 Reklama", state="*")
async def reklama_handler(message: types.Message):
    telegram_id = message.from_user.id
    if await check_admin_permission(telegram_id) or await check_super_admin_permission(telegram_id):
        await ReklamaTuriState.tur.set()  # Reklama turini tanlash holatiga o'tish
        await bot.send_message(chat_id=message.chat.id, text="Reklama turini tanlang:", reply_markup=get_ad_type_keyboard())
    else:
        await message.reply("Sizda ushbu amalni bajarish uchun ruxsat yo'q.")

# Har qanday noto'g'ri xabar uchun
@dp.message_handler()
async def wrong_input(message: types.Message):
    # /reklama komandasini o'tkazib yuborish
    if message.text.startswith('/reklama'):
        return await reklama_handler(message)

    subscription_status, markup, unsubscribed_channels = await ensure_subscription(message)
    if not subscription_status:
        return

    await message.answer("❗ Iltimos, to'g'ri ID kiriting yoki /start buyrug'ini bosing!")