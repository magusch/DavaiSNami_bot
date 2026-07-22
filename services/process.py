from datetime import datetime, timedelta, timezone
from typing import NamedTuple
import random
import secrets

from . import external_api
from . import crud

from config import CHANNEL_LINK, BOT_LINK, EXHIBITIONS_PHRASES, MONTHES, WEEK_MENU
from keyboards import user_event_menu
from . import utils


class EventsResult(NamedTuple):
    text: str
    count: int
    image: str = None

    @property
    def found(self) -> bool:
        return self.count > 0


def get_day(offset, daynow):
    return daynow + timedelta(days=offset)


def get_weekday(offset, daynow):
    weekday_offset = offset - daynow.weekday()
    if weekday_offset < 0:
        weekday_offset += 7
    return daynow + timedelta(days=weekday_offset)


def date_to_markdown(date):
    if date is None:
        return ""
    if type(date) == str:
        date = datetime.fromisoformat(date)
    return f"*{WEEK_MENU['ru'][date.weekday()]}, {date.day} {MONTHES['ru'][date.month-1]}*"


def build_event_message(events, is_dict=False):
    lines = []
    cnt_events = 0
    for event in events:
        if is_dict:
            title = event.get('title') or 'Без названия'
            post_url = event.get('post_url')
            price = event.get('price')
            event_id = event.get('id')
        else:
            title = event.title
            post_url = event.post_url
            price = event.price
            event_id = event.id

        if post_url:
            if not post_url.startswith('http'):
                post_url = f'https://t.me/{CHANNEL_LINK}/' + post_url
            link, label = post_url, title
        else:
            link = f"https://t.me/{BOT_LINK}?startapp=event_{event_id}"
            label = f"{title} 📱"

        if price:
            lines.append(f"[{label}]({link}) – {price}")
        else:
            lines.append(f"[{label}]({link})")
        cnt_events += 1
    if cnt_events > 0:
        return EventsResult(text='\n'.join(lines) + '\n', count=cnt_events)
    else:
        return EventsResult(text='Мероприятий не найдено\n', count=0)


async def footer_message(message):
    return message.strip() + f'\n\n[@{BOT_LINK}](@{BOT_LINK})'


async def process_events(date_from, date_to=None):
    if type(date_from) != str:
        date_from_str = date_from.strftime('%Y-%m-%d')
    else:
        date_from_str = date_from

    if date_to:
        if type(date_to) != str:
            date_to_str = date_to.strftime('%Y-%m-%d')
        else:
            date_to_str = date_to
    else:
        date_to_str = date_from_str

    params = {
        'date_from': date_from_str,
        'date_to': date_to_str,
        'limit': 100,
        'category': [-11]
    }
    events = await external_api.fetch_events(params)

    if events.get('result', {}).get('events'):
        body = build_event_message(events['result']['events'], is_dict=True)
        message = date_to_markdown(date_from) + '\n' + body.text
        return EventsResult(text=message, count=body.count)
    else:
        lucky = await process_lucky_event()
        message = (
            f'Мероприятий на {date_to_markdown(date_from)} не найдено\n\n'
            f'Но может вам понравится это:\n{lucky.text}'
        )
        return EventsResult(text=message, count=0)


async def process_day_events(offset, daynow):
    event_date = get_day(offset, daynow)
    return await process_events(event_date)


async def process_weekday_events(offset, daynow):
    event_date = get_weekday(offset, daynow)
    return await process_events(event_date)


async def process_weekend_events(daynow):
    saturday_events = await process_weekday_events(5, daynow)
    sunday_events = await process_weekday_events(6, daynow)
    return saturday_events, sunday_events


