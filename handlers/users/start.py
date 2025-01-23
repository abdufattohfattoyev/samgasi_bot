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

from loader import dp, bot, user_db
from data.config import ADMINS
from aiogram.types import ChatMemberStatus

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ChatMemberStatus, ParseMode
from aiogram import types



REQUIRED_CHANNELS = ["@yosh_dasturcii"]

# Foydalanuvchilarning obuna bo'lganligini tekshirish uchun flag
user_subscription_status = {}

async def check_subscription(user_id):
    """
    Foydalanuvchining majburiy kanallarga obuna bo'lganligini tekshiradi.
    """
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
    """
    Foydalanuvchining obunaga bo'lishi kerakligini tekshiradi va inline tugmalarni tayyorlaydi.
    """
    subscription_status = await check_subscription(message.from_user.id)

    # Inline tugmalarni tayyorlash
    markup = types.InlineKeyboardMarkup(row_width=1)
    all_subscribed = True
    unsubscribed_channels = []

    # Har bir kanalni tekshirish va tugmalarni yaratish
    for index, channel in enumerate(REQUIRED_CHANNELS, 1):
        is_subscribed = subscription_status.get(channel, False)
        button_text = f"{'✅' if is_subscribed else '❌'} Kanal {channel}"  # Kanal nomi "Kanal 1", "Kanal 2" tarzida
        button_url = f"https://t.me/{channel.lstrip('@')}"
        markup.add(types.InlineKeyboardButton(button_text, url=button_url))

        # Agar biron bir kanalga obuna bo'lmagan bo'lsa
        if not is_subscribed:
            unsubscribed_channels.append(channel)
            all_subscribed = False

    # Obunani tekshirish tugmasi
    markup.add(types.InlineKeyboardButton("Obunani tekshirish", callback_data="check_subscription"))

    # Agar barcha kanallarga obuna bo'lsa, foydalanuvchiga ruxsat berish
    if all_subscribed:
        # Foydalanuvchi faqat bir marta xabarni oladi
        if message.from_user.id not in user_subscription_status or not user_subscription_status[message.from_user.id]:
            # Foydalanuvchiga botdan foydalanish uchun ruxsat berish
            user_subscription_status[message.from_user.id] = True
        return True, markup, unsubscribed_channels

    else:
        # Agar foydalanuvchi hali ham obuna bo'lmagan kanallar mavjud bo'lsa
        await message.answer(
            "<b>❌ Kechirasiz botimizdan foydalanishdan oldin ushbu kanallarga a'zo bo'lishingiz kerak.</b>",
            parse_mode="HTML", reply_markup=markup
        )
        return False, markup, unsubscribed_channels


# Foydalanuvchini bazaga qo'shish
@dp.message_handler(CommandStart())
async def bot_start(message: types.Message):
    user_info = {
        "user_id": message.from_user.id,
        "full_name": message.from_user.full_name,
        "username": message.from_user.username,
    }
    existing_user = user_db.get_user_by_id(user_info['user_id'])
    if existing_user:
        print(f"Foydalanuvchi {message.from_user.full_name} allaqachon mavjud.")
    else:
        user_db.add_user(user_info['user_id'], user_info['username'])
        print(f"Foydalanuvchi {message.from_user.full_name} ro'yxatga olindi.")

    # Obuna bo'lishini tekshirish
    subscription_status = await ensure_subscription(message)

    if not subscription_status[0]:
        return

    await message.answer("Salom! Iltimos, ID ni kiriting.")


@dp.callback_query_handler(lambda c: c.data == "check_subscription")
async def check_subscription_callback(query: types.CallbackQuery):
    """
    Obunani tekshirish tugmasi bosilganda, foydalanuvchiga to'liq obuna bo'lishini so'raydi.
    """
    user_id = query.from_user.id
    subscription_status = await check_subscription(user_id)

    # Inline tugmalarni tayyorlash
    markup = types.InlineKeyboardMarkup(row_width=1)
    all_subscribed = True
    unsubscribed_channels = []

    # Faqat obuna bo'lmagan kanallarni tekshirish va tugmalarni yaratish
    for idx, channel in enumerate(REQUIRED_CHANNELS, 1):
        is_subscribed = subscription_status.get(channel, False)
        if not is_subscribed:
            unsubscribed_channels.append(channel)
            button_text = f"❌ Kanal {idx}"
            button_url = f"https://t.me/{channel.lstrip('@')}"
            markup.add(types.InlineKeyboardButton(button_text, url=button_url))
            all_subscribed = False

    # Obunani tekshirish tugmasi
    markup.add(types.InlineKeyboardButton("Obunani tekshirish", callback_data="check_subscription"))

    # Agar barcha kanallarga obuna bo'lsa
    if all_subscribed:
        await query.message.delete()  # Eski xabarni o'chirish
        await bot.send_message(
            user_id,
            "To'liq kanallarga a'zo bo'ldingiz! Endi botdan foydalanish uchun /start buyruqni bosing."
        )
    else:
        new_text = (
            "Siz hali barcha kanallarga obuna bo'lmagansiz. Iltimos, quyidagi kanallarga obuna bo'ling:"
        )
        if query.message.text != new_text:
            await query.message.edit_text(new_text, reply_markup=markup)

    await query.answer()


