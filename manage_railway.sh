#!/bin/bash
# Railway Deployment Management Script
# Use this to check and manage your Railway deployments

echo "🚂 RAILWAY DEPLOYMENT MANAGEMENT"
echo "=================================="
echo ""

# Check Railway CLI installation
if ! command -v railway &> /dev/null; then
    echo "❌ Railway CLI не установлен!"
    echo "Установите Railway CLI: https://docs.railway.app/develop/cli"
    echo ""
    echo "Альтернативно, используйте Railway Dashboard:"
    echo "1. Перейдите в https://railway.app/dashboard"
    echo "2. Выберите ваш проект"
    echo "3. Проверьте раздел 'Deployments'"
    echo "4. Остановите лишние deployments"
    exit 1
fi

echo "✅ Railway CLI найден"
echo ""

# Login to Railway (if not already logged in)
echo "🔐 Проверяем авторизацию..."
railway login --browserless || {
    echo "❌ Ошибка авторизации. Выполните: railway login"
    exit 1
}

echo ""

# List current deployments
echo "📋 Текущие deployments:"
echo "-----------------------"
railway deploy list || {
    echo "❌ Ошибка получения списка deployments"
    exit 1
}

echo ""
echo "🔧 Доступные действия:"
echo "1. Остановить все deployments: railway deploy list | grep -v STATUS | awk '{print \$1}' | xargs railway deploy remove"
echo "2. Проверить статус конкретного deployment: railway deploy status <DEPLOYMENT_ID>"
echo "3. Посмотреть логи: railway logs"
echo ""

echo "💡 Рекомендации:"
echo "- Оставьте только ОДИН активный deployment"
echo "- Убедитесь что старые deployments остановлены"
echo "- Подождите 1-2 минуты после остановки перед новым запуском"
echo ""

echo "🎯 Следующие шаги:"
echo "1. Остановите лишние deployments в Railway Dashboard"
echo "2. Перезапустите бота"
echo "3. Если проблема persists, проверьте переменную BOT_TOKEN"</content>
<parameter name="filePath">/Users/Mac/BotTelegramm/Alegro/manage_railway.sh
