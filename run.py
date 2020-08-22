import telebot
from telebot import types

import os, re

from flask import Flask, request
from analysis import what_message, exibit_analys

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

markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
date_menu=['сегодня', 'завтра', 'выходные', 'выставки']
markup.add(types.KeyboardButton(date_menu[0].capitalize()), types.KeyboardButton(date_menu[1].capitalize()))
markup.add(types.KeyboardButton(date_menu[2].capitalize()), types.KeyboardButton(date_menu[3].capitalize()))




@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
	bot.reply_to(message, "Привет! Это бот канала @DavaiSNami. Здесь можно получить краткий гид о мероприятиях на определённый день. Вся информация берётся с канала! \n Просто напишите дату в формате «31 декабря», «31.12» или «Сегодня» («Завтра», «Выходные»).", reply_markup=markup)

@bot.message_handler(content_types=['text', 'photo'])
def send_text(message):

	answer, bad_mess = what_message(message.text.lower())
	bot.send_message(message.chat.id, answer, parse_mode="Markdown", disable_web_page_preview=True, reply_markup=markup)
	
	if bad_mess:
		bad_message = message.text+' from @%s (%s %s)' %(message.from_user.username, message.from_user.first_name, message.from_user.last_name)
		bot.send_message(id_admin, bad_message) 


@bot.channel_post_handler(content_types=['text', 'photo'])
def take_post_fromChannel(message):
	if message.content_type =='text':
		post=message.text
	else:
		post=message.caption
	if post[:2]=='До': 
		try:
			exibit_analys(post, message.message_id)			
		except:
		 	bot.send_message(id_admin, 'Ошибка')



try:
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
except:
	bot.send_message(id_admin, 'Polling')
	bot.polling()