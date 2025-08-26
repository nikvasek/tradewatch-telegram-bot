from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import os
import glob
import shutil
import pandas as pd
import hashlib
from pathlib import Path
import threading
import concurrent.futures
from datetime import datetime
from selenium.webdriver.common.window import WindowTypes

# TradeWatch credentials (используйте переменные окружения для Railway)
TRADEWATCH_EMAIL = os.getenv("TRADEWATCH_EMAIL", "TRADEWATCH_EMAIL")
TRADEWATCH_PASSWORD = os.getenv("TRADEWATCH_PASSWORD", "TRADEWATCH_PASSWORD")

def get_railway_chrome_options(batch_number=None):
    """
    Получить настройки Chrome для Railway deployment
    """
    options = webdriver.ChromeOptions()
    
    # Уникальная директория для каждой сессии
    if batch_number:
        user_data_dir = f"/tmp/chrome_user_data_{batch_number}_{int(time.time())}"
        options.add_argument(f"--user-data-dir={user_data_dir}")
        print(f"🔧 Используем уникальную директорию: {user_data_dir}")
    
    # Базовые настройки для headless режима
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-logging")
    options.add_argument("--disable-web-security")
    options.add_argument("--allow-running-insecure-content")
    
    # Railway специфичные настройки
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-features=TranslateUI")
    options.add_argument("--disable-default-apps")
    options.add_argument("--disable-sync")
    options.add_argument("--disable-background-networking")
    options.add_argument("--single-process")
    
    # Проверяем переменные окружения Railway
    if os.getenv('RAILWAY_ENVIRONMENT_NAME'):
        print("🚂 Запуск на Railway - используем оптимизированные настройки")
        options.add_argument("--memory-pressure-off")
        options.add_argument("--max_old_space_size=4096")
        # Дополнительные настройки для экономии памяти на Railway
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-backing-store-limit")
        options.add_argument("--disable-hang-monitor")
        options.add_argument("--disable-client-side-phishing-detection")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-prompt-on-repost")
        options.add_argument("--disable-renderer-backgrounding")
        options.add_argument("--disable-ipc-flooding-protection")
    
    return options

def get_batch_size():
    """
    Получить оптимальный размер батча в зависимости от окружения
    """
    if os.getenv('RAILWAY_ENVIRONMENT_NAME'):
        print("🚂 Railway обнаружен - используем батчи по 50 кодов для максимальной стабильности")
        return 50  # Еще меньше для лучшей стабильности
    else:
        print("💻 Локальное окружение - используем батчи по 450 кодов")
        return 450

def cleanup_chrome_temp_dirs():
    """
    Очищает временные директории Chrome
    """
    try:
        import glob
        temp_dirs = glob.glob("/tmp/chrome_user_data_*")
        for temp_dir in temp_dirs:
            try:
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
                print(f"🧹 Очищена временная директория: {temp_dir}")
            except:
                pass
    except:
        pass

def get_chrome_service():
    """
    Получить Service для ChromeDriver в зависимости от окружения
    """
    # Проверяем, работаем ли в Docker с selenium/standalone-chrome
    if os.path.exists('/usr/bin/chromedriver'):
        print("🐳 Используем системный ChromeDriver из Docker образа")
        return Service('/usr/bin/chromedriver')
    elif os.path.exists('/opt/selenium/chromedriver-*/chromedriver'):
        # В selenium образах ChromeDriver может быть здесь
        import glob
        chromedriver_paths = glob.glob('/opt/selenium/chromedriver-*/chromedriver')
        if chromedriver_paths:
            print(f"🐳 Используем ChromeDriver из Selenium образа: {chromedriver_paths[0]}")
            return Service(chromedriver_paths[0])
    
    # Fallback - используем WebDriver Manager
    print("📦 Используем WebDriver Manager для скачивания ChromeDriver")
    return Service(ChromeDriverManager().install())

def clear_ean_field_thoroughly(driver, ean_field, batch_number):
    """
    КРИТИЧЕСКИ ВАЖНО: Тщательно очищает поле EAN кодов несколькими способами
    
    Args:
        driver: веб-драйвер
        ean_field: элемент поля EAN кодов
        batch_number: номер группы для логирования
    """
    print(f"НАЧИНАЕМ АГРЕССИВНУЮ ОЧИСТКУ поля EAN кодов для группы {batch_number}...")
    
    # Проверяем изначальное состояние
    initial_value = ean_field.get_attribute("value")
    print(f"Изначальное содержимое поля: '{initial_value}'")
    
    # Сначала убеждаемся, что поле в фокусе
    try:
        ean_field.click()
        time.sleep(0.3)
    except:
        pass
    
    # СПОСОБ 1: Стандартная очистка (может не работать)
    ean_field.clear()
    time.sleep(0.2)
    
    # СПОСОБ 2: Выделяем все и удаляем (может не работать)
    try:
        ean_field.send_keys(Keys.CONTROL + "a")
        time.sleep(0.1)
        ean_field.send_keys(Keys.DELETE)
        time.sleep(0.2)
    except:
        pass
    
    # СПОСОБ 3: Альтернативная очистка клавишами
    try:
        ean_field.send_keys(Keys.CONTROL + "a")
        time.sleep(0.1)
        ean_field.send_keys(Keys.BACKSPACE)
        time.sleep(0.2)
    except:
        pass
    
    # СПОСОБ 4: JavaScript очистка (основной метод)
    driver.execute_script("arguments[0].value = '';", ean_field)
    time.sleep(0.2)
    
    # СПОСОБ 5: Более агрессивная JavaScript очистка
    driver.execute_script("""
        var element = arguments[0];
        element.value = '';
        element.innerHTML = '';
        element.textContent = '';
        element.innerText = '';
        if (element.defaultValue) element.defaultValue = '';
    """, ean_field)
    time.sleep(0.2)
    
    # СПОСОБ 6: Эмуляция очистки через JavaScript события
    driver.execute_script("""
        var element = arguments[0];
        element.focus();
        element.value = '';
        element.dispatchEvent(new Event('input', { bubbles: true }));
        element.dispatchEvent(new Event('change', { bubbles: true }));
        element.dispatchEvent(new Event('blur', { bubbles: true }));
        element.dispatchEvent(new Event('keydown', { bubbles: true }));
        element.dispatchEvent(new Event('keyup', { bubbles: true }));
    """, ean_field)
    time.sleep(0.3)
    
    # СПОСОБ 7: Удаление через execCommand
    driver.execute_script("""
        var element = arguments[0];
        element.focus();
        element.select();
        document.execCommand('selectAll');
        document.execCommand('delete');
        document.execCommand('removeFormat');
    """, ean_field)
    time.sleep(0.2)
    
    # СПОСОБ 8: Принудительная замена содержимого
    driver.execute_script("""
        var element = arguments[0];
        element.setAttribute('value', '');
        element.removeAttribute('defaultValue');
        if (element.value) element.value = '';
    """, ean_field)
    time.sleep(0.3)
    
    # КРИТИЧЕСКАЯ ПРОВЕРКА: Проверяем, что поле действительно очищено
    for attempt in range(3):
        current_value = ean_field.get_attribute("value")
        print(f"Попытка {attempt + 1}: Содержимое поля после очистки: '{current_value}'")
        
        if not current_value or len(current_value.strip()) == 0:
            print(f"✅ Поле успешно очищено для группы {batch_number}")
            break
        else:
            print(f"❌ Поле не очищено! Осталось: '{current_value}'. Дополнительная агрессивная очистка...")
            
            # Дополнительная агрессивная очистка
            driver.execute_script("""
                var element = arguments[0];
                
                // Удаляем все возможные свойства
                element.value = '';
                element.defaultValue = '';
                element.textContent = '';
                element.innerHTML = '';
                element.innerText = '';
                
                // Принудительно удаляем атрибуты
                element.removeAttribute('value');
                element.removeAttribute('defaultValue');
                
                // Эмуляция пользовательских действий
                element.focus();
                element.select();
                
                // Очистка через range API
                if (window.getSelection) {
                    var selection = window.getSelection();
                    selection.removeAllRanges();
                    var range = document.createRange();
                    range.selectNodeContents(element);
                    selection.addRange(range);
                    selection.deleteFromDocument();
                }
                
                // Финальная установка пустого значения
                element.value = '';
                
                // Генерация событий
                element.dispatchEvent(new Event('input', { bubbles: true }));
                element.dispatchEvent(new Event('change', { bubbles: true }));
            """, ean_field)
            time.sleep(0.5)
            
            # Если все еще не очищено, принудительно заменяем элемент
            if attempt == 2:
                final_value = ean_field.get_attribute("value")
                if final_value and final_value.strip():
                    print(f"🔥 КРИТИЧЕСКАЯ ОШИБКА: Поле не удается очистить! Содержимое: '{final_value}'")
                    print("Выполняем принудительную перезагрузку страницы...")
                    driver.refresh()
                    time.sleep(3)
                    return False
    
    print(f"✅ Агрессивная очистка завершена для группы {batch_number}")
    return True