async def process_exhibitions(daynow):
    params = {
        'date_from': daynow.strftime('%Y-%m-%d'),
        'limit': 100,
        'category': [11],
        'fields': ['id', 'title', 'post_url', 'price', 'to_date', 'address', 'place'],
    }
    exhibitions = await external_api.fetch_events(params)
    divided_dates_dict = get_divided_dates_dict(daynow)
    message = ''

    if 'error' in exhibitions:
        return EventsResult(text=f"Ошибка при получении выставок: {exhibitions['error']}", count=0)

    cnt_exhibs = 0
    if exhibitions.get('result', {}).get('events'):
        for exhib in exhibitions['result']['events']:
            to_date_raw = exhib.get('to_date')
            if not to_date_raw:
                continue
            to_date_exhib = datetime.fromisoformat(to_date_raw).astimezone(timezone.utc)

            for divided_date_key, divided_date_value in divided_dates_dict.items():
                if to_date_exhib < divided_date_value['date']:

                    title = exhib['title']
                    post_url = exhib['post_url']
                    price = exhib['price']
                    place_name = exhib['address'].split(',')[0]
                    if post_url:
                        if not post_url.startswith('http'):
                            post_url = f'https://t.me/{CHANNEL_LINK}/' + post_url
                    else:
                        exhib_id = exhib['id']
                        post_url = f"https://t.me/{BOT_LINK}?startapp=event_{exhib_id}"

                    if exhib.get('place'):
                        place_name = exhib.get('place').get('place_name')

                    divided_dates_dict[divided_date_key]['exhibs'].append(f"[{title}]({post_url}) – {price} – {place_name}")
                    cnt_exhibs += 1
                    break

        for type, value in divided_dates_dict.items():
            if not value['exhibs']:
                continue

            exhib_message = '\n'.join(value['exhibs'])
            message += f"*{EXHIBITIONS_PHRASES[type]}:*\n {exhib_message}\n\n"

    if cnt_exhibs == 0:
        message = 'Выставок не найдено'

    return EventsResult(text=message, count=cnt_exhibs)


def get_divided_dates_dict(daynow):
    date_list = {}
    # 1) Ends in two week
    exhib_phrases = list(EXHIBITIONS_PHRASES.keys())
    date_list[exhib_phrases[0]] = {'date': daynow + timedelta(weeks=2), 'exhibs': []}

    # 2) Ends in next month
    if daynow.month < 11:
        date_list[exhib_phrases[1]] = {'date': daynow.replace(month=daynow.month+2, day=1) - timedelta(days=1), 'exhibs': []}
    elif daynow.month == 11:
        date_list[exhib_phrases[1]] = {'date': daynow.replace(month=12, day=31), 'exhibs': []}
    else:
        date_list[exhib_phrases[1]] = {'date': daynow.replace(year=daynow.year+1, month=1, day=31), 'exhibs': []}

    # 3) Others
    date_list[exhib_phrases[2]] = {'date': daynow.replace(year=daynow.year+10), 'exhibs': []}
    
    return date_list


async def process_lucky_event(daynow=datetime.now(timezone.utc) + timedelta(hours=3)):
    params = {
        'date_from': daynow.strftime('%Y-%m-%d'),
        'date_to': (daynow + timedelta(days=7)).strftime('%Y-%m-%d'),
        'limit': 100,
        'category': [-11]
    }
    events = await external_api.fetch_events(params)
    if events['result']:
        event = random.choice(events['result']['events'])
        post_url = event['post_url']
        if post_url:
            if not post_url.startswith('http'):
                post_url = f'https://t.me/{CHANNEL_LINK}/' + post_url
        else:
            post_url = f"https://t.me/{BOT_LINK}?startapp=event_{event['id']}"
        event_address = event['address']
        if event.get('place'):
            event_address = event['place']['place_name']
            if event.get('place').get('place_metro'):
                event_address += ', м.' + event['place']['place_metro']

        message =  f" [{event['title']}]({post_url}) – {event['category']}\n"
        message += f" 📆 {date_to_markdown(event['from_date'])}\n"
        message += f" 📍 {event_address}\n"
        message += f" 💰 {event['price']}\n"
        return EventsResult(text=message, count=1, image=event.get('image'))

    return EventsResult(text='', count=0)


# Предлоги — признак свободного текста, а не ключевого слова.
_PREPOSITIONS = {
    'в', 'во', 'на', 'с', 'со', 'по', 'до', 'от', 'из', 'за', 'под', 'над',
    'о', 'об', 'к', 'ко', 'у', 'для', 'про', 'без', 'при',
}


def is_keyword_query(text):
    """1–2 слова без предлогов → keyword-поиск; всё остальное → semantic."""
    words = text.split()
    if not (1 <= len(words) <= 2):
        return False
    return not any(w.lower() in _PREPOSITIONS for w in words)


def _semantic_header(query):
    """Короткая строка «что понял анализатор» из filters (цена)."""
    filters = (query or {}).get('filters') or {}
    parts = []
    if filters.get('free_only'):
        parts.append('бесплатно')
    elif filters.get('price_max'):
        parts.append(f"до {filters['price_max']} ₽")
    if not parts:
        return ''
    return f"_Ищу: {', '.join(parts)}_\n\n"


def _parse_dt(raw):
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except (ValueError, TypeError):
        return None


