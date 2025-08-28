# Railway Free Plan - Selenium Chrome Dockerfile - FORCE REBUILD v3.0
FROM selenium/standalone-chrome:latest

# Переключение на root для установки Python
USER root

# Установка Python и pip
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Создание символических ссылок
RUN ln -s /usr/bin/python3 /usr/bin/python

# Поиск и настройка ChromeDriver
RUN find /opt -name "chromedriver*" -type f -executable 2>/dev/null | head -1 | xargs -I {} ln -sf {} /usr/bin/chromedriver || echo "ChromeDriver not found in /opt, trying other locations" \
    && find /usr -name "chromedriver*" -type f -executable 2>/dev/null | head -1 | xargs -I {} ln -sf {} /usr/bin/chromedriver || echo "ChromeDriver will be downloaded by WebDriver Manager" \
    && which chromedriver || echo "ChromeDriver not found in PATH"

WORKDIR /app

# Копирование и установка зависимостей
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Копирование проекта
COPY . .

# Создание директории для временных файлов
RUN mkdir -p temp_files

# Переменные окружения
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:99

# Запуск
CMD ["python", "telegram_bot.py"]
