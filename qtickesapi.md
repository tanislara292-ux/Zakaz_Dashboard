
REST API
API принимает запросы на функции указанные в этой документации.

    Авторизация
    Список заказов
    Получение данных по заказу
    Удаление билетов
    Изменение билетов
    Возврат билетов
    Восстановление отменённого заказа
    Список покупателей
    Создание/обновление покупателя
    Список мероприятий
    Получение данных мероприятия
    Создание мероприятия
    Редактирование мероприятия
    Получение информации о местах
    Список оттенков для цен
    Список скидок
    Список промокодов
    Создание промокода
    Редактирование промокода
    Список штрихкодов билетов
    Информация о наличии сканирования
    Отметка о сканировании билета
    Пакетная отправка сканирований
    Обработка ошибок

Все запросы отправляются на сервер: https://qtickets.ru/api/rest/v1/{method}
Авторизация

Каждый запрос к API должен содержать заголовок Authorization: Bearer TOKEN. Токен API (TOKEN_API) можно сформировать в личном кабинете продавца билетов внизу раздела «Настройки – Основное».

Get Token
Заказы
Список заказов

GET https://qtickets.ru/api/rest/v1/orders

Accept: application/json

Cache-Control: no-cache

Content-Type: application/json

Authorization: Bearer TOKEN

 

{

  "where": [

    {

      "column": "payed",

      "value": 1

    }

  ],

  "orderBy": {

    "id": "asc"

  },

  "page": 1

}

Получение данных по заказу

GET https://qtickets.ru/api/rest/v1/orders/4360

Accept: application/json

Cache-Control: no-cache

Content-Type: application/json

Authorization: Bearer TOKEN

Пример ответа:

{

   "data":{

      "id":4360,

      "uniqid":"z7rkjcV2BV",

      "payed":true,

      "payed_at":"2019-07-30T12:50:52+03:00",

      "created_at":"2019-07-30T12:50:36+03:00",

      "updated_at":"2019-07-30T12:50:52+03:00",

      "deleted_at":null,

      "client_id":235,

      "client":{

         "id":235,

         "email":"username@gmail.com",

         "details":{

            "id":167,

            "name":"Иван",

            "middlename":null,

            "surname":"Петров",

            "phone":"+79100000000",

            "vk_id":"",

            "facebook_id":""

         }

      },

      "site_id":16,

      "site":{

         "id":16,

         "host":"qtickets.ru"

      },

      "payment_id":36,

      "payment_type_id":"bankcard",

      "payment_card_number":null,

      "payment_url":"https://qtickets.ru/pay/z7rkjcV2BV",

      "cancel_url":"https://qtickets.ru/cancel-order/z7rkjcV2BV/a800d6bfc609003205752c42844f541c",

      "basket_user_id":2111,

      "backend_user_id":null,

      "access_code_id":null,

      "discount_id":null,

      "promo_code_id":null,

      "reserved":0,

      "reserved_to":"2019-07-31T12:50:36+03:00",

      "reserve_extended":0,

      "event_id":33,

      "price":800,

      "original_price":800,

      "currency_id":"RUB",

      "utm":[

 

      ],

      "custom":{

         "var1":"val1",

         "var2":"val2"

      },

      "fields":{

         "organization_name":"ИП Петров"

      },

      "baskets":[

         {

            "id":63993,

            "barcode":"877076325904",

            "show_id":41,

            "seat_id":"CENTER_PARTERRE-21;12",

            "original_price":150,

            "discount_value":null,

            "price":150,

            "quantity":1,

            "client_email":"username@gmail.com",

            "client_phone":"+79100000000",

            "client_name":"Иван",

            "client_surname":"Петров",

            "client_middlename":"Петрович",

            "organization_name":null,

            "legal_name":null,

            "work_position":null,

            "inn":null,

            "kpp":null,

            "comment":null,

            "pdf_url": "https://qtickets.ru/ticket/pdf/FepllFLDqE/82db24e13831066dc792c265eec243fd",

            "passbook_url": "https://qtickets.ru/ticket/passbook/FepllFLDqE/82db24e13831066dc792c265eec243fd",

            "related_baskets":[

 

            ],

            "checked_at":null,

            "created_at":"2019-07-30T12:49:47+03:00",

            "updated_at":"2019-07-30T12:50:52+03:00",

            "deleted_at":null,

            "refunded_at":null,

            "refunded_amount":null,

            "refunded_deduction_amount":null

         },

         {

            "id":63994,

            "barcode":"877344688530",

            "show_id":41,

            "seat_id":"CENTER_PARTERRE-21;11",

            "original_price":150,

            "discount_value":null,

            "price":150,

            "quantity":1,

            "client_email":"username@gmail.com",

            "client_phone":"+79100000000",

            "client_name":"Иван",

            "client_surname":"Петров",

            "client_middlename":"Петрович",

            "organization_name":null,

            "legal_name":null,

            "work_position":null,

            "inn":null,

            "kpp":null,

            "comment":null,

            "related_baskets":[

 

            ],

            "checked_at":null,

            "created_at":"2019-07-30T12:49:50+03:00",

            "updated_at":"2019-07-30T12:50:52+03:00",

            "deleted_at":null,

            "refunded_at":null,

            "refunded_amount":null,

            "refunded_deduction_amount":null

         },

         {

            "id":63995,

            "barcode":"875606411179",

            "show_id":41,

            "seat_id":"CENTER_BALCONY-1;14",

            "original_price":500,

            "discount_value":null,

            "price":500,

            "quantity":1,

            "client_email":"username@gmail.com",

            "client_phone":"+79100000000",

            "client_name":"Иван",

            "client_surname":"Петров",

            "client_middlename":"Петрович",

            "organization_name":null,

            "legal_name":null,

            "work_position":null,

            "inn":null,

            "kpp":null,

            "comment":null,

            "related_baskets":[

 

            ],

            "checked_at":null,

            "created_at":"2019-07-30T12:49:54+03:00",

            "updated_at":"2019-07-30T12:50:52+03:00",

            "deleted_at":null,

            "refunded_at":null,

            "refunded_amount":null,

            "refunded_deduction_amount":null

         }

      ],

      "integrations":{

         "roistat":{

            "roistat_visit":"100018"

         }

      }

   }

}

где:
Поле 	Тип поля 	Описание
id 	int 	Идентификатор заказа
uniqid 	string 	Уникальный идентификатор заказа
payed 	boolean 	Флаг оплаты заказа
payed_at 	date 	Дата оплаты заказа
created_at 	date 	Дата создания заказа/билета
updated_at 	date 	Дата обновления заказа/билета
deleted_at 	date 	Дата отмены заказа/билета
client_id 	int 	Идентификатор покупателя
client 	array 	Данные о покупателе
payment_id 	int 	Идентификатор получателя платежей
payment_type_id 	string 	Идентификатор способа оплаты
payment_card_number 	string 	Номер банковской карты
payment_url 	string 	URL страницы для оплаты заказа
cancel_url 	string 	URL страницы для отмены заказа
basket_user_id 	int 	—
backend_user_id 	int 	Идентификатор пользователя, если заказ был оформлен через ЛК
access_code_id 	int 	Идентификатор кода доступа
discount_id 	int 	Идентификатор скидки
promo_code_id 	int 	Идентификатор промокода
reserved 	boolean 	Флаг бесконечного бронирования
reserved_to 	date 	Дата бронирования
reserve_extended 	boolean 	Флаг продления бронирования
event_id 	int 	Идентификатор мероприятия
price 	float 	Итоговая цена
original_price 	float 	Цена, без учета скидок
currency_id 	string 	Валюта
utm 	array 	UTM-метки
custom 	array 	Дополнительные данные, которые были указаны в data-custom аттрибуте кнопки покупки
fields 	array 	Дополнительные поля (Название компании, ИНН, КПП…)
baskets 	array 	Состав заказа (билеты)
• id 	int 	Номер билета
• barcode 	string 	Штрихкод билета
• seat_id 	string 	Уникальный идентификатор билета
• pdf_url 	string 	Ссылка на файл билета в формате PDF
• passbook_url 	string 	Ссылка на файл билета в формате Wallet iOS
• gpass_url 	string 	Ссылка на файл билета в формате Google Passes
• client_* 	string 	Информация о госте/владельце билета
• checked_at 	date 	Дата сканирования билета
• refunded_at 	date 	Дата возврата билета
• refunded_amount 	float 	Сумма возврата билета
• refunded_deduction_amount 	float 	Сумма удержания при возврате билета
integrations 	array 	Если подключена интеграция Roistat, то будет возвращен roistat_visit
Удаление билетов

