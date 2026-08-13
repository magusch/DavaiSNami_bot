from datetime import datetime, timedelta, timezone
from typing import NamedTuple
import random
import secrets

from . import external_api
from . import crud

from config import (CHANNEL_LINK, BOT_LINK, EXHIBITIONS_PHRASES, MONTHES, WEEK_MENU,
                    ACTION_COST, STARS_RATE, TOPUP_STARS, REFERRAL_BONUS)
from keyboards import user_event_menu
from . import utils
from .utils import (date_str, webapp_link, webapp_event_link,
                    webapp_date_filter, webapp_search_filters)


class EventsResult(NamedTuple):
    text: str
    count: int
    image: str = None

    @property
    def found(self) -> bool:
        return self.count > 0



class SearchResult(NamedTuple):
    """Text search outcome. `engine` is what actually ran (keyword/semantic) and
    decides the gem price of the query — semantic costs more."""
    text: str
    found: bool
    image: str = None
    engine: str = 'keyword'


class WebappLink(NamedTuple):
    """The "show all ..." web app link placed under a list.

    `filters` — startapp sections ('date-weekend', 'cat-1-3', 'price-1000'),
    `total` — how many events match those filters (used in the link text),
    `noun` — which word to inflect (event/exhibition)."""
    filters: tuple = ()
    total: int = None
    noun: str = 'events'


class FeedResult(NamedTuple):
    """Diversified feed result plus the pagination data for the "More" button."""
    text: str
    count: int
    has_more: bool = False
    date_from: str = None
    date_to: str = None
    page: int = 0
    webapp: WebappLink = None

    @property
    def found(self) -> bool:
        return self.count > 0


FEED_LIMIT = 15
FEED_PER_CATEGORY = 4

EXHIBITIONS_LIMIT = 15
EXHIBITIONS_FETCH = 100


def exhibitions_webapp(total=None):
    """Exhibitions link in the web app: by category alias, not by dates.
    `total` is dropped when the batch hit EXHIBITIONS_FETCH — there may be more."""
    if total is not None and total >= EXHIBITIONS_FETCH:
        total = None
    return WebappLink(filters=('cat-exhibition',), total=total, noun='exhibitions')


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
            link = webapp_event_link(event_id)
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
        link = webapp_event_link(event_id)
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


class Billing(NamedTuple):
    """How many gems the user has and what this action will cost.

    An empty Billing() means the action is free or the user is not in the DB —
    then no balance is shown in the footer."""
    balance: int = None
    cost: int = 0

    def remaining(self, charged=True):
        """Balance for the footer. charged=False when the reply is empty and nothing is debited."""
        if self.balance is None:
            return None
        return self.balance - self.cost if charged else self.balance


def _left_after(balance, engine):
    """Balance to show in the footer of a search reply: what remains once this
    search is charged. None (nothing shown) when we don't know the balance."""
    if balance is None:
        return None
    return balance - search_cost(engine)


def search_cost(engine):
    """Gem price of a text search by the engine that served it."""
    return ACTION_COST.get(f'search_{engine}', 0)


def balance_message(balance):
    """Balance screen: the number alone means nothing without the price list."""
    return (
        f"💎 *Ваш баланс: {balance if balance is not None else 0}*\n\n"
        f"Афиша — {ACTION_COST['feed']} 💎\n"
        f"Поиск по слову — {ACTION_COST['search_keyword']} 💎\n"
        f"Умный поиск текстом — {ACTION_COST['search_semantic']} 💎\n\n"
        f"Пополнение: {TOPUP_STARS} ⭐ → {TOPUP_STARS * STARS_RATE} 💎.\n"
        f"Рефералка: по {REFERRAL_BONUS} 💎 вам и другу."
    )


def not_enough_message(balance, cost):
    """This is the one moment a user really learns the balance exists, so state
    the price, what they have, and both ways to get more — all at once."""
    return (
        f"💎 *Не хватает самоцветов*\n\n"
        f"Это действие стоит *{cost} 💎*, а у вас *{balance}*.\n\n"
        f"Пополнить: {TOPUP_STARS} ⭐ → {TOPUP_STARS * STARS_RATE} 💎.\n"
        f"Или позовите друга по своей ссылке — по {REFERRAL_BONUS} 💎 обоим."
    )


async def footer_message(message, balance=None):
    footer = f'[@{BOT_LINK}](@{BOT_LINK})'
    if balance is not None:
        footer += f' · 💎 {balance}'
    return message.strip() + f'\n\n{footer}'


# Word forms for the link text: (1 item, 2-4, 5+).
WEBAPP_NOUNS = {
    'events': ('мероприятие', 'мероприятия', 'мероприятий'),
    'exhibitions': ('выставку', 'выставки', 'выставок'),
}


