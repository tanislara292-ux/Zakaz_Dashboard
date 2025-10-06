# Руководство по доступам

1. Создайте сервис-аккаунт в Google Cloud Console. Адрес будет вида `name@project-id.iam.gserviceaccount.com`.
2. Добавьте этот адрес в список пользователей Google Sheets `BI_Central` с ролью «Редактор».
3. Скачанный JSON-ключ сохраните локально по пути `secrets/google-sa.json` (папку `secrets/` добавляем в `.gitignore`).
4. Передавайте ссылку и доступ к `BI_Central` команде аналитики и Python-сервису только через защищённые каналы.
5. Доступы для DataLens предоставляет Заказчик; запрос оформляется письмом по шаблону из `ops/EMAIL_TEMPLATES.md`.
