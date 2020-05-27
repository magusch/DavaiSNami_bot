import re, time
import psycopg2


#CREATE TABLE posts (title varchar(100), posttext varchar, post_id int);
#CREATE TABLE exhibitions (day int,month int,title varchar(150), post_id int);

import os
from dotenv import load_dotenv
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

DATABASE_URL =os.environ.get('DATABASE_URL')

conn = psycopg2.connect(DATABASE_URL, sslmode='require')


url='https://t.me/DavaiSNami/'
monthes=['января', "февраля", 'марта', 'апреля', 'мая', 'июня','июля','августа','сентября','октября','ноября','декабря']

def savepost(post, message_id):
	title=post[:post.find('\n')].strip('\u200b')
	lineoftitle=title.split(' ')
	month=list(set(lineoftitle) & set(monthes))
	numbBegTitle=title.find(month[-1])
	date=title[:numbBegTitle]
	title=title[numbBegTitle+len(month[-1])+1:]
	#date=date[:date.index(month[-1])+1]
	if re.search(r'[–-]',date):
		dates=re.split(r'[–-]', date)
		dates=[*range(int(dates[0]), int(dates[1])+1)]
	else:
		dates=re.split(r'[и,]', date)
		for o in range(len(dates)):
			dates[o]=int(dates[o])


	#link=url+str(message_id)
	#data=[datesJSON, month[0], title, link]
	
	with conn.cursor() as cursor:
		for dateInt in dates:
			query = 'INSERT INTO datepost (dates,month,post_id) VALUES (%s,%s,%s)' 
			cursor.execute(query,(dateInt,month[0], message_id))
		query = 'INSERT INTO posts (title,post_id,posttext) VALUES (%s,%s,%s)' 
		cursor.execute(query,(title,message_id, post))
		conn.commit()


def events(mess):
	dateRequest, monthRequest=date_from_mess(mess)
	Message=str(mess)+':\n'
	with conn.cursor() as cursor:
		query="SELECT post_id FROM datepost WHERE dates=%s AND month=%s"
		cursor.execute(query, (dateRequest,monthRequest))
		post_ids = cursor.fetchall()
		for postid in post_ids:
			title="SELECT title, post_id FROM posts WHERE post_id=%s"
			cursor.execute(title, postid)
			titles=cursor.fetchall()
			Message=Message +'[%s](https://t.me/DavaiSNami/%s)\n'%(titles[0][0], titles[0][1])
	return Message

def date_from_mess(mess):
	Message=str(mess)+':\n'
	monthRequest=re.split(r'\d',mess)[-1][1:].lower()
	dateRequest=int(re.split(r'\s',mess)[0])
	if dateRequest>31 or monthRequest not in monthes:
		raise IOError("not correct data")
	return dateRequest, monthRequest

def save_exib(post,message_id):
	title=post[:post.find('\n')].strip('\u200b')
	lineoftitle=title.split(' ')
	day=int(lineoftitle[1])
	month=monthes.index(lineoftitle[2])+1
	title=' '.join(lineoftitle[3:])
	#link=url+str(message_id)
	
	with conn.cursor() as cursor:
		query = 'INSERT INTO exhibitions (day,month,title, post_id) VALUES (%s,%s,%s, %s)' 
		cursor.execute(query,(day,month, title, message_id))
		conn.commit()


def exhib_find(day_today,month_today):
	#dateRequest, monthRequest=date_from_mess(mess)
	#monthRequest=monthes.index(monthRequest)+1

	with conn.cursor() as cursor:
		query="SELECT title, post_id FROM exhibitions WHERE day>=%s AND month>=%s;"
		cursor.execute(query, (day_today,month_today))
		post = cursor.fetchall()

	message='*Выставки:*\n\n'
	for p in post:
		#link=url+str(p[1])
		message=message+'[%s](https://t.me/DavaiSNami/%s)\n' %(p[0],p[1])
	return message





# def delete(posts_ids):
# 	with conn.cursor() as cursor:
# 		query="DELETE FROM datepost WHERE post_id<%s;"
# 		cursor.execute(query,str(posts_ids))
#		query="DELETE FROM posts WHERE post_id<%s;"
#		cursor.execute(query,str(posts_ids))
# 		conn.commit()
