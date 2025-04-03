from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from config import MENU, DATE_MENU, WEEK_MENU, LANG

def main_menu(menu_key="date"):
    keyboard = []
    buttons = list(MENU.get(menu_key, {}).values())
    for i in range(len(buttons)//2):
        keyboard.append([KeyboardButton(text=item.capitalize()) for item in buttons[i*2:i*2+2]])

    markup = ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True
    )
    return markup


def get_menu(menu_key="date"):
    if not menu_key:
        menu_key = 'date'
    keyboard = []
    buttons = list(MENU.get(menu_key, {}).keys())
    for i in range(len(buttons)//2):
        keyboard.append([KeyboardButton(text=item.capitalize()) for item in buttons[i*2:i*2+2]])

    markup = ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True
    )
    return markup

def week_menu():
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=day) for day in WEEK_MENU[LANG][0:3]],
            [KeyboardButton(text=day) for day in WEEK_MENU[LANG][3:]],
        ],
        resize_keyboard=True
    )
    return markup