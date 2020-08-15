import telebot
from telebot import types

import os, re
from datetime import datetime 
from flask import Flask, request
from database import get_message_with_events, save_exibition, find_exibitions
from analysis import get_day

from dotenv import load_dotenv
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')

if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

token= os.environ['token']


URL = os.environ['URL']
#PORT = int(os.environ.get('PORT'))
id_admin=os.environ['id_admin']


bot = telebot.TeleBot(token)


server = Flask(__name__)

#month_int2name=["января","февраля","марта","апреля","мая","июня","июля","августа","сентября","октября", "ноября", "декабря"]
month_int2name=["янв","фев","мар","апр","мая","июн","июл","авг","сен","окт", "ноя", "дек"]

markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
date_menu=['сегодня', 'завтра', 'выходные', 'выставки']
markup.add(types.KeyboardButton(date_menu[0].capitalize()), types.KeyboardButton(date_menu[1].capitalize()))
markup.add(types.KeyboardButton(date_menu[2].capitalize()), types.KeyboardButton(date_menu[3].capitalize()))




@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
	bot.reply_to(message, "Привет! Это бот канала @DavaiSNami. Здесь можно получить краткий гид о мероприятиях на определённый день. Вся информация берётся с канала! \n Просто напишите дату в формате «31 декабря», «31.12» или «Сегодня» («Завтра», «Выходные»).", reply_markup=markup)

@bot.message_handler(content_types=['text', 'photo'])
def send_text(message):
	#bot.send_message(message.chat.id, 'Одну секунду')
	message_from_user = message.text.lower()
	daynow = datetime.now()

	if message_from_user==date_menu[0]:
		date_with_events = get_day(0)
		messg=get_message_with_events(date_with_events)

	elif message_from_user==date_menu[1]:
		date_with_events=get_day(1)
		messg=get_message_with_events(date_with_events)

	elif message_from_user==date_menu[2]:
		date_with_events = get_day(6)
		messg = get_message_with_events(date_with_events)
		date_with_events = get_day(7)
		messg=messg+'\n'+get_message_with_events(date_with_events)

	elif message_from_user==date_menu[3]:
		messg=find_exibitions(daynow)

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
			messg=get_message_with_events(date_with_events)
		except:
			bad_message = message_from_user+' from @%s (%s %s)' %(message.from_user.username, message.from_user.first_name, message.from_user.last_name)
			bot.send_message(id_admin, bad_message)
			messg='Некорректная дата'
	bot.send_message(message.chat.id, messg, parse_mode="Markdown", disable_web_page_preview=True, reply_markup=markup)
	


@bot.channel_post_handler(content_types=['text', 'photo'])
def take_post_fromChannel(message):
	if message.content_type =='text':
		post=message.text
	else:
		post=message.caption
	if post[:2]=='До':
		daynow = datetime.now()
		exib=dict()

		try:
			title_line = post[:post.find('\n')].strip('\u200b')
			title_list = title_line.split(' ')

			exib['date_before'] = datetime(day = int(title_list[1]), month = monthes.index(title_list[2])+1, year=daynow.year) 
			exib['title'] = ' '.join(title_list[3:])
			exib['post_id'] = message.message_id
			
			save_exibition(exib)
			#exbns="%s: http://davaisnami.magusch.ru/?post=%s"%(title,str(message.message_id))
		except:
			bot.send_message(id_admin, 'Ошибка')


#bot.polling()

@server.route("/webhook", methods=['POST'])
def getMessage():
	bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
	return "!", 200
@server.route("/")
def webhook():
	bot.remove_webhook()
	bot.set_webhook(url=URL+"/webhook") # эurl нужно заменить на url вашего Хероку приложения
	return "?", 200

server.run(host="0.0.0.0", port=os.environ.get('PORT', 80))
