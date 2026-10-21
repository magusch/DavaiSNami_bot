from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from config import MENU, LANG, emoji_keyboard, POPULAR_CATEGORIES, REMIND_OPTIONS, DEFAULT_REMIND_HOURS
from services.utils import webapp_link
from services.city import city_name


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


async def menu_with_more(more_callback, menu_key="events", text="➡️ Ещё мероприятия"):
    """Regular menu + a "More" button on top with the given callback."""
    base = await show_menu(menu_key)
    more_row = [InlineKeyboardButton(text=text, callback_data=more_callback)]
    return InlineKeyboardMarkup(inline_keyboard=[more_row] + base.inline_keyboard)


async def feed_more_keyboard(result, menu_key="events"):
    """Menu + "More events" when the feed has a next page.
    `result` is a FeedResult (has_more/date_from/date_to/page).
    callback: more:<date_from>:<date_to>:<next_page> (dates in YYYY-MM-DD)."""
    if not getattr(result, 'has_more', False):
        return await show_menu(menu_key)
    callback = f"more:{result.date_from}:{result.date_to}:{result.page + 1}"
    return await menu_with_more(callback, menu_key)


async def exhibitions_more_keyboard(result, menu_key="events"):
    """Menu + "More exhibitions" when there's a next page of exhibitions.
    callback: exmore:<next_page> (no dates — the period is always "from today")."""
    if not getattr(result, 'has_more', False):
        return await show_menu(menu_key)
    return await menu_with_more(f"exmore:{result.page + 1}", menu_key, text="➡️ Ещё выставки")


async def categories_menu(city=None):
    """Categories submenu: popular ones as direct web app links (no API calls at all),
    the full filter list lives in the app behind "all categories"."""
    buttons = [
        InlineKeyboardButton(text=f"{emoji} {title}", url=webapp_link(f"cat-{alias}", city=city))
        for alias, title, emoji in POPULAR_CATEGORIES
    ]
    inline_keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    inline_keyboard.append([InlineKeyboardButton(text="📱 Все категории в приложении",
                                                 url=webapp_link(city=city))])
    inline_keyboard.append([InlineKeyboardButton(text="⬅ Назад", callback_data="events")])
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


CITY_CALLBACK = 'city:'


async def city_menu(cities, current=None, back=True):
    """City picker: one button per city (city:<code>), the current one marked.
    back=False for the first /start question — there is no settings screen to return to."""
    inline_keyboard = [
        [InlineKeyboardButton(text=f"{'✅ ' if code == current else ''}{city_name(code)}",
                              callback_data=f"{CITY_CALLBACK}{code}")]
        for code in cities
    ]
    if back:
        inline_keyboard.append([InlineKeyboardButton(text="⬅ Назад", callback_data="settings")])
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


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
                InlineKeyboardButton(text=f"🔎 Похожие {idx}", callback_data=f"sevent_sim_{event['id']}"),
            ]
        )
    inline_keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="settings"),
                            InlineKeyboardButton(text="🦋 Мероприятия в истории", callback_data="saved_events_old")])

    markup = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
    return markup




SAVED_MARK, UNSAVED_MARK, CHOSEN_MARK = '✅', '⭐', '• '
FAV_LIST_CALLBACK = 'fav_list'


async def selection_picker_keyboard(selection_id, events, webapp_url=None, saved_ids=(),
                                    remind_hours=DEFAULT_REMIND_HOURS):
    """Digest picker: a ⭐ per event (save_event:<id>, ✅ when saved), one per row up to 6,
    then two per row. After the first save — a reminder offset row (remind_sel:<hours>).
    Then "save all" (save_all:<selection_id>), "my favourites" and the web app link.
    The whole state lives in the buttons, parse_picker() reads it back."""
    buttons = [
        InlineKeyboardButton(
            text=f"{SAVED_MARK if event['id'] in saved_ids else UNSAVED_MARK} {event['label']}",
            callback_data=f"save_event:{event['id']}")
        for event in events
    ]
    per_row = 1 if len(buttons) <= 6 else 2
    inline_keyboard = [buttons[i:i + per_row] for i in range(0, len(buttons), per_row)]

    if any(event['id'] in saved_ids for event in events):
        inline_keyboard.append([
            InlineKeyboardButton(text=f"{CHOSEN_MARK if hours == remind_hours else ''}⏰ {label}",
                                 callback_data=f"remind_sel:{hours}")
            for hours, label in REMIND_OPTIONS.items()
        ])

    all_saved = bool(events) and all(event['id'] in saved_ids for event in events)
    inline_keyboard.append([
        InlineKeyboardButton(
            text=f"{SAVED_MARK} Все сохранены" if all_saved else f"{UNSAVED_MARK} Сохранить все",
            callback_data=f"save_all:{selection_id}"),
        InlineKeyboardButton(text="📋 Моё избранное", callback_data=FAV_LIST_CALLBACK),
    ])
    if webapp_url:
        inline_keyboard.append([InlineKeyboardButton(text="📱 Все мероприятия — в приложении",
                                                     url=webapp_url)])
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def parse_picker(markup):
    """Picker state back from its buttons: {selection_id, events, saved_ids,
    remind_hours, webapp_url}; None when the markup is not a digest picker."""
    if not markup:
        return None
    state = {'selection_id': None, 'events': [], 'saved_ids': set(),
             'remind_hours': DEFAULT_REMIND_HOURS, 'webapp_url': None}
    for row in markup.inline_keyboard:
        for button in row:
            data = button.callback_data or ''
            if data.startswith('save_event:'):
                event_id = int(data.split(':', 1)[1])
                mark, _, label = button.text.partition(' ')
                state['events'].append({'id': event_id, 'label': label})
                if mark == SAVED_MARK:
                    state['saved_ids'].add(event_id)
            elif data.startswith('save_all:'):
                state['selection_id'] = int(data.split(':', 1)[1])
            elif data.startswith('remind_sel:') and button.text.startswith(CHOSEN_MARK):
                state['remind_hours'] = int(data.split(':', 1)[1])
            elif button.url:
                state['webapp_url'] = button.url
    return state if state['selection_id'] is not None else None
