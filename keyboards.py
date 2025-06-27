from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from config import MENU, LANG, emoji_keyboard


async def show_menu_keyboard(menu_key="events"):
    if not menu_key:
        menu_key = 'events'
    keyboard = []
    buttons = list(MENU.get(menu_key, {}).keys())

    for i in range(len(buttons)//2):
        keyboard.append([KeyboardButton(text=item.capitalize()) for item in buttons[i*2:i*2+2]])
    if len(buttons)//2 != 0:
        keyboard.append([KeyboardButton(text=buttons[-1])])

    markup = ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True
    )
    
    return markup


async def show_menu(menu_key="events"):
    if not menu_key:
        menu_key = 'events'
    inline_keyboard = []
    menu_items = MENU.get(menu_key, {}).items()
    
    # Create rows with 2 buttons each
    for i in range(0, len(menu_items), 2):
        row = []
        items = list(menu_items)[i:i+2]
        for callback_data, text in items:
            button_message = text.capitalize()
            if callback_data in emoji_keyboard and 'назад' not in button_message:
                button_message = emoji_keyboard[callback_data] + ' ' + button_message
            row.append(InlineKeyboardButton(text=button_message, callback_data=callback_data))
        inline_keyboard.append(row)

    markup = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
    
    return markup


async def week_menu():
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=day, callback_data=day) for day in WEEK_MENU[LANG][0:3]],
            [InlineKeyboardButton(text=day, callback_data=day) for day in WEEK_MENU[LANG][3:]],
        ],
    )
    return markup


async def user_event_menu(saved_events):
    inline_keyboard = []

    for idx, event in enumerate(saved_events, start=1):
        inline_keyboard.append(
            [
                InlineKeyboardButton(text=f"⚙️ Изменить {idx}", callback_data=f"sevent_edit_{event['id']}"),
                InlineKeyboardButton(
                    text=f"💤 Отключить {idx}" if event['remind_datetime'] else f"✅ Включить {idx}",
                    callback_data=f"sevent_dis_{event['id']}" if event['remind_datetime'] else f"sevent_enbl_{event['id']}"),
                InlineKeyboardButton(text=f"❌ Удалить {idx}", callback_data=f"sevent_del_{event['id']}"),
            ]
        )
    inline_keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="settings"),
                            InlineKeyboardButton(text="🦋 Мероприятия в истории", callback_data="saved_events_old")])

    markup = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
    return markup


