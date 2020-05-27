import re
import time datetime as dt ##chooose

month_int2name=["None","янв","фев","мар","апр","мая","июн","июл","авг","сен","окт", "ноя", "дек"]

def mess2date(message):
	mess=re.split(r'[:,./ ]',message)
	day=mess[0]
	try:
		month=int(mess[1])
	except:
		month=month_int2name.index(mess[1][:3].lower())
	print(day,month)
	return(day,month)






day,month=mess2date('31 мар=tcта')
Date_in_format=time.strptime('%s %s 20'%(day,month), '%d %m %y')
print(Date_in_format)

def whatday(mess):
	if message.lower()=='сегодня':
		Date_in_format=["current_date"]
	elif message.lower()=='завтра':
		Date_in_format=["current_date+integer '1'"]
	elif message.lower()=='выходные':
		Date_in_format=[""]
	else:
		day,month=mess2date('31 мар=tcта')
		Date_in_format=["%s-%s-2020" %(day,month)]
		#Date_in_format=time.strptime('%s %s 20'%(day,month), '%d %m %y') #dt.date(2020,3,15)

