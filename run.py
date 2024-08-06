import telebot
from telebot import types

import os, time

from flask import Flask, request

import database
from analysis import what_message, exibit_analys, save_post, get_reminder_events, send_text_to_ai
from database import check_event_in_db

from database import get_date_title, save_reminder, save_person

from dotenv import load_dotenv
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')

if os.path.exists(dotenv_path):
	load_dotenv(dotenv_path)

token = os.environ['token']

URL = os.environ['URL']
#PORT = int(os.environ.get('PORT'))
id_admin = os.environ['id_admin']
id_channel = os.environ['id_channel']

channel_telegram_link = os.getenv('channel_url', '@DavaiSNami')

bot = telebot.TeleBot(token)

server = Flask(__name__)

markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
date_menu=['сегодня', 'завтра', 'выходные', 'выставки','мне повезёт', 'день недели']
markup.add(types.KeyboardButton(date_menu[0].capitalize()), types.KeyboardButton(date_menu[1].capitalize()))
markup.add(types.KeyboardButton(date_menu[2].capitalize()), types.KeyboardButton(date_menu[3].capitalize()),
			types.KeyboardButton(date_menu[4].capitalize()), types.KeyboardButton(date_menu[5].capitalize()))

week_menu = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вск']
markup_week = types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)

markup_week.add(types.KeyboardButton(week_menu[0]), types.KeyboardButton(week_menu[1]), types.KeyboardButton(week_menu[2]))
markup_week.add(types.KeyboardButton(week_menu[3]), types.KeyboardButton(week_menu[4]),
				types.KeyboardButton(week_menu[5]), types.KeyboardButton(week_menu[6]))

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
	bot.reply_to(message, f"Привет! Это бот канала {channel_telegram_link}. С моей помощью можно получить краткий гид мероприятий на определённый день, на выходные или по проходящим выставкам в городе. \n\n Чтобы начать укажите дату в формате: *«31 декабря»*, *«31.12»*, *«31»* или фразу: *«Сегодня»*, *«Завтра»*, *«Выходные»*. Либо нажать на кнопку в меню.", parse_mode="Markdown", reply_markup=markup)


@bot.message_handler(content_types=['text', 'photo'])
def send_text(message):
	# if message.text=='q':
	# 	users_message = get_reminder_events()
	# 	for user, msg in users_message.items():
	# 		bot.send_message(user, msg, parse_mode="Markdown", disable_web_page_preview=True)

	if message.text:
		if message.text == date_menu[5].capitalize():
			bot.send_message(message.chat.id, 'Дни недели', disable_web_page_preview=True,
							reply_markup=markup_week)
			code=-1
		else:
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
		if message.forward_from_chat.id == int(id_channel):
			post_id = message.forward_from_message_id

			remind = get_date_title(post_id) # Get title and date from database of events
			
			if remind:
				remind.update({'post_id': post_id, 'user_id': message.chat.id})
				save_reminder(remind)
				msg = f"Мероприятие '{remind['title']}' сохранено"
				bot.send_message(remind['user_id'], msg)
			else: 
				bot.send_message(message.chat.id, 'Мероприятие прошло или является выставкой')
		else:
			if message.chat.id in admins:
				if message.photo:
					text = message.caption
				else:
					text = message.text

				if text is not None:
					bot.send_message(message.chat.id, 'Пост отправлен в GPT')
					result = send_text_to_ai(text)
					if result:
						bot.send_message('Началась обработка текста, через некоторое время появится в админ панели')
					else:
						bot.send_message('Возникла ошибка')

	if message.text:
		text = message.text[0:100]
	elif message.photo:
		text = message.caption[0:100]
	else:
		text = 'ANOTHER TYPE OF MESSAGE'

	msg = f"{text} from @{message.from_user.username} ({message.from_user.first_name} {message.from_user.last_name})"
	bot.send_message(id_admin, msg)
	save_person(message.from_user.id, msg)

@bot.channel_post_handler(content_types=['text', 'photo'])
def take_post_from_channel(message):
	if message.content_type =='text':
		post=message.text
	else:
		post=message.caption
	if post[:2] == 'До':
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
	last_time_error = int(time.time())
	attempt = 0
	admins = [admin[0] for admin in database.get_admins()]
	while attempt<5:
		attempt += 1
		try:
			bot.send_message(id_admin, 'Polling')
			bot.polling()
		finally:
			now_time = int(time.time())
			different_time = (now_time - last_time_error)/60/60
			print(f"Error: {attempt}. Last run was {different_time} hours ago")
			time.sleep(attempt*60)
			if different_time>2:
				attempt = 0
		last_time_error = int(time.time())

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
