import re
from datetime import datetime, timedelta

from database import get_message_with_events, find_exibitions, save_exibition

date_menu=['сегодня', 'завтра', 'выходные', 'выставки']

month_int2name=["янв","фев","мар","апр","мая","июн","июл","авг","сен","окт", "ноя", "дек"]

def get_day(when, daynow):
	if when==5 or when==6:
		weekday = daynow.weekday()
		when = when - weekday
	day_events = daynow + timedelta(days=when)
	return day_events


def what_message(message_from_user):
	daynow = datetime.utcnow()+timedelta(hours=3)
	bad = 0
	if message_from_user==date_menu[0]:
		date_with_events = get_day(0, daynow)
		answer=get_message_with_events(date_with_events)

	elif message_from_user==date_menu[1]:
		date_with_events=get_day(1, daynow)
		answer=get_message_with_events(date_with_events)

	elif message_from_user==date_menu[2]:
		date_with_events = get_day(5, daynow)
		answer = get_message_with_events(date_with_events)
		date_with_events = get_day(6, daynow)
		answer += f"\n{get_message_with_events(date_with_events)}"

	elif message_from_user==date_menu[3]:
		answer=find_exibitions(daynow)

	else:
		mq=re.split(r'[:,./ ]',message_from_user)
		try:
			day = int(mq[0])
			if len(mq)<2:
				month = daynow.month
				if day < daynow.day: month+=1
			elif re.search(r'[\d+]', mq[1]): #TODO: check month value
				month = int(mq[1])
			elif mq[1][:3] in month_int2name:
				month = month_int2name.index(mq[1][:3])+1			
			else:
				month = daynow.month
				if day < daynow.day: month+=1

			date_with_events = datetime(day=day, month=month, year=daynow.year)
			answer=get_message_with_events(date_with_events)
		except:
			bad = 1
			answer='Некорректная дата'

	return (answer, bad)


def exibit_analys(post, message_id):
	year = (datetime.utcnow()+timedelta(hours=3)).year

	title_line = post[:post.find('\n')].strip('\u200b')
	title_list = title_line.split(' ')

	exib=dict()
	exib['date_before'] = datetime(day = int(title_list[1]), month = month_int2name.index(title_list[2][:3].lower())+1, year=year) 
	exib['title'] = ' '.join(title_list[3:])
	exib['post_id'] = message_id
			
	save_exibition(exib)