В ключи baskets передаются идентификаторы билетов, которые необходимо удалить.

DELETE https://qtickets.ru/api/rest/v1/orders/4360/baskets

Accept: application/json

Cache-Control: no-cache

Content-Type: application/json

Authorization: Bearer TOKEN

 

{

  "delete": {

    "baskets": {

      "88344": [],

      "88402": []

    }

  }

}

Ответ будет содержать объект заказа, в котором будут помечены удаленные билеты в полях deleted_at

Для абонементов запрос принимает следующий вид:

{

  "delete": {

    "baskets": {

      "88374": [      

        88375,

        88376

      ]

    }

  }

}

Где, 88374 — это основной билет (который приходит пользователю на почту), а 88375 и 88376 связанные (related_baskets).
В этом примере удалятся билеты с идентификаторами 88375 и 88376. Основной билет 88374 останется не тронутым, только если у него еще остались активные связанные билеты. Если таковых не окажется, основной билет также автоматически удалится.
Изменение билетов

PUT https://qtickets.ru/api/rest/v1/baskets/140844

Accept: application/json

Cache-Control: no-cache

Content-Type: application/json

Authorization: Bearer TOKEN

 

{

  "data": {

    "client_email": "email@email.tld",

    "client_name": "Иван",

    "client_surname": "Иванов",

    "client_middlename": "Иванович",

    "multiprice_code": "child",

    "ticket_original_price": 300,

    "discount_value": 30

  }

}

В ответе возвратится массив объекта Basket. Поля ticket_original_price и discount_value можно изменять только для неоплаченного заказа.
Возврат билетов

В amount нужно передать сумму возврата. Если нужно выполнить возврат с суммой удержания, в таком случае необходимо передать в deduction_amount сумму удержания и сумма возврата высчитается автоматически исходя из стоимостей билетов.

DELETE https://qtickets.ru/api/rest/v1/orders/4360/baskets

Accept: application/json

Cache-Control: no-cache

Content-Type: application/json

Authorization: Bearer TOKEN

 

{

  "refund": {

    "amount": 1000, # или deduction_amount

    "baskets": {

      "88344": [],

      "88402": []

    }

  }

}

Ответ будет содержать объект заказа, в котором будут помечены возвращенные билеты в полях refunded_at, а также сумма возврата refunded_amount и сумма удержания refunded_deduction_amount.
Также список всех возвратов по заказу будет содержаться в поле refunds. В случае с абонементами, запрос будет похож на тот, что при удалении.
Восстановление отменённого заказа

Восстановить можно заказ, в котором нет возвратов

POST https://qtickets.ru/api/rest/v1/orders/11538/restore

Accept: application/json

Cache-Control: no-cache

Content-Type: application/json

Authorization: Bearer TOKEN

 

{}

В ответе возвратится массив объекта Order, с deleted_at = null, или ошибка, если заказ восстановить не удалось.
Покупатели
Список покупателей

Возвращает список покупателей

GET https://qtickets.ru/api/rest/v1/clients

Accept: application/json

Cache-Control: no-cache

Content-Type: application/json

Authorization: Bearer TOKEN

пример ответа:

{

  "data": [

    {

      "id": 337,

      "email": "ivanov@gmail.com",

      "details": {

        "id": 232,

        "name": "Иван",

        "middlename": "Иванов",

        "surname": "Иванович",

        "phone": null,

        "vk_id": "",

        "facebook_id": ""

      }

    },

    {

      "id": 10,

      "email": "sergeev@gmail.com",

      "details": {

        "id": 44,

        "name": "Сергей",

        "middlename": "Сергеев",

        "surname": "Сергеевич",

        "phone": "+79190001234",

        "vk_id": "",

        "facebook_id": ""

      }

    }

  ],

  "paging": {

    "perPage": 100,

    "currentPage": 1,

    "total": 2

  }

}

Создание/Обновление покупателя

POST https://qtickets.ru/api/rest/v1/clients

Accept: application/json

Cache-Control: no-cache

Content-Type: application/json

Authorization: Bearer TOKEN

 

{

  "data": {

    "email": "vasilev@gmail.com",

    "details": {

      "name": "Василий",

      "surname": "Васильев"

    }

  }

}

Мероприятия
Список мероприятий

GET https://qtickets.ru/api/rest/v1/events

Accept: application/json

Cache-Control: no-cache

Content-Type: application/json

Authorization: Bearer TOKEN

 

{

  "where": [

    {

      "column": "deleted_at",

      "operator": "null"

    }

  ],

  "orderBy": {

    "id": "desc"

  },

  "page": 1

}

Получение данных по id мероприятия

GET https://qtickets.ru/api/rest/v1/events/1240

Accept: application/json

Cache-Control: no-cache

Content-Type: application/json

Authorization: Bearer TOKEN

Создание мероприятия

POST https://qtickets.ru/api/rest/v1/events

Accept: application/json

Cache-Control: no-cache

Content-Type: application/json

Authorization: Bearer TOKEN

 

{

  "data": {

    "id": 12,

    "name": "Название мероприятия",

    "is_active": 1,

    "scheme_id": 18,

    "currency_id": "RUB",

    "place_name": "Олимпийский",

    "place_address": "Адрес места",

    "place_description": "",

    "site_url": "http://your-domain.ru/your-event",

    "city_id": 1,

    "description": "Начало координат, следовательно, охватывает аксиоматичный график функции многих переменных. Определитель системы линейных уравнений, в первом приближении, небезынтересно раскручивает определитель системы линейных уравнений, что известно даже школьникам. Огибающая семейства прямых, исключая очевидный случай, позитивно порождает анормальный интеграл от функции, имеющий конечный разрыв.",

    "external_id": null,

    "ticket_id": 17,

    "mail_template_id": 35,

    "payments": [

      38

    ],

    "poster": "data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBzdGFuZGFsb25lPSJubyI/PjwhRE9DVFlQRSBzdmcgUFVCTElDICItLy9XM0MvL0RURCBTVkcgMS4xLy9FTiIgImh0dHA6Ly93d3cudzMub3JnL0dyYXBoaWNzL1NWRy8xLjEvRFREL3N2ZzExLmR0ZCI+PHN2ZyB2ZXJzaW9uPSIxLjEiIGJhc2VQcm9maWxlPSJmdWxsIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPiAgIDxwb2x5Z29uIGlkPSJ0cmlhbmdsZSIgcG9pbnRzPSIwLDAgMCw1MCA1MCwwIiBmaWxsPSIjMDA5OTAwIiBzdHJva2U9IiMwMDQ0MDAiLz48L3N2Zz4=",

    "shows": [

      {

        "id": 21,

        "sale_start_date": null,

        "is_active": 1,

        "sale_finish_date": "2019-12-29T18:30:00+03:00",

        "open_date": "2019-12-29T18:30:00+03:00",

        "start_date": "2019-12-29T18:30:00+03:00",

        "finish_date": "2019-12-29T23:00:00+03:00",

        "scheme_properties": {

          "admin": {

            "zones": {

              "VIP": {

                "opened": "1"

              },

              "DANCE": {

                "opened": "1"

              },

              "SUPER_VIP": {

                "opened": "1"

              }

            }

          },

          "zones": {

            "VIP": {

              "disabled": "0",

              "shared": "",

              "price_id": "#0"

            },

            "DANCE": {

              "disabled": "0",

              "shared": "",

              "price_id": "#1"

            },

            "SUPER_VIP": {

              "disabled": "0",

              "shared": "",

              "price_id": "#2"

            }

          },

          "seats": {

            "VIP-1;1": {

              "hot": "1",

              "max_quantity": "100",

              "shared_max_quantity": ""

            },

            "DANCE-1;1": {

              "hot": "1",

              "max_quantity": "200",

              "shared_max_quantity": ""

            },

            "SUPER_VIP-1;1": {

              "hot": "1",

              "max_quantity": "300",

              "shared_max_quantity": ""

            }

          }

        },

        "prices": [

          {

            "default_price": 1000,

            "color_theme": 1

          },

          {

            "default_price": 2000,

            "color_theme": 2

          },

          {

            "default_price": 3000,

            "color_theme": 3

          }

        ]

      }

    ]

  }

}

Редактирование мероприятия

PUT https://qtickets.ru/api/rest/v1/events/1240

Accept: application/json

Cache-Control: no-cache

Content-Type: application/json

