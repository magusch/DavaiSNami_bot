from datetime import datetime, timedelta, timezone
import random
from . import external_api

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
        'limit': 100
    }
    events = await external_api.fetch_events(params)
    
    message = date_to_markdown(date_from)

    if events['result']:
        for event in events['result']['events']:
            message += f"[{event['title']}]({event['post_url']}) – {event['price']}\n"
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
    exhibitions = await external_api.fetch_exhibitions()

    date_list = get_list_dates(daynow)
    message = ''
    
    # Проверяем, есть ли ошибка в ответе API
    if 'error' in exhibitions:
        return f"Ошибка при получении выставок: {exhibitions['error']}"
    
    if exhibitions.get('result'):
        p = 0
        message = f"{EXHIBITIONS_PHRASES[0]}:\n"
        for exib in exhibitions['result']:
            if datetime.strptime(exib['date_before'], '%Y-%m-%dT%H:%M:%S').astimezone(timezone.utc) > date_list[p]:
                p += 1
                message += f"\n{EXHIBITIONS_PHRASES[p]}:\n"
            message = message +f"[{exib['title']}](https://t.me/{CHANNEL_LINK}/{exib['post_id']})\n"
    else:
        message = 'Выставок не найдено'

    return message

def get_list_dates(daynow):
    date_list = []
    # 1) Ends in two week
    date_list.append(daynow + timedelta(weeks=2))

    # 2) Ends in next month
    if daynow.month < 11:
        date_list.append(daynow.replace(month=daynow.month+2, day=1) - timedelta(days=1))
    elif daynow.month == 11:
        date_list.append(daynow.replace(month=12, day=31))
    else:
        date_list.append(daynow.replace(year=daynow.year+1, month=1, day=31))

    # 3) Others
    date_list.append(daynow.replace(year=daynow.year+10))
    
    return date_list


async def process_lucky_event(daynow):
    params = {
        'date_from': daynow.strftime('%Y-%m-%d'),
        'date_to': (daynow + timedelta(days=1)).strftime('%Y-%m-%d'),
        'limit': 100
    }
    events = await external_api.fetch_events(params)

    message = ''
    if events['result']:
        event = random.choice(events['result']['events'])
        message = f"[{event['title']}]({event['post_url']}) – {event['price']}\n"
    return message


async def process_telegram_monitor(monitor_dict):
    await crud.create_telegram_monitor(monitor_dict)

    