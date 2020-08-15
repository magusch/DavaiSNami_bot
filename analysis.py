import re
from datetime import datetime, timedelta



def get_day(when):
	if when==5 or when==6:
		weekday = datetime.now().weekday()
		when = when - weekday
	day_events = datetime.now()+timedelta(days=when)
	return day_events



