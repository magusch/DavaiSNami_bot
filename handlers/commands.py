from aiogram import types
from config import CHANNEL_LINK
from keyboards import show_menu

import services.crud as crud

async def send_welcome(message: types.Message):
    text = (f"Привет! Это бот канала {CHANNEL_LINK}. С моей помощью можно получить краткий гид мероприятий "
            "на определённый день, на выходные или по проходящим выставкам в городе.\n\n"
            "Чтобы начать, укажите дату или нажмите на кнопку в меню.")
    user_id = message.from_user.id
    
    keyboard = await show_menu('events')
    
    await message.answer(text, parse_mode="Markdown", reply_markup=keyboard)
    user_dict = {
        'telegram_id': user_id,
        'username': message.from_user.username,
        'first_name': message.from_user.first_name,
        'last_name': message.from_user.last_name,
        'balance': 50
    }
    await crud.make_new_user(user_dict)

    user_monitor_dict = {
        'telegram_id': message.from_user.id,
        'telegram_info': f"{message.from_user.username} ({message.from_user.first_name} {message.from_user.last_name})",
        'message': 'start',
        'type': 'command'
    }
    await crud.create_telegram_monitor(user_monitor_dict)

