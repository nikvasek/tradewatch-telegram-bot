# 🚀 Инструкция по загрузке на GitHub

## 1. Создание репозитория на GitHub

1. Зайдите на https://github.com под аккаунтом nik.vasek@gmail.com
2. Нажмите "New repository" (зеленая кнопка)
3. Название репозитория: `tradewatch-telegram-bot` 
4. Описание: `TradeWatch Telegram Bot for Railway - automated Excel processing with competitor analysis`
5. Выберите **Public** (чтобы Railway мог получить доступ)
6. **НЕ** добавляйте README, .gitignore или LICENSE (у нас уже есть)
7. Нажмите "Create repository"

## 2. ✅ ГОТОВО! Код уже загружен

Репозиторий создан и код успешно загружен:

```bash
cd /Users/Mac/BotTelegramm/Alegro
git remote add origin https://github.com/nikvasek/tradewatch-telegram-bot.git
git branch -M main
git push -u origin main
```

## 3. Проверка загрузки

После успешной загрузки вы увидите все файлы на GitHub:
- README.md с красивым описанием
- Dockerfile для Railway
- Все исходные файлы бота

## 4. Развертывание на Railway

1. Зайдите на https://railway.app
2. Нажмите "New Project"
3. Выберите "Deploy from GitHub repo"
4. Найдите и выберите `nikvasek/tradewatch-telegram-bot`
5. Добавьте переменные окружения:
   ```
   BOT_TOKEN=ваш_токен_от_botfather
   OWNER_ID=ваш_telegram_id
   TRADEWATCH_EMAIL=ваш_email_tradewatch
   TRADEWATCH_PASSWORD=ваш_пароль_tradewatch
   ```
6. Railway автоматически развернет бота!

## 5. Результат

✅ Репозиторий на GitHub: `https://github.com/nikvasek/tradewatch-telegram-bot`
✅ Автоматическое развертывание на Railway
✅ Бот работает 24/7 в облаке с поддержкой Selenium

**Готово! 🎉**