Authorization: Bearer TOKEN

 

{

  "data": {

    "id": 12,

    "name": "Название мероприятия",

    "is_active": 1,

    "scheme_id": 18,

    "currency_id": "RUB",

    "place_name": "Олимпийский",

    "place_address": "Адрес места",

    "place_description": "",

    "site_url": "http://your-domain.ru/your-event",

    "city_id": 1,

    "description": "Начало координат, следовательно, охватывает аксиоматичный график функции многих переменных. Определитель системы линейных уравнений, в первом приближении, небезынтересно раскручивает определитель системы линейных уравнений, что известно даже школьникам. Огибающая семейства прямых, исключая очевидный случай, позитивно порождает анормальный интеграл от функции, имеющий конечный разрыв.",

    "external_id": null,

    "ticket_id": 17,

    "mail_template_id": 35,

    "payments": [

      38

    ],

    "poster": "data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBzdGFuZGFsb25lPSJubyI/PjwhRE9DVFlQRSBzdmcgUFVCTElDICItLy9XM0MvL0RURCBTVkcgMS4xLy9FTiIgImh0dHA6Ly93d3cudzMub3JnL0dyYXBoaWNzL1NWRy8xLjEvRFREL3N2ZzExLmR0ZCI+PHN2ZyB2ZXJzaW9uPSIxLjEiIGJhc2VQcm9maWxlPSJmdWxsIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPiAgIDxwb2x5Z29uIGlkPSJ0cmlhbmdsZSIgcG9pbnRzPSIwLDAgMCw1MCA1MCwwIiBmaWxsPSIjMDA5OTAwIiBzdHJva2U9IiMwMDQ0MDAiLz48L3N2Zz4=",

    "shows": [

      {

        "id": 21,

        "sale_start_date": null,

        "is_active": 1,

        "sale_finish_date": "2019-12-29T18:30:00+03:00",

        "open_date": "2019-12-29T18:30:00+03:00",

        "start_date": "2019-12-29T18:30:00+03:00",

        "finish_date": "2019-12-29T23:00:00+03:00",

        "scheme_properties": {

          "admin": {

            "zones": {

              "VIP": {

                "opened": "1"

              },

              "DANCE": {

                "opened": "1"

              },

              "SUPER_VIP": {

                "opened": "1"

              }

            }

          },

          "zones": {

            "VIP": {

              "disabled": "0",

              "shared": "",

              "price_id": "1001"

            },

            "DANCE": {

              "disabled": "0",

              "shared": "",

              "price_id": "1002"

            },

            "SUPER_VIP": {

              "disabled": "0",

              "shared": "",

              "price_id": "#3"

            }

          },

          "seats": {

            "VIP-1;1": {

              "hot": "1",

              "max_quantity": "100",

              "shared_max_quantity": ""

            },

            "DANCE-1;1": {

              "hot": "1",

              "max_quantity": "200",

              "shared_max_quantity": ""

            },

            "SUPER_VIP-1;1": {

              "hot": "1",

              "max_quantity": "300",

              "shared_max_quantity": ""

            }

          }

        },

        "prices": [

          {

            "id": 1001,

            "default_price": 1000,

            "color_theme": 1

          },

          {

            "id": 1002,

            "default_price": 2000,

            "color_theme": 2

          },

          {

            "id": 1003,

            "default_price": 3000,

            "color_theme": 3

          },

          {

            "default_price": 6000,

            "color_theme": 4

          }

        ]

      }

    ]

  }

}

Получение информации о местах

GET https://qtickets.ru/api/rest/v1/shows/{show_id}/seats

Accept: application/json

Cache-Control: no-cache

Content-Type: application/json

Authorization: Bearer secret_token

 

{

  "select": [

    "id",

    "root_id",

    "name",

    "zone_id",

    "zone_root_id",

    "short_seat_id",

    "admission",

    "row",

    "place",

    "max_quantity",

    "free_quantity",

    "ordered_quantity",

    "available",

    "disabled",

    "ordered",

    "payed_quantity",

    "in_basket_quantity",

    "price",

    "currency_id",

    "related_seats",

    "spread.partner_id",

    "spread.users",

    "spread.client_groups",

    "spread.client_emails",

    "spread.agents",

    "color_theme_id",

    "coords"

  ],

  "where": [

    {

      "column": "available",

      "value": true

    },

    {

      "column": "price",

      "operator": ">=",

      "value": 2000

    },

    {

      "column": "root_zone_id",

      "operator": "in",

      "value": [

        "LEFT_PARTERRE",

        "RIGHT_PARTERRE"

      ]

    }

  ],

  "context": {

    "client_email": "username@gmail.com"

  },

  "flat": true

}

Пример ответа:

{

  "data": {

    "full_RIGHT_PARTERRE-1;6": {

      "id": "full_RIGHT_PARTERRE-1;6",

      "root_id": "RIGHT_PARTERRE-1;6",

      "name": "Правый боковой партер: Ряд 1, Место 6",

      "zone_id": "full_RIGHT_PARTERRE",

      "zone_root_id": "RIGHT_PARTERRE",

      "short_seat_id": "1;6",

      "admission": false,

      "row": "1",

      "place": "6",

      "max_quantity": 1,

      "free_quantity": 1,

      "ordered_quantity": 0,

      "available": true,

      "disabled": false,

      "ordered": false,

      "payed_quantity": 0,

      "in_basket_quantity": 0,

      "price": 22,

      "currency_id": "RUB",

      "related_seats": [],

      "spread": {

        "partner_id": null,

        "users": [

          1

        ],

        "client_groups": [],

        "client_emails": [

          "username@gmail.com"

        ],

        "agents": false

      },

      "color_theme_id": 5,

      "coords": [

        325,

        347

      ]

    },

    "full_LEFT_PARTERRE-1;22": {

      "id": "full_LEFT_PARTERRE-1;22",

      "root_id": "LEFT_PARTERRE-1;22",

      "name": "Левый боковой партер: Ряд 1, Место 22",

      "zone_id": "full_RIGHT_PARTERRE",

      "zone_root_id": "RIGHT_PARTERRE",

      "short_seat_id": "1;22",

      "admission": false,

      "row": "1",

      "place": "22",

      "max_quantity": 1,

      "free_quantity": 1,

      "ordered_quantity": 0,

      "available": true,

      "disabled": false,

      "ordered": false,

      "payed_quantity": 0,

      "in_basket_quantity": 0,

      "price": 300,

      "currency_id": "RUB",

      "related_seats": [],

      "spread": {

        "partner_id": null,

        "users": [

          2

        ],

        "client_groups": [],

        "client_emails": [

          "username@gmail.com"

        ],

        "agents": false

      },

      "color_theme_id": 5,

      "coords": [

        686,

        347

      ]

    }

  }

}

В select можно передавать такие значения:
Поле 	Тип поля 	Описание
id 	string 	Идентификатор билета
root_id 	string 	Идентификатор родительского билета
name 	string 	Читаемое название билета (Сектор, ряд, место)
zone_id 	string 	Идентификатор сектора
zone_root_id 	string 	Идентификатор родительского сектора
short_seat_id 	string 	Краткий идентификатор места, содержит "ряд;место"
admission 	bool 	Входной без места (да/нет)
row 	string 	Ряд места
place 	string 	Номер места
max_quantity 	int 	Максимальное количество мест
free_quantity 	int 	Свободное количество мест
ordered_quantity 	int 	Количество мест в заказе
available 	bool 	Признак доступности места для бронирования
disabled 	bool 	Выключено (да/нет)
ordered 	bool 	В заказе (да/нет)
payed_quantity 	int 	Оплаченное количество мест
in_basket_quantity 	int 	Количество мест в корзине
price 	float 	Номинальная цена
currency_id 	string 	Валюта
related_seats 	array 	Связанные места
multiprice_name 	?string 	Название тарифа
multiprice_code 	?string 	Символьный код тарифа
spread.partner_id 	?int 	Персональная квота для партнёра
spread.users 	?array 	Персональная квота для пользователя ЛК Qtickets
spread.client_groups 	?array 	Персональная квота по группе покупателя
spread.client_emails 	?array 	Персональная квота по email покупателя
spread.agents 	bool 	Персональная квота по агенту да/нет
color_theme_id 	?int 	Идентификатор оттенка цены места
coords 	array 	Координаты места на схеме зала

Массив where в запросе используется для фильтрации. Можно фильтровать по любому полю (column) из таблицы выше. Доступные значения поля operator: =, !=, <, >, <=, >=, in, not in, in array, not in array. Поле operator необязательное, значение по-умолчанию =

