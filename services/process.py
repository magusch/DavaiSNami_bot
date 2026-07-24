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


class FeedResult(NamedTuple):
    """Diversified feed result plus the pagination data for the "More" button."""
    text: str
    count: int
    has_more: bool = False
    date_from: str = None
    date_to: str = None
    page: int = 0

    @property
    def found(self) -> bool:
        return self.count > 0


FEED_LIMIT = 15
FEED_PER_CATEGORY = 4

EXHIBITIONS_LIMIT = 15
EXHIBITIONS_FETCH = 100


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


def _event_link_line(event):
    """A single feed event line: [title](link) – price."""
    title = (event.get('title') or 'Без названия').strip()
    price = event.get('price')
    post_url = event.get('post_url')
    event_id = event.get('id')

    if post_url:
        if not post_url.startswith('http'):
            post_url = f'https://t.me/{CHANNEL_LINK}/' + post_url
        link, label = post_url, title
    else:
        link = f"https://t.me/{BOT_LINK}?startapp=event_{event_id}"
        label = f"{title} 📱"

    if price:
        return f"[{label}]({link}) – {price}"
    return f"[{label}]({link})"


def build_feed_message(events, window_start=None):
    """Render the feed: events grouped by day, each day with a date header,
    events within a day kept in feed order (by score).

    An event's day is taken from its `from_date`, but never earlier than
    `window_start` (the start of the requested period). Otherwise a multi-day
    event (a festival running all week) queried for Thursday would show under a
    "Mon" header, and one running since last week would show in "Tomorrow"
    under its start date. For single-day queries (Today/Tomorrow/weekday) this
    collapses everything under one header = the requested day."""
    if not events:
        return EventsResult(text='Мероприятий не найдено\n', count=0)

    groups = {}
    for event in events:
        dt = _parse_dt(event.get('from_date'))
        if dt is not None:
            day_key = utils.dt_utc_to_user(dt).date().isoformat()
            # event may have started before the window — show it under the window's first day
            if window_start and day_key < window_start:
                day_key = window_start
        elif window_start:
            day_key = window_start
        else:
            day_key = 'nodate'
        groups.setdefault(day_key, []).append(event)

    # days ascending by date, undated events last
    day_keys = sorted(groups, key=lambda k: (k == 'nodate', k))

    blocks = []
    cnt = 0
    for day_key in day_keys:
        lines = [_event_link_line(e) for e in groups[day_key]]
        cnt += len(lines)
        header = date_to_markdown(day_key) if day_key != 'nodate' else ''
        block = '\n'.join(lines)
        blocks.append(f"{header}\n{block}" if header else block)

    return EventsResult(text='\n\n'.join(blocks) + '\n', count=cnt)


async def footer_message(message):
    return message.strip() + f'\n\n[@{BOT_LINK}](@{BOT_LINK})'


def _date_str(date):
    """Date (datetime|str) → 'YYYY-MM-DD'."""
    if isinstance(date, str):
        return date
    return date.strftime('%Y-%m-%d')


async def process_feed(date_from, date_to=None, page=0, limit=FEED_LIMIT):
    """Diversified event feed for a period (POST /events/feed/).

    One page = up to `limit` diverse events that fit into a single message.
    The next chunk = the same request with page+1 (the "More" button). Returns
    a FeedResult with the has_more flag and the period bounds used to build that button."""
    date_from_str = _date_str(date_from)
    date_to_str = _date_str(date_to) if date_to else date_from_str

    params = {
        'date_from': date_from_str,
        'date_to': date_to_str,
        'limit': limit,
        'page': page,
        'per_category': FEED_PER_CATEGORY,
        'category': [-11],
    }
    data = await external_api.fetch_feed(params)

    if 'error' in data:
        return FeedResult(text=f"Не удалось получить мероприятия: {data['error']}", count=0)

    result = data.get('result', {}) or {}
    events = result.get('events', [])
    diverse_total = (result.get('request', {}) or {}).get('diverse_total', len(events))

    if not events:
        if page == 0:
            lucky = await process_lucky_event()
            message = (
                f'Мероприятий на {date_to_markdown(date_from_str)} не найдено\n\n'
                f'Но может вам понравится это:\n{lucky.text}'
            )
            return FeedResult(text=message, count=0)
        # page past the end of the feed — the user has scrolled through everything
        return FeedResult(text='Это были все мероприятия за этот период ✨', count=0,
                          date_from=date_from_str, date_to=date_to_str, page=page)

    body = build_feed_message(events, window_start=date_from_str)
    has_more = (page + 1) * limit < diverse_total
    return FeedResult(text=body.text, count=body.count, has_more=has_more,
                      date_from=date_from_str, date_to=date_to_str, page=page)