def _fmt_event_date(raw):
    """ISO-дата события → «Вт, 7 июля 16:00» в часовом поясе пользователя."""
    dt = _parse_dt(raw)
    if dt is None:
        return ''
    dt = utils.dt_utc_to_user(dt)
    return f"{WEEK_MENU['ru'][dt.weekday()]}, {dt.day} {MONTHES['ru'][dt.month - 1]} {dt.strftime('%H:%M')}"


def _top_event(events):
    """Самое релевантное событие: min distance → max score → первое от API."""
    with_dist = [e for e in events if isinstance(e.get('distance'), (int, float))]
    if with_dist:
        return min(with_dist, key=lambda e: e['distance'])
    with_score = [e for e in events if isinstance(e.get('score'), (int, float))]
    if with_score:
        return max(with_score, key=lambda e: e['score'])
    return events[0] if events else None


def build_search_message(events):
    """Рендер результатов поиска: сортировка по дате + дата в каждой строке.
    Картинку берём у самого релевантного события (а не первого по дате)."""
    if not events:
        return EventsResult(text='Мероприятий не найдено\n', count=0)

    top = _top_event(events)
    image = top.get('image') if top else None

    far = datetime.max.replace(tzinfo=timezone.utc)
    events = sorted(events, key=lambda e: _parse_dt(e.get('from_date')) or far)

    lines = []
    for event in events:
        title = (event.get('title') or 'Без названия').strip()
        price = event.get('price')
        post_url = event.get('post_url')
        if post_url:
            if not post_url.startswith('http'):
                post_url = f'https://t.me/{CHANNEL_LINK}/' + post_url
            link, label = post_url, title
        else:
            link = f"https://t.me/{BOT_LINK}?startapp=event_{event.get('id')}"
            label = f"{title} 📱"

        date_str = _fmt_event_date(event.get('from_date'))
        head = f"📅 {date_str}\n" if date_str else ''
        price_str = f" – {price}" if price else ''
        lines.append(f"{head}[{label}]({link}){price_str}")

    if not lines:
        return EventsResult(text='Мероприятий не найдено\n', count=0)
    return EventsResult(text='\n\n'.join(lines) + '\n', count=len(lines), image=image)


def _event_not_past(event, now):
    """keyword-поиск не фильтрует по дате — отсекаем прошедшие события."""
    raw = event.get('to_date') or event.get('from_date')
    if not raw:
        return True
    try:
        return datetime.fromisoformat(raw) >= now
    except (ValueError, TypeError):
        return True


async def process_keyword_search(query):
    """GET /search/. Возвращает (answer, found, image). found=False если ничего нет."""
    result = await external_api.keyword_search(query)
    if 'error' in result:
        return 'Не удалось выполнить поиск, попробуйте чуть позже.', False, None
    now = datetime.now(timezone.utc)
    events = [e for e in result.get('events', []) if _event_not_past(e, now)]
    if not events:
        return '', False, None
    body = build_search_message(events)
    return await footer_message(body.text), body.found, body.image


async def process_semantic_search(message_text, history=None):
    """POST /search/semantic/. Возвращает (answer, found, image)."""
    result = await external_api.semantic_search(message_text, history=history)

    if 'error' in result:
        return 'Не удалось выполнить поиск, попробуйте ещё раз чуть позже.', False, None

    if result.get('status') == 'not_event_search':
        return (
            'Кажется, это не запрос мероприятия 🙂\n'
            'Спросите меня, например: «джазовый концерт в выходные» '
            'или «бесплатные лекции на этой неделе».'
        ), False, None

    events = result.get('result', {}).get('events', [])
    if not events:
        return 'По вашему запросу ничего не нашлось. Попробуйте переформулировать запрос.', False, None

    body = build_search_message(events)
    answer = _semantic_header(result.get('query')) + body.text
    return await footer_message(answer), body.found, body.image


async def process_text_search(message_text, history=None):
    """Маршрутизация свободного текста: keyword → (fallback) semantic.
    Возвращает (answer, found, image)."""
    if is_keyword_query(message_text):
        answer, found, image = await process_keyword_search(message_text)
        if found:
            return answer, found, image
        # ничего по ключевому слову — пробуем семантику
    return await process_semantic_search(message_text, history=history)


async def process_telegram_monitor(monitor_dict):
    await crud.create_telegram_monitor(monitor_dict)


