# EstateFlow AI — Telegram Real Estate Bot

Готовый Telegram-бот для агентства недвижимости.

## Возможности
- Русский / O'zbek / English
- Сбор: тип недвижимости, бюджет, район, комнаты, срок покупки и телефон
- HOT/WARM/COLD lead scoring
- Уведомление менеджера в Telegram
- SQLite база лидов
- `/start`, `/help`, `/admin`, `/leads`, `/stats`
- Экспорт лидов в CSV
- Кнопки и валидация телефона/бюджета
- Защита админ-команд по Telegram user ID

## 1. Создай нового токена
Токен, который был опубликован в чате, считать скомпрометированным. В @BotFather:
`/revoke` → выбери бота → получи новый токен.

## 2. Установка Windows
Установи Python 3.11+.

В папке проекта:
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Открой `.env` и вставь новый токен.

## 3. Узнать свой Telegram ID
Запусти:
```powershell
python bot.py
```
Напиши боту `/myid`. Скопируй ID в `ADMIN_IDS` в `.env`, перезапусти.

## 4. Запуск
```powershell
python bot.py
```

Бот работает через long polling, поэтому отдельный сервер на старте не нужен.

## 5. Команды
Пользователь:
- `/start`
- `/help`
- `/myid`

Администратор:
- `/admin`
- `/leads`
- `/stats`
- `/export`
- `/cancel`

## Важно
Для реального бизнеса добавь HTTPS/webhook или размести бота на VPS/Render/Railway/другом сервере. Не храни токен в коде и никогда не публикуй `.env`.