# Backwards-compat: old name, now built on top of the feed (typed dates, etc.).
async def process_events(date_from, date_to=None, page=0):
    return await process_feed(date_from, date_to, page=page)


async def process_day_events(offset, daynow, page=0):
    event_date = get_day(offset, daynow)
    return await process_feed(event_date, page=page)


async def process_weekday_events(offset, daynow, page=0):
    event_date = get_weekday(offset, daynow)
    return await process_feed(event_date, page=page)


def weekend_range(daynow):
    """Upcoming Saturday and Sunday (Sat = get_weekday(5), Sun = Sat+1)."""
    saturday = get_weekday(5, daynow)
    return saturday, saturday + timedelta(days=1)


async def process_weekend_events(daynow, page=0):
    """Weekend — ONE feed request for the Sat–Sun range. The feed balances
    events across the two days, so the reply fits in one message (was 2–3)."""
    saturday, sunday = weekend_range(daynow)
    return await process_feed(saturday, sunday, page=page)


async def process_exhibitions(daynow, page=0):
    """Exhibitions (category 11) with their own layout by end date
    (Ending soon / Next month / Others). Show at most EXHIBITIONS_LIMIT at a
    time; the rest are reachable via the "More" button (page+1)."""
    params = {
        'date_from': daynow.strftime('%Y-%m-%d'),
        'limit': EXHIBITIONS_FETCH,
        'category': [11],
        'fields': ['id', 'title', 'post_url', 'price', 'to_date', 'address', 'place'],
    }
    exhibitions = await external_api.fetch_events(params)

    if 'error' in exhibitions:
        return FeedResult(text=f"Ошибка при получении выставок: {exhibitions['error']}", count=0)

    # only exhibitions with an end date (we bucket them by it)
    all_exhibs = [e for e in (exhibitions.get('result', {}).get('events') or []) if e.get('to_date')]

    start = page * EXHIBITIONS_LIMIT
    page_exhibs = all_exhibs[start:start + EXHIBITIONS_LIMIT]
    has_more = start + EXHIBITIONS_LIMIT < len(all_exhibs)

    if not page_exhibs:
        text = 'Выставок не найдено' if page == 0 else 'Это были все выставки ✨'
        return FeedResult(text=text, count=0, page=page)

    divided_dates_dict = get_divided_dates_dict(daynow)
    cnt_exhibs = 0
    for exhib in page_exhibs:
        to_date_exhib = datetime.fromisoformat(exhib['to_date']).astimezone(timezone.utc)

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

    message = ''
    for type, value in divided_dates_dict.items():
        if not value['exhibs']:
            continue

        exhib_message = '\n'.join(value['exhibs'])
        message += f"*{EXHIBITIONS_PHRASES[type]}:*\n {exhib_message}\n\n"

    if cnt_exhibs == 0:
        message = 'Выставок не найдено'

    return FeedResult(text=message, count=cnt_exhibs, has_more=has_more, page=page)


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
    """POST /search/semantic/. Возвращает (answer, found, image).
    Всю фильтрацию (даты/категории/релевантность/ослабление при пустой выдаче)
    держит API — бот ничего сам не отсекает."""
    result = await external_api.semantic_search(message_text, history=history)

    if 'error' in result:
        return 'Не удалось выполнить поиск, попробуйте ещё раз чуть позже.', False, None

    if result.get('status') == 'not_event_search':
        return (
            'Кажется, это не запрос мероприятия 🙂\n'
            'Спросите меня, например: «джазовый концерт в выходные» '
            'или «бесплатные лекции на этой неделе».'
        ), False, None

    query = result.get('query') or {}
    events = result.get('result', {}).get('events', [])
    if not events:
        return 'По вашему запросу ничего не нашлось. Попробуйте переформулировать запрос.', False, None

    body = build_search_message(events)
    intro = (result.get('reply') or '').strip()
    intro = f"{intro}\n\n" if intro else _semantic_header(query)
    answer = intro + body.text
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