Массив context используется для получения мест соответствующих настройкам персональной квоты, допустимые значения:
Поле 	Тип 	Описание
client_email 	string 	Email покупателя
user_id 	int 	Идентификатор пользователя в системе Qtickets
partner_id 	int 	Идентификатор партнёра в системе Qtickets

Параметр flat (bool) определяет, будет ли ответ в виде "плоского" массива мест seats или в виде иерархии категорий и мест в них zones/seats
Список оттенков для цен

GET https://qtickets.ru/api/rest/v1/color-themes

Accept: application/json

Cache-Control: no-cache

Content-Type: application/json

Authorization: Bearer TOKEN

ответ:

{

  "data": [

    {

      "id": 1,

      "color": "#d80000"

    },

    {

      "id": 2,

      "color": "#d8007f"

    },

    {

      "id": 3,

      "color": "#b700d8"

    },

    {

      "id": 4,

      "color": "#8400d8"

    },

    {

      "id": 5,

      "color": "#004cd8"

    },

    {

      "id": 6,

      "color": "#00add8"

    },

    {

      "id": 7,

      "color": "#00d8d0"

    },

    {

      "id": 8,

      "color": "#00d833"

    },

    {

      "id": 15,

      "color": "#009f4b"

    },

    {

      "id": 9,

      "color": "#a8d800"

    },

    {

      "id": 10,

      "color": "#d5d800"

    },

    {

      "id": 11,

      "color": "#d89e00"

    },

    {

      "id": 12,

      "color": "#e27500"

    },

    {

      "id": 13,

      "color": "#606060"

    },

    {

      "id": 14,

      "color": "#a82d2d"

    }

  ]

}

Промо
Список скидок

GET https://qtickets.ru/api/rest/v1/discounts

Accept: application/json

Cache-Control: no-cache

Content-Type: application/json

Authorization: Bearer TOKEN

 

{

  "where": [

    {

      "column": "deleted_at",

      "operator": "null"

    }

  ],

  "orderBy": {

    "id": "desc"

  },

  "page": 1

}

Список промокодов

GET https://qtickets.ru/api/rest/v1/promo-codes

Accept: application/json

Cache-Control: no-cache

Content-Type: application/json

Authorization: Bearer TOKEN

 

{

  "where": [

    {

      "column": "discount_id",

      "value": 45

    },

    {

      "column": "deleted_at",

      "operator": "null"

    }

  ],

  "orderBy": {

    "id": "desc"

  },

  "page": 1

}

Создание промокода

POST https://qtickets.ru/api/rest/v1/promo-codes

Accept: application/json

Cache-Control: no-cache

Content-Type: application/json

Authorization: Bearer TOKEN

 

{

  "data": {

    "is_active": 1,

    "discount_id": 45,

    "code": "308076-15950-3",

    "max_uses_count": 5,

    "active_from": null,

    "active_to": null

  }

}

Редактирование промокода

PUT https://qtickets.ru/api/rest/v1/promo-codes/13513

Accept: application/json

Cache-Control: no-cache

Content-Type: application/json

Authorization: Bearer TOKEN

 

{

  "data": {

    "is_active": 1,

    "code": "308076-15950-3",

    "max_uses_count": 3,

    "active_from": null,

    "active_to": null

  }

}

Штрихкоды
Список штрихкодов

Возвращает все актуальные штрихкоды на текущий момент. В запросе указывается {show_id} — это идентификатор даты мероприятия, получить можно в мероприятии в секции shows

GET https://qtickets.ru/api/rest/v1/shows/{show_id}/barcodes

Accept: application/json

Cache-Control: no-cache

Content-Type: application/json

Authorization: Bearer TOKEN

 

{

  "select": [

    "barcode",

    "price",

    "seat_name"

  ]

}

пример ответа:

[

  {

    "barcode": "871495495233",

    "price": 500,

    "seat_name": "Танцевальный партер"

  },

  {

    "barcode": "874432174155",

    "price": 500,

    "seat_name": "Танцевальный партер"

  },

  {

    "barcode": "875196723453",

    "price": 1000,

    "seat_name": "VIP: ряд 1, место 1"

  },

  {

    "barcode": "872900619969",

    "price": 1000,

    "seat_name": "VIP: ряд 1, место 2"

  }

]

В select можно передавать такие значения:
Поле 	Тип поля 	Описание
barcode 	string 	Штрихкод
admission 	bool 	Входной без места (да/нет)
price 	float 	Цена
seat_name 	string 	Название места
zone_name 	string 	Название категории
row 	string 	Ряд места
place 	string 	Номер места
client_name 	?string 	Имя покупателя
client_surname 	?string 	Фамилия покупателя
client_middlename 	?string 	Отчество покупателя
Получение информации о сканировании по штрихкоду

GET https://qtickets.ru/api/rest/v1/shows/{show_id}/barcode/875196723453

Accept: application/json

Cache-Control: no-cache

Content-Type: application/json

Authorization: Bearer secret_token

Пример ответа:

{

  "barcode": "875196723453",

  "checked_at": "2020-03-02T17:08:35+03:00"

}

Отправка информации о сканировании билета

POST https://qtickets.ru/api/rest/v1/shows/{show_id}/barcode/875196723453

Accept: application/json

Cache-Control: no-cache

Content-Type: application/json

Authorization: Bearer secret_token

 

{

  "checked_at": "2020-03-02T17:08:35+03:00"

}

Пример ответа:

{

  "success": true,

  "barcode": "875196723453",

  "checked_at": "2020-03-02T17:08:35+03:00"

}

Пакетная отправка информации о сканировании билетов

POST https://qtickets.ru/api/rest/v1/shows/{show_id}/barcodes

Accept: application/json

Cache-Control: no-cache

Content-Type: application/json

Authorization: Bearer secret_token

 

[

  {

    "barcode": "875196723453",

    "checked_at": "2020-03-02T18:08:35+03:00"

  },

  {

    "barcode": "875136523412",

    "checked_at": "2020-03-02T18:08:39+03:00"

  },

  {

    "barcode": "875136213454",

    "checked_at": "2020-03-02T18:08:40+03:00"

  },

]

Обработка ошибок

Если сервер не может обработать запрос, то вернется ответ с HTTP статусом не равным 200 (например 403 или 503)
Пример:

{

  "error": "Some error",

  "status": 403

}

Webhooks »
Статьи по теме

    Webhooks
        0
    Partners API
        0

Популярное

    Как сделать возврат
    Как освободить место в почтовом ящике
    Скидки и промокоды
    Как управлять мероприятиями
    Схемы продаж и каталог схем

Не нашли что искали?
Если вы продавец билетов, то обратитесь на info@qtickets.ru

Если вы покупатель билетов, то обратитесь на support@qtickets.ru
Регистрация в Qtickets
Зарегистрируйтесь в сервисе сейчас, чтобы запустить продажи ваших билетов уже сегодня!




Webhooks
Вебхуки позволяют мгновенно оповестить внешний сервис об изменениях в заказах.

Настраивается в разделе настроек https://qtickets.ru/backend/idesigning/qtickets/organizers/myaccount?tab=webhooks

При добавлении вебхуков указывается:

    Тип события (Новый заказ, Заказ изменен, Заказ оплачен, Заказ отменен, Заказ возвращен, Сканирование)
    URL (куда будет отправлен запрос)
    Секрет (если необходимо проверять цифровую подпись)

Данные передаются в формате JSON (Content-type: application/json). В заголовках передаются:

    X-Signature — сигнатура, для проверки цифровой подписи
    X-Event-Type — тип события (created, updated, payed, deleted, refunded, checked)
    X-Model-Name — всегда Order
    User-Agent — Qtickets-Webhooks/2.0

Пример данных:

