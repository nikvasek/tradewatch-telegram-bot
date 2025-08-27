"""
Fallback версия без Selenium для тестирования Railway deployment
"""
import os
import pandas as pd
import time
from pathlib import Path

# TradeWatch credentials (используйте переменные окружения для Railway)
TRADEWATCH_EMAIL = os.getenv("TRADEWATCH_EMAIL", "TRADEWATCH_EMAIL")
TRADEWATCH_PASSWORD = os.getenv("TRADEWATCH_PASSWORD", "TRADEWATCH_PASSWORD")

def get_railway_chrome_options():
    """
    Fallback - возвращает None, так как Selenium недоступен
    """
    print("❌ Selenium недоступен - функция работает в режиме fallback")
    return None

def download_from_tradewatch(chat_id, source_file_path, save_path, progress_callback=None):
    """
    Fallback версия - возвращает сообщение о недоступности функции
    """
    try:
        if progress_callback:
            progress_callback("❌ TradeWatch интеграция временно недоступна")
        
        print(f"❌ TradeWatch функция недоступна без Selenium")
        print(f"Chat ID: {chat_id}")
        print(f"Source file: {source_file_path}")
        print(f"Save path: {save_path}")
        
        # Возвращаем информацию об ошибке
        return {
            'success': False,
            'message': 'TradeWatch интеграция недоступна без Selenium.\nБот работает в ограниченном режиме.',
            'files': []
        }
        
    except Exception as e:
        print(f"❌ Ошибка в fallback функции: {e}")
        return {
            'success': False,
            'message': f'Ошибка: {str(e)}',
            'files': []
        }

def test_selenium_availability():
    """
    Проверка доступности Selenium
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager
        return True
    except ImportError as e:
        print(f"❌ Selenium недоступен: {e}")
        return False
    except Exception as e:
        print(f"❌ Ошибка при инициализации Selenium: {e}")
        return False

# Проверяем доступность Selenium при импорте
SELENIUM_AVAILABLE = test_selenium_availability()

if SELENIUM_AVAILABLE:
    print("✅ Selenium доступен")
else:
    print("❌ Selenium недоступен - работаем в fallback режиме")
