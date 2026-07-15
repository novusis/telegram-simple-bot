# Telegram Simple Bot Deployment

## Что Это За Приложение

`telegram-simple-bot` - это Telegram game-bot с встроенным web-сервером.

Основные части приложения:

- Telegram bot на `aiogram`.
- Игровая логика и пользователи через общий `GameController`.
- SQLite-базы для приложения, ресурсов и аналитики.
- Встроенный `aiohttp` web-сервер для отдачи страниц по домену.
- API web-сервера, использующее те же модели, что и Telegram bot.
- HTTPS-сертификат Let's Encrypt, создаваемый через `certbot` при старте.

Web-сервер и Telegram bot запускаются в одном Python-процессе и используют общие модели.

## Что Хранится Вне Docker

На backend-сервере данные нужно хранить вне контейнера:

- `~/telegram-simple-bot/db` - SQLite-базы.
- `~/telegram-simple-bot/certs` - SSL-сертификаты Let's Encrypt.
- `~/telegram-simple-bot/data/app_config_prod.json` - production-конфиг.

Контейнер можно пересоздавать, данные при этом сохранятся.

## Подготовка Директорий

```bash
mkdir -p ~/telegram-simple-bot/db
mkdir -p ~/telegram-simple-bot/certs
mkdir -p ~/telegram-simple-bot/data
```

## Получение Репозитория

```bash
git clone <YOUR_REPO_URL> telegram-simple-bot-repo
cd telegram-simple-bot-repo
```

## Production Конфиг

Создай production-конфиг из примера:

```bash
cp data/app_config_prod_example.json ~/telegram-simple-bot/data/app_config_prod.json
nano ~/telegram-simple-bot/data/app_config_prod.json
```

Минимально нужно заменить:

```json
{
  "application": {
    "admins": ["YOUR_TELEGRAM_USERNAME"],
    "token": "YOUR_TELEGRAM_BOT_TOKEN",
    "app_url": "https://YOUR_DOMAIN",
    "short_game_name": "YOUR_SHORT_GAME_NAME"
  }
}
```

В секции `web_server.ssl` замени домен и email:

```json
{
  "enabled": true,
  "port": 8443,
  "cert_file": "web/certs/live/YOUR_DOMAIN/fullchain.pem",
  "key_file": "web/certs/live/YOUR_DOMAIN/privkey.pem",
  "common_name": "YOUR_DOMAIN",
  "email": "YOUR_EMAIL",
  "webroot": "web/webroot",
  "alt_names": [
    "YOUR_DOMAIN"
  ],
  "renew_before_days": 30,
  "letsencrypt_enabled": true,
  "create_self_signed": false,
  "close_http_after_ssl_start": false
}
```

Приложение внутри Docker всегда слушает все интерфейсы контейнера.
Внешний IP не нужно указывать в конфиге. Домен указывается только в `app_url`, `common_name`, `alt_names` и `domains`.

Пути к базам в конфиге должны оставаться такими:

```json
{
  "db_uri": "db/application.db",
  "db_resources_uri": "db/resources.db",
  "db_analytic_uri": "db/analytic.db"
}
```

Внутри контейнера `/app/db` будет смонтирован на внешний каталог `~/telegram-simple-bot/db`.

## Сборка Docker-Образа

Из директории репозитория:

```bash
docker build -t telegram-simple-bot:latest .
```

## Запуск Контейнера

```bash
docker run -d \
  --name telegram-simple-bot \
  --restart unless-stopped \
  -p 80:8080 \
  -p 443:8443 \
  -e CONFIG=prod \
  -v ~/telegram-simple-bot/db:/app/db \
  -v ~/telegram-simple-bot/certs:/app/web/certs \
  -v ~/telegram-simple-bot/data/app_config_prod.json:/app/data/app_config_prod.json:ro \
  telegram-simple-bot:latest
```

## Проверка Запуска

Посмотреть логи:

```bash
docker logs -f telegram-simple-bot
```

Нормальный первый запуск сертификата:

1. Приложение запускает HTTP на `8080`, снаружи это порт `80`.
2. `certbot` создает challenge-файл в `web/webroot/.well-known/acme-challenge`.
3. Let's Encrypt проверяет `http://YOUR_DOMAIN/.well-known/acme-challenge/...`.
4. После успешной проверки certbot создает `web/certs/live/YOUR_DOMAIN/fullchain.pem` и `privkey.pem`.
5. Приложение запускает HTTPS на `8443`, снаружи это порт `443`.

Ожидаемые сообщения web-сервера и сертификата:

```text
.web_server started on 0.0.0.0:8080
.certificate_manager checking certificate: cert=web/certs/live/YOUR_DOMAIN/fullchain.pem, key=web/certs/live/YOUR_DOMAIN/privkey.pem
.certificate_manager certificate is not ready: certificate file is missing
.certificate_manager requesting Let's Encrypt certificate for YOUR_DOMAIN
.certificate_manager Let's Encrypt certificate request completed
.certificate_manager certificate renewed and valid until ...
.certificate_manager SSL context is ready
.web_server HTTPS started on 0.0.0.0:8443
```

Проверить файлы баз:

```bash
ls -la ~/telegram-simple-bot/db
```

Проверить сертификаты:

```bash
ls -la ~/telegram-simple-bot/certs/live/YOUR_DOMAIN
```

Должны появиться:

```text
application.db
resources.db
analytic.db
fullchain.pem
privkey.pem
```

## Проверка HTTP/HTTPS

Health endpoint:

```bash
curl http://localhost:8080/api/health
```

HTTP должен оставаться включенным, потому что Let's Encrypt проверяет домен через порт `80`.

Проверка HTTPS:

```bash
curl https://YOUR_DOMAIN/api/health
```

## Остановка И Удаление Контейнера

```bash
docker stop telegram-simple-bot
docker rm telegram-simple-bot
```

Внешние данные при этом не удаляются.

## Обновление Приложения

```bash
cd ~/telegram-simple-bot-repo
git pull
docker build -t telegram-simple-bot:latest .
docker stop telegram-simple-bot
docker rm telegram-simple-bot
```

Затем снова выполнить команду запуска контейнера.

## Локальный Запуск Только Telegram-Бота

Для локальной разработки используется `data/app_config_local.json`.

Он не коммитится в git и должен содержать токен тестового Telegram-бота.

Запуск:

```bash
make run_local
```

В локальном конфиге web-сервер и SSL выключены.

## Важные Порты

- `80` - внешний HTTP, проброшен в контейнерный `8080`; нужен для Let's Encrypt.
- `443` - внешний HTTPS, проброшен в контейнерный `8443`.
- `8080` - HTTP внутри контейнера.
- `8443` - HTTPS внутри контейнера.

Если сервер находится за firewall, открой нужные порты.

## Важные Файлы

- `data/app_config_prod_example.json` - пример production-конфига.
- `data/app_config_local.json` - локальный конфиг, не коммитится.
- `web/web_server.py` - web-сервер.
- `web/certificates.py` - проверка и выпуск HTTPS-сертификата.
- `simple_game.py` - общая игровая модель для Telegram и web.
- `models/database.py` - SQLite manager и буферная аналитика `info`.