def insert_ean_codes_safely(driver, ean_field, ean_codes_string, batch_number):
    """
    Безопасно вставляет EAN коды с проверкой результата
    
    Args:
        driver: веб-драйвер
        ean_field: элемент поля EAN кодов
        ean_codes_string: строка с EAN кодами
        batch_number: номер группы для логирования
    """
    # Убеждаемся, что поле в фокусе
    try:
        ean_field.click()
        time.sleep(0.2)
    except:
        pass
    
    # Вставляем коды
    ean_field.send_keys(ean_codes_string)
    
    # Даем время на обработку
    time.sleep(0.5)
    
    # Проверяем, что коды вставились корректно
    inserted_value = ean_field.get_attribute("value")
    if not inserted_value or len(inserted_value.strip()) == 0:
        print(f"Коды не вставились! Попытка повторной вставки через JavaScript...")
        
        # Попытка через JavaScript
        driver.execute_script("""
            var element = arguments[0];
            var text = arguments[1];
            element.focus();
            element.value = text;
            element.dispatchEvent(new Event('input', { bubbles: true }));
            element.dispatchEvent(new Event('change', { bubbles: true }));
        """, ean_field, ean_codes_string)
        
        time.sleep(1)
        
        # Повторная проверка
        inserted_value = ean_field.get_attribute("value")
        if not inserted_value or len(inserted_value.strip()) == 0:
            print(f"Ошибка: коды так и не вставились даже через JavaScript!")
            
            # Последняя попытка - прямая вставка
            try:
                ean_field.clear()
                ean_field.send_keys(ean_codes_string)
                time.sleep(1)
                inserted_value = ean_field.get_attribute("value")
            except:
                pass
            
            if not inserted_value or len(inserted_value.strip()) == 0:
                return False
    
    # Проверяем соответствие количества кодов
    inserted_codes = inserted_value.strip().split()
    expected_codes = ean_codes_string.strip().split()
    
    if len(inserted_codes) != len(expected_codes):
        print(f"Предупреждение: количество вставленных кодов ({len(inserted_codes)}) не совпадает с ожидаемым ({len(expected_codes)})")
        print(f"Ожидались: {expected_codes[:5]}...")
        print(f"Вставлены: {inserted_codes[:5]}...")
        
        # Проверяем, что хотя бы половина кодов вставилась
        if len(inserted_codes) < len(expected_codes) * 0.5:
            print(f"Критическая ошибка: вставлено менее половины кодов!")
            return False
    else:
        print(f"✅ Вставлено {len(inserted_codes)} EAN кодов для группы {batch_number}")
    
    return True


def verify_batch_uniqueness(downloaded_files):
    """
    Проверяет уникальность содержимого загруженных файлов
    
    Args:
        downloaded_files: список путей к загруженным файлам
        
    Returns:
        bool: True если все файлы уникальны, False если есть дублирования
    """
    print("\n🔍 ПРОВЕРКА УНИКАЛЬНОСТИ содержимого файлов...")
    
    file_hashes = {}
    duplicates_found = False
    
    for file_path in downloaded_files:
        if not os.path.exists(file_path):
            print(f"❌ Файл не найден: {file_path}")
            continue
            
        try:
            # Читаем файл и создаем хеш содержимого
            df = pd.read_excel(file_path)
            
            # Создаем строку из содержимого для хеширования
            content_string = df.to_string()
            content_hash = hashlib.md5(content_string.encode()).hexdigest()
            
            filename = os.path.basename(file_path)
            
            if content_hash in file_hashes:
                print(f"🚨 ОБНАРУЖЕНО ДУБЛИРОВАНИЕ: {filename} идентичен {file_hashes[content_hash]}")
                duplicates_found = True
            else:
                file_hashes[content_hash] = filename
                print(f"✅ Файл уникален: {filename}")
                
        except Exception as e:
            print(f"❌ Ошибка при проверке файла {file_path}: {e}")
    
    if duplicates_found:
        print("\n🚨 НАЙДЕНЫ ДУБЛИРОВАННЫЕ ФАЙЛЫ! Требуется исправление.")
        return False
    else:
        print("\n✅ Все файлы уникальны.")
        return True


def format_ean_to_13_digits(ean_code):
    """
    Форматирует EAN код в стандартный 13-цифровой формат
    
    Args:
        ean_code: EAN код (строка или число)
        
    Returns:
        str: EAN код в 13-цифровом формате с ведущими нулями
        
    Пример:
        format_ean_to_13_digits("123456789") -> "0000123456789"
        format_ean_to_13_digits("1234567890123") -> "1234567890123"
    """
    try:
        # Конвертируем в строку и удаляем пробелы
        ean_str = str(ean_code).strip()
        
        # Если получилось пустое значение, возвращаем None
        if not ean_str:
            return None
        
        # Особая обработка для научной нотации
        if 'E' in ean_str.upper() or 'e' in ean_str:
            try:
                # Конвертируем через float для обработки научной нотации
                ean_float = float(ean_str)
                ean_str = str(int(ean_float))
            except:
                pass
        
        # Удаляем все нечисловые символы
        ean_digits = ''.join(char for char in ean_str if char.isdigit())
        
        # Если получилось пустое значение, возвращаем None
        if not ean_digits:
            return None
            
        # Обрезаем до 13 цифр если больше
        if len(ean_digits) > 13:
            ean_digits = ean_digits[:13]
            
        # Дополняем ведущими нулями до 13 цифр
        ean_formatted = ean_digits.zfill(13)
        
        return ean_formatted
        
    except Exception as e:
        print(f"Ошибка при форматировании EAN кода '{ean_code}': {e}")
        return None

