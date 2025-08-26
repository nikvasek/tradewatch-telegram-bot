# Простейший Dockerfile для Railway - без Selenium для быстрого тестирования
FROM python:3.11-slim

# Установка минимальных зависимостей
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копирование и установка Python зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование проекта
COPY . .

# Создание директории для временных файлов
RUN mkdir -p temp_files

# Переменные окружения
ENV PYTHONUNBUFFERED=1

# Запуск
CMD ["python", "telegram_bot.py"]
