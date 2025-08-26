# Минимальный Dockerfile для Railway (для быстрого тестирования)
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