{

   "id":4360,

   "uniqid":"z7rkjcV2BV",

   "payed":true,

   "payed_at":"2019-07-30T12:50:52+03:00",

   "created_at":"2019-07-30T12:50:36+03:00",

   "updated_at":"2019-07-30T12:50:52+03:00",

   "deleted_at":null,

   "client_id":235,

   "client":{

      "id":235,

      "email":"username@gmail.com",

      "details":{

         "id":167,

         "name":"Иван",

         "middlename":null,

         "surname":"Петров",

         "phone":"+79100000000",

         "vk_id":"",

         "facebook_id":"",

         "telegram_user": {

           "id": 12345678,

           "first_name": "Ivan",

           "last_name": "Petrov",

           "username": "username"

         }

      }

   },

   "site_id":16,

   "site":{

      "id":16,

      "host":"qtickets.ru"

   },

   "payment_id":36,

   "payment_type_id":"bankcard",

   "payment_url":"https://qtickets.test/pay/z7rkjcV2BV",

   "payment_card_number":null,

   "cancel_url":"https://qtickets.test/cancel-order/z7rkjcV2BV/a800d6bfc609003205752c42844f541c",

   "basket_user_id":2111,

   "backend_user_id":null,

   "access_code_id":null,

   "discount_id":null,

   "promo_code_id":null,

   "reserved":0,

   "reserved_to":"2019-07-31T12:50:36+03:00",

   "reserve_extended":0,

   "event_id":33,

   "price":800,

   "original_price":800,

   "currency_id":"RUB",

   "utm":[

 

   ],

   "custom":{

      "var1":"val1",

      "var2":"val2"

   },

   "fields":{

      "organization_name":"ИП Петров"

   },

   "baskets":[

      {

         "id":63993,

         "barcode":"877076325904",

         "show_id":41,

         "seat_id":"CENTER_PARTERRE-21;12",

         "original_price":150,

         "discount_value":null,

         "price":150,

         "quantity":1,

         "client_email":"username@gmail.com",

         "client_phone":"+79100000000",

         "client_name":"Иван",

         "client_surname":"Петров",

         "organization_name":null,

         "legal_name":null,

         "work_position":null,

         "inn":null,

         "kpp":null,

         "comment":null,

         "related_baskets":[

 

         ],

         "created_at":"2019-07-30T12:49:47+03:00",

         "updated_at":"2019-07-30T12:50:52+03:00",

         "deleted_at":null

      },

      {

         "id":63994,

         "barcode":"877344688530",

         "show_id":41,

         "seat_id":"CENTER_PARTERRE-21;11",

         "original_price":150,

         "discount_value":null,

         "price":150,

         "quantity":1,

         "client_email":"username@gmail.com",

         "client_phone":"+79100000000",

         "client_name":"Иван",

         "client_surname":"Петров",

         "organization_name":null,

         "legal_name":null,

         "work_position":null,

         "inn":null,

         "kpp":null,

         "comment":null,

         "related_baskets":[

 

         ],

         "created_at":"2019-07-30T12:49:50+03:00",

         "updated_at":"2019-07-30T12:50:52+03:00",

         "deleted_at":null

      },

      {

         "id":63995,

         "barcode":"875606411179",

         "show_id":41,

         "seat_id":"CENTER_BALCONY-1;14",

         "original_price":500,

         "discount_value":null,

         "price":500,

         "quantity":1,

         "client_email":"username@gmail.com",

         "client_phone":"+79100000000",

         "client_name":"Иван",

         "client_surname":"Петров",

         "organization_name":null,

         "legal_name":null,

         "work_position":null,

         "inn":null,

         "kpp":null,

         "comment":null,

         "related_baskets":[

 

         ],

         "created_at":"2019-07-30T12:49:54+03:00",

         "updated_at":"2019-07-30T12:50:52+03:00",

         "deleted_at":null

      }

   ],

   "primary_orders": [

     {

       "id": 9234,

       "uniqid": "r8O2iN6CAH",

       "payed": true,

       "payed_at": "2024-05-01T10:51:38+03:00",

       "price": 1000,

       "original_price": 1000,

       "currency_id": "RUB",

       "created_at": "2024-05-01T10:50:54+03:00",

       "updated_at": "2024-05-01T10:51:38+03:00",

       "deleted_at": null

     }

   ],

   "secondary_orders": [],

   "integrations":{

      "roistat":{

         "roistat_visit":"100018"

      }

   }

}

где:
поле 	тип поля 	Описание
id 	int 	Идентификатор заказа
uniqid 	string 	Уникальный идентификатор заказа
payed 	boolean 	Флаг оплаты заказа
payed_at 	date 	Дата оплаты заказа
created_at 	date 	Дата создания заказа
updated_at 	date 	Дата обновления заказа
client_id 	int 	Идентификатор покупателя
client 	array 	Данные о покупателе
payment_id 	int 	Идентификатор получателя платежей
payment_type_id 	string 	Идентификатор способа оплаты
payment_card_number 	string 	Номер банковской карты
payment_url 	string 	URL страницы для оплаты заказа
cancel_url 	string 	URL страницы для отмены заказа
basket_user_id 	int 	—
backend_user_id 	int 	Идентификатор пользователя, если заказ был оформлен через ЛК
access_code_id 	int 	Идентификатор кода доступа
discount_id 	int 	Идентификатор скидки
promo_code_id 	int 	Идентификатор промокода
reserved 	boolean 	Флаг бесконечного бронирования
reserved_to 	date 	Дата бронирования
reserve_extended 	boolean 	Флаг продления бронирования
event_id 	int 	Идентификатор мероприятия
price 	float 	Итоговая цена
original_price 	float 	Цена, без учета скидок
currency_id 	string 	Валюта
utm 	array 	UTM-метки
custom 	array 	Дополнительные данные, которые были указаны в data-custom аттрибуте кнопки покупки
fields 	array 	Дополнительные поля (Название компании, ИНН, КПП…)
baskets 	array 	Состав заказа (билеты)
integrations 	array 	Если подключена интеграция Roistat, то будет возвращен roistat_visit
refunded_baskets 	array 	Возвращенные билеты (для типа "Заказ возвращен")
checked_basket 	array 	Проверенный билет (для типа "Сканирование на вход")
checked_service 	array 	Проверенная услуга (для типа "Сканирование на вход")
unchecked_basket 	array 	Проверенный билет (для типа "Сканирование на выход")
unchecked_service 	array 	Проверенная услуга (для типа "Сканирование на выход")
primary_orders 	array 	Заказ, который заменили в процессе замены
secondary_orders 	array 	Заказ, на который заменили в процессе замены
Доставка данных

Данные считаются успешно доставленными, если сервер вернул ответ с HTTP статусом 200. Если этого не произошло, то всего будет 10 попыток отправки, где каждая попытка будет отложена на n^3 сек, где n — номер попытки. Т.е. вебхук будет пытаться отправиться в течении 50 минут.
Проверка цифровой подписи

Служит для проверки данных, чтобы исключить посторонние запросы (не от сервиса Qtickets). Для этого укажите в настройках вебхука ваш секрет и проверяйте данные на вашей стороне.
Пример кода на PHP

// Читаем содержимое POST-запроса

$body = file_get_contents("php://input");

$data = json_decode($body, true); // Массив с данными

$event = $_SERVER['HTTP_X_EVENT_TYPE']; // Тип события

 

print_r($data);

Пример кода на PHP (с проверкой цифровой подписи)

// Читаем содержимое POST-запроса

$body = file_get_contents("php://input");

 

// Генерируем код, которым должен быть подписан webhook

$sha1 = hash_hmac('sha1', $body, 'SuperSecret');

 

// Сравниваем полученный код подписи, с тем что пришёл с хуком

if ($sha1 == $_SERVER['HTTP_X_SIGNATURE']) {

    // webhook пришёл от сервиса Qtickets

    $data = json_decode($body, true); // Массив с данными

    $event = $_SERVER['HTTP_X_EVENT_TYPE']; // Тип события

 

    print_r($data);

}




Partners API
Данное API предназначено для партнёров, которые работают как дистрибьюторы и сторонние продавцы билетов в отрыве от продаж пользователя Qtickets.

API принимает GET/POST запросы на функции указанные в этой документации. Методы не различаются: как GET, так и POST вернут идентичный ответ.

Все запросы отправляются на сервер: https://qtickets.ru
Авторизация

Каждый запрос к API должен содержать заголовок
Authorization: Bearer YOUR_API_KEY. API ключ выдается техподдержкой.

В случае, если ключ неверный или отсутствует заголовок, сервер вернет JSON с кодом ошибки:

{

   "status": "error",

   "code": "WRONG_AUTHORIZATION",

   "message": "Wrong authorization"

}

Events/Lists — листинг мероприятий

Метод api/partners/v1/events/lists возвращает список предстоящих мероприятий, в которых включена возможность продажи билетов через партнеров. Пример ответа:

