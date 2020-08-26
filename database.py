import re, time
import psycopg2

from random import randint
#CREATE TABLE posts (title varchar(100), posttext varchar, post_id int);
#CREATE TABLE exhibitions (post_id INT UNIQUE, title varchar(150), date_before TIMESTAMP);

import os
from dotenv import load_dotenv
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

DATABASE_URL =os.environ.get('DATABASE_URL')

#conn = psycopg2.connect(DATABASE_URL, sslmode='require')


url='https://t.me/DavaiSNami/'

monthes=['января', "февраля", 'марта', 'апреля', 'мая', 'июня','июля','августа','сентября','октября','ноября','декабря']

TAGS_EVENTS = ["id", "title", "post_id"]
TABLENAME_EVENTS = "events"


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

	for event in events:
		message += '[%s](https://t.me/DavaiSNami/%s)\n' %(event['title'], event['post_id'])

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
        "AND EXTRACT(DAY FROM date_from) = %s " 
        "AND EXTRACT(MONTH FROM date_from) = %s " %(dt.day, dt.month)
    )

    events = list()
    for values in _get(script):
        events.append(
            dict(title=values[1], post_id=values[2])
        )

    return events

def save_exibition(exib):
	script = f"INSERT INTO exhibitions (post_id, title, date_before) \
		VALUES ({exib['post_id']}, '{exib['title']}', cast('{exib['date_before']}' as TIMESTAMP))"
	#data = [exib['post_id'], exib['title'], exib['date_before']]
	_insert(script)


def find_exibitions(date_today):
	#dateRequest, monthRequest=date_from_mess(mess)
	#monthRequest=monthes.index(monthRequest)+1
	script = "SELECT title, post_id FROM exhibitions \
	WHERE date_before>=cast('%s' as TIMESTAMP)" %(date_today)

	message='*Выставки:*\n\n'
	for exib in _get(script):
		#link=url+str(p[1])
		message = f"{message}[{exib[0]}]({url}{exib[1]})\n"
	return message


def save_event(title, post_id, dates):
	#Delete FROM events WHERE id>410003 AND id<499995;
	script = ''
	for date in dates:
		script += f"INSERT INTO events (id, title, post_id, date_from, url) \
			VALUES  (4{randint(1000,9999)}4, '{title}', {post_id},\
				cast('{date}' as TIMESTAMP), '{url}{post_id}'); "
	_insert(script)
	


# def delete(posts_ids):
# 	with conn.cursor() as cursor:
# 		query="DELETE FROM datepost WHERE post_id<%s;"
# 		cursor.execute(query,str(posts_ids))
#		query="DELETE FROM posts WHERE post_id<%s;"
#		cursor.execute(query,str(posts_ids))
# 		conn.commit()
