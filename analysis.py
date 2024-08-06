import os, re, json
import requests

from datetime import datetime, timedelta

from database import get_message_with_events, find_exibitions, save_exibition, save_event, get_random_event

from database import get_reminder,delete_reminder

date_menu = ['сегодня', 'завтра', 'выходные', 'мне повезёт', 'выставки', 'день недели']

monthes = ['января', "февраля", 'марта', 'апреля', 'мая', 'июня','июля','августа','сентября','октября','ноября','декабря']
week_menu = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вск']
month_int2name = [month[:3] for month in monthes]
year = (datetime.utcnow()+timedelta(hours=3)).year

BOT_LINK = os.getenv('bot_link', '@DavaiSNamiBot')

CHANNEL_API_URL = os.getenv('CHANNEL_API_URL')
CHANNEL_API_TOKEN = os.getenv('CHANNEL_API_TOKEN')

def get_day(when, daynow):
	return daynow + timedelta(days=when)


def get_weekday(when, daynow):
	when = when - daynow.weekday()
	if when < 0: when = 7 + when
	day_events = daynow + timedelta(days=when)
	return day_events


def what_message(message_from_user):
	daynow = datetime.utcnow()+timedelta(hours=3)
	code = 0
	if message_from_user == date_menu[0]:
		date_with_events = get_day(0, daynow)
		answer = get_message_with_events(date_with_events)
	elif message_from_user == date_menu[1]:
		date_with_events = get_day(1, daynow)
		answer = get_message_with_events(date_with_events)
	elif message_from_user in week_menu:
		date_with_events = get_weekday(week_menu.index(message_from_user), daynow)
		answer = get_message_with_events(date_with_events)
	elif message_from_user == date_menu[2]:
		date_with_events = get_weekday(5, daynow)
		answer = get_message_with_events(date_with_events)
		date_with_events = get_weekday(6, daynow)
		answer += f"\n{get_message_with_events(date_with_events)}"

	elif message_from_user == date_menu[4]:
		answer = find_exibitions(daynow)

	elif message_from_user == date_menu[3]:
		answer, code = get_random_event(daynow)

	else:
		mq=re.split(r'[:,./ ]', message_from_user)
		try:
			day = int(mq[0])
			if len(mq) < 2:
				if day < daynow.day:
					month = daynow.month % 12 + 1
				else:
					month = daynow.month

			elif re.search(r'[\d+]', mq[1]): #TODO: check month value
				month = int(mq[1])
			elif mq[1][:3] in month_int2name:
				month = month_int2name.index(mq[1][:3])+1			
			else:
				month = daynow.month
				if day < daynow.day: month+=1

			if month >= daynow.month:
				year = daynow.year
			else:
				year = daynow.year + 1

			date_with_events = datetime(day=day, month=month, year=year)
			answer = get_message_with_events(date_with_events)
		except:
			code = 1
			answer = 'Укажите дату, подробности: /help'

	if type(answer)==str: answer += f"\n[{BOT_LINK}]({BOT_LINK})"
	return answer, code


def get_title_list(post):
	title = post[:post.find('\n')].strip('\u200b')
	return title.split(' ')


def exibit_analys(post, message_id):
	title_list = get_title_list(post)

	exib=dict()
	date_before = datetime(day = int(title_list[1]), month = month_int2name.index(title_list[2][:3].lower())+1, year=year)
	if date_before<datetime.now(): date_before=date_before.replace(year=year+1)
	exib['date_before'] = date_before
	exib['title'] = ' '.join(title_list[3:])
	exib['post_id'] = message_id
			
	save_exibition(exib)


def save_post(post, post_id):
	title_list = get_title_list(post)

	index_month = [title_list.index(word) for word in title_list if word.lower() in monthes]

	if len(index_month) == 0: return True

	title = ' '.join(title_list[index_month[-1]+1:])

	i_prev_month = 0
	dates_from, dates_to = list(), list()
	for i_m in index_month:
		month =  monthes.index(title_list[i_m])+1

		days_str = ' '.join(title_list[i_prev_month:i_m])
		if re.search(r'[–-]',days_str):
			days_list = re.split(r'[–-]', days_str)

			dates_from.append(datetime(year,month,int(days_list[0])))
			dates_to.append(datetime(year,month,int(days_list[1])))
		else:
			days_list = re.split(r'[и,]', days_str)

			dates_from.extend([datetime(year,month,int(day)) for day in days_list])
			dates_to.extend([datetime(year,month,int(day)) for day in days_list])

		i_prev_month = i_m+2

	save_event(title, post_id, dates_from, dates_to)


def get_reminder_events():
#(user_id, title, post_id)
	remind_events = get_reminder()
	users_message = {}
	
	for events in remind_events:
		user_id = events[0]

		ev = {'title':events[1],'post_id':events[2]}
		if user_id not in users_message: users_message[user_id] = []
		users_message[user_id].append(ev)

	for user, events in users_message.items():
		message = '*Сегодня:*\n\n'
		for e in events:
			url = f"https://t.me/DavaiSNami/{e['post_id']}"
			message += f"[{e['title']}]({url})\n"
		users_message[user]=message

	delete_reminder()
	return users_message

def send_text_to_ai(text):
	url = CHANNEL_API_URL + 'api/ai_update_event/'
	headers = {
		'Authorization': f"Bearer {CHANNEL_API_TOKEN}",
		'Content-Type': 'application/json'
	}
	data = {
		'is_new': 1,
		'event': {
			'full_text': text
		}
	}

	response = requests.post(url, headers=headers, data=json.dumps(data))
	if 'task_id' in response.json():
		return True

	