def _plural(number, one, few, many):
    """Russian noun form after a number: 21 мероприятие, 23 мероприятия, 25 мероприятий."""
    tail = abs(number) % 100
    if 11 <= tail <= 14:
        return many
    tail %= 10
    if tail == 1:
        return one
    if 2 <= tail <= 4:
        return few
    return many


def all_events_line(webapp, shown=0):
    """The "show all 28 events" link line at the end of a list.

    The count is included only when the filter holds more than we already showed,
    otherwise the text is a plain "see all". Empty when there are no filters
    (a bare keyword search has nothing to translate into a web app filter)."""
    if not webapp or not webapp.filters:
        return ''
    one, few, many = WEBAPP_NOUNS.get(webapp.noun, WEBAPP_NOUNS['events'])
    total = webapp.total or 0
    if total > max(shown, 1):
        text = f"Показать все {total} {_plural(total, one, few, many)}"
    else:
        # without a number the nominative plural is needed: «все мероприятия», «все выставки»
        text = f"Посмотреть все {few}"
    return f"\n📱 [{text}]({webapp_link(*webapp.filters)})\n"


async def feed_answer(result, title=None, billing=None):
    """The whole reply text: title + list + web app link + footer.
    `billing` puts the remaining gems into the footer (we charge exactly when something was found)."""
    body = f"{title}\n{result.text}" if title else result.text
    body += all_events_line(getattr(result, 'webapp', None), result.count)
    balance = billing.remaining(charged=result.found) if billing else None
    return await footer_message(body, balance)


async def process_feed(date_from, date_to=None, page=0, limit=FEED_LIMIT, webapp_filter=None):
    """Diversified event feed for a period (POST /events/feed/).

    One page = up to `limit` diverse events that fit into a single message.
    The next chunk = the same request with page+1 (the "More" button). Returns
    a FeedResult with the has_more flag and the period bounds used to build that button.

    `webapp_filter` is the section for the "see all" link (e.g. 'date-weekend');
    by default it is built from the period dates themselves."""
    date_from_str = date_str(date_from)
    date_to_str = date_str(date_to) if date_to else date_from_str
    webapp_filter = webapp_filter or webapp_date_filter(date_from_str, date_to_str)

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
    # total_count is every event of the period under the filters: what the web app will show
    webapp = WebappLink(filters=(webapp_filter,), total=result.get('total_count'))

    if not events:
        if page == 0:
            lucky = await process_lucky_event()
            message = (
                f'Мероприятий на {date_to_markdown(date_from_str)} не найдено\n\n'
                f'Но может вам понравится это:\n{lucky.text}'
            )
            return FeedResult(text=message, count=0, webapp=webapp)
        # page past the end of the feed — the user has scrolled through everything
        return FeedResult(text='Это были все мероприятия за этот период ✨', count=0,
                          date_from=date_from_str, date_to=date_to_str, page=page,
                          webapp=webapp)

    body = build_feed_message(events, window_start=date_from_str)
    has_more = (page + 1) * limit < diverse_total
    return FeedResult(text=body.text, count=body.count, has_more=has_more,
                      date_from=date_from_str, date_to=date_to_str, page=page,
                      webapp=webapp)


# Backwards-compat: old name, now built on top of the feed (typed dates, etc.).
async def process_events(date_from, date_to=None, page=0):
    return await process_feed(date_from, date_to, page=page)


# The nearest days are addressed by alias in the web app, not by date.
DAY_WEBAPP_FILTERS = {0: 'date-today', 1: 'date-tomorrow'}


async def process_day_events(offset, daynow, page=0):
    event_date = get_day(offset, daynow)
    return await process_feed(event_date, page=page,
                              webapp_filter=DAY_WEBAPP_FILTERS.get(offset))


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
    return await process_feed(saturday, sunday, page=page, webapp_filter='date-weekend')


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
        return FeedResult(text=text, count=0, page=page,
                          webapp=exhibitions_webapp(len(all_exhibs)))

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
                    post_url = webapp_event_link(exhib_id)

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

    return FeedResult(text=message, count=cnt_exhibs, has_more=has_more, page=page,
                      webapp=exhibitions_webapp(len(all_exhibs)))


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


SIMILAR_LIMIT = 3


def _similar_line(event):
    """One similar event: link, price and date, kept to a single compact line."""
    line = _event_link_line(event)
    date_str = _fmt_event_date(event.get('from_date'))
    return f"{line} · {date_str}" if date_str else line


async def process_similar_events(event_id, limit=SIMILAR_LIMIT):
    """Similar events (GET /events/{id}/similar).

    A hint, not the main content: when the API fails or the embedding is still
    being computed we quietly return nothing and the "similar" block is skipped."""
    data = await external_api.fetch_similar_events(event_id, limit=limit)
    if not isinstance(data, dict) or 'error' in data:
        return EventsResult(text='', count=0)

    result = data.get('result') or {}
    events = (result.get('events') or [])[:limit]
    if not events:
        return EventsResult(text='', count=0)

    lines = [_similar_line(e) for e in events]
    return EventsResult(text='\n'.join(lines) + '\n', count=len(lines))


