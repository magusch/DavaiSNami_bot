from aiogram import types
from config import DATE_MENU, MENU
from keyboards import main_menu, get_menu

from datetime import datetime, timedelta
#from database import get_message_with_events, find_exibitions, get_random_event  # ваши функции


async def handle_text(message: types.Message):
    text = f"What'sup? *#{message.text}*"
    await message.answer(text, parse_mode="Markdown", reply_markup=get_menu())


def get_day(offset, daynow):
    return daynow + timedelta(days=offset)

def get_weekday(offset, daynow):
    weekday_offset = offset - daynow.weekday()
    if weekday_offset < 0:
        weekday_offset += 7
    return daynow + timedelta(days=weekday_offset)

# Ваши команды в date_menu с использованием DATE_MENU из config.py
date_menu = {
    DATE_MENU['today']: lambda daynow: get_day(0, daynow),
    DATE_MENU['tomorrow']: lambda daynow: get_day(1, daynow),
    DATE_MENU['weekend']: lambda daynow: (get_weekday(5, daynow), get_weekday(6, daynow)),
    #DATE_MENU['lucky']: lambda daynow: get_random_event(daynow),
    #DATE_MENU['exhibitions']: find_exibitions,
    DATE_MENU['weekday']: None  # если понадобится
}

async def handle_message(message: types.Message):
    message_lower = message.text.lower()
    if message_lower in MENU['date'].keys():
        await handle_date_command(message_lower)
    elif message_lower in MENU['settings'].keys():
        await handle_setting(message_lower)


async def handle_date_command(text_message):

    daynow = datetime.utcnow() + timedelta(hours=3)

    # Получаем обработчик из date_menu по команде
    handler = date_menu.get(text_message)

    if handler:
        if text_message == DATE_MENU['weekend']:
            saturday_events, sunday_events = handler(daynow)

            answer = f"_Выходные:_\n{saturday_events}\n{sunday_events}"
        else:
            answer = handler(daynow) if text_message != DATE_MENU['lucky'] else handler(daynow)[0]

    return answer

async def handle_setting(message_lower):
    pass

async def handle_date_text(message: types.Message):
    message = message.text.lower()