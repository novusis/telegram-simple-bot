# Выбираем базовый образ
FROM python:3.11.1-slim-buster as base

# Устанавливаем переменную окружения
ENV CONFIG=prod

# Устанавливаем рабочую директорию в контейнере
WORKDIR /app

# Копируем файл с зависимостями в контейнер
COPY requirements.txt ./

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все файлы в контейнер
COPY . .

# Команда, которую запускает контейнер
CMD ["python", "./bot_main.py"]