@dp.message_handler(commands=["start", "help", "settings"])
async def start_help_settings_handler(message: types.Message):
    """
    Har qanday komanda yuborilganda, kanalga obuna bo'lishini tekshirish.
    """
    user_id = message.from_user.id
    subscription_status = await check_subscription(user_id)

    all_subscribed = True
    for channel in REQUIRED_CHANNELS:
        if not subscription_status.get(channel, False):
            all_subscribed = False
            break

    if all_subscribed:
        await message.answer("Botdan foydalanishingiz mumkin!")
    else:
        # Obuna bo'lmagan kanallar ro'yxatini yuborish
        markup = types.InlineKeyboardMarkup(row_width=1)
        for idx, channel in enumerate(REQUIRED_CHANNELS, 1):
            if not subscription_status.get(channel, False):
                button_text = f"❌ Kanal {idx}"
                button_url = f"https://t.me/{channel.lstrip('@')}"
                markup.add(types.InlineKeyboardButton(button_text, url=button_url))

        markup.add(types.InlineKeyboardButton("Obunani tekshirish", callback_data="check_subscription"))

        await message.answer(
            "Siz hali barcha kanallarga obuna bo'lmagansiz. Iltimos, quyidagi kanallarga obuna bo'ling:",
            reply_markup=markup
        )




# Noto'g'ri kiritilgan ma'lumotlarga javob berish
# @dp.message_handler(lambda message: not message.text.isdigit() and message.text.lower() not in ['/reklama', '/admin_panel'])
# async def wrong_input(message: types.Message):
#     await message.answer("Iltimos, to'g'ri ma'lumot kiriting!")

# Excel faylini o'qish uchun sinf
class ExcelDataHandler:
    def __init__(self):
        self.excel_data = None
        self.saved_file_name = None

    def load_excel(self, file_path):
        try:
            self.excel_data = pd.read_excel(file_path, engine='openpyxl')

            # 'ID' ustuni mavjudligini tekshirish
            if 'ID' not in self.excel_data.columns:
                return None, "'ID' ustuni mavjud emas."

            # 'ID' ustunini string ko'rinishida o'qish va tozalash
            self.excel_data['ID'] = self.excel_data['ID'].astype(str).str.strip()
            return True, "Fayl muvaffaqiyatli o'qildi."
        except Exception as e:
            return None, str(e)

    def save_excel(self, file_path):
        try:
            if self.excel_data is not None:
                self.excel_data.to_excel(file_path, index=False)
                return True
            else:
                return False
        except Exception as e:
            return False, str(e)

    def get_user_data_by_id(self, user_id):
        """
        Berilgan ID bo'yicha ma'lumotlarni qaytaradi.
        """
        if self.excel_data is None:
            return None

        user_data = self.excel_data[self.excel_data['ID'].astype(str).str.strip() == user_id]

        if not user_data.empty:
            return user_data
        else:
            return None



excel_data_handler = ExcelDataHandler()  # Instantiation fixed

# ID bo‘yicha ma’lumot qidirish
@dp.message_handler(lambda message: message.text.isdigit())
async def handle_id_input(message: types.Message):
    # Agar foydalanuvchi kanalga obuna bo'lmagan bo'lsa
    if message.from_user.id not in user_subscription_status or not user_subscription_status[message.from_user.id]:
        await message.answer(
            "❗ **Diqqat!**\n\n"
            "Siz hali ham kanalga obuna bo'lmagansiz. Iltimos, kanalga obuna bo'ling va keyin ID yuboring.",
            parse_mode="Markdown"
        )
        return

    user_id = message.text

    # Excel fayli yuklanganligini tekshirish
    if excel_data_handler.excel_data is None:
        await message.answer(
            "❗ **Diqqat!**\n\n"
            "Hozircha ma'lumotlar mavjud emas. Iltimos, fayl yuklanishini kuting yoki admin bilan bog‘laning.\n\n"
            "@FATTOYEVABDUFATTOH",
            parse_mode="Markdown"
        )
        return

    try:
        # ID bo‘yicha ma’lumot qidirish
        user_data = excel_data_handler.get_user_data_by_id(user_id)

        if user_data is None:
            await message.answer(f"❌ ID {user_id} bo‘yicha ma'lumot topilmadi.")
        else:
            # Ma'lumotni rasm shaklida yuborish
            await send_user_data_as_image(message, user_id)

    except Exception as e:
        await message.answer(f"❗ Xatolik yuz berdi: {str(e)}")

