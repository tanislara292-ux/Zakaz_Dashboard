# Инструкция по получению токенов

## VK Ads API Токен

### Шаги по получению токена:

1. Войдите в аккаунт VK Ads: https://ads.vk.com/
   - Логин: `lazur.estate@yandex.ru`

2. Перейдите в настройки API:
   - Меню → Настройки → API
   - Или переход по прямой ссылке: https://ads.vk.com/settings/api/

3. Создайте новый токен:
   - Нажмите "Создать токен"
   - Выберите права доступа:
     - `ads` - доступ к рекламным кабинетам
     - `stats` - доступ к статистике
   - Установите срок действия токена (рекомендуем: 90 дней)
   - Скопируйте полученный токен

4. Получите ID рекламных кабинетов:
   - В разделе "Кабинеты" скопируйте ID нужных кабинетов
   - ID выглядят как числа: 123456789, 987654321

5. Обновите файл `secrets/.env.vk_ads`:
   ```env
   VK_API_TOKEN=вставьте_тут_ваш_токен
   VK_ACCOUNT_IDS=123456789,987654321
   ```

## Яндекс.Директ OAuth Токен

### Шаги по получению токена:

1. Войдите в Яндекс ID: https://id.yandex.ru/
   - Логин: `ads-irsshow@yandex.ru`
   - Пароль: `irs20show24`

2. Создайте приложение:
   - Перейдите: https://oauth.yandex.ru/client/new
   - Заполните форму:
     - Название: Zakaz Dashboard Direct API
     - Описание: Интеграция с API Яндекс.Директ для загрузки статистики
     - Права: `Яндекс.Директ` (проверка прав, получение статистики)
     - Callback URL: `https://oauth.yandex.ru/verification_code`
     - DCD: оставьте пустым
   - Сохраните приложение и скопируйте ID

3. Получите токен:
   - Перейдите по ссылке (замените CLIENT_ID):
     ```
     https://oauth.yandex.ru/authorize?response_type=token&client_id=CLIENT_ID
     ```
   - Разрешите доступ к Яндекс.Директ
   - Скопируйте токен из URL после перенаправления

4. Обновите файл `secrets/.env.direct`:
   ```env
   DIRECT_OAUTH_TOKEN=вставьте_тут_ваш_токен
   ```

## Проверка токенов

### VK Ads:
```bash
python -c "
from integrations.vk_ads.loader import VkAdsClient
import os
from dotenv import load_dotenv

load_dotenv('secrets/.env.vk_ads')
client = VkAdsClient(token=os.getenv('VK_API_TOKEN'))
with client:
    accounts = client.get_accounts()
    print('Доступные кабинеты:', accounts)
"
```

### Яндекс.Директ:
```bash
python -c "
from integrations.direct.loader import DirectAPIClient
import os
from dotenv import load_dotenv

load_dotenv('secrets/.env.direct')
client = DirectAPIClient(
    login=os.getenv('YANDEX_DIRECT_LOGIN'),
    token=os.getenv('DIRECT_OAUTH_TOKEN')
)
print('Токен действителен')
"
```

## Токены для GitHub Secrets

Если используется CI/CD, добавьте токены в GitHub Secrets:
- `VK_API_TOKEN`
- `DIRECT_OAUTH_TOKEN`
- `QTICKETS_API_TOKEN`

## Важные замечания

1. **Безопасность**:
   - Никогда не коммитьте токены в репозиторий
   - Регулярно обновляйте токены (рекомендуем раз в 3 месяца)
   - Используйте токены с минимальными необходимыми правами

2. **Хранение**:
   - Храните токены только в файлах в директории `secrets/`
   - Установите права доступа: `chmod 600 secrets/.env.*`

3. **Мониторинг**:
   - Следите за сроком действия токенов
   - Настройте алерты за 7 дней до истечения срока действия