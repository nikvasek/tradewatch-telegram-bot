import logging
import os
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import zipfile
import time

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode
import pandas as pd

# Проверяем доступность Selenium и выбираем соответствующий модуль
try:
    from selenium import webdriver
    SELENIUM_AVAILABLE = True
    from tradewatch_login import process_supplier_file_with_tradewatch, get_parallel_sessions, get_batch_size
    print("✅ Selenium доступен - TradeWatch интеграция активна")
except ImportError:
    SELENIUM_AVAILABLE = False
    from tradewatch_fallback import download_from_tradewatch
    print("❌ Selenium недоступен - работаем без TradeWatch интеграции")

# Импортируем наши функции для обработки Excel
from merge_excel_with_calculations import process_supplier_with_tradewatch_auto

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
# Устанавливаем более высокий уровень логирования для httpx и telegram.ext, чтобы избежать спама в консоли
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Настройка логирования для активности бота
activity_logger = logging.getLogger("bot_activity")
activity_logger.setLevel(logging.INFO)
file_handler = logging.FileHandler("bot_activity.log")
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
activity_logger.addHandler(file_handler)

# Токен бота (используйте переменную окружения для безопасности)
BOT_TOKEN = os.getenv("BOT_TOKEN", "8196649413:AAHQ6KmQgBTfYtC3MeFQRFHE5L37CKQvJlw")

# ID владельца бота (замените на ваш Telegram ID или используйте переменную окружения)  
OWNER_ID = int(os.getenv("OWNER_ID", "6755735414"))

# Папка для временных файлов
TEMP_DIR = Path("temp_files")
TEMP_DIR.mkdir(exist_ok=True)

# Хранилище для файлов пользователей - теперь только файлы поставщика
user_supplier_files: Dict[int, str] = {}

# Глобальные переменные для отслеживания прогресса
processing_progress = {}
active_timers = {}

class ProcessingTimer:
    """Класс для отслеживания прогресса обработки EAN кодов"""
    
    def __init__(self, user_id: int, total_ean_count: int, progress_message, estimated_rate: float = 600):
        self.user_id = user_id
        self.total_ean_count = total_ean_count
        self.progress_message = progress_message
        self.start_time = time.time()
        self.processed_count = 0
        self.estimated_rate = estimated_rate  # EAN в минуту
        self.actual_rate = estimated_rate  # Будет пересчитываться
        self.running = True
        self.timer_task = None
        self.loop = None
        
    def start(self, loop):
        """Запуск таймера"""
        self.loop = loop
        self._force_update_event = asyncio.Event()
        self.timer_task = asyncio.create_task(self._timer_loop())
        
    async def stop(self):
        """Остановка таймера"""
        self.running = False
        if self.timer_task:
            self.timer_task.cancel()
            try:
                await self.timer_task
            except asyncio.CancelledError:
                pass
    
    def update_progress(self, processed_count: int):
        """Обновление прогресса"""
        print(f"📈 Обновление прогресса: {processed_count} из {self.total_ean_count} кодов")
        self.processed_count = processed_count
        elapsed_time = time.time() - self.start_time
        
        if elapsed_time > 0 and processed_count > 0:
            # Пересчитываем фактическую скорость (EAN в минуту)
            self.actual_rate = (processed_count / elapsed_time) * 60
            print(f"🚀 Новая скорость: {self.actual_rate:.0f} EAN/мин")
            
        # Принудительно обновляем таймер после изменения прогресса
        if self.timer_task and not self.timer_task.done():
            # Создаем событие для немедленного обновления
            try:
                if hasattr(self, '_force_update_event'):
                    self._force_update_event.set()
            except:
                pass
    
    async def _timer_loop(self):
        """Основной цикл таймера"""
        print(f"🕐 Таймер запущен для пользователя {self.user_id}")
        
        last_update_time = time.time()
        
        while self.running:
            try:
                current_time = time.time()
                elapsed_time = current_time - self.start_time
                
                if self.processed_count > 0:
                    # Используем фактическую скорость
                    rate = self.actual_rate
                else:
                    # Используем расчетную скорость для первой минуты
                    rate = self.estimated_rate
                
                remaining_count = self.total_ean_count - self.processed_count
                
                if remaining_count <= 0:
                    print(f"🏁 Таймер завершен - все коды обработаны")
                    break
                
                # Рассчитываем оставшееся время
                remaining_minutes = remaining_count / rate if rate > 0 else 0
                
                # Обновляем сообщение только если прошло достаточно времени или есть принудительное обновление
                time_since_update = current_time - last_update_time
                force_update = self._force_update_event.is_set()
                
                if time_since_update >= 15 or force_update:
                    # Формируем сообщение
                    progress_text = f"🔄 Обработка EAN кодов...\n\n"
                    progress_text += f"📊 Прогресс: {self.processed_count}/{self.total_ean_count} кодов\n"
                    progress_text += f"⏱️ Прошло времени: {elapsed_time/60:.1f} мин\n"
                    progress_text += f"🚀 Скорость: {rate:.0f} EAN/мин\n"
                    progress_text += f"⏰ До конца обработки осталось: {remaining_minutes:.1f} мин"
                    
                    print(f"📊 Обновление таймера: {self.processed_count}/{self.total_ean_count} кодов")
                    
                    # Обновляем сообщение (с защитой от ошибок)
                    try:
                        await self.progress_message.edit_text(progress_text)
                        print(f"✅ Сообщение обновлено успешно")
                        last_update_time = current_time
                        
                        # Сбрасываем флаг принудительного обновления
                        if force_update:
                            self._force_update_event.clear()
                            
                    except Exception as e:
                        print(f"❌ Ошибка обновления сообщения: {e}")
                
                # Ждем 5 секунд до следующей проверки или принудительного обновления
                try:
                    await asyncio.wait_for(self._force_update_event.wait(), timeout=5)
                except asyncio.TimeoutError:
                    pass  # Нормальное поведение - продолжаем цикл
                
            except asyncio.CancelledError:
                print(f"🛑 Таймер отменен для пользователя {self.user_id}")
                break
            except Exception as e:
                print(f"❌ Ошибка в таймере: {e}")
                break
        
        print(f"🔚 Таймер завершен для пользователя {self.user_id}")

