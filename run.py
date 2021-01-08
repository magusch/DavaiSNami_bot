import telebot
from telebot import types

import os, time

from flask import Flask, request
from analysis import what_message, exibit_analys,save_post, get_reminder_events
from database import check_event_in_db

from database import get_date_title, save_reminder

from dotenv import load_dotenv
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')

if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

token= os.environ['token']


URL = os.environ['URL']
#PORT = int(os.environ.get('PORT'))
id_admin = os.environ['id_admin']
id_channel = os.environ['id_channel']


bot = telebot.TeleBot(token)

server = Flask(__name__)

markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
date_menu=['сегодня', 'завтра', 'выходные', 'выставки','мне повезёт' ]
markup.add(types.KeyboardButton(date_menu[0].capitalize()), types.KeyboardButton(date_menu[1].capitalize()))
markup.add(types.KeyboardButton(date_menu[2].capitalize()), types.KeyboardButton(date_menu[3].capitalize()), types.KeyboardButton(date_menu[4].capitalize()))




@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
	bot.reply_to(message, "Привет! Это бот канала @DavaiSNami. С моей помощью можно получить краткий гид мероприятий на определённый день, на выходные или по проходящим выставкам в Петербурге. \n\n Чтобы начать укажите дату в формате: *«31 декабря»*, *«31.12»*, *«31»* или фразу: *«Сегодня»*, *«Завтра»*, *«Выходные»*.", parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(content_types=['text', 'photo'])
def send_text(message):
	# if message.text=='q':		
	# 	users_message = get_reminder_events()
	# 	for user, msg in users_message.items(): 
	# 		bot.send_message(user, msg, parse_mode="Markdown", disable_web_page_preview=True)

	if message.text:
		answer, code = what_message(message.text.lower())
		if code == 0:
			bot.send_message(message.chat.id, answer, parse_mode="Markdown", disable_web_page_preview=True, reply_markup=markup)	
		elif code == 2:
			bot.forward_message(message.chat.id, id_channel, int(answer))
		elif code == 1:
			bot.reply_to(message, answer, reply_markup=markup)
			#bad_message = message.text+' from @%s (%s %s)' %(message.from_user.username, message.from_user.first_name, message.from_user.last_name)
			#bot.send_message(id_admin, bad_message) 
	elif message.forward_from_chat:#
		if message.forward_from_chat.id==int(id_channel):
			post_id = message.forward_from_message_id

			remind = get_date_title(post_id) #get title and date from database of events
			
			if remind:
				remind.update({'post_id': post_id, 'user_id': message.chat.id})
				save_reminder(remind)
				msg = f"Мероприятие '{remind['title']}' сохранено"
				bot.send_message(remind['user_id'], msg)
			else: 
				bot.send_message(message.chat.id, 'Мероприятие прошло или является выставкой')

	msg = f"{message.text} from @{message.from_user.username} ({message.from_user.first_name} {message.from_user.last_name})"
	bot.send_message(id_admin, msg) #delete

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
	else:
		time.sleep(20)
		try:
			if not check_event_in_db(message.message_id):
				if save_post(post, message.message_id):
					bot.send_message(id_admin, 'Ошибка_post')
		except Exception as e:
			bot.send_message(id_admin, 'Ошибка_2')
			bot.send_message(id_admin, str(e))

	users_message = get_reminder_events()
	for user, msg in users_message.items(): 
		bot.send_message(user, msg, parse_mode="Markdown", disable_web_page_preview=True)


#req = f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={URL}/webhook"

try: #polling from user and webhook from server
	run_from_user = int(os.environ['run_from_user'])
except:
	run_from_user = 0


if run_from_user==1:
	bot.send_message(id_admin, 'Polling')
	bot.polling()
else:
	@server.route("/webhook", methods=['POST'])
	def getMessage():
		bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
		return "!", 200
	@server.route("/")
	def webhook():
		bot.remove_webhook()
		bot.set_webhook(url=URL+"/webhook") 
		return "?", 200

	server.run(host="0.0.0.0", port=os.environ.get('PORT', 80))
