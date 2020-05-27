import telebot
from telebot import types

import os, time,re
from flask import Flask, request
from database import events, savepost, exhib_find, save_exib
from timepad2chan import timepad2post

from dotenv import load_dotenv
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')

if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

token= os.environ.get('token')

#PORT = int(os.environ.get('PORT'))
URL = os.environ.get('URL')
id_admin=os.environ.get('id_admin')


bot = telebot.TeleBot(token)
#logger = telebot.logger
#telebot.logger.setLevel(logging.INFO)


server = Flask(__name__)

month_int2name=["января","февраля","марта","апреля","мая","июня","июля","августа","сентября","октября", "ноября", "декабря"]

markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
date_menu=['Сегодня', 'Завтра', 'Выходные', 'Выставки']
markup.add(types.KeyboardButton(date_menu[0]), types.KeyboardButton(date_menu[1]))
markup.add(types.KeyboardButton(date_menu[2]), types.KeyboardButton(date_menu[3]))

def timetime(when):
	if when==6 or when==7:
		b=time.strftime('%w', time.gmtime(time.time()+3*3600))
		when=when-int(b)
	timenow=time.gmtime(time.time()+3*3600+when*86400);
	datenow=time.strftime('%d %m', timenow) # day month
	z=re.split(' ', datenow)
	z[1]=month_int2name[int(z[1])-1]
	datenow = ' '.join(z)
	return datenow








@bot.channel_post_handler(content_types=['text', 'photo'])
def take_post_fromChannel(message):
	if message.content_type =='text':
		post=message.text
	else:
		post=message.caption
	if post[:2]!='До':
		try:
			savepost(post, message.message_id)
		except:
			bot.send_message(id_admin, 'Ошибка1')
			bot.send_message(id_admin, post)
	elif post[:2]=='До':
		try:
			save_exib(post, message.message_id)
			#exbns="%s: http://davaisnami.magusch.ru/?post=%s"%(title,str(message.message_id))
		#bot.send_message(id_admin, exbns)
		except:
			bot.send_message(id_admin, 'Ошибка2')
		#	bot.send_message(id_admin, post)
	else:
		bot.send_message(id_admin, 'Ошибка3')

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
	bot.reply_to(message, "Привет! Это бот канала @DavaiSNami. Здесь можно получить краткий гид о мероприятиях на определённый день. Вся информация берётся с канала! \n Просто напишите дату в формате «31 декабря», «31.12» или «Сегодня» («Завтра», «Выходные»).", reply_markup=markup)

@bot.message_handler(content_types=['text', 'photo'])
def send_text(message):
	#bot.send_message(message.chat.id, 'Одну секунду')
	try:
		mq=re.split(r'[:,./ ]',message.text)
		mq[1]=month_int2name[int(mq[1])-1]
		message.text=' '.join(mq)
	except:
		msooo=message.text+' from @%s (%s %s)' %(message.from_user.username, message.from_user.first_name, message.from_user.last_name)
		bot.send_message(id_admin, msooo)
	if message.text.lower()==date_menu[0].lower():
		msg_date=timetime(0)
		messg=events(msg_date)
	elif message.text.lower()==date_menu[1].lower():
		msg_date=timetime(1)
		messg=events(msg_date)
	elif message.text.lower()==date_menu[2].lower():
		msg_date=timetime(6)
		messg=events(msg_date)
		msg_date=timetime(7)
		messg=messg+'\n'+events(msg_date)
	elif message.text.lower()==date_menu[3].lower():
		day_today=time.strftime('%d', time.gmtime(time.time()+3*3600))
		month_today=time.strftime('%m', time.gmtime(time.time()+3*3600))
		messg=exhib_find(day_today,month_today)
	else:
		try:
			messg=events(message.text)
		except:
			msooo=message.text+' from @%s (%s %s)' %(message.from_user.username, message.from_user.first_name, message.from_user.last_name)
			bot.send_message(id_admin, msooo)
			messg='Некорректная дата'
	bot.send_message(message.chat.id, messg,parse_mode="Markdown", disable_web_page_preview=True, reply_markup=markup)
	if message.chat.id==id_admin:
		if message.text[:3]=='tmp':
			mesq=timepad2post(message.text[4:])
			bot.send_message(id_admin, mesq, disable_web_page_preview=True, reply_markup=markup)





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
