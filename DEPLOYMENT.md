# Telegram Simple Bot Deployment

## Что Это За Приложение

`telegram-simple-bot` - это Telegram game-bot с встроенным web-сервером.

Основные части приложения:

- Telegram bot на `aiogram`.
- Игровая логика и пользователи через общий `GameController`.
- SQLite-базы для приложения, ресурсов и аналитики.
- Встроенный `aiohttp` web-сервер для отдачи страниц по домену.
- API web-сервера, использующее те же модели, что и Telegram bot.
- Самоподписываемый SSL-сертификат для HTTPS, создаваемый при старте.

Web-сервер и Telegram bot запускаются в одном Python-процессе и используют общие модели.

## Что Хранится Вне Docker

На backend-сервере данные нужно хранить вне контейнера:

- `~/telegram-simple-bot/db` - SQLite-базы.
- `~/telegram-simple-bot/certs` - SSL-сертификаты.
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
    "app_url": "https://YOUR_DOMAIN:8443",
    "short_game_name": "YOUR_SHORT_GAME_NAME"
  }
}
```

В секции `web_server.ssl` замени домен:

```json
{
  "common_name": "YOUR_DOMAIN",
  "alt_names": [
    "YOUR_DOMAIN",
    "127.0.0.1"
  ]
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
  -p 8080:8080 \
  -p 8443:8443 \
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

Ожидаемые сообщения web-сервера и сертификата:

```text
.web_server started on 0.0.0.0:8080
.certificate_manager checking certificate: cert=web/certs/selfsigned/fullchain.pem, key=web/certs/selfsigned/privkey.pem
.certificate_manager certificate is not ready: certificate file is missing
.certificate_manager creating self-signed certificate for YOUR_DOMAIN
.certificate_manager self-signed certificate files written: cert=..., key=...
.certificate_manager certificate created and valid until ...
.certificate_manager SSL context is ready
.web_server HTTPS started on 0.0.0.0:8443
.web_server stopping HTTP bootstrap site after HTTPS start
```

Проверить файлы баз:

```bash
ls -la ~/telegram-simple-bot/db
```

Проверить сертификаты:

```bash
ls -la ~/telegram-simple-bot/certs/selfsigned
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

Если `close_http_after_ssl_start` включен, HTTP может быть закрыт после успешного старта HTTPS.

Проверка HTTPS с самоподписанным сертификатом:

```bash
curl -k https://localhost:8443/api/health
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

- `8080` - HTTP bootstrap/web.
- `8443` - HTTPS web.

Если сервер находится за firewall, открой нужные порты.

## Важные Файлы

- `data/app_config_prod_example.json` - пример production-конфига.
- `data/app_config_local.json` - локальный конфиг, не коммитится.
- `web/web_server.py` - web-сервер.
- `web/certificates.py` - проверка и создание self-signed сертификата.
- `simple_game.py` - общая игровая модель для Telegram и web.
- `models/database.py` - SQLite manager и буферная аналитика `info`.