{

    "status": "success",

    "result":[

        {

            "event_id": 12,

            "show_id": 20,

            "event_name": "Название мероприятия 1",

            "start_date": "2018-05-04T06:22:00+10:00",

            "finish_date": "2018-05-04T10:22:00+10:00",

            "scheme":{

                "id": 48,

                "venue_id": 120,

                "place_name": "Кремлевский дворец",

                "place_address": "ул. Воздвиженка, 1",

                "place_description": "м. Библиотека им. Ленина, Александровский сад, Боровицкая"

            },

            "city":{

                "id": 2,

                "name": "Москва",

                "timezone": "Europe/Moscow",

                "coords":[

                    55.7558,

                    37.6176

                ]

            },

            "event_type": {

                "id": 2,

                "name": "Концерт"

            },

            "age": "12+",

            "fanid_required": false,

            "has_document_verification": false,

            "integrations": [

              {

                "source_name": "pro-culture",

                "source_id": 100

              }

            ],

            "last_update_hash": "63e9effbdeca7a633d73d118a65dc78478110a39"

        },

        {

            "event_id": 12,

            "show_id": 21,

            "event_name": "Название мероприятия 1",

            "start_date": "2019-01-03T17:00:00+10:00",

            "finish_date": "2019-01-03T20:00:00+10:00",

            "scheme":{

                "id": 48,

                "venue_id": 120,

                "place_name": "Кремлевский дворец",

                "place_address": "ул. Воздвиженка, 1",

                "place_description": "м. Библиотека им. Ленина, Александровский сад, Боровицкая"

            },

            "city":{

                "id": 2,

                "name": "Москва",

                "timezone": "Europe/Moscow",

                "coords":[

                    55.7558,

                    37.6176

                ]

            },

            "event_type": {

                "id": 2,

                "name": "Концерт"

            },          

            "age": "16+",

            "fanid_required": false,

            "has_document_verification": false,   

            "integrations": [],

            "last_update_hash": "becffa60e0c682208f537fe71818aab62ba2b5a4"

        },

        {

            "event_id": 33,

            "show_id": 41,

            "event_name": "Название мероприятия 2",

            "start_date": "2018-12-31T18:00:00+07:00",

            "finish_date": "2018-12-31T20:00:00+07:00",          

            "scheme":{

                "id": 48,

                "venue_id": 120,

                "place_name": "Кремлевский дворец",

                "place_address": "ул. Воздвиженка, 1",

                "place_description": "м. Библиотека им. Ленина, Александровский сад, Боровицкая"

            },

            "city":{

                "id": 2,

                "name": "Москва",

                "timezone": "Europe/Moscow",

                "coords":[

                    55.7558,

                    37.6176

                ]

            },

            "event_type": {

              "id": 7,

              "name": "Конференция"

            },          

            "age": "6+",

            "fanid_required": false,

            "has_document_verification": true,      

            "integrations": [],

            "last_update_hash": "9e02e444620a3621f08c85732f1634f48fe35571"

        }

    ]

}

Где:

    event_id — Идентификатор мероприятия
    show_id— Идентификатор даты мероприятия
    event_name — Название мероприятия
    scheme — Массив информации о месте проведения и доступных билетах (scheme.zones), где venue_id – идентификатор площадки, place_name – название места проведения, place_address – адрес места проведения, place_description – уточнения для более точного ориентирования.
    city — Город
    start_date — Дата начала мероприятия
    finish_date — Дата окончания мероприятия
    fanid_required — Признак работы мероприятия по паспорту болельщика (Fan ID), если true, то при добавлении билетов в методе Add обязательно нужно указывать параметр fanid
    event_type — Тип мероприятия
    age — Возрастное ограничение
    has_document_verification — Признак требования документа удостоверяющего личность у посетителя мероприятия в соответствии с правилами проекта города Москва
    integrations — Может содержать идентификаторы сущностей в сторонних системах. В частности, {"source_name": "pro-culture", "source_id": 100} информирует о возможности покупки билетов по Пушкинской карте, где 100 — идентификатор мероприятия в системе pro.culture.ru
    last_update_hash — Содержит хэш, который меняется при некоторых изменениях в мероприятии. Например, поменялись квоты или места для продажи. Этот параметр будет возвращаться во всех последующих методах, и если он изменится, то это сигнал для пересинхронизации.

Все последующие запросы к API должны содержать event_id. В случае, если мероприятие содержит более 1-й даты, то также нужно указывать и show_id.
Events/Seatmap — карта мест зала

Метод api/partners/v1/events/seatmap/{event_id}/{show_id?}

ответ:

{

  ....

  "seatmap": {

    "width": 1361,

    "height": 1342,

    "zones": {

      "RIGHT_PARTERRE": {

        "name": "Правый боковой партер",

        "description": null,

        "width": 950.10009765625,

        "height": 155.70689392089844,

        "offset": [

          163.10000610351562,

          233.19309997558594

        ],

        "seats": {

          "RIGHT_PARTERRE-1;1": {"coords": [225, 347], "row": 1, "place": 1},

          "RIGHT_PARTERRE-1;2": {"coords": [245, 347], "row": 1, "place": 2}

        }

      },

      "CENTER_PARTERRE": {

        "name": "Партер",

        "description": null,

        "width": 950.5,

        "height": 585.7999877929688,

        "offset": [

          163.10000610351562,

          392.20001220703125

        ],

        "seats": {

          "CENTER_PARTERRE-1;1": {"coords": [299, 444], "row": 1, "place": 1},

          "CENTER_PARTERRE-1;2": {"coords": [299, 464], "row": 1, "place": 2}

        }

      }

    }

  }

}

где:

    ключи в seatmap.zones.[*] — это идентификаторы категорий zone_id
    ключи в seatmap.zones.*.seats.[*] — это идентификаторы мест seat_id
    seatmap.width — Ширина схемы зала (float)
    seatmap.height — Высота схемы зала (float)
    seatmap.zones[*].width — Ширина сектора для категории билета (float)
    seatmap.zones[*].height — Высота сектора для категории билета (float)
    seatmap.zones[*].offset — Смещение сектора категории билета (array)

В zones содержится список категорий, каждая категория имеет свой уникальный идентификатор zone_id (ключ массива), название name и места seats.

Место имеет свой уникальный идентификатор seat_id (ключ массива), boolean флаг доступности для продажи available, а также ряд row и номер места place. Координаты места указаны в свойстве coords

Для мест, где указано admission: true продаются входные билеты, в параметре free_quantity оставшееся кол-во для продажи.
Events/Offers — статус мест в мероприятии, доступных партнёру

Метод api/partners/v1/events/offers/{event_id}/{show_id?}

ответ:

{

  ...

  "offers": {

    "full": {

      "name": "Полный",

      "seats": {

        "RIGHT_PARTERRE-1;1": {"available": true, "price": 600},

        "RIGHT_PARTERRE-1;2": {"available": false, "price": 600},

        "RIGHT_PARTERRE-1;3": {"available": false, "price": 600}

      }

    },

    "preferential": {

      "name": "Льготный",

      "seats": {

        "RIGHT_PARTERRE-1;1": {"available": true, "price": 300}

      }

    }

  }

}

где:

    ключи в offers.[*] — идентификатор тарифа offer_id, может быть пустым ""
    ключи в offers.*.seats.[*] — это идентификаторы мест seat_id

В методе бронирования билета, следует передавать seat_id и offer_id из этого метода.
Tickets/Add — бронирование билета для места

Метод api/partners/v1/tickets/add/{event_id}/{show_id?}

В GET или POST параметрах нужно передать:

    seat_id идентификатор места
    offer_id идентификатор тарифа, строка или NULL
    paid признак оплаты билета 0 или 1. Можно также вместо этого использовать paid_at с датой оплаты
    payment_type_id если оплата по Пушкинской карте, то в это поле необходимо передать pushka_card, а в остальных случаях null
    reserved_to если билет еще не оплачен, нужно передавать дату, до которой билет бронируется, например 2018-05-24T17:00:00+10:00
    external_id необязательный параметр, может содержать произвольное уникальное значение, по которому в дальнейшем будет вестись работа по этому конкретному билету, например ticket12345
    external_order_id идентификатор заказа из вашей системы. Если параметр неизвестен на этапе бронирования билетов, укажите его позднее в методе update
    user_session любая строка, до 40 символов, идентифицирующая пользователя. Примеры: id пользователя из вашей системы или md5(session_id())
    price необязательный параметр, стоимость билета
    client_email необязательный параметр, email покупателя
    client_phone необязательный параметр, телефон покупателя
    client_name необязательный параметр, имя покупателя
    client_surname необязательный параметр, фамилия покупателя
    client_middlename необязательный параметр, отчество покупателя
    fanid номер карты болельщика (Fan ID)
    visitor_user_id Для проекта ЕБС. Идентификатор посетителя в вашей учётной системе.

