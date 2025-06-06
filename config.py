import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('token')
URL = os.getenv('URL')
ID_ADMIN = int(os.getenv('id_admin', 0))
ID_CHANNEL = int(os.getenv('id_channel', 0))
CHANNEL_LINK = os.getenv('channel_url', '@DavaiSNami')
BOT_LINK = os.getenv('bot_url', 'DavaiSNamiBot')

DATABASE_URL = os.getenv('DATABASE_URL')
LANG = os.getenv('language', 'ru')

API_URL = os.getenv('API_URL')
API_TOKEN = os.getenv('API_TOKEN')


DATE_MENU = {
    'today': 'сегодня',
    'tomorrow': 'завтра',
    'weekend': 'выходные',
    'exhibitions': 'выставки',
    'lucky': 'мне повезёт',
    'weekday': 'день недели',
}


MENU = {
    'events': {
        'today':       'Сегодня',
        'tomorrow':    'Завтра',
        'weekend':     'Выходные',
        'exhibitions': 'Выставки',
        'lucky':       'Мне повезёт',
        'weekday':     'День Недели',
        'settings':    '⚙️ Настройки',
    },
    'weekday': {
        'Mon': 'Пн', 'Tue': 'Вт', 'Wed': 'Ср',  'Thr': 'Чт',
        'Fri': 'Пт', 'Sat': 'Сб', 'Sun': 'Вск', 'events': '⬅ Назад'
    },
    'city': {
        'spb':      'Санкт-Петербург',
        'settings': '⬅ Назад'
    },
    'settings': {
        'events':           '🧩 Мероприятия',
       # '🏙 Выбор города': 'city',
        'weekend_guide':    '🌅 Гайд на выходные',
        'saved_events':     '⭐ Сохранённые Мероприятия',
        #'reminders':       'Напоминания',
        'balance':          '💎 Баланс',

    },
    'balance': {
        'balance_add':      '💎 Пополнить Баланс',
        'referral_url':     '⭐ Рефералка',
        'settings':         '⬅ Назад'
    },
    'referral_url': {
        'copy_referral':    '📋 Копировать ссылку',
        'share_referral':   '📤 Поделиться',
        'balance':          '⬅ Назад',
    },
    'back': {
        'events':           '🧩 Вернуть меню назад'
    }
}

EXHIBITIONS_PHRASES = {
    'two_week':     'Скоро заканчиваются',
    'next_month':   'Заканчиваются в следующем месяце',
    'others':       'Остальные'
}


WEEK_MENU = {
    'ru': ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вск'],
    'en': ['Mon', 'Tue', 'Wed', 'Thr', 'Fri', 'Sat', 'Sun']
}

MONTHES = {
    'ru': ['января', "февраля", 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'],
    'en': ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
}

waiting_for_time = {}