async def process_similar_message(event_id, limit=SIMILAR_LIMIT):
    """Reply for the "similar" button in saved events: the list plus a card link."""
    similar = await process_similar_events(event_id, limit=limit)
    if not similar.found:
        return 'Похожих мероприятий пока не нашлось, попробуйте позже.'
    return (f"*Похожие мероприятия:*\n{similar.text}"
            f"\n📱 [Ещё похожие в приложении]({webapp_event_link(event_id)})")


async def process_lucky_event(daynow=None, with_similar=False):
    # compute the date here when not given: a default argument would freeze at
    # import time, and this bot stays up for weeks
    if daynow is None:
        daynow = datetime.now(timezone.utc) + timedelta(hours=3)
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
            post_url = webapp_event_link(event['id'])
        event_address = event['address']
        if event.get('place'):
            event_address = event['place']['place_name']
            if event.get('place').get('place_metro'):
                event_address += ', м.' + event['place']['place_metro']

        message =  f" [{event['title']}]({post_url}) – {event['category']}\n"
        message += f" 📆 {date_to_markdown(event['from_date'])}\n"
        message += f" 📍 {event_address}\n"
        message += f" 💰 {event['price']}\n"

        if with_similar:
            similar = await process_similar_events(event['id'])
            if similar.found:
                message += f"\n*Похожее:*\n{similar.text}"
                message += f"\n📱 [Ещё похожие в приложении]({webapp_event_link(event['id'])})\n"

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
            link = webapp_event_link(event.get('id'))
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


async def process_keyword_search(query, balance=None):
    """GET /search/. Returns a SearchResult; found=False when there is nothing.
    `balance` is the pre-charge balance, so the footer can show what is left."""
    result = await external_api.keyword_search(query)
    if 'error' in result:
        return SearchResult('Не удалось выполнить поиск, попробуйте чуть позже.', False)
    now = datetime.now(timezone.utc)
    events = [e for e in result.get('events', []) if _event_not_past(e, now)]
    if not events:
        return SearchResult('', False)
    body = build_search_message(events)
    return SearchResult(await footer_message(body.text, _left_after(balance, 'keyword')),
                        body.found, body.image)


async def process_semantic_search(message_text, history=None, balance=None):
    """POST /search/semantic/. Returns a SearchResult.

    All filtering (dates/categories/relevance/loosening on an empty result set)
    stays on the API side — the bot drops nothing on its own. `balance` is the
    pre-charge balance, so the footer can show what is left."""
    result = await external_api.semantic_search(message_text, history=history)

    if 'error' in result:
        return SearchResult('Не удалось выполнить поиск, попробуйте ещё раз чуть позже.',
                            False, engine='semantic')

    if result.get('status') == 'not_event_search':
        return SearchResult(
            'Кажется, это не запрос мероприятия 🙂\n'
            'Спросите меня, например: «джазовый концерт в выходные» '
            'или «бесплатные лекции на этой неделе».',
            False, engine='semantic')

    query = result.get('query') or {}
    inner = result.get('result', {}) or {}
    events = inner.get('events', [])

    # translate what the analyser understood into web app filters: dates, categories, price
    webapp = WebappLink(filters=webapp_search_filters(query.get('filters')),
                        total=inner.get('total_count'))

    if not events:
        answer = 'По вашему запросу ничего не нашлось. Попробуйте переформулировать запрос.'
        # filters parsed but nothing matched — offer the app instead of a dead end
        return SearchResult(answer + all_events_line(webapp), False, engine='semantic')

    body = build_search_message(events)
    intro = (result.get('reply') or '').strip()
    intro = f"{intro}\n\n" if intro else _semantic_header(query)
    answer = intro + body.text + all_events_line(webapp, body.count)
    return SearchResult(await footer_message(answer, _left_after(balance, 'semantic')),
                        body.found, body.image, engine='semantic')


async def process_text_search(message_text, history=None, allow_semantic=True, balance=None):
    """Free-text routing: keyword → (fallback) semantic.
    Returns a SearchResult; the handler prices the query by .engine.

    `allow_semantic=False` means the user cannot afford semantic search: we return
    engine 'semantic_needed' so the handler offers a top-up instead of emptiness."""
    if is_keyword_query(message_text):
        result = await process_keyword_search(message_text, balance=balance)
        if result.found:
            return result
        # nothing by keyword — fall back to semantic
    if not allow_semantic:
        return SearchResult('', False, engine='semantic_needed')
    return await process_semantic_search(message_text, history=history, balance=balance)


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
    await crud.change_balance(user_telegram_id, REFERRAL_BONUS)
    await crud.change_balance(referral_telegram_id, REFERRAL_BONUS)