Пример ответа:

{

     "event_id": 12,

     "show_id": 21,

     "event_name": "Название мероприятия 1",

     "start_date": "2019-01-03T17:00:00+10:00",

     "finish_date": "2019-01-03T20:00:00+10:00",

     "scheme":{

         "id": 48,

         "venue_id": 120,

         "place_name": "Кремлевский дворец",

         "place_address": "ул. Воздвиженка, 1",

         "place_description": "м. Библиотека им. Ленина, Александровский сад, Боровицкая",

         "width": 1000,

         "height": 800

     },

     "city":{

         "id": 2,

         "name": "Москва",

         "timezone": "Europe/Moscow",

         "coords":[

             55.7558,

             37.6176

         ]

     },

     "last_update_hash": "2f030832e2eb309b811dc9675df611273aefe618",

     "status": "success",

     "result": {

         "id": "27061",

         "paid": 0,

         "paid_at": null,

         "seat_id": "PARTERRE-1;25",

         "offer_id": "full",

         "admission": false,

         "payment_type_id": null,

         "reserved_to": "2018-05-24T17:00:00+10:00",

         "external_id": "ticket12345",

         "barcode": null,

         "price": null,

         "client_email": null,

         "client_phone": null,

         "client_name": null,

         "client_surname": null,

         "client_middlename": null,

         "fanid_card": null,

         "visitor_user_id": "ydx-PQaDzaqqiGTIklE3tTgTEQ"

     }

}

где в result содержится:

    id — идентификатор билета, в дальнейшем потребуется для работы в других методах
    external_id — ваш внешний идентификатор, если был передан в запросе
    barcode — будет содержать значение для ШК кода, в случае, если билет оплачен paid: 1
    fanid_card — будет заполнен, если был привязан номер карты болельщика (Fan ID), массив вида {"id": 123, "value": "1234567890"}

В случае, если закончились билеты, в ответе вернется ошибка:

{

"status": "error",

"code": "SEAT_NOT_AVAILABLE",

"message": "Seat "6-1;52" is not available"

}

Tickets/Update — обновление билета

Метод api/partners/v1/tickets/update/{event_id}/{show_id?} служит для обновления билета, например продлить бронь reserved_to или сделать билет оплаченным paid: 1
В запросе нужно передать:

    id идентификатор билета или external_id
    paid 0 или 1
    reserved_to в случае, если paid: 0
    external_order_id идентификатор заказа из вашей системы
    price необязательный параметр, стоимость билета
    client_email необязательный параметр, email покупателя
    client_phone необязательный параметр, телефон покупателя
    client_name необязательный параметр, имя покупателя
    client_surname необязательный параметр, фамилия покупателя
    client_middlename необязательный параметр, отчество покупателя

Tickets/Remove — удаление билета

Метод api/partners/v1/tickets/remove/{event_id}/{show_id?} служит для отмены брони. Например, пользователь сначала добавил билет в корзину, а потому удалил его сразу или закрыл вкладку в браузере.
В запросе нужно передать:

    id идентификатор билета или external_id
    Ответ:

{

"event_id": 12,

"show_id": 21,

"event_name": "Название мероприятия 1",

"scheme":{

"id": 48,

"venue_id": 120,

"place_name": "Кремлевский дворец",

"place_address": "ул. Воздвиженка, 1",

"place_description": "м. Библиотека им. Ленина, Александровский сад, Боровицкая",

"width": 1000,

"height": 800

},

"city":{

"id": 2,

"name": "Москва",

"timezone": "Europe/Moscow",

"coords":[

  55.7558,

  37.6176

]

},

"start_date": "2019-01-03T17:00:00+10:00",

"finish_date": "2019-01-03T20:00:00+10:00",  

"last_update_hash": "2f030832e2eb309b811dc9675df611273aefe618",

"status": "success",

"result": true

    }

Tickets/Check — статус места

Метод api/partners/v1/tickets/check/{event_id}/{show_id?}

В GET или POST параметрах нужно передать:

    seat_id идентификатор места
    offer_id идентификатор тарифа, значение может быть пустым или NULL

Пример ответа:

{

  ...

  "result": {

    "seat_id": "CENTER_PARTERRE-20;5",

    "offer_id": "full",

    "available": true,

    "coords": [

      967,

      525

    ],

    "row": 20,

    "place": 5,

    "price": 300,

    "currency_id": "RUB"

  }

}

BATCH режим

Позволяет одним запросом забронировать/обновить/удалить несколько билетов.
Пример бронирования нескольких билетов:

POST https://qtickets.ru/api/partners/v1/tickets/add/12/4076

Accept: application/json

Cache-Control: no-cache

Content-Type: application/json

Authorization: Bearer YOUR_TOKEN

 

{

  "batch": [

    {

      "user_session": "ASeUqnvcgkJy",

      "seat_id": "2-2;37",

      "offer_id": null,

      "paid_at": null,

      "reserved_to": "2021-09-12T17:00:00+10:00",

      "price": 800,

      "client_email": "mail@email.com",

      "client_phone": "+79101234567",

      "client_name": "Имя",

      "client_surname": "Фамилия",

      "client_middlename": "Отчество"

    },

    {

      "user_session": "ASeUqnvcgkJy",

      "seat_id": "2-2;38",

      "offer_id": null,

      "paid_at": null,

      "reserved_to": "2021-09-12T17:00:00+10:00",

      "price": 1000,

      "client_email": "mail@email.com",

      "client_phone": "+79101234567",

      "client_name": "Имя",

      "client_surname": "Фамилия",

      "client_middlename": "Отчество"

    },

  ]

}

ответ:

....

"result": [

    {

      "id": 120299,

      "paid": 0,

      "paid_at": null,

      "seat_id": "PARTERRE-1;25",

      "offer_id": "full",

      "admission": false,

      "reserved_to": "2021-09-12T10:00:00+03:00",

      "external_id": null,

      "external_order_id": null,

      "barcode": null,

      "price": 800,

      "client_email": "mail@email.com",

      "client_phone": "+79101234567",

      "client_name": "Имя",

      "client_surname": "Фамилия",

      "client_middlename": "Отчество"

    },

    {

      "id": 120300,

      "paid": 0,

      "paid_at": null,

      "seat_id": "PARTERRE-1;25",

      "offer_id": "full",

      "admission": false,

      "reserved_to": "2021-09-12T10:00:00+03:00",

      "external_id": null,

      "external_order_id": null,

      "barcode": null,

      "price": 1000,

      "client_email": "mail@email.com",

      "client_phone": "+79101234567",

      "client_name": "Имя",

      "client_surname": "Фамилия",

      "client_middlename": "Отчество"

    }

]

....

Оплата нескольких билетов, а также привязка их к заказу:

POST https://qtickets.ru/api/partners/v1/tickets/update/12/4076

Accept: application/json

Cache-Control: no-cache

Content-Type: application/json

Authorization: Bearer YOUR_TOKEN

 

{

  "batch": [

    {

      "id": 120260,

      "external_order_id": "6a5cc185-bc59-451f-b7cb-94376476ae01",

      "paid_at": "2021-09-12T17:00:00+10:00"

    },

    {

      "id": 120261,

      "external_order_id": "6a5cc185-bc59-451f-b7cb-94376476ae01",

      "paid_at": "2021-09-12T17:00:00+10:00"

    }

  ]

}

Удаление нескольких билетов:

POST https://qtickets.ru/api/partners/v1/tickets/remove/12/4076

Accept: application/json

Cache-Control: no-cache

Content-Type: application/json

Authorization: Bearer YOUR_TOKEN

 

{

  "batch": [

    {

      "id": 120260

    },

    {

      "id": 120261

    }

  ]

}

Проверка статусов нескольких мест:

POST https://qtickets.ru/api/partners/v1/tickets/check/12/4076

Accept: application/json

Cache-Control: no-cache

Content-Type: application/json

Authorization: Bearer YOUR_TOKEN

 

{

  "batch": [

    {

      "seat_id": "CENTER_PARTERRE-20;5",

      "offer_id": "preferential"

    },

    {

      "seat_id": "CENTER_PARTERRE-20;5",

      "offer_id": "full"

    },

    {

      "seat_id": "CENTER_PARTERRE-20;6",

      "offer_id": "full"

    }

  ]

}

Tickets/Find — поиск билетов

