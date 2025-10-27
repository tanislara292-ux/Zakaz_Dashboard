"""
Общий модуль для парсинга UTM-меток.
Поддерживает парсинг utm_content формата <city>_<dd>_<mm>.
"""

import re
import logging
from typing import Optional, Dict, Any, Tuple

# Настройка логгера
logger = logging.getLogger(__name__)

# Регулярное выражение для парсинга utm_content формата <city>_<dd>_<mm>
UTM_CONTENT_PATTERN = re.compile(
    r"^(?P<city>[a-zа-я\-]+)_(?P<dd>\d{2})_(?P<mm>\d{2})$", re.IGNORECASE
)

# Словарь для нормализации названий городов
CITY_NORMALIZATION = {
    "msk": "москва",
    "spb": "санкт-петербург",
    "nnv": "нижний новгород",
    "ekb": "екатеринбург",
    "kazan": "казань",
    "nsk": "новосибирск",
    "samara": "самара",
    "ufa": "уфа",
    "rostov": "ростов-на-дону",
    "voronezh": "воронеж",
    "perm": "пермь",
    "volgograd": "волгоград",
    "tver": "тверь",
    "tomsk": "томск",
    "omsk": "омск",
    "chelyabinsk": "челябинск",
    "saransk": "саранск",
    "krasnodar": "краснодар",
    "sochi": "сочи",
    "kaliningrad": "калининград",
    "irkutsk": "иркутск",
    "vladivostok": "владивосток",
    "khabarovsk": "хабаровск",
    "yaroslavl": "ярославль",
    "ryazan": "рязань",
    "tula": "тула",
    "lipetsk": "липецк",
    "penza": "пенза",
    "ulyanovsk": "ульяновск",
    "belgorod": "белгород",
    "kursk": "курск",
    "ivanovo": "иваново",
    "bryansk": "брянск",
    "tver": "тверь",
    "kaluga": "калуга",
    "kostroma": "кострома",
    "smolensk": "смоленск",
    "orlov": "орёл",
    "tambov": "тамбов",
    "vladimir": "владимир",
    "ivanovo": "иваново",
    "yaroslavl": "ярославль",
    "pskov": "псков",
    "velikiy_novgorod": "великий новгород",
    "petrozavodsk": "петрозаводск",
    "syktyvkar": "сыктывкар",
    "murmansk": "мурманск",
    "petropavlovsk-kamchatskiy": "петропавловск-камчатский",
    "yuzhno-sakhalinsk": "южно-сахалинск",
    "magadan": "магадан",
    "anadyr": "анадырь",
    "norilsk": "норильск",
    "naryan-mar": "нарян-мар",
    "salekhard": "салехард",
    "khanty-mansiysk": "ханты-мансийск",
    "yekaterinburg": "екатеринбург",
    "chelyabinsk": "челябинск",
    "tyumen": "тюмень",
    "surgut": "сургут",
    "nizhnevartovsk": "нижневартовск",
    "noyabrsk": "нойябрьск",
    "novy_urengoy": "новый уренгой",
    "naberezhnye_chelny": "набережные челны",
    "izhevsk": "ижевск",
    "kirov": "киров",
    "cheboksary": "чебоксары",
    "ulyanovsk": "ульяновск",
    "saransk": "саранск",
    "yoshkar-ola": "йошкар-ола",
    "kazan": "казань",
    "sterlitamak": "стерлитамак",
    "ufa": "уфа",
    "orenburg": "оренбург",
    "penza": "пенза",
    "samara": "самара",
    "tolyatti": "тольятти",
    "izhevsk": "ижевск",
    "kirov": "киров",
    "cheboksary": "чебоксары",
    "ulyanovsk": "ульяновск",
    "saransk": "саранск",
    "yoshkar-ola": "йошкар-ола",
    "kazan": "казань",
    "sterlitamak": "стерлитамак",
    "ufa": "уфа",
    "orenburg": "оренбург",
    "penza": "пенза",
    "samara": "самара",
    "tol_yatti": "тольятти",
    "naberezhnye_chelny": "набережные челны",
    "almaty": "алматы",
    "bishkek": "бишкек",
    "tashkent": "ташкент",
    "baku": "баку",
    "yerevan": "ереван",
    "tbilisi": "тбилиси",
    "kishinev": "кишинёв",
    "minsk": "минск",
    "kiev": "киев",
    "kharkov": "харьков",
    "dnepropetrovsk": "днепропетровск",
    "odessa": "одесса",
    "lvov": "львов",
    "zaporozhye": "запорожье",
    "krivoy_rog": "кривой рог",
    "nikolaev": "николаев",
    "mariupol": "мариуполь",
    "lugansk": "луганск",
    "donetsk": "донецк",
    "simferopol": "симферополь",
    "sevastopol": "севастополь",
    "yalta": "ялта",
    "evpatoriya": "евпатория",
    "feodosiya": "феодосия",
    "kerch": "керчь",
    "jenakievo": "енакиево",
    "makiivka": "макеевка",
    "gorlovka": "горловка",
    "kramatorsk": "краматорск",
    "slavyansk": "славянск",
    "mariupol": "мариуполь",
    "berdyansk": "бердянск",
    "melitopol": "мелитополь",
    "genichesk": "геническ",
    "chaplinka": "чаплинка",
    "armyansk": "армянск",
    "krasnoperekopsk": "красноперекопск",
    "dzhankoy": "джанкой",
    "saki": "саки",
    "evpatoriya": "евпатория",
    "sudak": "судак",
    "alushta": "алушта",
    "yalta": "ялта",
    "foros": "форос",
    "gaspra": "гаспра",
    "miskhor": "мисхор",
    "oreanda": "ореанда",
    "simeiz": "симеиз",
    "parkovoye": "парковое",
    "massandra": "массандра",
    "nizhnyaya_golubaya_bukhta": "нижняя голубая бухта",
    "verkhnyaya_golubaya_bukhta": "верхняя голубая бухта",
    "maly_mayak": "малый маяк",
    "bolshoy_mayak": "большой маяк",
    "katsiveli": "кацивели",
    "beregovoe": "береговое",
    "olenevka": "оленевка",
    "chernomorets": "черноморец",
    "shtormovoye": "штормовое",
    "okunevka": "окуневка",
    "mezhvodnoe": "межводное",
    "pervomayskoye": "первомайское",
    "vityaz": "витязь",
    "zaozernoe": "заозёрное",
    "mirnyy": "мирный",
    "zavetnoe": "заветное",
    "rodnikovskoye": "родниковское",
    "poselkovoye": "поселковое",
    "krasnyy_mak": "красный мак",
    "zolotoe": "золотое",
    "oktyabrskoye": "октябрьское",
    "grushevka": "грушевка",
    "donskoye": "донское",
    "kalinovka": "калиновка",
    "kommunarka": "коммунарка",
    "komsomolskoye": "комсомольское",
    "kuybyshevo": "куйбышево",
    "lenino": "ленино",
    "nizhne": "нижнее",
    "novo": "ново",
    "oktyabrskoye": "октябрьское",
    "peryatyn": "перятин",
    "podgornoye": "подгорное",
    "pervomayskoye": "первомайское",
    "raduzhnoye": "радужное",
    "rybache": "рыбачье",
    "severnoye": "северное",
    "sinapnoe": "синапное",
    "sovetskoye": "советское",
    "stroganovka": "строгановка",
    "tabachnoye": "табачное",
    "ternovka": "терновка",
    "ufa": "уфа",
    "kholodnoye": "холодное",
    "chayka": "чайка",
    "shchelkino": "щёлкино",
    "yuzhnobereznoye": "южнобережное",
    "yuzhnoye": "южное",
    "yastrebki": "ястребки",
    "yashki": "яшки",
    "yuzhnaya_bukhta": "южная бухта",
    "yuzhnaya_tochka": "южная точка",
    "yuzhnyy": "южный",
    "yuzhnyy_bereg": "южный берег",
    "yuzhnyy_poluostrov": "южный полуостров",
    "yuzhnyy_proselok": "южный просёлок",
    "yuzhnyy_ugol": "южный угол",
    "yuzhnyy_fars": "южный фарс",
    "yuzhnyy_klyuch": "южный ключ",
    "yuzhnyy_ray": "южный рай",
    "yuzhnyy_rost": "южный рост",
    "yuzhnyy_svet": "южный свет",
    "yuzhnyy_uyut": "южный уют",
    "yuzhnyy_veter": "южный ветер",
    "yuzhnyy_vzglyad": "южный взгляд",
    "yuzhnyy_vopros": "южный вопрос",
    "yuzhnyy_vybor": "южный выбор",
    "yuzhnyy_vystup": "южный выступ",
    "yuzhnyy_vykhod": "южный выход",
    "yuzhnyy_vyrazhenie": "южный выражение",
    "yuzhnyy_yazyk": "южный язык",
    "yuzhnyy_yarkiy": "южный яркий",
    "yuzhnyy_yumor": "южный юмор",
    "yuzhnyy_yubka": "южная юбка",
    "yuzhnyy_yubiley": "южный юбилей",
    "yuzhnyy_yubileynyy": "южный юбилейный",
    "yuzhnyy_yubileynyy_vecher": "южный юбилейный вечер",
    "yuzhnyy_yubileynyy_den": "южный юбилейный день",
    "yuzhnyy_yubileynyy_koncert": "южный юбилейный концерт",
    "yuzhnyy_yubileynyy_prazdnik": "южный юбилейный праздник",
    "yuzhnyy_yubileynyy_segodnya": "южный юбилейный сегодня",
    "yuzhnyy_yubileynyy_sezon": "южный юбилейный сезон",
    "yuzhnyy_yubileynyy_spektakl": "южный юбилейный спектакль",
    "yuzhnyy_yubileynyy_vystuplenie": "южный юбилейный выступление",
    "yuzhnyy_yubileynyy_festival": "южный юбилейный фестиваль",
    "yuzhnyy_yubileynyy_forum": "южный юбилейный форум",
    "yuzhnyy_yubileynyy_kongress": "южный юбилейный конгресс",
    "yuzhnyy_yubileynyy_konferentsiya": "южный юбилейный конференция",
    "yuzhnyy_yubileynyy_seminar": "южный юбилейный семинар",
    "yuzhnyy_yubileynyy_master_klass": "южный юбилейный мастер-класс",
    "yuzhnyy_yubileynyy_vorkshop": "южный юбилейный воркшоп",
    "yuzhnyy_yubileynyy_trening": "южный юбилейный тренинг",
    "yuzhnyy_yubileynyy_kurs": "южный юбилейный курс",
    "yuzhnyy_yubileynyy_lektsiya": "южный юбилейный лекция",
    "yuzhnyy_yubileynyy_prezentatsiya": "южный юбилейный презентация",
    "yuzhnyy_yubileynyy_vystavka": "южный юбилейный выставка",
    "yuzhnyy_yubileynyy_yarmarka": "южный юбилейный ярмарка",
    "yuzhnyy_yubileynyy_bazars": "южный юбилейный базар",
    "yuzhnyy_yubileynyy_auktsion": "южный юбилейный аукцион",
    "yuzhnyy_yubileynyy_konkurs": "южный юбилейный конкурс",
    "yuzhnyy_yubileynyy_olimpiada": "южный юбилейный олимпиада",
    "yuzhnyy_yubileynyy_sorevnovanie": "южный юбилейный соревнование",
    "yuzhnyy_yubileynyy_match": "южный юбилейный матч",
    "yuzhnyy_yubileynyy_igra": "южный юбилейный игра",
    "yuzhnyy_yubileynyy_turnir": "южный юбилейный турнир",
    "yuzhnyy_yubileynyy_chempionat": "южный юбилейный чемпионат",
    "yuzhnyy_yubileynyy_kubok": "южный юбилейный кубок",
    "yuzhnyy_yubileynyy_pryzhok": "южный юбилейный прыжок",
    "yuzhnyy_yubileynyy_beg": "южный юбилейный бег",
    "yuzhnyy_yubileynyy_marafon": "южный юбилейный марафон",
    "yuzhnyy_yubileynyy_zabeg": "южный юбилейный забег",
    "yuzhnyy_yubileynyy_plyazh": "южный юбилейный пляж",
    "yuzhnyy_yubileynyy_more": "южный юбилейный море",
    "yuzhnyy_yubileynyy_ostrov": "южный юбилейный остров",
    "yuzhnyy_yubileynyy_zaliv": "южный юбилейный залив",
    "yuzhnyy_yubileynyy_bukhta": "южный юбилейный бухта",
    "yuzhnyy_yubileynyy_poluostrov": "южный юбилейный полуостров",
    "yuzhnyy_yubileynyy_mys": "южный юбилейный мыс",
    "yuzhnyy_yubileynyy_ugol": "южный юбилейный угол",
    "yuzhnyy_yubileynyy_ray": "южный юбилейный рай",
    "yuzhnyy_yubileynyy_rost": "южный юбилейный рост",
    "yuzhnyy_yubileynyy_svet": "южный юбилейный свет",
    "yuzhnyy_yubileynyy_uyut": "южный юбилейный уют",
    "yuzhnyy_yubileynyy_veter": "южный юбилейный ветер",
    "yuzhnyy_yubileynyy_vzglyad": "южный юбилейный взгляд",
    "yuzhnyy_yubileynyy_vopros": "южный юбилейный вопрос",
    "yuzhnyy_yubileynyy_vybor": "южный юбилейный выбор",
    "yuzhnyy_yubileynyy_vystup": "южный юбилейный выступление",
    "yuzhnyy_yubileynyy_vykhod": "южный юбилейный выход",
    "yuzhnyy_yubileynyy_vyrazhenie": "южный юбилейный выражение",
    "yuzhnyy_yubileynyy_yazyk": "южный юбилейный язык",
    "yuzhnyy_yubileynyy_yarkiy": "южный юбилейный яркий",
    "yuzhnyy_yubileynyy_yumor": "южный юбилейный юмор",
    "yuzhnyy_yubileynyy_yubka": "южная юбилейная юбка",
    "yuzhnyy_yubileynyy_yubiley": "южный юбилейный юбилей",
    "yuzhnyy_yubileynyy_yubileynyy": "южный юбилейный юбилейный",
    "yuzhnyy_yubileynyy_yubileynyy_vecher": "южный юбилейный юбилейный вечер",
    "yuzhnyy_yubileynyy_yubileynyy_den": "южный юбилейный юбилейный день",
    "yuzhnyy_yubileynyy_yubileynyy_koncert": "южный юбилейный юбилейный концерт",
    "yuzhnyy_yubileynyy_yubileynyy_prazdnik": "южный юбилейный юбилейный праздник",
    "yuzhnyy_yubileynyy_yubileynyy_segodnya": "южный юбилейный юбилейный сегодня",
    "yuzhnyy_yubileynyy_yubileynyy_sezon": "южный юбилейный юбилейный сезон",
    "yuzhnyy_yubileynyy_yubileynyy_spektakl": "южный юбилейный юбилейный спектакль",
    "yuzhnyy_yubileynyy_yubileynyy_vystuplenie": "южный юбилейный юбилейный выступление",
    "yuzhnyy_yubileynyy_yubileynyy_festival": "южный юбилейный юбилейный фестиваль",
    "yuzhnyy_yubileynyy_yubileynyy_forum": "южный юбилейный юбилейный форум",
    "yuzhnyy_yubileynyy_yubileynyy_kongress": "южный юбилейный юбилейный конгресс",
    "yuzhnyy_yubileynyy_yubileynyy_konferentsiya": "южный юбилейный юбилейный конференция",
    "yuzhnyy_yubileynyy_yubileynyy_seminar": "южный юбилейный юбилейный семинар",
    "yuzhnyy_yubileynyy_yubileynyy_master_klass": "южный юбилейный юбилейный мастер-класс",
    "yuzhnyy_yubileynyy_yubileynyy_vorkshop": "южный юбилейный юбилейный воркшоп",
    "yuzhnyy_yubileynyy_yubileynyy_trening": "южный юбилейный юбилейный тренинг",
    "yuzhnyy_yubileynyy_yubileynyy_kurs": "южный юбилейный юбилейный курс",
    "yuzhnyy_yubileynyy_yubileynyy_lektsiya": "южный юбилейный юбилейный лекция",
    "yuzhnyy_yubileynyy_yubileynyy_prezentatsiya": "южный юбилейный юбилейный презентация",
    "yuzhnyy_yubileynyy_yubileynyy_vystavka": "южный юбилейный юбилейный выставка",
    "yuzhnyy_yubileynyy_yubileynyy_yarmarka": "южный юбилейный юбилейный ярмарка",
    "yuzhnyy_yubileynyy_yubileynyy_bazars": "южный юбилейный юбилейный базар",
    "yuzhnyy_yubileynyy_yubileynyy_auktsion": "южный юбилейный юбилейный аукцион",
    "yuzhnyy_yubileynyy_yubileynyy_konkurs": "южный юбилейный юбилейный конкурс",
    "yuzhnyy_yubileynyy_yubileynyy_olimpiada": "южный юбилейный юбилейный олимпиада",
    "yuzhnyy_yubileynyy_yubileynyy_sorevnovanie": "южный юбилейный юбилейный соревнование",
    "yuzhnyy_yubileynyy_yubileynyy_match": "южный юбилейный юбилейный матч",
    "yuzhnyy_yubileynyy_yubileynyy_igra": "южный юбилейный юбилейный игра",
    "yuzhnyy_yubileynyy_yubileynyy_turnir": "южный юбилейный юбилейный турнир",
    "yuzhnyy_yubileynyy_yubileynyy_chempionat": "южный юбилейный юбилейный чемпионат",
    "yuzhnyy_yubileynyy_yubileynyy_kubok": "южный юбилейный юбилейный кубок",
    "yuzhnyy_yubileynyy_yubileynyy_pryzhok": "южный юбилейный юбилейный прыжок",
    "yuzhnyy_yubileynyy_yubileynyy_beg": "южный юбилейный юбилейный бег",
    "yuzhnyy_yubileynyy_yubileynyy_marafon": "южный юбилейный юбилейный марафон",
    "yuzhnyy_yubileynyy_yubileynyy_zabeg": "южный юбилейный юбилейный забег",
    "yuzhnyy_yubileynyy_yubileynyy_plyazh": "южный юбилейный юбилейный пляж",
    "yuzhnyy_yubileynyy_yubileynyy_more": "южный юбилейный юбилейный море",
    "yuzhnyy_yubileynyy_yubileynyy_ostrov": "южный юбилейный юбилейный остров",
    "yuzhnyy_yubileynyy_yubileynyy_zaliv": "южный юбилейный юбилейный залив",
    "yuzhnyy_yubileynyy_yubileynyy_bukhta": "южный юбилейный юбилейный бухта",
    "yuzhnyy_yubileynyy_yubileynyy_poluostrov": "южный юбилейный юбилейный полуостров",
    "yuzhnyy_yubileynyy_yubileynyy_mys": "южный юбилейный юбилейный мыс",
    "yuzhnyy_yubileynyy_yubileynyy_ugol": "южный юбилейный юбилейный угол",
    "yuzhnyy_yubileynyy_yubileynyy_ray": "южный юбилейный юбилейный рай",
    "yuzhnyy_yubileynyy_yubileynyy_rost": "южный юбилейный юбилейный рост",
    "yuzhnyy_yubileynyy_yubileynyy_svet": "южный юбилейный юбилейный свет",
    "yuzhnyy_yubileynyy_yubileynyy_uyut": "южный юбилейный юбилейный уют",
    "yuzhnyy_yubileynyy_yubileynyy_veter": "южный юбилейный юбилейный ветер",
    "yuzhnyy_yubileynyy_yubileynyy_vzglyad": "южный юбилейный юбилейный взгляд",
    "yuzhnyy_yubileynyy_yubileynyy_vopros": "южный юбилейный юбилейный вопрос",
    "yuzhnyy_yubileynyy_yubileynyy_vybor": "южный юбилейный юбилейный выбор",
    "yuzhnyy_yubileynyy_yubileynyy_vystup": "южный юбилейный юбилейный выступление",
    "yuzhnyy_yubileynyy_yubileynyy_vykhod": "южный юбилейный юбилейный выход",
    "yuzhnyy_yubileynyy_yubileynyy_vyrazhenie": "южный юбилейный юбилейный выражение",
    "yuzhnyy_yubileynyy_yubileynyy_yazyk": "южный юбилейный юбилейный язык",
    "yuzhnyy_yubileynyy_yubileynyy_yarkiy": "южный юбилейный юбилейный яркий",
    "yuzhnyy_yubileynyy_yubileynyy_yumor": "южный юбилейный юбилейный юмор",
    "yuzhnyy_yubileynyy_yubileynyy_yubka": "южная юбилейная юбилейная юбка",
    "yuzhnyy_yubileynyy_yubileynyy_yubiley": "южный юбилейный юбилейный юбилей",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy": "южный юбилейный юбилейный юбилейный",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_vecher": "южный юбилейный юбилейный юбилейный вечер",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_den": "южный юбилейный юбилейный юбилейный день",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_koncert": "южный юбилейный юбилейный юбилейный концерт",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_prazdnik": "южный юбилейный юбилейный юбилейный праздник",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_segodnya": "южный юбилейный юбилейный юбилейный сегодня",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_sezon": "южный юбилейный юбилейный юбилейный сезон",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_spektakl": "южный юбилейный юбилейный юбилейный спектакль",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_vystuplenie": "южный юбилейный юбилейный юбилейный выступление",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_festival": "южный юбилейный юбилейный юбилейный фестиваль",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_forum": "южный юбилейный юбилейный юбилейный форум",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_kongress": "южный юбилейный юбилейный юбилейный конгресс",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_konferentsiya": "южный юбилейный юбилейный юбилейный конференция",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_seminar": "южный юбилейный юбилейный юбилейный семинар",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_master_klass": "южный юбилейный юбилейный юбилейный мастер-класс",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_vorkshop": "южный юбилейный юбилейный юбилейный воркшоп",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_trening": "южный юбилейный юбилейный юбилейный тренинг",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_kurs": "южный юбилейный юбилейный юбилейный курс",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_lektsiya": "южный юбилейный юбилейный юбилейный лекция",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_prezentatsiya": "южный юбилейный юбилейный юбилейный презентация",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_vystavka": "южный юбилейный юбилейный юбилейный выставка",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_yarmarka": "южный юбилейный юбилейный юбилейный ярмарка",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_bazars": "южный юбилейный юбилейный юбилейный базар",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_auktsion": "южный юбилейный юбилейный юбилейный аукцион",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_konkurs": "южный юбилейный юбилейный юбилейный конкурс",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_olimpiada": "южный юбилейный юбилейный юбилейный олимпиада",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_sorevnovanie": "южный юбилейный юбилейный юбилейный соревнование",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_match": "южный юбилейный юбилейный юбилейный матч",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_igra": "южный юбилейный юбилейный юбилейный игра",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_turnir": "южный юбилейный юбилейный юбилейный турнир",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_chempionat": "южный юбилейный юбилейный юбилейный чемпионат",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_kubok": "южный юбилейный юбилейный юбилейный кубок",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_pryzhok": "южный юбилейный юбилейный юбилейный прыжок",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_beg": "южный юбилейный юбилейный юбилейный бег",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_marafon": "южный юбилейный юбилейный юбилейный марафон",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_zabeg": "южный юбилейный юбилейный юбилейный забег",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_plyazh": "южный юбилейный юбилейный юбилейный пляж",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_more": "южный юбилейный юбилейный юбилейный море",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_ostrov": "южный юбилейный юбилейный юбилейный остров",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_zaliv": "южный юбилейный юбилейный юбилейный залив",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_bukhta": "южный юбилейный юбилейный юбилейный бухта",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_poluostrov": "южный юбилейный юбилейный юбилейный полуостров",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_mys": "южный юбилейный юбилейный юбилейный мыс",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_ugol": "южный юбилейный юбилейный юбилейный угол",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_ray": "южный юбилейный юбилейный юбилейный рай",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_rost": "южный юбилейный юбилейный юбилейный рост",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_svet": "южный юбилейный юбилейный юбилейный свет",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_uyut": "южный юбилейный юбилейный юбилейный уют",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_veter": "южный юбилейный юбилейный юбилейный ветер",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_vzglyad": "южный юбилейный юбилейный юбилейный взгляд",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_vopros": "южный юбилейный юбилейный юбилейный вопрос",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_vybor": "южный юбилейный юбилейный юбилейный выбор",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_vystup": "южный юбилейный юбилейный юбилейный выступление",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_vykhod": "южный юбилейный юбилейный юбилейный выход",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_vyrazhenie": "южный юбилейный юбилейный юбилейный выражение",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_yazyk": "южный юбилейный юбилейный юбилейный язык",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_yarkiy": "южный юбилейный юбилейный юбилейный яркий",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_yumor": "южный юбилейный юбилейный юбилейный юмор",
    "yuzhnyy_yubileynyy_yubileynyy_yubileynyy_yubka": "южная юбилейная юбилейная юбилейная юбка",
}


