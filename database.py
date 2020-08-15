import re, time
import psycopg2


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


def get_db_cursor():
	return psycopg2.connect(DATABASE_URL, sslmode='require').cursor()

def _get(script):
	db_cursor = get_db_cursor()
	db_cursor.execute(script)
	values = db_cursor.fetchall()
	db_cursor.close()
	return values

def _insert(script, data):
	"""
	    Parameters:
	    -----------
	    data : list of values
	        inserting data
	    script : str
	        executing script
	    """
	db_cursor = get_db_cursor()

	db_cursor.execute(script, data)
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
	script = "INSERT INTO exhibitions (post_id, title, date_before) VALUES (%s, %s, cast('%s' as TIMESTAMP))"
	data = [event['post_id'], event['title'], event['date_before']]
	_insert(script, data)


def find_exibitions(date_today):
	#dateRequest, monthRequest=date_from_mess(mess)
	#monthRequest=monthes.index(monthRequest)+1
	script = "SELECT title, post_id FROM exhibitions \
	WHERE date_before>=cast('%s' as TIMESTAMP)" %(date_today)

	message='*Выставки:*\n\n'
	for exib in _get(script):
		#link=url+str(p[1])
		message=message+'[%s](https://t.me/DavaiSNami/%s)\n' %(exib[0],exib[1])
	return message





# def delete(posts_ids):
# 	with conn.cursor() as cursor:
# 		query="DELETE FROM datepost WHERE post_id<%s;"
# 		cursor.execute(query,str(posts_ids))
#		query="DELETE FROM posts WHERE post_id<%s;"
#		cursor.execute(query,str(posts_ids))
# 		conn.commit()