Метод api/partners/v1/tickets/find/{event_id?}/{show_id?} служит для поиска ранее добавленных билетов. URL параметры {event_id} и {show_id} в данном запросе необязательные.

В GET или POST параметре нужно передать массив filter с такими возможными полями для фильтрации:

    external_order_id идентификатор заказа из вашей системы (строка или массив)
    external_id идентификатор билета из вашей системы (строка или массив)
    barcode значение ШК кода (строка или массив)
    id идентификатор билета из системы Qtickets (строка или массив)

Пример запроса:

POST https://qtickets.ru/api/partners/v1/tickets/find/{event_id?}/{show_id?}`

Accept: application/json

Cache-Control: no-cache

Content-Type: application/json

 

{

  "filter": {

    "external_order_id": "6a5cc185-bc59-451f-b7cb-94376476ae01",

    "external_id": ["ticket12345"],

    "barcode": ["872964136579", "879979255977"],

    "id": [134857, 134858]

  }

}

ответ:

{

  "status": "success",

  "result": [

    {

      "id": 134856,

      "paid": 1,

      "paid_at": "2022-04-06T20:56:00+03:00",

      "seat_id": "PARTERRE-1;25",

      "offer_id": "full",

      "admission": false,      

      "reserved_to": "2022-04-07T10:00:00+03:00",

      "external_id": null,

      "external_order_id": "EXT-007",

      "barcode": "872964136579",

      "price": 1222.03,

      "client_email": "mail@email.com",

      "client_phone": "+79101234567",

      "client_name": "Имя",

      "client_surname": "Фамилия",

      "client_middlename": "Отчество",

      "deleted": 0

    },

    {

      "id": 134857,

      "paid": 1,

      "paid_at": "2022-04-06T20:56:00+03:00",

      "seat_id": "PARTERRE-1;25",

      "offer_id": "full",

      "admission": false,      

      "reserved_to": "2022-04-07T10:00:00+03:00",

      "external_id": null,

      "external_order_id": "EXT-007",

      "barcode": "879979255977",

      "price": 100.55,

      "client_email": "mail@email.com",

      "client_phone": "+79101234567",

      "client_name": "Имя",

      "client_surname": "Фамилия",

      "client_middlename": "Отчество",

      "deleted": 0

    }

  ]

}

В ответе возвращаются найденные билеты, в том же виде, как возвращает данные методы add и update, единственное отличие, здесь также добавляется поле deleted, в котором будет значение 1 для отменённого билета (например, если закончилось время бронирования)
Events/Seats — статус мест в мероприятии (устаревший метод)

Метод api/partners/v1/events/seats/{event_id}/{show_id?}

Этот метод устарел. Не используйте его в новом коде. Используйте метод Events/Offers

Пример ответа:

{

   "event_id": 12,

   "show_id": 21,

   "event_name":"Название мероприятия 1",

   "start_date":"2019-01-03T17:00:00+10:00",

   "finish_date":"2019-01-03T20:00:00+10:00",  

   "scheme":{

        "id": 48,

        "venue_id": 120,

        "place_name": "Кремлевский дворец",

        "place_address": "ул. Воздвиженка, 1",

        "place_description": "м. Библиотека им. Ленина, Александровский сад, Боровицкая",

        "width": 1000,

        "height": 800,

        "zones":[

            {"zone_id": 8, "name": "VIP left", "description": "", "seats":[{"seat_id": "8-1;42"/*....*/}]},

            {"zone_id": 7, "name": "Supervip right", "description": "", "seats":[{"seat_id": "7-1;8"/*....*/}]},

            {"zone_id": 6, "name": "VIP right 2", "description": "", "seats":[{"seat_id": "6-1;52"/*....*/}]},

            {"zone_id": 5, "name": "Supervip left", "description": "", "seats":[{"seat_id": "5-1;8"/*....*/}]},

            {"zone_id": 4, "name": "VIP left 1", "description": "", "seats":[{"seat_id": "4-1;49"/*....*/}]},

            {"zone_id": 3, "name": "Танцевальный партер", "description": "", "seats":[{"seat_id": "3-1;1"/*....*/}]},

            {"zone_id": 2, "name": "VIP right 1", "description": "", "seats":[{"seat_id": "2-2;49"/*....*/}]},

            {"zone_id": 1, "name": "VIP 3", "description": "", "seats":[{"seat_id": "1-1;49"/*....*/}]}

        ]

    },

   "city":{

        "id": 2,

        "name": "Москва",

        "timezone": "Europe/Moscow",

        "coords":[

            55.7558,

            37.6176

        ]

   },

   "last_update_hash":"2f030832e2eb309b811dc9675df611273aefe618",

   "zones": [

     {

       "zone_id":7,

       "name":"Supervip right",

       "seats":[

         {"seat_id":"7-1;8","available":true,"coords":[283,977],"row":1,"place":8,"price":0,"currency_id":"RUB"},

         {"seat_id":"7-1;7","available":true,"coords":[299,963],"row":1,"place":7,"price":0,"currency_id":"RUB"},

         {"seat_id":"7-1;6","available":true,"coords":[316,949],"row":1,"place":6,"price":0,"currency_id":"RUB"},

         {"seat_id":"7-1;5","available":true,"coords":[333,935],"row":1,"place":5,"price":0,"currency_id":"RUB"},

         {"seat_id":"7-1;4","available":true,"coords":[349,921],"row":1,"place":4,"price":0,"currency_id":"RUB"},

         {"seat_id":"7-1;3","available":true,"coords":[366,907],"row":1,"place":3,"price":0,"currency_id":"RUB"}

       ]

     },

     {

       "zone_id":6,

       "name":"VIP right 2",

       "seats":[

         {"seat_id":"6-1;52","available":true,"coords":[58,600],"row":1,"place":52,"price":0,"currency_id":"RUB"},

         {"seat_id":"6-1;53","available":true,"coords":[74,614],"row":1,"place":53,"price":0,"currency_id":"RUB"},

         {"seat_id":"6-1;51","available":true,"coords":[58,579],"row":1,"place":51,"price":0,"currency_id":"RUB"},

         {"seat_id":"6-1;50","available":true,"coords":[74,565],"row":1,"place":50,"price":0,"currency_id":"RUB"},

         {"seat_id":"6-1;49","available":true,"coords":[91,551],"row":1,"place":49,"price":0,"currency_id":"RUB"},

         {"seat_id":"6-1;48","available":true,"coords":[108,537],"row":1,"place":48,"price":0,"currency_id":"RUB"},

         {"seat_id":"6-1;47","available":true,"coords":[125,523],"row":1,"place":47,"price":0,"currency_id":"RUB"}

       ]

     },

     {

       "zone_id":3,

       "name":"Танцевальный партер",

       "seats":[

         {"seat_id":"3-1;1","available":true,"coords":[730,806],"free_quantity":14,"admission":true,"price":300,"currency_id":"RUB"}

       ]

     },

     {

       "zone_id":1,

       "name":"VIP 3",

       "seats":[

         {"seat_id":"1-1;3","available":true,"coords":[1032,137],"row":1,"place":3,"price":1234,"currency_id":"RUB"},

         {"seat_id":"1-1;2","available":true,"coords":[1052,137],"row":1,"place":2,"price":100,"currency_id":"RUB"}

       ]

     }

   ]

}

где:

    scheme.width — Ширина схемы зала (float)
    scheme.height — Высота схемы зала (float)
    scheme.zones[*].width — Ширина сектора для категории билета (float)
    scheme.zones[*].height — Высота сектора для категории билета (float)
    scheme.zones[*].offset — Смещение сектора категории билета (array)

В zones содержится список категорий, каждая категория имеет свой уникальный идентификатор zone_id, название name и места seats.

Место имеет свой уникальный идентификатор seat_id, boolean флаг доступности для продажи available, а также ряд row и номер места place. Координаты места указаны в свойстве coords

Для мест, где указано admission: true продаются входные билеты, в параметре free_quantity оставшееся кол-во для продажи.
Список возможных ошибок в ответе

В случае, если status: error

    UNKNOWN_ERROR — неизвестная ошибка, вероятно стоит обратиться в техподдержку
    WRONG_AUTHORIZATION — авторизация не удалась, вероятно неверный API KEY
    EVENT_NOT_FOUND — мероприятие не найдено
    SEAT_NOT_FOUND — место не найдено
    SEAT_NOT_AVAILABLE — место недоступно для продажи
    TICKET_NOT_FOUND — билет не найден
    VALIDATION_ERROR — ошибка валидации параметров в запросе