class TelegramBot:
    def __init__(self, token: str):
        logger.info(f"🔧 Инициализация TelegramBot с токеном: {token[:10]}...")
        self.token = token
        # Создаём Application с увеличенными таймаутами для больших файлов
        from telegram.request import HTTPXRequest
        request = HTTPXRequest(
            connection_pool_size=8,
            read_timeout=300,  # 5 минут на чтение больших файлов
            write_timeout=300,  # 5 минут на запись больших файлов
            connect_timeout=60  # 1 минута на подключение
        )
        self.application = Application.builder().token(token).request(request).build()
        logger.info("✅ Application создана успешно")

        # ДОБАВИТЬ: Логирование конфигурации при запуске бота
        print("🚀 ЗАПУСК TELEGRAM БОТА")
        print("=" * 50)
        print("� Railway Hobby план - максимальная производительность")

        parallel_sessions = get_parallel_sessions()
        batch_size = get_batch_size()
        print(f"🔄 Количество параллельных сессий: {parallel_sessions}")
        print(f"📦 Размер батча: {batch_size} EAN кодов")
        print(f"⚡ Расчетная производительность: {batch_size * parallel_sessions} EAN одновременно")
        print("=" * 50)

        self.setup_handlers()
        logger.info("✅ Обработчики настроены успешно")

    async def setup_bot_commands(self):
        """Настройка команд бота в меню"""
        commands = [
            BotCommand("start", "Начать работу"),
            BotCommand("help", "Показать справку"),
            BotCommand("clear", "Очистить загруженные файлы")
        ]
        await self.application.bot.set_my_commands(commands)

    def setup_handlers(self):
        """Настройка обработчиков команд и сообщений"""
        
        # Команды
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help))
        self.application.add_handler(CommandHandler("clear", self.clear_files))
        
        # Callback для кнопок
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Обработка файлов
        self.application.add_handler(MessageHandler(filters.Document.FileExtension("xlsx"), self.handle_file))
        
        # Обработка текстовых сообщений
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name
        
        welcome_text = f"""
Добро пожаловать, {user_name}!

Бот автоматически получит данные из TradeWatch и объединит их с вашим прайс-листом поставщика.

📋 **Как использовать:**
1. Отправьте файл поставщика (.xlsx) с названиями колонок в первой строке:
   • **GTIN** 
   • **Price** 
2. Нажмите кнопку "📊 Создать отчёт"
3. Бот автоматически:
   • Извлечёт EAN коды из вашего файла
   • Получит данные из TradeWatch по этим кодам
   • Объединит всё в итоговый файл
4. Получите готовый файл с объединёнными данными

💡 **Дополнительно:**
• 🗑️ Очистить файл - удалить загруженный файл

Просто отправьте файл, чтобы начать! 👇
        """
        
        keyboard = self.get_main_keyboard(user_id)
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = """
📖 **Справка по использованию бота**

**Команды:**
• `/start` - Начать работу
• `/help` - Показать эту справку
• `/clear` - Очистить загруженный файл

**Поддерживаемые файлы:**
• Excel файлы поставщика (.xlsx)
• Файл должен содержать колонки в первой строке:
  - **GTIN** (EAN коды товаров)
  - **Price** (цена товаров)

**Принцип работы:**
1. Загружаете прайс поставщика с EAN кодами
2. Бот извлекает EAN коды из колонки GTIN
3. Автоматически получает данные из TradeWatch
4. Объединяет всё в один файл с расчётами Profit и ROI

**Важно:** Убедитесь, что в файле поставщика колонки GTIN и Price находятся именно в первой строке!

Если возникли проблемы, используйте `/clear` для очистки файлов и начните заново.

**Поддержка:**
• Для вопросов и помощи: [@iilluummiinnaattoorr](https://t.me/iilluummiinnaattoorr)
        """
        
        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def clear_files(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Очистка файлов пользователя"""
        user_id = update.effective_user.id
        
        if user_id in user_supplier_files:
            # Удаляем файл с диска
            file_path = user_supplier_files[user_id]
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.error(f"Ошибка при удалении файла {file_path}: {e}")
            
            # Очищаем запись
            del user_supplier_files[user_id]
            
            await update.message.reply_text(
                "🗑️ Файл поставщика удалён! Можете загрузить новый файл.",
                reply_markup=self.get_main_keyboard(user_id)
            )
        else:
            await update.message.reply_text(
                "📁 У вас нет загруженных файлов.",
                reply_markup=self.get_main_keyboard(user_id)
            )

    def get_main_keyboard(self, user_id: int) -> InlineKeyboardMarkup:
        """Создание основной клавиатуры"""
        has_file = user_id in user_supplier_files
        
        if has_file:
            file_name = os.path.basename(user_supplier_files[user_id])
            keyboard = [
                [InlineKeyboardButton(f" Создать отчёт ({file_name})", callback_data="report")],
                [InlineKeyboardButton("🗑️ Очистить файл", callback_data="clear")]
            ]
        else:
            keyboard = [
                [InlineKeyboardButton("📊 Создать отчёт (нет файла)", callback_data="report")],
                [InlineKeyboardButton("🗑️ Очистить файл", callback_data="clear")]
            ]
        
        return InlineKeyboardMarkup(keyboard)

    def get_processing_keyboard(self, user_id: int) -> InlineKeyboardMarkup:
        """Создание клавиатуры во время обработки"""
        keyboard = []
        return InlineKeyboardMarkup(keyboard)

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка нажатий на кнопки"""
        query = update.callback_query
        user_id = query.from_user.id
        
        await query.answer()
        
        if query.data == "report":
            await self.create_report(query, user_id)
        
        elif query.data == "clear":
            await self.clear_user_files(query, user_id)

    async def clear_user_files(self, query, user_id: int):
        """Очистка файлов пользователя через callback"""
        if user_id in user_supplier_files:
            # Удаляем файл с диска
            file_path = user_supplier_files[user_id]
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.error(f"Ошибка при удалении файла {file_path}: {e}")
            
            # Очищаем запись
            del user_supplier_files[user_id]
            
            await query.edit_message_text(
                "🗑️ Файл поставщика удалён! Можете загрузить новый файл.",
                reply_markup=self.get_main_keyboard(user_id)
            )
        else:
            await query.edit_message_text(
                "📁 У вас нет загруженных файлов.",
                reply_markup=self.get_main_keyboard(user_id)
            )

    async def handle_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка загруженного файла поставщика"""
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name
        telegram_username = update.effective_user.username or "Unknown"
        file = update.message.document

        if not file.file_name.endswith('.xlsx'):
            await update.message.reply_text(
                "❌ Поддерживаются только файлы .xlsx",
                reply_markup=self.get_main_keyboard(user_id)
            )
            return

        try:
            # Создаём папку для пользователя
            user_dir = TEMP_DIR / str(user_id)
            user_dir.mkdir(exist_ok=True)

            # Скачиваем файл
            file_path = user_dir / file.file_name
            downloaded_file = await context.bot.get_file(file.file_id)
            await downloaded_file.download_to_drive(file_path)

            # Проверяем наличие необходимых колонок
            try:
                df = pd.read_excel(file_path)
                if 'GTIN' not in df.columns or 'Price' not in df.columns:
                    await update.message.reply_text(
                        "❌ В файле нет необходимых колонок GTIN и Price!",
                        reply_markup=self.get_main_keyboard(user_id)
                    )
                    return

                # Подсчитываем количество EAN кодов
                ean_count = df['GTIN'].dropna().count()

                if ean_count == 0:
                    await update.message.reply_text(
                        "❌ В колонке GTIN нет данных!",
                        reply_markup=self.get_main_keyboard(user_id)
                    )
                    return

                # Логируем информацию о пользователе и файле
                activity_logger.info(f"User ID: {user_id}, Nickname: {user_name}, Username: {telegram_username}, EAN Count: {ean_count}, File: {file.file_name}")

                # Отправляем сообщение владельцу бота
                owner_message = (
                    f"📢 Бот использован!\n"
                    f"👤 Пользователь: {user_name} (@{telegram_username})\n"
                    f"🆔 ID: {user_id}\n"
                    f"📂 Файл: {file.file_name}\n"
                    f"🏷️ EAN кодов: {ean_count}"
                )
                await context.bot.send_message(chat_id=OWNER_ID, text=owner_message)

            except Exception as e:
                await update.message.reply_text(
                    f"❌ Ошибка при чтении файла: {str(e)}",
                    reply_markup=self.get_main_keyboard(user_id)
                )
                return

            # Сохраняем файл поставщика
            user_supplier_files[user_id] = str(file_path)

            await update.message.reply_text(
                f"✅ Файл поставщика загружен!\n\n"
                f"📂 Файл: {file.file_name}\n"
                f"🏷️ EAN кодов: {ean_count}\n\n"
                f"Теперь нажмите 'Создать отчёт' для обработки через TradeWatch.",
                reply_markup=self.get_main_keyboard(user_id)
            )

        except Exception as e:
            logger.error(f"Ошибка при загрузке файла: {e}")
            await update.message.reply_text(
                f"❌ Ошибка при загрузке файла: {str(e)}",
                reply_markup=self.get_main_keyboard(user_id)
            )

    async def create_report(self, query, user_id: int):
        """Создание отчёта с автоматическим получением данных TradeWatch"""
        if user_id not in user_supplier_files or not user_supplier_files[user_id]:
            await query.edit_message_text(
                "📁 Сначала загрузите файл поставщика!\n\n"
                "Отправьте Excel файл (.xlsx) с колонками GTIN и Price.",
                reply_markup=self.get_main_keyboard(user_id)
            )
            return
        
        # Показываем прогресс
        progress_message = await query.edit_message_text(
            "⏳ Начинаю обработку файла поставщика...\n"
            "Это может занять несколько минут."
        )
        
        try:
            supplier_file_path = user_supplier_files[user_id]
            
            # Проверяем, что файл существует
            if not os.path.exists(supplier_file_path):
                await progress_message.edit_text(
                    "❌ Файл поставщика не найден. Попробуйте загрузить снова.",
                    reply_markup=self.get_main_keyboard(user_id)
                )
                return
            
            # Обновляем прогресс
            await progress_message.edit_text(
                "⏳ Извлекаю EAN коды из файла поставщика...\n"
                "Подготавливаю запросы к TradeWatch..."
            )
            
            # Подсчитываем количество EAN кодов для таймера
            try:
                df = pd.read_excel(supplier_file_path)
                if 'GTIN' in df.columns:
                    ean_codes = df['GTIN'].dropna().astype(str).tolist()
                    ean_codes = [code.strip() for code in ean_codes if code.strip() and code.strip() != 'nan']
                    total_ean_count = len(ean_codes)
                else:
                    total_ean_count = 0
            except Exception as e:
                print(f"Ошибка при подсчете EAN кодов: {e}")
                total_ean_count = 0
            
            # Создаём временную папку для пользователя
            user_temp_dir = TEMP_DIR / str(user_id)
            user_temp_dir.mkdir(exist_ok=True)
            
            # Запускаем таймер
            timer = None
            if total_ean_count > 0:
                # Обновляем сообщение с информацией о найденных кодах
                await progress_message.edit_text(
                    f"⏳ Найдено {total_ean_count} EAN кодов для обработки\n"
                    f"Запускаю таймер прогресса..."
                )
                
                timer = ProcessingTimer(user_id, total_ean_count, progress_message)
                active_timers[user_id] = timer
                timer.start(asyncio.get_event_loop())
                
                # Небольшая задержка для инициализации таймера
                await asyncio.sleep(2)
            
            # Запускаем обработку в отдельном потоке, чтобы не блокировать таймер
            import concurrent.futures
            import threading
            
            def run_processing():
                # ДОБАВИТЬ: Логирование конфигурации обработки
                print("� Railway Hobby план - запускаем параллельную обработку")
                parallel_sessions = get_parallel_sessions()
                batch_size = get_batch_size()
                print(f"🔄 Параллельные сессии: {parallel_sessions}")
                print(f"📦 Размер батча: {batch_size} EAN кодов")

                return process_supplier_with_tradewatch_auto(
                    supplier_file_path, 
                    str(user_temp_dir),
                    progress_callback=lambda processed: timer.update_progress(processed) if timer else None
                )
            
            # Запускаем обработку в отдельном потоке
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = loop.run_in_executor(executor, run_processing)
                result = await future
            
            # Останавливаем таймер
            if timer:
                await timer.stop()
                if user_id in active_timers:
                    del active_timers[user_id]
            
            if not result['success']:
                error_msg = result.get('error', 'Неизвестная ошибка')
                await progress_message.edit_text(
                    f"❌ Ошибка при обработке:\n{error_msg}\n\n"
                    "Убедитесь, что в файле поставщика есть колонки:\n"
                    "• GTIN (с EAN кодами)\n"
                    "• Price (с ценами)\n\n"
                    "Колонки должны быть в первой строке файла!",
                    reply_markup=self.get_main_keyboard(user_id)
                )
                return
            
            # Обновляем прогресс
            await progress_message.edit_text(
                "📊 Создаю итоговый отчёт с расчётами...\n"
                "Почти готово!"
            )
            
            # Проверяем результат
            output_file = result['output_file']
            
            if not os.path.exists(output_file):
                await progress_message.edit_text(
                    "❌ Файл результата не найден после обработки.",
                    reply_markup=self.get_main_keyboard(user_id)
                )
                return
            
            # Получаем информацию о файле
            file_size = os.path.getsize(output_file)
            file_size_mb = file_size / (1024 * 1024)
            
            await progress_message.edit_text(f"📤 Отправляю результат... (размер: {file_size_mb:.1f} MB)")
            
            # Telegram ограничение: 50MB для документов
            if file_size_mb > 45:  # Оставляем небольшой запас
                # Пробуем сжать файл
                zip_file = Path(output_file).parent / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
                
                with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED) as zf:
                    zf.write(output_file, os.path.basename(output_file))
                
                zip_size = zip_file.stat().st_size / (1024 * 1024)
                
                if zip_size > 45:
                    await progress_message.edit_text(
                        f"❌ Файл слишком большой для отправки ({file_size_mb:.1f} MB)\n"
                        f"Даже в сжатом виде: {zip_size:.1f} MB\n\n"
                        "Попробуйте разделить файл поставщика на части.",
                        reply_markup=self.get_main_keyboard(user_id)
                    )
                    return
                
                # Отправляем сжатый файл
                report_status = " Отчёт готов!"
                with open(zip_file, 'rb') as f:
                    await query.message.reply_document(
                        document=f,
                        filename=zip_file.name,
                        caption=f"{report_status}\n\n"
                               f"Статистика:\n"
                               f"• Всего строк: {result['total_rows']}\n"
                               f"• Уникальных EAN: {result['unique_ean']}\n"
                               f"• Размер файла: {file_size_mb:.1f} MB\n"
                               f"• Архив: {zip_size:.1f} MB"
                    )
            else:
                # Отправляем файл как есть с увеличенными таймаутами
                report_status = "📊 Отчёт готов!"
                try:
                    with open(output_file, 'rb') as f:
                        await asyncio.wait_for(
                            query.message.reply_document(
                                document=f,
                                filename=os.path.basename(output_file),
                                caption=f"{report_status}\n\n"
                                       f"Статистика:\n"
                                       f"• Всего строк: {result['total_rows']}\n"
                                       f"• Уникальных EAN: {result['unique_ean']}\n"
                                       f"• Размер файла: {file_size_mb:.1f} MB"
                            ),
                            timeout=600  # 10 минут для загрузки больших файлов
                        )
                except asyncio.TimeoutError:
                    await progress_message.edit_text(
                        f"❌ Превышено время ожидания при отправке файла ({file_size_mb:.1f} MB)\n\n"
                        "Файл слишком большой для отправки через Telegram.\n"
                        "Попробуйте разделить файл поставщика на части.",
                        reply_markup=self.get_main_keyboard(user_id)
                    )
                    return
            
            # Удаляем временные файлы
            try:
                os.remove(output_file)
                if 'zip_file' in locals():
                    os.remove(zip_file)
            except:
                pass
            
            final_status = "✅ Отчёт успешно создан и отправлен!"
            await progress_message.edit_text(
                f"{final_status}\n\n"
                "Можете загрузить новый файл поставщика для создания следующего отчёта.",
                reply_markup=self.get_main_keyboard(user_id)
            )
            
        except Exception as e:
            # Останавливаем таймер в случае ошибки
            if user_id in active_timers:
                await active_timers[user_id].stop()
                del active_timers[user_id]
            
            logger.error(f"Ошибка при создании отчёта для пользователя {user_id}: {str(e)}")
            await progress_message.edit_text(
                f"❌ Произошла ошибка при обработке:\n{str(e)}\n\n"
                "Попробуйте:\n"
                "• Проверить формат файла (.xlsx)\n"
                "• Убедиться, что колонки GTIN и Price в первой строке\n"
                "• Загрузить файл заново",
                reply_markup=self.get_main_keyboard(user_id)
            )

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений"""
        user_id = update.effective_user.id
        
        await update.message.reply_text(
            "👋 Отправьте Excel файл (.xlsx) или используйте кнопки!\n\n"
            "� Отправить файл - загрузить прайс поставщика\n"
            "📊 Создать отчёт - получить данные TradeWatch\n"
            "🗑️ Очистить файл - удалить загруженный файл",
            reply_markup=self.get_main_keyboard(user_id)
        )

    def run(self):
        """Запуск бота с обработкой конфликтов"""
        logger.info("Запуск Telegram бота...")

        # Настраиваем команды меню при запуске
        async def post_init(application):
            await self.setup_bot_commands()

        self.application.post_init = post_init

        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                # Запускаем polling с обработкой ошибок
                self.application.run_polling(
                    allowed_updates=Update.ALL_TYPES,
                    drop_pending_updates=True  # Сбрасываем pending updates при перезапуске
                )
                break  # Успешный запуск, выходим из цикла

            except Exception as e:
                logger.error(f"Ошибка при запуске бота (попытка {retry_count + 1}/{max_retries}): {e}")

                if "Conflict" in str(e):
                    logger.error("❌ КОНФЛИКТ: Другая копия бота уже запущена!")
                    print("\n❌ КОНФЛИКТ ОБНАРУЖЕН!")
                    print("Другая копия бота уже запущена.")
                    print("Решение:")
                    print("1. Остановите другие deployments в Railway dashboard")
                    print("2. Убедитесь что бот не запущен локально")
                    print("3. Подождите 1-2 минуты и попробуйте снова")

                    if retry_count < max_retries - 1:
                        wait_time = 30 * (retry_count + 1)  # 30s, 60s, 90s
                        logger.info(f"⏳ Ждем {wait_time} секунд перед следующей попыткой...")
                        print(f"⏳ Ждем {wait_time} секунд перед следующей попыткой...")
                        import time
                        time.sleep(wait_time)
                        retry_count += 1
                    else:
                        logger.error("❌ Превышено максимальное количество попыток. Останавливаемся.")
                        print("❌ Превышено максимальное количество попыток.")
                        break
                else:
                    logger.error(f"Неизвестная ошибка: {e}")
                    break

        if retry_count >= max_retries:
            logger.error("❌ Не удалось запустить бота после всех попыток")
            print("❌ Не удалось запустить бота после всех попыток")

def main():
    """Основная функция"""
    # Отображаем информацию об окружении для отладки
    logger.info("🔍 Проверяем переменные окружения...")
    print("🔍 Проверяем переменные окружения...")

    # Определяем ожидаемый токен
    expected_token = "8196649413:AAHQ6KmQgBTfYtC3MeFQRFHE5L37CKQvJlw"

    # Показываем статус переменных (без значений по соображениям безопасности)
    bot_token_raw = os.getenv("BOT_TOKEN", "")
    bot_token_status = "✅ УСТАНОВЛЕН" if bot_token_raw and bot_token_raw == expected_token else "❌ НЕ УСТАНОВЛЕН"

    # Отладочная информация
    print(f"BOT_TOKEN: {bot_token_status}")
    if bot_token_raw:
        print(f"BOT_TOKEN длина: {len(bot_token_raw)} символов")
        print(f"BOT_TOKEN начинается с: {bot_token_raw[:20]}..." if len(bot_token_raw) > 20 else f"BOT_TOKEN: {bot_token_raw}")
        if bot_token_raw == expected_token:
            print("BOT_TOKEN статус: ✅ ПРАВИЛЬНЫЙ ТОКЕН")
        else:
            print("BOT_TOKEN статус: ❌ НЕПРАВИЛЬНЫЙ ТОКЕН")
    else:
        print("BOT_TOKEN: (пустое значение)")

    tradewatch_email_status = "✅ УСТАНОВЛЕН" if os.getenv("TRADEWATCH_EMAIL") else "❌ НЕ УСТАНОВЛЕН"
    tradewatch_password_status = "✅ УСТАНОВЛЕН" if os.getenv("TRADEWATCH_PASSWORD") else "❌ НЕ УСТАНОВЛЕН"

    print(f"TRADEWATCH_EMAIL: {tradewatch_email_status}")
    print(f"TRADEWATCH_PASSWORD: {tradewatch_password_status}")
    print("")

    # Показываем все переменные окружения (для отладки)
    print("🔍 Все переменные окружения содержащие 'BOT' или 'TRADE':")
    for key, value in os.environ.items():
        if 'BOT' in key.upper() or 'TRADE' in key.upper():
            masked_value = value[:10] + "..." + value[-5:] if len(value) > 15 else value
            print(f"  {key}: {masked_value}")
    print("")

    # Проверяем токен бота с более детальной диагностикой
    bot_token_env = os.getenv("BOT_TOKEN", "")

    print(f"🔍 Детальная проверка BOT_TOKEN:")
    print(f"  Значение установлено: {'Да' if bot_token_env else 'Нет'}")
    print(f"  Длина значения: {len(bot_token_env)} символов")
    print(f"  Ожидаемая длина: {len(expected_token)} символов")
    print(f"  Совпадает с ожидаемым: {'Да' if bot_token_env == expected_token else 'Нет'}")
    print("")

    if not bot_token_env:
        logger.error("❌ BOT_TOKEN не установлен!")
        print("❌ ПРОБЛЕМА С BOT_TOKEN!")
        print("")
        print("🔍 ПРИЧИНА: Переменная BOT_TOKEN не найдена")
        print("")
        print("🔧 РЕШЕНИЕ:")
        print("1. Перейдите в Railway Dashboard: https://railway.app/dashboard")
        print("2. Выберите проект 'tradewatch-telegram-bot'")
        print("3. Перейдите во вкладку 'Variables' в вашем СЕРВИСЕ")
        print("4. Добавьте переменную:")
        print(f"   Name: BOT_TOKEN")
        print(f"   Value: {expected_token}")
        print("5. Нажмите 'Save' и затем 'Redeploy'")
        print("")
        return

    if bot_token_env != expected_token:
        logger.error(f"❌ BOT_TOKEN установлен неправильно! Ожидалось: {expected_token[:20]}..., Получено: {bot_token_env[:20]}...")
        print("❌ ПРОБЛЕМА С BOT_TOKEN!")
        print("")
        print("� ПРИЧИНА: Значение BOT_TOKEN не совпадает с ожидаемым")
        print(f"   Ожидаемое: {expected_token}")
        print(f"   Полученное: {bot_token_env}")
        print("")
        print("🔧 РЕШЕНИЕ:")
        print("1. Скопируйте точное значение:")
        print(f"   {expected_token}")
        print("2. Обновите переменную BOT_TOKEN в Railway")
        print("3. Перезапустите deployment")
        print("")
        return

    logger.info(f"✅ BOT_TOKEN найден, начинаем инициализацию...")

    try:
        bot = TelegramBot(BOT_TOKEN)
        bot.run()
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске бота: {e}")
        raise

if __name__ == "__main__":
    main()
