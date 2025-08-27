#!/bin/bash
# Quick Railway BOT_TOKEN Setup Script
# Run this after setting up environment variables in Railway

echo "🚀 RAILWAY BOT_TOKEN SETUP VERIFICATION"
echo "========================================"
echo ""

# Check if Railway CLI is available
if command -v railway &> /dev/null; then
    echo "✅ Railway CLI найден"

    # Check login status
    if railway status &> /dev/null; then
        echo "✅ Авторизован в Railway"
    else
        echo "❌ Не авторизован в Railway"
        echo "Выполните: railway login"
        exit 1
    fi

    echo ""
    echo "📋 Текущие переменные окружения в Railway:"
    echo "--------------------------------------------"

    # Try to list environment variables
    if railway variables list 2>/dev/null; then
        echo ""
    else
        echo "❌ Не удалось получить список переменных"
        echo "Убедитесь что вы находитесь в правильном проекте"
        echo "Выполните: railway link <project-id>"
    fi

else
    echo "❌ Railway CLI не установлен"
    echo "Установите Railway CLI: https://docs.railway.app/develop/cli"
fi

echo ""
echo "🔧 РУЧНАЯ НАСТРОЙКА (если CLI недоступен):"
echo "=========================================="
echo ""
echo "1. Перейдите: https://railway.app/dashboard"
echo "2. Выберите проект: tradewatch-telegram-bot"
echo "3. Вкладка 'Variables' → 'Add Variable'"
echo ""
echo "📝 ОБЯЗАТЕЛЬНЫЕ ПЕРЕМЕННЫЕ:"
echo "-----------------------------"
echo "BOT_TOKEN = 8196649413:AAHQ6KmQgBTfYtC3MeFQRFHE5L37CKQvJlw"
echo ""
echo "🔄 ПОСЛЕ НАСТРОЙКИ:"
echo "-------------------"
echo "1. Перейдите во вкладку 'Deployments'"
echo "2. Нажмите 'Redeploy' на активном deployment"
echo "3. Дождитесь перезапуска (2-3 минуты)"
echo ""
echo "✅ ПРОВЕРКА:"
echo "------------"
echo "После перезапуска вы должны увидеть:"
echo "BOT_TOKEN: ✅ УСТАНОВЛЕН"
echo "TRADEWATCH_EMAIL: ✅ УСТАНОВЛЕН"
echo "TRADEWATCH_PASSWORD: ✅ УСТАНОВЛЕН"
echo ""
echo "🚀 ГОТОВО! Бот запустится с максимальной производительностью!"</content>
<parameter name="filePath">/Users/Mac/BotTelegramm/Alegro/check_railway_setup.sh
