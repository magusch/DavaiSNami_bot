import urllib.request
from bs4 import BeautifulSoup

class AppURLopener(urllib.request.FancyURLopener):
    version = "Mozilla/5.0"




def timepad2post(url):
	opener = AppURLopener()
	html_doc = opener.open(url)

	#req=Request(url)
	#html_doc=urlopen(req).read()

	soup = BeautifulSoup(html_doc, 'html.parser')

	title=soup.title.string #Лекция ????

	place_name=soup.find(class_ = "morg__name").get_text() # название места
	q=place_name.split()  # Музей ...
	place_name=' '.join(q)  #сделать в одну строку

	post_text=soup.find(class_ = "toverride").get_text()
	#print(text[1:-1])

	date1= soup.find_all(class_ = "acard")[0].find(class_ = "tcaption")
	date1.b.replaceWith('')
	date_list=date1.get_text().replace(', начало в','').split()
	date=date_list[:date_list.index('Добавить')]
	date=' '.join(date)


	adress=soup.find_all(class_ = "acard")[1].find(class_ = "tcaption").span.string 

	title=title.replace('«','*«').replace('»','»*')

	title_line=' '.join(date_list[:2])+'*  '+title +'\n'

	poster_imag=soup.find(class_='mcover__image').img.get('src')


	title_line='[ᅠ]('+poster_imag+')*'+title_line
	#print(title_line)

	#print(post_text.replace('\n\n',''))

	footer='*Где:* '+place_name+', '+adress +' \n' +\
	'*Когда:* '+date+' \n'+\
	'*Вход свободный* [по предварительной регистрации](%s)' % url

	#print(footer)

	full_text=title_line+post_text+footer
	return full_text
	# f = open('text.txt', 'w')
	# f.write(full_text)
	# f.close()