def process_ean_codes_batch(ean_codes_batch, download_dir, batch_number=1, headless=True):
    """
    [УСТАРЕЛО] Обрабатывает группу EAN кодов в TradeWatch и скачивает файл
    Используйте process_supplier_file_with_tradewatch() для более эффективной обработки
    
    Args:
        ean_codes_batch: список EAN кодов для обработки
        download_dir: папка для скачивания файлов
        batch_number: номер группы для идентификации файла
        headless: запуск в headless режиме (True) или с GUI (False)
    
    Returns:
        str: путь к скачанному файлу или None если ошибка
    """
    print("⚠️  ВНИМАНИЕ: Эта функция устарела. Используйте process_supplier_file_with_tradewatch() для более эффективной обработки с единой сессией браузера.")
    
    if not ean_codes_batch:
        print("Пустая группа EAN кодов")
        return None
        
    # Создаем папку для скачивания если её нет
    download_path = Path(download_dir)
    download_path.mkdir(parents=True, exist_ok=True)
    
    # Удаляем только файлы с оригинальным именем (не переименованные)
    old_files = glob.glob(os.path.join(download_dir, "TradeWatch - raport konkurencji.xlsx"))
    for old_file in old_files:
        try:
            os.remove(old_file)
            print(f"Удален старый файл: {old_file}")
        except Exception as e:
            print(f"Не удалось удалить файл {old_file}: {e}")
            pass
    
    # Соединяем EAN коды в одну строку через пробел
    ean_codes_string = ' '.join(str(code) for code in ean_codes_batch)
    
    # Настройка драйвера Chrome для Railway
    if os.getenv('RAILWAY_ENVIRONMENT_NAME'):
        # Используем Railway-оптимизированные настройки
        options = get_railway_chrome_options(batch_number)
        print("🚂 Railway режим: используем headless Chrome")
    else:
        # Локальная разработка
        options = webdriver.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        if headless:
            options.add_argument("--headless")  # Запуск в headless режиме
        
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-logging")
        options.add_argument("--disable-web-security")
        options.add_argument("--allow-running-insecure-content")
    
    # Настройка для автоматической загрузки файлов
    prefs = {
        "download.default_directory": str(download_path.absolute()),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    options.add_experimental_option("prefs", prefs)
    
    # Инициализация драйвера
    service = get_chrome_service()
    driver = webdriver.Chrome(service=service, options=options)
    
    try:
        print(f"Обработка группы {batch_number} с {len(ean_codes_batch)} EAN кодами...")
        
        # Переход на страницу входа
        driver.get("https://tradewatch.pl/login.jsf")
        
        # Ждем загрузки страницы
        wait = WebDriverWait(driver, 10)
        
        # Ищем поле для email
        email_field = wait.until(EC.presence_of_element_located((By.NAME, "j_username")))
        
        # Вводим email
        email_field.clear()
        email_field.send_keys(TRADEWATCH_EMAIL)
        
        # Ищем поле для пароля
        password_field = driver.find_element(By.NAME, "j_password")
        
        # Вводим пароль
        password_field.clear()
        password_field.send_keys(TRADEWATCH_PASSWORD)
        
        # Ищем кнопку входа
        login_button = driver.find_element(By.NAME, "btnLogin")
        
        # Нажимаем кнопку входа
        login_button.click()
        
        # Ждем немного после входа
        time.sleep(3)
        
        # Проверяем успешность входа
        current_url = driver.current_url
        
        if "login.jsf" not in current_url:
            print("Успешный вход в систему!")
            
            # Переходим на страницу EAN Price Report
            driver.get("https://tradewatch.pl/report/ean-price-report.jsf")
            time.sleep(3)
            
            try:
                # Ищем поле для ввода EAN кодов
                ean_field = wait.until(EC.presence_of_element_located((By.ID, "eansPhrase")))
                
                # Тщательно очищаем поле
                clear_ean_field_thoroughly(driver, ean_field, batch_number)
                
                # Безопасно вставляем EAN коды
                if not insert_ean_codes_safely(driver, ean_field, ean_codes_string, batch_number):
                    print(f"Ошибка: не удалось вставить EAN коды для группы {batch_number}")
                    return None
                
                # Ждем немного
                time.sleep(1)
                
                # Ищем кнопку "Generuj"
                generate_button = driver.find_element(By.ID, "j_idt703")
                
                # Нажимаем кнопку
                generate_button.click()
                
                # Ждем обработки
                print("Ждем обработки запроса...")
                time.sleep(5)
                
                # Ждем появления результатов
                print("Ждем появления результатов...")
                time.sleep(5)  # Увеличиваем время ожидания результатов
                
                # Ищем кнопку "Eksport do XLS"
                try:
                    export_button = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Eksport do XLS")))
                    
                    # Нажимаем кнопку экспорта
                    export_button.click()
                    
                    # Ждем начала загрузки файла
                    print("Ждем загрузки файла...")
                    
                    # Ждем появления файла с проверкой каждые 2 секунды
                    max_wait_time = 60  # Максимальное время ожидания 60 секунд
                    wait_interval = 2   # Проверяем каждые 2 секунды
                    waited_time = 0
                    
                    downloaded_file_found = False
                    
                    while waited_time < max_wait_time:
                        time.sleep(wait_interval)
                        waited_time += wait_interval
                        
                        # Ищем скачанный файл (только оригинальное имя)
                        downloaded_files = glob.glob(os.path.join(download_dir, "TradeWatch - raport konkurencji.xlsx"))
                        if downloaded_files:
                            # Проверяем, что файл полностью скачался (не изменяется в размере)
                            latest_file = downloaded_files[0]  # Берем первый (и единственный) файл
                            
                            # Ждем немного и проверяем, что размер файла не изменился
                            initial_size = os.path.getsize(latest_file)
                            time.sleep(3)  # Ждем 3 секунды
                            
                            try:
                                final_size = os.path.getsize(latest_file)
                                if initial_size == final_size and final_size > 0:
                                    # Файл стабильного размера, значит скачивание завершено
                                    print(f"Файл для группы {batch_number} загружен: {latest_file} (размер: {final_size} байт)")
                                    downloaded_file_found = True
                                    break
                                else:
                                    print(f"Файл еще скачивается... (размер: {final_size} байт)")
                            except:
                                # Файл может быть заблокирован, продолжаем ждать
                                print(f"Файл заблокирован, продолжаем ждать...")
                                continue
                        else:
                            print(f"Ожидание файла... ({waited_time}/{max_wait_time} сек)")
                    
                    if downloaded_file_found:
                        # Переименовываем файл для идентификации
                        new_filename = f"TradeWatch_batch_{batch_number}.xlsx"
                        new_filepath = os.path.join(download_dir, new_filename)
                        
                        if os.path.exists(new_filepath):
                            os.remove(new_filepath)
                        
                        os.rename(latest_file, new_filepath)
                        return new_filepath
                    else:
                        print(f"Файл для группы {batch_number} не найден после {max_wait_time} секунд ожидания")
                        return None
                        
                except Exception as export_error:
                    print(f"Ошибка при экспорте группы {batch_number}: {export_error}")
                    # Попробуем альтернативный способ
                    try:
                        export_button = driver.find_element(By.CSS_SELECTOR, "a.icon-excel")
                        export_button.click()
                        
                        # Ждем с проверкой завершения скачивания
                        max_wait_time = 60
                        wait_interval = 2
                        waited_time = 0
                        
                        while waited_time < max_wait_time:
                            time.sleep(wait_interval)
                            waited_time += wait_interval
                            
                            downloaded_files = glob.glob(os.path.join(download_dir, "TradeWatch - raport konkurencji.xlsx"))
                            if downloaded_files:
                                latest_file = downloaded_files[0]
                                
                                # Проверяем стабильность размера файла
                                initial_size = os.path.getsize(latest_file)
                                time.sleep(3)
                                
                                try:
                                    final_size = os.path.getsize(latest_file)
                                    if initial_size == final_size and final_size > 0:
                                        new_filename = f"TradeWatch_batch_{batch_number}.xlsx"
                                        new_filepath = os.path.join(download_dir, new_filename)
                                        
                                        if os.path.exists(new_filepath):
                                            os.remove(new_filepath)
                                        
                                        os.rename(latest_file, new_filepath)
                                        return new_filepath
                                except:
                                    continue
                            else:
                                print(f"Альтернативный способ: ожидание файла... ({waited_time}/{max_wait_time} сек)")
                        
                        return None
                    except Exception as alt_error:
                        print(f"Альтернативный метод тоже не сработал для группы {batch_number}: {alt_error}")
                        return None
                
            except Exception as e:
                print(f"Ошибка при работе с EAN кодами группы {batch_number}: {e}")
                return None
        else:
            print("Ошибка при входе в систему")
            return None
            
    except Exception as e:
        print(f"Произошла ошибка при обработке группы {batch_number}: {e}")
        return None
    
    finally:
        # Закрываем браузер
        driver.quit()


def process_batch_in_session(driver, ean_codes_batch, download_dir, batch_number):
    """
    Обрабатывает группу EAN кодов в уже открытой сессии браузера
    
    Args:
        driver: активный веб-драйвер
        ean_codes_batch: список EAN кодов для обработки
        download_dir: папка для скачивания файлов
        batch_number: номер группы для идентификации файла
    
    Returns:
        str: путь к скачанному файлу или None если ошибка
    """
    if not ean_codes_batch:
        print("Пустая группа EAN кодов")
        return None
    
    try:
        # Форматируем EAN коды в 13-цифровой формат
        formatted_ean_codes = []
        for code in ean_codes_batch:
            formatted_code = format_ean_to_13_digits(code)
            if formatted_code:
                formatted_ean_codes.append(formatted_code)
        
        if not formatted_ean_codes:
            print("Нет валидных EAN кодов после форматирования")
            return None
        
        print(f"Отформатировано {len(formatted_ean_codes)} EAN кодов в 13-цифровой формат")
        
        # Соединяем отформатированные EAN коды в одну строку через пробел
        ean_codes_string = ' '.join(formatted_ean_codes)
        
        print(f"DEBUG: Обрабатываем группу {batch_number} с EAN кодами: {ean_codes_string[:100]}...")
        
        # КРИТИЧЕСКИ ВАЖНО: Полный сброс страницы между группами
        print(f"Выполняем полный сброс страницы для группы {batch_number}...")
        
        # Сначала очищаем куки и локальное хранилище
        driver.execute_script("localStorage.clear(); sessionStorage.clear();")
        
        # Переходим на пустую страницу для полного сброса
        driver.get("about:blank")
        time.sleep(1)
        
        # Переходим на страницу EAN Price Report заново
        driver.get("https://tradewatch.pl/report/ean-price-report.jsf")
        time.sleep(3)  # Увеличиваем время ожидания после полного сброса
        
        wait = WebDriverWait(driver, 15)  # Увеличиваем время ожидания
        
        # Ищем поле для ввода EAN кодов
        ean_field = wait.until(EC.presence_of_element_located((By.ID, "eansPhrase")))
        
        # Дополнительная проверка - убеждаемся, что поле пустое
        initial_value = ean_field.get_attribute("value")
        if initial_value and initial_value.strip():
            print(f"КРИТИЧЕСКАЯ ОШИБКА: Поле не пустое перед очисткой! Содержимое: '{initial_value}'")
            
            # Принудительная очистка всей страницы
            driver.refresh()
            time.sleep(3)
            ean_field = wait.until(EC.presence_of_element_located((By.ID, "eansPhrase")))
        
        # Тщательно очищаем поле
        if not clear_ean_field_thoroughly(driver, ean_field, batch_number):
            print(f"Критическая ошибка: не удалось очистить поле для группы {batch_number}")
            return None
        
        # Безопасно вставляем EAN коды
        if not insert_ean_codes_safely(driver, ean_field, ean_codes_string, batch_number):
            print(f"Ошибка: не удалось вставить EAN коды для группы {batch_number}")
            return None
        
        # КРИТИЧЕСКИ ВАЖНО: Проверяем, что в поле только наши коды
        final_value = ean_field.get_attribute("value")
        final_codes = final_value.strip().split() if final_value else []
        expected_codes = ean_codes_string.strip().split()
        
        # Проверяем на наличие посторонних кодов
        extra_codes = [code for code in final_codes if code not in expected_codes]
        if extra_codes:
            print(f"КРИТИЧЕСКАЯ ОШИБКА: Обнаружены посторонние коды в поле: {extra_codes}")
            print(f"Ожидались только: {expected_codes}")
            print(f"Найдено в поле: {final_codes}")
            
            # Принудительная перезагрузка и повторная попытка
            driver.refresh()
            time.sleep(3)
            ean_field = wait.until(EC.presence_of_element_located((By.ID, "eansPhrase")))
            clear_ean_field_thoroughly(driver, ean_field, batch_number)
            
            if not insert_ean_codes_safely(driver, ean_field, ean_codes_string, batch_number):
                print(f"Повторная попытка также не удалась для группы {batch_number}")
                return None
        
        # Ждем немного
        time.sleep(1)
        
        # Ищем кнопку "Generuj"
        generate_button = driver.find_element(By.ID, "j_idt703")
        
        # Нажимаем кнопку
        generate_button.click()
        
        # Ждем обработки
        print("Ждем обработки запроса...")
        time.sleep(5)
        
        # Ждем появления результатов
        print("Ждем появления результатов...")
        time.sleep(3)
        
        # Ищем кнопку "Eksport do XLS"
        try:
            export_button = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Eksport do XLS")))
            
            # Пытаемся кликнуть разными способами
            click_success = False
            
            # Способ 1: Обычный клик
            try:
                export_button.click()
                click_success = True
                print("Клик по кнопке экспорта выполнен (обычный клик)")
            except Exception as e:
                print(f"Обычный клик не сработал: {e}")
                
                # Способ 2: JavaScript клик
                try:
                    driver.execute_script("arguments[0].click();", export_button)
                    click_success = True
                    print("Клик по кнопке экспорта выполнен (JavaScript клик)")
                except Exception as js_e:
                    print(f"JavaScript клик не сработал: {js_e}")
                    
                    # Способ 3: Закрываем возможные оверлеи и пытаемся снова
                    try:
                        # Закрываем оверлеи
                        overlays = driver.find_elements(By.CLASS_NAME, "ui-widget-overlay")
                        for overlay in overlays:
                            driver.execute_script("arguments[0].style.display = 'none';", overlay)
                        
                        # Пытаемся кликнуть снова
                        time.sleep(1)
                        export_button.click()
                        click_success = True
                        print("Клик по кнопке экспорта выполнен (после закрытия оверлеев)")
                    except Exception as overlay_e:
                        print(f"Клик после закрытия оверлеев не сработал: {overlay_e}")
                        
                        # Способ 4: Scroll to element и клик
                        try:
                            driver.execute_script("arguments[0].scrollIntoView(true);", export_button)
                            time.sleep(1)
                            driver.execute_script("arguments[0].click();", export_button)
                            click_success = True
                            print("Клик по кнопке экспорта выполнен (с прокруткой)")
                        except Exception as scroll_e:
                            print(f"Клик с прокруткой не сработал: {scroll_e}")
            
            if not click_success:
                print("Все методы клика не сработали, пробуем альтернативный способ...")
                raise Exception("Не удалось кликнуть по кнопке экспорта")
            
            # Если клик успешен, ждем скачивания
            # Ждем появления файла с проверкой каждые 2 секунды
            print("Ждем загрузки файла...")
            max_wait_time = 60
            wait_interval = 2
            waited_time = 0
            
            downloaded_file_found = False
            
            while waited_time < max_wait_time:
                time.sleep(wait_interval)
                waited_time += wait_interval
                
                # Ищем скачанный файл (только оригинальное имя)
                downloaded_files = glob.glob(os.path.join(download_dir, "TradeWatch - raport konkurencji.xlsx"))
                if downloaded_files:
                    # Проверяем, что файл полностью скачался
                    latest_file = downloaded_files[0]
                    
                    # Ждем немного и проверяем, что размер файла не изменился
                    initial_size = os.path.getsize(latest_file)
                    time.sleep(3)
                    
                    try:
                        final_size = os.path.getsize(latest_file)
                        if initial_size == final_size and final_size > 0:
                            print(f"Файл для группы {batch_number} загружен: {latest_file} (размер: {final_size} байт)")
                            downloaded_file_found = True
                            break
                        else:
                            print(f"Файл еще скачивается... (размер: {final_size} байт)")
                    except:
                        print(f"Файл заблокирован, продолжаем ждать...")
                        continue
                else:
                    print(f"Ожидание файла... ({waited_time}/{max_wait_time} сек)")
            
            if downloaded_file_found:
                # Переименовываем файл для идентификации
                new_filename = f"TradeWatch_batch_{batch_number}.xlsx"
                new_filepath = os.path.join(download_dir, new_filename)
                
                # Проверяем, что новый файл действительно отличается от существующего
                if os.path.exists(new_filepath):
                    try:
                        existing_size = os.path.getsize(new_filepath)
                        new_size = os.path.getsize(latest_file)
                        
                        if existing_size == new_size:
                            print(f"Файл {new_filepath} уже существует с таким же размером ({existing_size} байт), пропускаем...")
                            # Удаляем загруженный файл, так как он дублирует существующий
                            os.remove(latest_file)
                            return new_filepath
                        else:
                            print(f"Существующий файл {new_filepath} имеет другой размер ({existing_size} vs {new_size} байт), заменяем...")
                            os.remove(new_filepath)
                    except Exception as rm_e:
                        print(f"Не удалось удалить существующий файл {new_filepath}: {rm_e}")
                
                # Переименовываем файл
                try:
                    os.rename(latest_file, new_filepath)
                    print(f"Файл переименован: {latest_file} -> {new_filepath}")
                    return new_filepath
                except Exception as rename_e:
                    print(f"Ошибка при переименовании файла: {rename_e}")
                    return None
            else:
                print(f"Файл для группы {batch_number} не найден после {max_wait_time} секунд ожидания")
                return None
                
        except Exception as export_error:
            print(f"Ошибка при экспорте группы {batch_number}: {export_error}")
            
            # Дополнительная попытка с альтернативными методами
            try:
                # Попытка найти кнопку по другим селекторам
                alternative_buttons = [
                    (By.CSS_SELECTOR, "a.icon-excel"),
                    (By.CSS_SELECTOR, "a[onclick*='j_idt133']"),
                    (By.XPATH, "//a[contains(@class, 'icon-excel')]"),
                    (By.XPATH, "//a[contains(@onclick, 'j_idt133')]")
                ]
                
                button_found = False
                for selector_type, selector in alternative_buttons:
                    try:
                        alt_button = driver.find_element(selector_type, selector)
                        
                        # Удаляем оверлеи
                        driver.execute_script("""
                            var overlays = document.querySelectorAll('.ui-widget-overlay');
                            for (var i = 0; i < overlays.length; i++) {
                                overlays[i].style.display = 'none';
                            }
                        """)
                        
                        # Прокручиваем к элементу
                        driver.execute_script("arguments[0].scrollIntoView(true);", alt_button)
                        time.sleep(1)
                        
                        # Используем JavaScript для клика
                        driver.execute_script("arguments[0].click();", alt_button)
                        
                        print(f"Альтернативный метод клика сработал для группы {batch_number}")
                        button_found = True
                        break
                        
                    except Exception as alt_e:
                        continue
                
                if not button_found:
                    print(f"Все альтернативные методы не сработали для группы {batch_number}")
                    return None
                    
                # Если альтернативный метод сработал, ждем файл
                print("Ждем загрузки файла...")
                max_wait_time = 60
                wait_interval = 2
                waited_time = 0
                
                downloaded_file_found = False
                
                while waited_time < max_wait_time:
                    time.sleep(wait_interval)
                    waited_time += wait_interval
                    
                    # Ищем скачанный файл
                    downloaded_files = glob.glob(os.path.join(download_dir, "TradeWatch - raport konkurencji.xlsx"))
                    if downloaded_files:
                        latest_file = downloaded_files[0]
                        
                        initial_size = os.path.getsize(latest_file)
                        time.sleep(3)
                        
                        try:
                            final_size = os.path.getsize(latest_file)
                            if initial_size == final_size and final_size > 0:
                                print(f"Файл для группы {batch_number} загружен: {latest_file} (размер: {final_size} байт)")
                                downloaded_file_found = True
                                break
                        except:
                            continue
                    else:
                        print(f"Ожидание файла... ({waited_time}/{max_wait_time} сек)")
                
                if downloaded_file_found:
                    new_filename = f"TradeWatch_batch_{batch_number}.xlsx"
                    new_filepath = os.path.join(download_dir, new_filename)
                    
                    # Проверяем, что новый файл действительно отличается от существующего
                    if os.path.exists(new_filepath):
                        try:
                            existing_size = os.path.getsize(new_filepath)
                            new_size = os.path.getsize(latest_file)
                            
                            if existing_size == new_size:
                                print(f"Файл {new_filepath} уже существует с таким же размером ({existing_size} байт), пропускаем...")
                                # Удаляем загруженный файл, так как он дублирует существующий
                                os.remove(latest_file)
                                return new_filepath
                            else:
                                print(f"Существующий файл {new_filepath} имеет другой размер ({existing_size} vs {new_size} байт), заменяем...")
                                os.remove(new_filepath)
                        except Exception as rm_e:
                            print(f"Не удалось удалить существующий файл {new_filepath}: {rm_e}")
                    
                    # Переименовываем файл
                    try:
                        os.rename(latest_file, new_filepath)
                        print(f"Файл переименован: {latest_file} -> {new_filepath}")
                        return new_filepath
                    except Exception as rename_e:
                        print(f"Ошибка при переименовании файла: {rename_e}")
                        return None
                else:
                    return None
                    
            except Exception as alt_error:
                print(f"Альтернативный метод тоже не сработал для группы {batch_number}: {alt_error}")
                return None
        
    except Exception as e:
        print(f"Ошибка при обработке группы {batch_number}: {e}")
        return None


def process_supplier_file_with_tradewatch(supplier_file_path, download_dir, headless=True, progress_callback=None):
    """
    Обрабатывает файл поставщика: извлекает EAN коды, 
    разбивает на группы и получает данные из TradeWatch
    КАЖДАЯ ГРУППА обрабатывается в НОВОЙ сессии браузера для исключения кеширования
    
    Args:
        supplier_file_path: путь к файлу поставщика
        download_dir: папка для скачивания файлов TradeWatch
        headless: запуск в headless режиме (True) или с GUI (False)
        progress_callback: функция для отслеживания прогресса
    
    Returns:
        list: список путей к скачанным файлам TradeWatch
    """
    try:
        # Читаем файл поставщика
        print(f"Читаем файл поставщика: {supplier_file_path}")
        df = pd.read_excel(supplier_file_path)
        
        # Проверяем наличие необходимых колонок
        if 'GTIN' not in df.columns:
            print("Ошибка: В файле поставщика нет колонки GTIN")
            return []
        
        if 'Price' not in df.columns:
            print("Ошибка: В файле поставщика нет колонки Price")
            return []
        
        # Извлекаем EAN коды
        ean_codes = df['GTIN'].dropna().astype(str).tolist()
        # Удаляем пустые и некорректные коды
        ean_codes = [code.strip() for code in ean_codes if code.strip() and code.strip() != 'nan']
        
        print(f"Найдено {len(ean_codes)} EAN кодов в файле поставщика")
        
        if not ean_codes:
            print("Нет EAN кодов для обработки")
            return []
        
        # Разбиваем на группы оптимального размера
        batch_size = get_batch_size()
        batches = [ean_codes[i:i + batch_size] for i in range(0, len(ean_codes), batch_size)]
        
        print(f"Разбиваем на {len(batches)} групп по {batch_size} кодов")
        
        # Создаем папку для скачивания если её нет
        download_path = Path(download_dir)
        download_path.mkdir(parents=True, exist_ok=True)
        
        # Очищаем все старые файлы TradeWatch перед началом обработки
        print("Очищаем старые файлы TradeWatch...")
        old_files_patterns = [
            "TradeWatch - raport konkurencji*.xlsx",
            "TradeWatch_raport_konkurencji_*.xlsx"
        ]
        
        for pattern in old_files_patterns:
            old_files = glob.glob(os.path.join(download_dir, pattern))
            for old_file in old_files:
                try:
                    os.remove(old_file)
                    print(f"Удален старый файл: {old_file}")
                except Exception as e:
                    print(f"Не удалось удалить файл {old_file}: {e}")
                    pass
        
        # 🔥 КРИТИЧЕСКОЕ ИЗМЕНЕНИЕ: Обрабатываем каждую группу в новой сессии браузера
        print(f"🔥 НОВАЯ ЛОГИКА: Каждая группа обрабатывается в отдельной сессии браузера")
        downloaded_files = []
        processed_count = 0
        
        for i, batch in enumerate(batches, 1):
            print(f"\n🆕 СОЗДАЕМ НОВУЮ СЕССИЮ БРАУЗЕРА для группы {i}/{len(batches)}")
            
            # Очищаем временные директории Chrome перед новой сессией
            cleanup_chrome_temp_dirs()
            
            # Обрабатываем группу в новой сессии браузера
            result = process_batch_with_new_browser(batch, download_dir, i, headless)
            
            if result:
                downloaded_files.append(result)
                processed_count += len(batch)
                print(f"✅ Группа {i} обработана успешно в новой сессии")
                
                # Обновляем прогресс через callback
                if progress_callback:
                    try:
                        progress_callback(processed_count)
                    except Exception as e:
                        print(f"Ошибка в progress_callback: {e}")
            else:
                print(f"❌ Ошибка при обработке группы {i} в новой сессии")
        
        print(f"\n🏁 Обработка завершена. Загружено {len(downloaded_files)} файлов из {len(batches)} групп")
        
        # Проверяем, что все файлы существуют
        print("Проверка существования файлов:")
        existing_files = []
        for i, file_path in enumerate(downloaded_files):
            if os.path.exists(file_path):
                size = os.path.getsize(file_path)
                print(f"  ✅ {file_path} (размер: {size} байт)")
                existing_files.append(file_path)
            else:
                print(f"  ❌ {file_path} - НЕ НАЙДЕН!")
        
        # КРИТИЧЕСКИ ВАЖНО: Проверяем уникальность содержимого
        if existing_files:
            verify_batch_uniqueness(existing_files)
        
        return downloaded_files
        
    except Exception as e:
        print(f"Ошибка при обработке файла поставщика: {e}")
        return []


def process_batch_with_new_browser(ean_codes_batch, download_dir, batch_number, headless=True):
    """
    🔥 НОВАЯ ФУНКЦИЯ: Обрабатывает группу EAN кодов в НОВОЙ сессии браузера
    Это гарантированно исключает любое кеширование между группами
    
    Args:
        ean_codes_batch: список EAN кодов для обработки
        download_dir: папка для скачивания файлов
        batch_number: номер группы для идентификации файла
        headless: запуск в headless режиме (True) или с GUI (False)
    
    Returns:
        str: путь к скачанному файлу или None если ошибка
    """
    if not ean_codes_batch:
        print("Пустая группа EAN кодов")
        return None
    
    # Настройка драйвера Chrome для НОВОЙ сессии
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    if headless:
        options.add_argument("--headless")
    
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-logging")
    options.add_argument("--disable-web-security")
    options.add_argument("--allow-running-insecure-content")
    
    # 🔥 КРИТИЧЕСКИ ВАЖНО: Отключаем ВСЕ виды кеширования
    options.add_argument("--disable-application-cache")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-features=TranslateUI")
    options.add_argument("--disable-ipc-flooding-protection")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-default-apps")
    options.add_argument("--disable-sync")
    options.add_argument("--disable-translate")
    options.add_argument("--hide-scrollbars")
    options.add_argument("--metrics-recording-only")
    options.add_argument("--no-first-run")
    options.add_argument("--safebrowsing-disable-auto-update")
    options.add_argument("--disable-plugins")
    options.add_argument("--disable-plugins-discovery")
    options.add_argument("--disable-preconnect")
    
    # Настройка для автоматической загрузки файлов
    download_path = Path(download_dir)
    prefs = {
        "download.default_directory": str(download_path.absolute()),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    options.add_experimental_option("prefs", prefs)
    
    # 🆕 СОЗДАЕМ НОВЫЙ ДРАЙВЕР для каждой группы
    service = get_chrome_service()
    driver = webdriver.Chrome(service=service, options=options)
    
    try:
        print(f"🔥 НОВАЯ СЕССИЯ: Обрабатываем группу {batch_number} с {len(ean_codes_batch)} EAN кодами")
        
        # Форматируем EAN коды в 13-цифровой формат
        formatted_ean_codes = []
        for code in ean_codes_batch:
            formatted_code = format_ean_to_13_digits(code)
            if formatted_code:
                formatted_ean_codes.append(formatted_code)
        
        if not formatted_ean_codes:
            print("Нет валидных EAN кодов после форматирования")
            return None
        
        print(f"Отформатировано {len(formatted_ean_codes)} EAN кодов в 13-цифровой формат")
        
        # Соединяем отформатированные EAN коды в одну строку через пробел
        ean_codes_string = ' '.join(formatted_ean_codes)
        print(f"🔍 DEBUG: EAN коды для группы {batch_number}: {ean_codes_string[:100]}...")
        
        # Переход на страницу входа
        driver.get("https://tradewatch.pl/login.jsf")
        
        # Ждем загрузки страницы
        wait = WebDriverWait(driver, 15)
        
        # Ищем поле для email
        email_field = wait.until(EC.presence_of_element_located((By.NAME, "j_username")))
        
        # Вводим email
        email_field.clear()
        email_field.send_keys(TRADEWATCH_EMAIL)
        
        # Ищем поле для пароля
        password_field = driver.find_element(By.NAME, "j_password")
        
        # Вводим пароль
        password_field.clear()
        password_field.send_keys(TRADEWATCH_PASSWORD)
        
        # Ищем кнопку входа
        login_button = driver.find_element(By.NAME, "btnLogin")
        
        # Нажимаем кнопку входа
        login_button.click()
        
        # Ждем немного после входа
        time.sleep(3)
        
        # Проверяем успешность входа
        current_url = driver.current_url
        
        if "login.jsf" in current_url:
            print(f"❌ Ошибка при входе в систему для группы {batch_number}")
            return None
        
        print(f"✅ Успешный вход в систему для группы {batch_number}!")
        
        # Переходим на страницу EAN Price Report
        driver.get("https://tradewatch.pl/report/ean-price-report.jsf")
        time.sleep(3)
        
        # Ищем поле для ввода EAN кодов
        ean_field = wait.until(EC.presence_of_element_located((By.ID, "eansPhrase")))
        
        # Проверяем, что поле изначально пустое (должно быть в новой сессии)
        initial_value = ean_field.get_attribute("value")
        if initial_value and initial_value.strip():
            print(f"🚨 КРИТИЧЕСКАЯ ОШИБКА: Поле не пустое в новой сессии! Содержимое: '{initial_value}'")
            return None
        else:
            print(f"✅ Поле изначально пустое в новой сессии для группы {batch_number}")
        
        # Вставляем EAN коды (поле уже должно быть пустым)
        ean_field.send_keys(ean_codes_string)
        
        # Проверяем, что вставились именно наши коды
        inserted_value = ean_field.get_attribute("value")
        inserted_codes = inserted_value.strip().split() if inserted_value else []
        expected_codes = ean_codes_string.strip().split()
        
        if len(inserted_codes) != len(expected_codes):
            print(f"⚠️ Количество вставленных кодов ({len(inserted_codes)}) не совпадает с ожидаемым ({len(expected_codes)})")
            return None
        
        print(f"✅ Вставлено {len(inserted_codes)} EAN кодов для группы {batch_number}")
        
        # Ждем немного
        time.sleep(1)
        
        # Ищем кнопку "Generuj"
        generate_button = driver.find_element(By.ID, "j_idt703")
        
        # Нажимаем кнопку
        generate_button.click()
        
        # Ждем обработки
        print(f"⏳ Ждем обработки запроса для группы {batch_number}...")
        time.sleep(5)
        
        # Ждем появления результатов
        print(f"⏳ Ждем появления результатов для группы {batch_number}...")
        time.sleep(3)
        
        # Очищаем старые файлы перед скачиванием
        old_files = glob.glob(os.path.join(download_dir, "TradeWatch - raport konkurencji.xlsx"))
        for old_file in old_files:
            try:
                os.remove(old_file)
            except:
                pass
        
        # Ищем кнопку "Eksport do XLS"
        export_button = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Eksport do XLS")))
        
        # Нажимаем кнопку экспорта
        export_button.click()
        
        # Ждем загрузки файла
        print(f"⏳ Ждем загрузки файла для группы {batch_number}...")
        max_wait_time = 60
        wait_interval = 2
        waited_time = 0
        
        downloaded_file_found = False
        
        while waited_time < max_wait_time:
            time.sleep(wait_interval)
            waited_time += wait_interval
            
            # Ищем скачанный файл
            downloaded_files = glob.glob(os.path.join(download_dir, "TradeWatch - raport konkurencji.xlsx"))
            if downloaded_files:
                latest_file = downloaded_files[0]
                
                # Проверяем стабильность размера файла
                initial_size = os.path.getsize(latest_file)
                time.sleep(3)
                
                try:
                    final_size = os.path.getsize(latest_file)
                    if initial_size == final_size and final_size > 0:
                        print(f"✅ Файл для группы {batch_number} загружен: {latest_file} (размер: {final_size} байт)")
                        downloaded_file_found = True
                        break
                    else:
                        print(f"⏳ Файл еще скачивается... (размер: {final_size} байт)")
                except:
                    print(f"⏳ Файл заблокирован, продолжаем ждать...")
                    continue
            else:
                print(f"⏳ Ожидание файла... ({waited_time}/{max_wait_time} сек)")
        
        if downloaded_file_found:
            # Переименовываем файл с оригинальным названием и датой/временем
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_filename = f"TradeWatch_raport_konkurencji_{timestamp}.xlsx"
            new_filepath = os.path.join(download_dir, new_filename)
            
            # Убеждаемся, что целевой файл не существует
            if os.path.exists(new_filepath):
                try:
                    os.remove(new_filepath)
                    print(f"🗑️ Удален существующий файл: {new_filepath}")
                except Exception as rm_e:
                    print(f"❌ Не удалось удалить существующий файл {new_filepath}: {rm_e}")
            
            # Переименовываем файл
            try:
                os.rename(latest_file, new_filepath)
                print(f"✅ Файл переименован: {latest_file} -> {new_filepath}")
                return new_filepath
            except Exception as rename_e:
                print(f"❌ Ошибка при переименовании файла: {rename_e}")
                return None
        else:
            print(f"❌ Файл для группы {batch_number} не найден после {max_wait_time} секунд ожидания")
            return None
            
    except Exception as e:
        print(f"❌ Ошибка при обработке группы {batch_number} в новой сессии: {e}")
        return None
    
    finally:
        # 🔥 КРИТИЧЕСКИ ВАЖНО: Закрываем браузер после каждой группы
        print(f"🔒 Закрываем браузер для группы {batch_number}")
        driver.quit()


def process_supplier_file_with_tradewatch_old_version(supplier_file_path, download_dir, headless=True):
    """
    Обрабатывает файл поставщика: извлекает EAN коды, 
    разбивает на группы и получает данные из TradeWatch
    Использует одну сессию браузера для всех групп
    
    Args:
        supplier_file_path: путь к файлу поставщика
        download_dir: папка для скачивания файлов TradeWatch
        headless: запуск в headless режиме (True) или с GUI (False)
    
    Returns:
        list: список путей к скачанным файлам TradeWatch
    """
    try:
        # Читаем файл поставщика
        print(f"Читаем файл поставщика: {supplier_file_path}")
        df = pd.read_excel(supplier_file_path)
        
        # Проверяем наличие необходимых колонок
        if 'GTIN' not in df.columns:
            print("Ошибка: В файле поставщика нет колонки GTIN")
            return []
        
        if 'Price' not in df.columns:
            print("Ошибка: В файле поставщика нет колонки Price")
            return []
        
        # Извлекаем EAN коды
        ean_codes = df['GTIN'].dropna().astype(str).tolist()
        # Удаляем пустые и некорректные коды
        ean_codes = [code.strip() for code in ean_codes if code.strip() and code.strip() != 'nan']
        
        print(f"Найдено {len(ean_codes)} EAN кодов в файле поставщика")
        
        if not ean_codes:
            print("Нет EAN кодов для обработки")
            return []
        
        # Разбиваем на группы оптимального размера
        batch_size = get_batch_size()
        batches = [ean_codes[i:i + batch_size] for i in range(0, len(ean_codes), batch_size)]
        
        print(f"Разбиваем на {len(batches)} групп по {batch_size} кодов")
        
        # Создаем папку для скачивания если её нет
        download_path = Path(download_dir)
        download_path.mkdir(parents=True, exist_ok=True)
        
        # Очищаем все старые файлы TradeWatch перед началом обработки
        print("Очищаем старые файлы TradeWatch...")
        old_files_patterns = [
            "TradeWatch - raport konkurencji*.xlsx",
            "TradeWatch_raport_konkurencji_*.xlsx"
        ]
        
        for pattern in old_files_patterns:
            old_files = glob.glob(os.path.join(download_dir, pattern))
            for old_file in old_files:
                try:
                    os.remove(old_file)
                    print(f"Удален старый файл: {old_file}")
                except Exception as e:
                    print(f"Не удалось удалить файл {old_file}: {e}")
                    pass
        
        # Настройка драйвера Chrome один раз
        options = webdriver.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        if headless:
            options.add_argument("--headless")
        
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-logging")
        options.add_argument("--disable-web-security")
        options.add_argument("--allow-running-insecure-content")
        
        # Настройка для автоматической загрузки файлов
        prefs = {
            "download.default_directory": str(download_path.absolute()),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        options.add_experimental_option("prefs", prefs)
        
        # Инициализация драйвера один раз
        service = get_chrome_service()
        driver = webdriver.Chrome(service=service, options=options)
        
        try:
            print("Запускаем браузер и выполняем вход в систему...")
            
            # Переход на страницу входа
            driver.get("https://tradewatch.pl/login.jsf")
            
            # Ждем загрузки страницы
            wait = WebDriverWait(driver, 10)
            
            # Ищем поле для email
            email_field = wait.until(EC.presence_of_element_located((By.NAME, "j_username")))
            
            # Вводим email
            email_field.clear()
            email_field.send_keys(TRADEWATCH_EMAIL)
            
            # Ищем поле для пароля
            password_field = driver.find_element(By.NAME, "j_password")
            
            # Вводим пароль
            password_field.clear()
            password_field.send_keys(TRADEWATCH_PASSWORD)
            
            # Ищем кнопку входа
            login_button = driver.find_element(By.NAME, "btnLogin")
            
            # Нажимаем кнопку входа
            login_button.click()
            
            # Ждем немного после входа
            time.sleep(3)
            
            # Проверяем успешность входа
            current_url = driver.current_url
            
            if "login.jsf" in current_url:
                print("Ошибка при входе в систему")
                return []
            
            print("✅ Успешный вход в систему! Начинаем обработку групп...")
            
            # Обрабатываем группы последовательно в одной сессии (стабильный подход)
            print(f"Обрабатываем {len(batches)} групп последовательно в одной сессии")
            downloaded_files = []
            
            for i, batch in enumerate(batches, 1):
                print(f"\nОбрабатываем группу {i}/{len(batches)} ({len(batch)} EAN кодов)")
                
                # Проверяем, что файл группы уже не существует
                target_filename = f"TradeWatch_batch_{i}.xlsx"
                target_filepath = os.path.join(download_dir, target_filename)
                
                if os.path.exists(target_filepath):
                    existing_size = os.path.getsize(target_filepath)
                    if existing_size > 0:
                        print(f"Файл группы {i} уже существует ({existing_size} байт), пропускаем обработку...")
                        downloaded_files.append(target_filepath)
                        continue
                
                # Очищаем старые файлы перед обработкой группы
                # Удаляем файлы с оригинальным именем
                old_files = glob.glob(os.path.join(download_dir, "TradeWatch - raport konkurencji.xlsx"))
                for old_file in old_files:
                    try:
                        os.remove(old_file)
                        print(f"Удален старый файл: {old_file}")
                    except:
                        pass
                
                # Также удаляем файл с целевым именем, если он существует
                if os.path.exists(target_filepath):
                    try:
                        os.remove(target_filepath)
                        print(f"Удален существующий файл: {target_filepath}")
                    except:
                        pass
                
                # Обрабатываем группу в той же сессии
                result = process_batch_in_session(driver, batch, download_dir, i)
                
                if result:
                    downloaded_files.append(result)
                    print(f"✅ Группа {i} обработана успешно")
                else:
                    print(f"❌ Ошибка при обработке группы {i}")
                
                # КРИТИЧЕСКИ ВАЖНАЯ пауза между группами для полного сброса
                if i < len(batches):
                    print(f"🔄 ВАЖНАЯ ПАУЗА между группами {i} и {i+1} для предотвращения дублирования...")
                    time.sleep(5)  # Увеличиваем до 5 секунд для полного сброса
                    
                    # Дополнительная очистка кеша браузера между группами
                    driver.execute_script("localStorage.clear(); sessionStorage.clear();")
                    print(f"🧹 Очищен кеш браузера между группами {i} и {i+1}")
            
            print(f"\nОбработка завершена. Загружено {len(downloaded_files)} файлов из {len(batches)} групп")
            
            # Проверяем, что все файлы существуют
            print("Проверка существования файлов:")
            existing_files = []
            for i, file_path in enumerate(downloaded_files):
                if os.path.exists(file_path):
                    size = os.path.getsize(file_path)
                    print(f"  ✅ {file_path} (размер: {size} байт)")
                    existing_files.append(file_path)
                else:
                    print(f"  ❌ {file_path} - НЕ НАЙДЕН!")
            
            # КРИТИЧЕСКИ ВАЖНО: Проверяем уникальность содержимого
            if existing_files:
                verify_batch_uniqueness(existing_files)
            
            return downloaded_files
            
        finally:
            # Закрываем браузер в конце
            print("Закрываем браузер...")
            driver.quit()
        
    except Exception as e:
        print(f"Ошибка при обработке файла поставщика: {e}")
        return []


def login_to_tradewatch():
    """
    Оригинальная функция для совместимости (устарела)
    """
    print("Эта функция устарела. Используйте process_supplier_file_with_tradewatch()")
    pass


def process_multiple_batches_parallel(main_driver, ean_groups, download_dir, max_parallel=4):
    """
    Обрабатывает несколько групп EAN кодов параллельно в отдельных браузерах
    
    Args:
        main_driver: основной веб-драйвер (не используется, но нужен для совместимости)
        ean_groups: список групп EAN кодов
        download_dir: папка для скачивания файлов
        max_parallel: максимальное количество параллельных браузеров
    
    Returns:
        list: список путей к скачанным файлам
    """
    results = []
    
    # Обрабатываем группы по 4 штуки
    for i in range(0, len(ean_groups), max_parallel):
        batch_to_process = ean_groups[i:i + max_parallel]
        
        print(f"Обрабатываем параллельно группы {i+1}-{min(i+max_parallel, len(ean_groups))}")
        
        # Используем потоки для параллельной обработки с отдельными браузерами
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_parallel) as executor:
            futures = []
            
            for j, group in enumerate(batch_to_process):
                batch_number = i + j + 1
                future = executor.submit(
                    process_batch_in_separate_browser, 
                    group, 
                    download_dir, 
                    batch_number
                )
                futures.append(future)
            
            # Собираем результаты
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception as e:
                    print(f"Ошибка при обработке группы: {e}")
        
        if i + max_parallel < len(ean_groups):
            print("Пауза между пакетами групп...")
            time.sleep(3)
    
    return results


def process_batch_in_separate_browser(ean_codes_batch, download_dir, batch_number):
    """
    Обрабатывает группу EAN кодов в отдельном браузере
    
    Args:
        ean_codes_batch: список EAN кодов для обработки
        download_dir: папка для скачивания файлов
        batch_number: номер группы
    
    Returns:
        str: путь к скачанному файлу или None
    """
    driver = None
    try:
        # Создаем отдельный браузер для этой группы
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from webdriver_manager.chrome import ChromeDriverManager
        from selenium.webdriver.chrome.service import Service
        
        # Настройки Chrome
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        # Настройки загрузки
        prefs = {
            "download.default_directory": download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        # Создаем драйвер
        service = get_chrome_service()
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        print(f"Создан браузер для группы {batch_number}")
        
        # Вход в систему
        driver.get("https://tradewatch.pl/login.jsf")
        
        # Ждем загрузки страницы
        wait = WebDriverWait(driver, 20)
        
        # Вводим логин
        username_field = wait.until(EC.presence_of_element_located((By.NAME, "username")))
        username_field.clear()
        username_field.send_keys(TRADEWATCH_EMAIL)
        
        # Вводим пароль
        password_field = driver.find_element(By.NAME, "password")
        password_field.clear()
        password_field.send_keys(TRADEWATCH_PASSWORD)
        
        # Нажимаем кнопку входа
        login_button = driver.find_element(By.NAME, "btnLogin")
        login_button.click()
        
        time.sleep(3)
        
        # Проверяем успешность входа
        current_url = driver.current_url
        if "login.jsf" in current_url:
            print(f"Ошибка при входе в систему для группы {batch_number}")
            return None
            
        print(f"Успешный вход для группы {batch_number}")
        
        # Переходим на страницу EAN Price Report
        driver.get("https://tradewatch.pl/report/ean-price-report.jsf")
        
        # Соединяем EAN коды в одну строку
        ean_codes_string = ' '.join(str(code) for code in ean_codes_batch)
        
        # Ищем текстовое поле для ввода EAN кодов
        ean_input = wait.until(EC.presence_of_element_located((By.ID, "report_form:ean_codes")))
        ean_input.clear()
        ean_input.send_keys(ean_codes_string)
        
        print(f"Вставлены EAN коды для группы {batch_number}: {len(ean_codes_batch)} кодов")
        
        # Нажимаем кнопку "Szukaj"
        search_button = wait.until(EC.element_to_be_clickable((By.ID, "report_form:search_button")))
        search_button.click()
        
        print(f"Ждем обработки запроса для группы {batch_number}...")
        time.sleep(5)
        
        # Ждем появления результатов
        wait.until(EC.presence_of_element_located((By.ID, "report_form:results")))
        print(f"Ждем появления результатов для группы {batch_number}...")
        time.sleep(3)
        
        # Экспортируем результаты
        return export_results_for_separate_browser(driver, download_dir, batch_number, wait)
        
    except Exception as e:
        print(f"Ошибка при обработке группы {batch_number}: {e}")
        return None
    finally:
        # Обязательно закрываем браузер
        if driver:
            try:
                driver.quit()
                print(f"Браузер для группы {batch_number} закрыт")
            except:
                pass


def export_results_for_separate_browser(driver, download_dir, batch_number, wait):
    """
    Экспортирует результаты для отдельного браузера
    """
    try:
        # Очищаем старые файлы
        old_files = glob.glob(os.path.join(download_dir, "TradeWatch - raport konkurencji*.xlsx"))
        for old_file in old_files:
            try:
                os.remove(old_file)
            except:
                pass
        
        export_button = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Eksport do XLS")))
        
        # Пытаемся кликнуть разными способами
        click_success = False
        
        # Способ 1: Обычный клик
        try:
            export_button.click()
            click_success = True
            print(f"Клик по кнопке экспорта выполнен для группы {batch_number} (обычный клик)")
        except Exception as e:
            print(f"Обычный клик не сработал для группы {batch_number}: {e}")
            
            # Способ 2: JavaScript клик
            try:
                driver.execute_script("arguments[0].click();", export_button)
                click_success = True
                print(f"Клик по кнопке экспорта выполнен для группы {batch_number} (JavaScript клик)")
            except Exception as js_e:
                print(f"JavaScript клик не сработал для группы {batch_number}: {js_e}")
                
                # Способ 3: Закрываем оверлеи
                try:
                    overlays = driver.find_elements(By.CLASS_NAME, "ui-widget-overlay")
                    for overlay in overlays:
                        driver.execute_script("arguments[0].style.display = 'none';", overlay)
                    
                    time.sleep(1)
                    export_button.click()
                    click_success = True
                    print(f"Клик по кнопке экспорта выполнен для группы {batch_number} (после закрытия оверлеев)")
                except Exception as overlay_e:
                    print(f"Клик после закрытия оверлеев не сработал для группы {batch_number}: {overlay_e}")
        
        if not click_success:
            print(f"Все методы клика не сработали для группы {batch_number}")
            return None
        
        # Ждем загрузки файла
        print(f"Ждем загрузки файла для группы {batch_number}...")
        return wait_for_download_separate_browser(download_dir, batch_number)
        
    except Exception as e:
        print(f"Ошибка при экспорте группы {batch_number}: {e}")
        return None


def wait_for_download_separate_browser(download_dir, batch_number):
    """
    Ждет загрузки файла для отдельного браузера
    """
    max_wait_time = 60
    wait_interval = 2
    waited_time = 0
    
    while waited_time < max_wait_time:
        time.sleep(wait_interval)
        waited_time += wait_interval
        
        # Ищем скачанный файл
        downloaded_files = glob.glob(os.path.join(download_dir, "TradeWatch - raport konkurencji*.xlsx"))
        if downloaded_files:
            # Берем самый новый файл
            latest_file = max(downloaded_files, key=os.path.getctime)
            
            # Проверяем стабильность размера
            initial_size = os.path.getsize(latest_file)
            time.sleep(3)
            
            try:
                final_size = os.path.getsize(latest_file)
                if initial_size == final_size and final_size > 0:
                    print(f"Файл для группы {batch_number} загружен: {latest_file} (размер: {final_size} байт)")
                    
                    # Переименовываем файл
                    new_filename = f"TradeWatch_batch_{batch_number}.xlsx"
                    new_filepath = os.path.join(download_dir, new_filename)
                    
                    if os.path.exists(new_filepath):
                        os.remove(new_filepath)
                    
                    os.rename(latest_file, new_filepath)
                    return new_filepath
                else:
                    print(f"Файл для группы {batch_number} еще скачивается... (размер: {final_size} байт)")
            except:
                print(f"Файл для группы {batch_number} заблокирован, продолжаем ждать...")
                continue
        else:
            print(f"Ожидание файла для группы {batch_number}... ({waited_time}/{max_wait_time} сек)")
    
    print(f"Файл для группы {batch_number} не найден после {max_wait_time} секунд ожидания")
    return None


def process_supplier_file_with_tradewatch_interruptible(supplier_file_path, download_dir, stop_flag_callback=None, progress_callback=None, headless=True):
    """
    Обрабатывает файл поставщика с возможностью остановки процесса
    
    Args:
        supplier_file_path: путь к файлу поставщика
        download_dir: папка для скачивания файлов TradeWatch
        stop_flag_callback: функция для проверки флага остановки
        progress_callback: функция для обновления прогресса
        headless: запуск в headless режиме (True) или с GUI (False)
    
    Returns:
        list: список путей к скачанным файлам TradeWatch
    """
    try:
        # Читаем файл поставщика
        print(f"Читаем файл поставщика: {supplier_file_path}")
        df = pd.read_excel(supplier_file_path)
        
        # Проверяем наличие необходимых колонок
        if 'GTIN' not in df.columns:
            print("Ошибка: В файле поставщика нет колонки GTIN")
            return []
        
        if 'Price' not in df.columns:
            print("Ошибка: В файле поставщика нет колонки Price")
            return []
        
        # Извлекаем EAN коды
        ean_codes = df['GTIN'].dropna().astype(str).tolist()
        # Удаляем пустые и некорректные коды
        ean_codes = [code.strip() for code in ean_codes if code.strip() and code.strip() != 'nan']
        
        print(f"Найдено {len(ean_codes)} EAN кодов в файле поставщика")
        
        if not ean_codes:
            print("Нет EAN кодов для обработки")
            return []
        
        # Разбиваем на группы оптимального размера
        batch_size = get_batch_size()
        batches = [ean_codes[i:i + batch_size] for i in range(0, len(ean_codes), batch_size)]
        
        print(f"Разбиваем на {len(batches)} групп по {batch_size} кодов")
        
        # Создаем папку для скачивания если её нет
        download_path = Path(download_dir)
        download_path.mkdir(parents=True, exist_ok=True)
        
        # Очищаем все старые файлы TradeWatch перед началом обработки
        print("Очищаем старые файлы TradeWatch...")
        old_files_patterns = [
            "TradeWatch - raport konkurencji*.xlsx",
            "TradeWatch_raport_konkurencji_*.xlsx"
        ]
        
        for pattern in old_files_patterns:
            old_files = glob.glob(os.path.join(download_dir, pattern))
            for old_file in old_files:
                try:
                    os.remove(old_file)
                    print(f"Удален старый файл: {old_file}")
                except Exception as e:
                    print(f"Не удалось удалить файл {old_file}: {e}")
                    pass
        
        # Обрабатываем каждую группу в отдельной сессии браузера
        print(f"🔥 НОВАЯ ЛОГИКА: Каждая группа обрабатывается в отдельной сессии браузера")
        downloaded_files = []
        
        for i, batch in enumerate(batches, 1):
            # Проверяем флаг остановки
            if stop_flag_callback and stop_flag_callback():
                print(f"🛑 Получен сигнал остановки. Прерываем обработку на группе {i}/{len(batches)}")
                break
            
            # Обновляем прогресс
            if progress_callback:
                progress_callback(f"🔄 Обрабатываю группу {i}/{len(batches)} ({len(batch)} EAN кодов)...")
            
            print(f"\n🆕 СОЗДАЕМ НОВУЮ СЕССИЮ БРАУЗЕРА для группы {i}/{len(batches)}")
            
            # Очищаем временные директории Chrome перед новой сессией
            cleanup_chrome_temp_dirs()
            
            # Обрабатываем группу в новой сессии браузера
            result = process_batch_with_new_browser(batch, download_dir, i, headless)
            
            if result:
                downloaded_files.append(result)
                print(f"✅ Группа {i} обработана успешно в новой сессии")
            else:
                print(f"❌ Ошибка при обработке группы {i} в новой сессии")
        
        if stop_flag_callback and stop_flag_callback():
            print(f"\n🛑 Процесс остановлен пользователем. Обработано {len(downloaded_files)} из {len(batches)} групп")
        else:
            print(f"\n🏁 Обработка завершена. Загружено {len(downloaded_files)} файлов из {len(batches)} групп")
        
        # Проверяем, что все файлы существуют
        print("Проверка существования файлов:")
        existing_files = []
        for i, file_path in enumerate(downloaded_files):
            if os.path.exists(file_path):
                size = os.path.getsize(file_path)
                print(f"  ✅ {file_path} (размер: {size} байт)")
                existing_files.append(file_path)
            else:
                print(f"  ❌ {file_path} - НЕ НАЙДЕН!")
        
        # Проверяем уникальность содержимого
        if existing_files:
            verify_batch_uniqueness(existing_files)
        
        return downloaded_files
        
    except Exception as e:
        print(f"Ошибка при обработке файла поставщика: {e}")
        return []
