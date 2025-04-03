import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('token')
URL = os.getenv('URL')
ID_ADMIN = int(os.getenv('id_admin', 0))
ID_CHANNEL = int(os.getenv('id_channel', 0))
CHANNEL_LINK = os.getenv('channel_url', '@DavaiSNami')
LANG = os.getenv('language', 'ru')


START_MENU = {
    'ru': ['']
}

DATE_MENU = {
    'today': 'сегодня',
    'tomorrow': 'завтра',
    'weekend': 'выходные',
    'exhibitions': 'выставки',
    'lucky': 'мне повезёт',
    'weekday': 'день недели',
}

# MENU = {
#     'date': DATE_MENU.update({
#         'settings': '⚙ Настройки'
#     }),
#     'weekday': {
#         'Mon': 'Пн', 'Tue': 'Вт', 'Wed': 'Ср',  'Thr': 'Чт',
#         'Fri': 'Пт', 'Sat': 'Сб', 'Sun': 'Вск', 'date': '⬅ Назад'
#     },
#     'city': {
#         'spb': 'Санкт-Петербург',
#         'date': '⬅ Назад'
#     },
#     'settings': {
#         'city': '🏙 Выбрать город',
#         'saved_events': '⭐ Сохраненные Мероприятия',
#         'date': '⬅ Назад'
#     }
# }

MENU = {
    'date': {
        'сегодня': 'today',
        'завтра': 'tomorrow',
        'выходные': 'weekend',
        'выставки': 'exhibitions',
        'мне повезёт': 'lucky',
        'день недели': 'weekday',
        '⚙ Настройки': 'settings'
    },
    'weekday': {
        'Пн': 'Mon', 'Tue': 'Вт', 'Wed': 'Ср',  'Thr': 'Чт',
        'Fri': 'Пт', 'Sat': 'Сб', 'Sun': 'Вск', 'date': '⬅ Назад'
    },
    'city': {
        'Санкт-Петербург': 'spb',
        '⬅ Назад': 'date'
    },
    'settings': {
        '🏙 Выбрать город': 'city',
        '⭐ Сохраненные Мероприятия': 'saved_events',
        '⬅ Назад': 'date'
    }
}

# DATE_MENU = {
#     'ru': ['сегодня', 'завтра', 'выходные', 'выставки', 'мне повезёт', 'день недели'],
#     #'en': ['today', 'tomorrow', 'weekend', 'exhibitions', 'im lucky', 'day of week'],
#     #'commands'
# }

WEEK_MENU = {
    'ru': ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вск'],
    #'en': ['Mon', 'Tue', 'Wed', 'Thr', 'Fri', 'Sat', 'Sun']
}