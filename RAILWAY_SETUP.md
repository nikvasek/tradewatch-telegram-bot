# Railway Environment Variables Setup Guide
# Follow these steps to configure BOT_TOKEN in Railway

## Step 1: Access Railway Dashboard
1. Go to https://railway.app/dashboard
2. Select your project: `tradewatch-telegram-bot`

## Step 2: Configure Environment Variables
1. Click on the **"Variables"** tab in your project
2. Click **"Add Variable"**
3. Enter:
   - **Name:** `BOT_TOKEN`
   - **Value:** `8196649413:AAHQ6KmQgBTfYtC3MeFQRFHE5L37CKQvJlw`

## Step 3: Additional Required Variables
Also add these variables for TradeWatch integration:

### Name: `TRADEWATCH_EMAIL`
Value: `your_tradewatch_email@example.com`

### Name: `TRADEWATCH_PASSWORD`
Value: `your_tradewatch_password`

## Step 4: Redeploy
1. After adding variables, go to **"Deployments"** tab
2. Click **"Redeploy"** on your active deployment
3. Wait for the new deployment to start

## Verification
After redeployment, you should see:
```
✅ BOT_TOKEN найден, начинаем инициализацию...
🔧 Инициализация TelegramBot с токеном: 8196649413:AA...
✅ Application создана успешно
✅ Обработчики настроены успешно
🚀 ЗАПУСК TELEGRAM БОТА
==================================================
� Railway Hobby план - максимальная производительность
```

## Troubleshooting
- If you still get errors, check that the BOT_TOKEN value is correct
- Make sure there are no extra spaces in the token value
- Verify that the deployment restarted after adding variables</content>
<parameter name="filePath">/Users/Mac/BotTelegramm/Alegro/RAILWAY_SETUP.md
