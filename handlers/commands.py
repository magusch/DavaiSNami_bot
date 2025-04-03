from aiogram import types
from config import CHANNEL_LINK
from keyboards import get_menu

async def send_welcome(message: types.Message):
    text = (f"Привет! Это бот канала {CHANNEL_LINK}. С моей помощью можно получить краткий гид мероприятий "
            "на определённый день, на выходные или по проходящим выставкам в городе.\n\n"
            "Чтобы начать, укажите дату или нажмите на кнопку в меню.")
    await message.reply(text, parse_mode="Markdown", reply_markup=get_menu())