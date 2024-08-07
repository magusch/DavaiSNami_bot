import re, datetime
import psycopg2

import random

#CREATE TABLE exhibitions (post_id INT UNIQUE, title varchar(150), date_before TIMESTAMP);

import os
from dotenv import load_dotenv
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

DATABASE_URL =os.environ.get('DATABASE_URL')

#conn = psycopg2.connect(DATABASE_URL, sslmode='require')


channel_url = os.getenv('channel_url', '@DavaiSNami').replace("\\", "").replace('@','')

url = f'https://t.me/{channel_url}/'

monthes=['января', "февраля", 'марта', 'апреля', 'мая', 'июня','июля','августа','сентября','октября','ноября','декабря']

TAGS_EVENTS = ["id", "title", "post_id", "price"]
TABLENAME_EVENTS = os.environ.get('TABLENAME_EVENTS')


def get_db_connection():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def _get(script):
    db_cursor = get_db_connection().cursor()
    db_cursor.execute(script)
    values = db_cursor.fetchall()
    db_cursor.close()
    return values

def _insert(script):
    """
        Parameters:
        -----------
        data : list of values
            inserting data
        script : str
            executing script
        """
    db_connection = get_db_connection()
    db_cursor = db_connection.cursor()

    db_cursor.execute(script)
    db_connection.commit()

    db_connection.close()
    db_cursor.close()


def date_from_mess(mess):
    Message=str(mess)+':\n'
    monthRequest=re.split(r'\d',mess)[-1][1:].lower()
    dateRequest=int(re.split(r'\s',mess)[0])
    if dateRequest>31 or monthRequest not in monthes:
        raise IOError("not correct data")
    return dateRequest, monthRequest

def get_message_with_events(dt):
    message = f"*{dt.day} {monthes[dt.month-1]}:*\n"

    events = event_by_date(dt)

    if not events:
        message += "мероприятий ещё не появилось"
    else:
        for event in events:
            if event['price']:
                message += f"[{event['title']}]({url}{event['post_id']}) – {event['price']}\n"
            else:
                message += f"[{event['title']}]({url}{event['post_id']})\n"

    return message

def check_event_in_db(post_id):
    script = f"SELECT id FROM {TABLENAME_EVENTS} WHERE post_id={post_id}"
    if _get(script):
        return True
    return False

def event_by_date(dt):
    """
    Required for dt (type datetime):
    Only year, month and day.
    """
    script = (
            f"SELECT {', '.join(TAGS_EVENTS)} FROM {TABLENAME_EVENTS} "
            "WHERE post_id IS NOT NULL "
            "AND date_from::date <= '%s'::date AND date_to::date >= '%s'::date" % (dt,dt)
    )

    events = list()
    for values in _get(script):
        events.append(
            dict(title=values[1], post_id=values[2], price=values[3])
        )

    return events


def save_exibition(exib):
    script = f"INSERT INTO exhibitions (post_id, title, date_before) \
        VALUES ({exib['post_id']}, '{exib['title']}', cast('{exib['date_before']}' as TIMESTAMP))"
    _insert(script)


# List of three dates for dividing exibitions on category: ends in two week, ends in next month and others
def get_list_dates(date_today):
    # 1) Ends in two week
    date_list = [date_today + datetime.timedelta(weeks=2)]

    # 2) Ends in next month
    if date_today.month < 11:
        date_list.append(date_today.replace(month=date_today.month+2, day=1) - datetime.timedelta(days=1))
    elif date_today.month == 11:
        date_list.append(date_today.replace(month=12, day=31))
    else:
        date_list.append(date_today.replace(year=date_today.year+1, month=1, day=31))

    # 3) Others
    date_list.append(date_today.replace(year=date_today.year+10))
    return date_list


phrases_exhibitions = ['Скоро заканчиваются', 'Заканчиваются в следующем месяце', 'Остальные']


def find_exibitions(date_today):
    date_list = get_list_dates(date_today)

    script = "SELECT title, post_id, date_before FROM exhibitions \
    WHERE date_before >= cast('%s' as DATE) order by date_before" %(date_today)
    p = 0
    message = f"*Выставки:*\n{phrases_exhibitions[0]}:\n"
    for exib in _get(script):
        if exib[2] > date_list[p]:
            p += 1
            message += f"\n{phrases_exhibitions[p]}:\n"
        message = f"{message}[{exib[0]}]({url}{exib[1]})\n"

    return message


def save_event(title, post_id, dates_from, dates_to):
    script = ''
    for i in range(len(dates_from)):
        script += f"INSERT INTO {TABLENAME_EVENTS} (id, title, post_id, date_from, date_to) \
        VALUES  (4{random.randint(1000,9999)}4, '{title}', {post_id},\
            cast('{dates_from[i]}' as TIMESTAMP), cast('{dates_to[i]}' as TIMESTAMP)); "
    _insert(script)


def get_random_event(date):
    script = (
        f"SELECT post_id FROM {TABLENAME_EVENTS} "
        "WHERE post_id IS NOT NULL "
        f"AND '{date}'::date <= date_from::date "
        f"AND '{date}'::date + 5 >= date_from::date;"
    )
    if _get(script):
        return (random.choice(_get(script))[0], 2)
    else:
        return ('Мероприятий нет', 0)

# def delete(posts_ids):
# 	with conn.cursor() as cursor:
# 		query="DELETE FROM datepost WHERE post_id<%s;"
# 		cursor.execute(query,str(posts_ids))
#		query="DELETE FROM posts WHERE post_id<%s;"
#		cursor.execute(query,str(posts_ids))
# 		conn.commit()


#____________REMINDER___________

def get_date_title(post_id):
    script = f'SELECT title, date_from FROM {TABLENAME_EVENTS} Where post_id={post_id}';
    answer = _get(script)
    if answer:
        remind = {'title':answer[0][0], 'date':answer[0][1]}
        return remind


def save_reminder(remind):
    script = f"INSERT INTO reminder (user_id, title, post_id, date) \
        VALUES ({remind['user_id']}, '{remind['title']}', '{remind['post_id']}', '{remind['date']}'::date)"
    _insert(script)

def delete_reminder():
    script = f"DELETE FROM reminder WHERE date = current_date"
    _insert(script)

def get_reminder():
    script = f'SELECT user_id, title, post_id FROM reminder WHERE date = current_date'
    return _get(script)


def save_person(user_id, message):
    today = datetime.datetime.now()
    script = f"INSERT INTO bot_users (user_id, message, date) \
            VALUES ({user_id}, '{message}', '{today}'::timestamp)"
    _insert(script)

#____________END___REMINDER___________


def get_admins():
    script = f"SELECT user_id FROM bot_users_general where is_admin is True"
    return _get(script)

