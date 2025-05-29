from datetime import datetime, timedelta, timezone
import random
from . import external_api
from . import crud

from config import CHANNEL_LINK, EXHIBITIONS_PHRASES, MONTHES


def get_day(offset, daynow):
    return daynow + timedelta(days=offset)

def get_weekday(offset, daynow):
    weekday_offset = offset - daynow.weekday()
    if weekday_offset < 0:
        weekday_offset += 7
    return daynow + timedelta(days=weekday_offset)

def date_to_markdown(date):
    return f"*{date.day} {MONTHES['ru'][date.month-1]}*\n"


def build_event_message(events, is_dict=False):
    lines = []
    for event in events:
        title = event['title'] if is_dict else event.title
        post_url = event['post_url'] if is_dict else event.post_url
        price = event['price'] if is_dict else event.price

        if post_url:
            if not post_url.startswith('http'):
                post_url = f'https://t.me/{CHANNEL_LINK}/' + post_url
            lines.append(f"[{title}]({post_url}) – {price}")
    return '\n'.join(lines)

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
    
    message = date_to_markdown(date_from)

    if events['result']:
        message += build_event_message(events['result']['events'], is_dict=True)
    else:
        message = 'Мероприятий не найдено'

    return message


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
        'fields': ['title', 'post_url', 'price', 'to_date'],
    }
    exhibitions = await external_api.fetch_events(params)
    divided_dates_dict = get_divided_dates_dict(daynow)
    message = ''

    if 'error' in exhibitions:
        return f"Ошибка при получении выставок: {exhibitions['error']}"

    if exhibitions.get('result', 'events'):
        for exib in exhibitions['result']['events']:
            to_date_exhib = datetime.strptime(exib['to_date'].split('+')[0], '%Y-%m-%dT%H:%M:%S').astimezone(timezone.utc)

            for divided_date_key, divided_date_value in divided_dates_dict.items():
                if to_date_exhib < divided_date_value['date']:

                    title = exib['title']
                    post_url = exib['post_url']
                    price = exib['price']

                    if post_url:
                        if not post_url.startswith('http'):
                            post_url = f'https://t.me/{CHANNEL_LINK}/' + post_url

                    divided_dates_dict[divided_date_key]['exhibs'].append(f"[{title}]({post_url}) – {price}")
                    break

        for type, value in divided_dates_dict.items():
            exhib_message = '\n'.join(value['exhibs'])
            message += f"*{EXHIBITIONS_PHRASES[type]}:*\n {exhib_message}\n\n"

    else:
        message = 'Выставок не найдено'

    return message


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


async def process_lucky_event(daynow):
    params = {
        'date_from': daynow.strftime('%Y-%m-%d'),
        'date_to': (daynow + timedelta(days=7)).strftime('%Y-%m-%d'),
        'limit': 100,
        'category': [-11]
    }
    events = await external_api.fetch_events(params)

    message = ''
    if events['result']:
        event = random.choice(events['result']['events'])
        message += build_event_message([event], is_dict=True)
    return message


async def process_telegram_monitor(monitor_dict):
    await crud.create_telegram_monitor(monitor_dict)


async def process_user_event(user_event_dict):
    if 'user_id' not in user_event_dict and 'telegram_id' in user_event_dict:
        user = await crud.get_user_by_telegram(user_event_dict['telegram_id'])
        if user:
            user_event_dict['user_id'] = user.id
    elif 'user_id' not in user_event_dict and 'telegram_id' not in user_event_dict:
        return False

    if 'event_id' not in user_event_dict and 'post_id' in user_event_dict:
        event = await crud.get_event_by_telegram(user_event_dict['post_id'])
        if event:
            user_event_dict['event_id'] = event.id

    await crud.save_event_for_user(**user_event_dict)
    return True


async def get_saved_user_event_fast(telegram_id):
    user_events = await crud.get_saved_user_event_by_teleram(telegram_id)
    if user_events:
        event_ids = [event.event_id for event in user_events]
        saved_events = await crud.get_event_by_ids(event_ids)
        message = build_event_message(saved_events)
        return message


async def get_saved_user_event(user_id=None, telegram_id=None):
    if not user_id and telegram_id:
        user = await crud.get_user_by_telegram(telegram_id)
        if not user:
            return None
        user_id = user.id

    user_events = await crud.get_saved_user_event(user_id)
    if not user_events:
        return None

    event_ids = [event.event_id for event in user_events]
    saved_events = await external_api.fetch_events({
        'ids': event_ids,
        'limit': 100
    })

    if saved_events['result']:
        return build_event_message(saved_events['result']['events'], is_dict=True)


async def new_user(message):
    user_dict = {
        'telegram_id': message.from_user.id,
        'username': message.from_user.username,
        'first_name': message.from_user.first_name,
        'last_name': message.from_user.last_name,
        'balance': 50
    }
    await crud.make_new_user(user_dict)


async def referal_click(referral_telegram_id, user_telegram_id):
    await crud.increase_balance(user_telegram_id, 100)
    await crud.increase_balance(referral_telegram_id, 100)