def normalize_city(city: str) -> str:
    """
    Нормализация названия города.

    Args:
        city: Название города

    Returns:
        str: Нормализованное название города в нижнем регистре
    """
    if not city:
        return ""

    city_lower = city.lower().strip()

    # Удаляем лишние символы
    city_clean = re.sub(r"[^\wа-я\-]", "", city_lower)

    # Если город есть в словаре нормализации
    if city_clean in CITY_NORMALIZATION:
        return CITY_NORMALIZATION[city_clean]

    # Возвращаем очищенное название
    return city_clean


def parse_utm_content(utm_content: str) -> Optional[Dict[str, Any]]:
    """
    Парсит utm_content формата <city>_<dd>_<mm>.

    Args:
        utm_content: Значение utm_content

    Returns:
        dict: Словарь с распарсенными данными или None в случае ошибки
    """
    if not utm_content:
        return None

    match = UTM_CONTENT_PATTERN.match(utm_content.strip())
    if not match:
        logger.warning(f"Не удалось распарсить utm_content: {utm_content}")
        return None

    try:
        city = normalize_city(match.group("city"))
        day = int(match.group("dd"))
        month = int(match.group("mm"))

        # Валидация дня и месяца
        if day < 1 or day > 31:
            logger.warning(f"Некорректный день в utm_content: {utm_content}")
            return None

        if month < 1 or month > 12:
            logger.warning(f"Некорректный месяц в utm_content: {utm_content}")
            return None

        return {
            "utm_content": utm_content,
            "utm_city": city,
            "utm_day": day,
            "utm_month": month,
        }
    except (ValueError, AttributeError) as e:
        logger.warning(f"Ошибка при парсинге utm_content {utm_content}: {e}")
        return None


def extract_utm_params(params: Dict[str, str]) -> Dict[str, Any]:
    """
    Извлекает и нормализует UTM-параметры из словаря.

    Args:
        params: Словарь с параметрами

    Returns:
        dict: Словарь с UTM-параметрами
    """
    result = {}

    # Базовые UTM-параметры
    for utm_param in [
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
    ]:
        value = params.get(utm_param, "").strip()
        if value:
            result[utm_param] = value

    # Дополнительный парсинг utm_content
    if "utm_content" in result:
        parsed = parse_utm_content(result["utm_content"])
        if parsed:
            result.update(parsed)

    return result


def build_utm_content(city: str, day: int, month: int) -> str:
    """
    Собирает utm_content из компонентов.

    Args:
        city: Город
        day: День
        month: Месяц

    Returns:
        str: utm_content в формате <city>_<dd>_<mm>
    """
    city_norm = normalize_city(city)
    return f"{city_norm}_{day:02d}_{month:02d}"


def validate_utm_content(utm_content: str) -> bool:
    """
    Валидирует utm_content.

    Args:
        utm_content: Значение utm_content

    Returns:
        bool: True если валидный
    """
    return parse_utm_content(utm_content) is not None