# Ma'lumotni rasm shaklida jo'natish
async def send_user_data_as_image(message: types.Message, user_id: str):
    # Foydalanuvchi ma'lumotlarini olish
    user_data = excel_data_handler.excel_data[
        excel_data_handler.excel_data['ID'].astype(str).str.strip() == user_id
        ]

    # Ma'lumotlar mavjudligini tekshirish
    if user_data.empty:
        await message.answer("🛑 Kiritilgan ID bo'yicha ma'lumotlar topilmadi.")
        return

    headers = user_data.columns.to_list()

    # Raqqamlarni butun son sifatida formatlash
    def format_value(val):
        if isinstance(val, float) and val.is_integer():
            return int(val)  # Butun sonni qaytarish
        return val

    values = [list(map(format_value, row)) for row in user_data.values.tolist()]

    # Grafikni yaratish
    fig, ax = plt.subplots(figsize=(10, len(user_data) * 0.6 + 1))  # figsize ni kichraytirish
    ax.axis('tight')
    ax.axis('off')

    table_data = [headers] + values
    table = ax.table(cellText=table_data, cellLoc='center', loc='center')

    # Jadvalni chiroyli qilish
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.4, 1.6)  # Jadvalni biroz kichraytirish
    table.auto_set_column_width(col=list(range(len(headers))))

    # Yacheyka rangini o'zgartirish (masalan, sarlavhalar uchun)
    for (i, j), cell in table.get_celld().items():
        if i == 0:  # Sarlavhalar qatori
            cell.set_fontsize(10)
            cell.set_text_props(weight='bold')
            cell.set_facecolor('lightgrey')

    # Rasmni saqlash va yuborish
    img_stream = io.BytesIO()
    plt.savefig(img_stream, format='png', bbox_inches='tight', dpi=300)  # dpi ni kamaytirish
    img_stream.seek(0)
    plt.close()

    photo = InputFile(img_stream, filename="user_data.png")
    await message.answer_photo(photo, caption=f"📊 <b>ID {user_id} bo‘yicha ma'lumot</b>", parse_mode='HTML')


# Admin panel
@dp.message_handler(commands=['admin_panel'])
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMINS:
        await message.answer("Siz admin emassiz!")
        return
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton('Fayl yuklash'), KeyboardButton("Fayl o'chirish"))
    await message.answer("Admin paneliga xush kelibsiz. Quyidagi amallarni tanlang:", reply_markup=keyboard)

@dp.message_handler(lambda message: message.text.lower() == 'fayl yuklash')
async def cmd_upload(message: types.Message):
    await message.answer("Iltimos, Excel faylini yuboring.")

# Fayl yuborilganida ma'lumotni qayta ishlash
@dp.message_handler(content_types=['document'])
async def handle_document(message: types.Message):
    file_name = message.document.file_name
    # Fayl turi tekshiruvi
    if not file_name.endswith('.xlsx'):
        await message.answer("Iltimos, faqat .xlsx formatidagi fayl yuboring.")
        return

    # Faylni saqlash
    file_path = os.path.join('files', file_name)
    os.makedirs('files', exist_ok=True)
    await message.document.download(destination_file=file_path)

    # Excel faylini yuklash
    success, error_msg = excel_data_handler.load_excel(file_path)
    if success:
        excel_data_handler.saved_file_name = file_name
        await message.answer("Fayl muvaffaqiyatli yuklandi!")
    else:
        await message.answer(f"Faylni o'qishda xatolik: {error_msg}")


@dp.message_handler(lambda message: message.text.lower() == "fayl o'chirish")
async def delete_file(message: types.Message):
    if excel_data_handler.saved_file_name:
        os.remove(os.path.join('files', excel_data_handler.saved_file_name))
        excel_data_handler.saved_file_name = None
        await message.answer("Fayl muvaffaqiyatli o'chirildi.")
    else:
        await message.answer("O'chirish uchun fayl topilmadi.")