async def process_user_event(user_event_dict):
    if 'user_id' not in user_event_dict and 'telegram_id' in user_event_dict:
        user = await crud.get_user_by_telegram(user_event_dict['telegram_id'])
        if user:
            user_event_dict['user_id'] = user.id
        else:
            return False
    elif 'user_id' not in user_event_dict and 'telegram_id' not in user_event_dict:
        return False

    if 'event_id' not in user_event_dict and 'post_id' in user_event_dict:
        event = await crud.get_event_by_telegram(user_event_dict['post_id'])
        if event:
            user_event_dict.update({
                'event_id': event.id,
                'remind_datetime': event.from_date - timedelta(hours=5)
            })
        else:
            return False
    user_event_to_db = {
        'user_id': user_event_dict['user_id'],
        'event_id': user_event_dict['event_id'],
        'remind_datetime': user_event_dict.get('remind_datetime')
    }
    await crud.save_event_for_user(**user_event_to_db)
    return True


async def process_saved_user_event(user_id=None, telegram_id=None, old=0):
    if not user_id and telegram_id:
        user = await crud.get_user_by_telegram(telegram_id)
        if not user:
            return None
        user_id = user.id

    user_events = await crud.get_saved_user_event(user_id, old)
    if not user_events:
        return None

    user_event_ids = {event.event_id: event for event in user_events}
    saved_events = await external_api.fetch_events({
        'ids': list(user_event_ids.keys()),
        'limit': 100
    })

    event_for_menu = []
    if saved_events['result']:
        lines = []
        for idx, event in enumerate(saved_events['result']['events'], start=1):
            remind_date = user_event_ids[event['id']].remind_datetime
            if remind_date and not user_event_ids[event['id']].remind_sent and old == 0:
                remind_date = utils.dt_utc_to_user(remind_date)
                remind_date_str = f"{remind_date.day} {MONTHES['ru'][remind_date.month - 1]} {remind_date.strftime('%H:%M')}"
            else:
                remind_date_str = 'отключено'
                remind_date = None
            event_date = utils.dt_utc_to_user(datetime.fromisoformat(event['from_date']))
            event_date_str = f"{event_date.day} {MONTHES['ru'][event_date.month - 1]} {event_date.strftime('%H:%M')}"

            if event['post_url']:
                if not event['post_url'].startswith('http'):
                    event['post_url'] = f'https://t.me/{CHANNEL_LINK}/' + event['post_url']

            lines.append(
                f"{idx}. [{event['title']}]({event['post_url']}) — {event_date_str} \n    *Напоминание:* {remind_date_str} \n"
            )
            event_for_menu.append({
                'id': event['id'], 'remind_datetime': remind_date
            })

        message_menu = await user_event_menu(event_for_menu)
        return "*Ваши мероприятия:*\n\n" + "\n".join(lines), message_menu


        #return build_event_message(saved_events['result']['events'], is_dict=True)

async def toggle_saved_event(telegram_id, event_id, mod):
    user = await crud.get_user_by_telegram(telegram_id)
    if not user:
        return None
    user_id = user.id

    if mod == 'dis':
        await crud.toggle_remind_events(user_id, event_id, 0)
        return 0
    elif mod == 'del':
        await crud.toggle_remind_events(user_id, event_id, -1)
        return -1


async def edit_remind_time(telegram_id, event_id, message_text):
    user = await crud.get_user_by_telegram(telegram_id)
    if not user:
        return None
    user_id = user.id
    # parse time
    remind_dt = utils.parse_user_datetime(message_text)
    if remind_dt is not None:
        await crud.edit_time_reminder(user_id, event_id, utils.dt_local_to_utc(remind_dt))
    return remind_dt


async def new_user(message):
    full_name = ''
    if message.from_user.first_name:
        full_name += message.from_user.first_name + ' '
    if message.from_user.last_name:
        full_name += message.from_user.last_name
    nickname = 'tg_' + str(message.from_user.id)
    if message.from_user.username:
        nickname = 'tg_' + message.from_user.username

    hashed_password = secrets.token_urlsafe(32)

    new_user_dict = {
        'telegram_id': message.from_user.id,
        'full_name': full_name,
        'nickname': nickname,
        'email': f"{message.from_user.id}@tg.me",
        'is_active': True,
        'balance': 100,
        'hashed_password': hashed_password
    }
    await crud.make_new_user(new_user_dict)


async def referral_click(referral_telegram_id, user_telegram_id):
    await crud.change_balance(user_telegram_id, 100)
    await crud.change_balance(referral_telegram_id, 100)
