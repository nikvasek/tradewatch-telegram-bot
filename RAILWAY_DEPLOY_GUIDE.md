# 🚀 Пошаговое развертывание на Railway

## Шаг 1: Регистрация на Railway

1. Перейдите на https://railway.app
2. Нажмите **"Start a New Project"**
3. Войдите через GitHub (используйте аккаунт nik.vasek@gmail.com)
4. Разрешите Railway доступ к вашим репозиториям

## Шаг 2: Создание проекта

1. На главной странице Railway нажмите **"New Project"**
2. Выберите **"Deploy from GitHub repo"**
3. Найдите и выберите репозиторий **`nikvasek/tradewatch-telegram-bot`**
4. Нажмите **"Deploy Now"**

## Шаг 3: Настройка переменных окружения

Railway автоматически найдет Dockerfile и начнет сборку, но нужно добавить переменные:

1. В панели проекта нажмите на ваш сервис
2. Перейдите в раздел **"Variables"** 
3. Добавьте следующие переменные:

```
BOT_TOKEN = ваш_токен_от_@BotFather
OWNER_ID = ваш_telegram_id (число)
TRADEWATCH_EMAIL = ваш_email_для_tradewatch
TRADEWATCH_PASSWORD = ваш_пароль_для_tradewatch
```

### Как получить нужные данные:

**BOT_TOKEN:**
- Напишите @BotFather в Telegram
- Отправьте `/mybots`
- Выберите вашего бота → API Token

**OWNER_ID:** 
- Напишите @userinfobot в Telegram
- Он пришлет ваш ID (например: 123456789)

**TRADEWATCH данные:**
- Ваш email и пароль для входа на tradewatch.pl

## Шаг 4: Проверка развертывания

1. После добавления переменных Railway перезапустит деплой
2. В разделе **"Deployments"** вы увидите процесс сборки
3. Ожидайте сообщения **"✅ Build successful"**
4. В логах должно появиться: `Bot started successfully!`

## Шаг 5: Тестирование

1. Найдите вашего бота в Telegram
2. Отправьте `/start`
3. Загрузите Excel файл для тестирования
4. Проверьте, что бот отвечает и обрабатывает файлы

## 🔧 Возможные проблемы и решения

### Проблема: "Build failed" с Chrome
**Решение:** У нас есть 3 варианта Dockerfile:
1. `Dockerfile` - основной (полная установка Chrome)
2. `Dockerfile.alternative` - альтернативный способ установки
3. `Dockerfile.selenium` - использует готовый образ с Chrome

Чтобы использовать альтернативный:
1. В Railway Settings → Build переименуйте файл:
   - `Dockerfile.alternative` → `Dockerfile` 
   - Или `Dockerfile.selenium` → `Dockerfile`
2. Redeploy проект

### Проблема: "Bot not responding"
**Решение:** 
1. Проверьте BOT_TOKEN в переменных
2. Убедитесь, что бот не запущен локально
3. Проверьте логи в Railway

### Проблема: "TradeWatch login failed"
**Решение:** Проверьте TRADEWATCH_EMAIL и TRADEWATCH_PASSWORD

## 📊 Мониторинг

В Railway вы можете:
- Смотреть логи в реальном времени
- Отслеживать использование ресурсов
- Настроить автоматические перезапуски

## 💰 Стоимость

- **Hobby Plan:** $5/месяц - достаточно для бота
- **Pro Plan:** $20/месяц - для высокой нагрузки

## ✅ Готово!

После успешного развертывания ваш бот будет работать 24/7 в облаке Railway с полной поддержкой:
- ✅ Selenium Chrome (headless)
- ✅ Обработка Excel файлов  
- ✅ TradeWatch интеграция
- ✅ Автоматические рестарты
- ✅ Логирование и мониторинг

**Ссылка на ваш проект:** https://railway.app/project/your-project-id
