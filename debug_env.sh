#!/bin/bash
# Railway Environment Variables Debug Script
# This script helps debug BOT_TOKEN and other environment variable issues

echo "🔍 RAILWAY ENVIRONMENT DEBUG"
echo "============================="
echo ""

echo "📋 Все переменные окружения:"
echo "------------------------------"
env | grep -E "(BOT|TRADE)" | while read line; do
    key=$(echo $line | cut -d'=' -f1)
    value=$(echo $line | cut -d'=' -f2-)
    # Mask the value for security
    if [ ${#value} -gt 20 ]; then
        masked="${value:0:10}...${value: -5}"
    else
        masked="$value"
    fi
    echo "  $key: $masked"
done

echo ""
echo "🔍 Детальный анализ BOT_TOKEN:"
echo "-------------------------------"

BOT_TOKEN_VALUE=$(env | grep "^BOT_TOKEN=" | cut -d'=' -f2-)
EXPECTED_TOKEN="8196649413:AAHQ6KmQgBTfYtC3MeFQRFHE5L37CKQvJlw"

if [ -z "$BOT_TOKEN_VALUE" ]; then
    echo "❌ BOT_TOKEN не установлена"
    echo "   Статус: НЕ НАЙДЕНА"
else
    echo "✅ BOT_TOKEN найдена"
    echo "   Длина: ${#BOT_TOKEN_VALUE} символов"
    echo "   Ожидаемая длина: ${#EXPECTED_TOKEN} символов"
    echo "   Начинается с: ${BOT_TOKEN_VALUE:0:20}..."
    echo "   Заканчивается: ...${BOT_TOKEN_VALUE: -10}"

    if [ "$BOT_TOKEN_VALUE" = "$EXPECTED_TOKEN" ]; then
        echo "   Совпадение: ✅ ТОЧНОЕ СОВПАДЕНИЕ"
    else
        echo "   Совпадение: ❌ НЕ СОВПАДАЕТ"
        echo "   Ожидаемое: $EXPECTED_TOKEN"
        echo "   Полученное: $BOT_TOKEN_VALUE"
    fi
fi

echo ""
echo "🔍 Анализ других переменных:"
echo "-----------------------------"

check_env_var() {
    local var_name=$1
    local value=$(env | grep "^$var_name=" | cut -d'=' -f2-)
    if [ -z "$value" ]; then
        echo "❌ $var_name: НЕ УСТАНОВЛЕНА"
    else
        echo "✅ $var_name: УСТАНОВЛЕНА (длина: ${#value})"
    fi
}

check_env_var "TRADEWATCH_EMAIL"
check_env_var "TRADEWATCH_PASSWORD"

echo ""
echo "💡 РЕКОМЕНДАЦИИ ПО ИСПРАВЛЕНИЮ:"
echo "================================="
echo ""
echo "1. Перейдите в Railway Dashboard:"
echo "   https://railway.app/dashboard"
echo ""
echo "2. Выберите ваш проект 'tradewatch-telegram-bot'"
echo ""
echo "3. Перейдите во вкладку 'Variables' В ВАШЕМ СЕРВИСЕ"
echo "   (НЕ в корне проекта, а в конкретном сервисе!)"
echo ""
echo "4. Добавьте/проверьте переменную:"
echo "   Name: BOT_TOKEN"
echo "   Value: $EXPECTED_TOKEN"
echo ""
echo "5. Нажмите 'Save' и затем 'Redeploy'"
echo ""
echo "6. Дождитесь полного перезапуска (2-3 минуты)"
echo ""
echo "🚨 ВАЖНО:"
echo "--------"
echo "- Переменные должны быть на уровне СЕРВИСА, не ПРОЕКТА"
echo "- После добавления переменной ОБЯЗАТЕЛЬНО перезапустите deployment"
echo "- Проверьте что значение переменной скопировано БЕЗ лишних пробелов"
echo ""

echo "🔄 После исправления запустите этот скрипт снова:"
echo "   ./debug_env.sh"</content>
<parameter name="filePath">/Users/Mac/BotTelegramm/Alegro/debug_env.sh
