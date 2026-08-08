# Шаблон для телеграм бота

````
your-repository/
│
├── data/
│   └── app_config_example.json
│
├── db/
│
├── Makefile
└── README.md
````

#Деплой описан в Makefile!

#создание volume:
make create_volume
#or
docker volume create simple-bot-data

создание бекапа:
#docker run --rm -v your-volume-name:/from -v $(pwd):/to ubuntu tar cvf /to/backup.tar /from
make build
#or
docker build -t simple-bot-1 .

#запуск:
#docker run -d -p 8080:8080 -v ttdb:/app/db novusis/treasure-trip:v0.4
make run
#or
docker run -d --name python-container-for-simple-bot -v simple-bot-data:/app/db simple-bot-1

## Локальное тестирование в LAN без HTTPS

Для быстрой проверки текущей web-сборки на телефоне можно поднять упрощенный HTTP-сервер без Telegram polling и без HTTPS:

```bash
make run_web_local
```

Сервер слушает `0.0.0.0:8080`, поэтому с телефона в той же Wi-Fi сети открывай:

```text
http://<IP_КОМПЬЮТЕРА>:8080/rubber/
```

Например:

```text
http://192.168.0.10:8080/rubber/
```

Проверка, что сервер жив:

```bash
curl http://127.0.0.1:8080/api/health
```

В этом режиме отдаются статические файлы из `web/webroot`. API, которым нужен игровой контроллер бота, например `/api/me` и `/api/share-score`, в standalone-режиме не подключены.


Ниже инструкция для backend-сервера с Docker и внешним хранением `db` вне контейнера.
**1. Получить репозиторий**
```bash
cd /opt
git clone <YOUR_REPO_URL> telegram-simple-bot
cd /opt/telegram-simple-bot
```

**2. Создать внешние директории**
```bash
sudo mkdir -p /srv/telegram-simple-bot/db
sudo mkdir -p /srv/telegram-simple-bot/certs
sudo mkdir -p /srv/telegram-simple-bot/config
```
`db` будет хранить SQLite-базы вне Docker.  

`certs` будет хранить self-signed сертификат вне Docker, чтобы он не терялся при пересоздании контейнера.

`web/webroot` из директории репозитория будет смонтирован в контейнер как volume. После обновления этой папки контейнер можно просто перезапустить без пересборки.

**3. Создать production-конфиг**
```bash
cp data/app_config_example.json /srv/telegram-simple-bot/config/app_config_prod.json
nano /srv/telegram-simple-bot/config/app_config_prod.json
```

Минимально проверь поля:

```json
{
  "application": {
    "admins": ["YOUR_TELEGRAM_USERNAME"],
    "token": "YOUR_TELEGRAM_BOT_TOKEN",
    "app_url": "https://YOUR_DOMAIN:8443",
    "short_game_name": "YOUR_SHORT_GAME_NAME",
    "templates_data": "data/templates_data.json",

    "db_uri": "db/application.db",
    "db_resources_uri": "db/resources.db",
    "db_analytic_uri": "db/analytic.db",

    "web_server": {
      "enabled": true,
      "host": "0.0.0.0",
      "port": 8080,
      "webroot": "web/webroot",
      "index": "index.html",
      "ssl": {
        "enabled": true,
        "host": "0.0.0.0",
        "port": 8443,
        "cert_file": "web/certs/selfsigned/fullchain.pem",
        "key_file": "web/certs/selfsigned/privkey.pem",
        "common_name": "YOUR_DOMAIN",
        "alt_names": ["YOUR_DOMAIN"],
        "valid_days": 365,
        "renew_before_days": 30,
        "create_self_signed": true,
        "close_http_after_ssl_start": true
      }
    }
  }
}
```

Важно: пути `db/...` остаются такими, потому внутри контейнера `/app/db` будет примонтирован к `/srv/telegram-simple-bot/db`.

**4. Собрать Docker-образ**
```bash
docker build -t telegram-simple-bot:latest .
```

**5. Запустить контейнер**
```bash
docker run -d \
  --name telegram-simple-bot \
  --restart unless-stopped \
  -p 8080:8080 \
  -p 8443:8443 \
  -e CONFIG=prod \
  -v /srv/telegram-simple-bot/db:/app/db \
  -v /srv/telegram-simple-bot/certs:/app/web/certs \
  -v /opt/telegram-simple-bot/web/webroot:/app/web/webroot \
  -v /srv/telegram-simple-bot/config/app_config_prod.json:/app/data/app_config_prod.json:ro \
  telegram-simple-bot:latest
```

**6. Проверить логи**
```bash
docker logs -f telegram-simple-bot
```

Ожидаемые сообщения:
```text
.web_server started on 0.0.0.0:8080
.certificate_manager checking certificate...
.certificate_manager creating self-signed certificate...
.certificate_manager SSL context is ready
.web_server HTTPS started on 0.0.0.0:8443
.web_server stopping HTTP bootstrap site after HTTPS start
```

**7. Проверить файлы на хосте**
```bash
ls -la /srv/telegram-simple-bot/db
ls -la /srv/telegram-simple-bot/certs/selfsigned
```

Должны появиться:
```text
application.db
resources.db
analytic.db
fullchain.pem
privkey.pem
```

**8. Обновление после git pull**
```bash
cd /opt/telegram-simple-bot
git pull

docker build -t telegram-simple-bot:latest .

docker stop telegram-simple-bot
docker rm telegram-simple-bot

docker run -d \
  --name telegram-simple-bot \
  --restart unless-stopped \
  -p 8080:8080 \
  -p 8443:8443 \
  -e CONFIG=prod \
  -v /srv/telegram-simple-bot/db:/app/db \
  -v /srv/telegram-simple-bot/certs:/app/web/certs \
  -v /opt/telegram-simple-bot/web/webroot:/app/web/webroot \
  -v /srv/telegram-simple-bot/config/app_config_prod.json:/app/data/app_config_prod.json:ro \
  telegram-simple-bot:latest

docker image prune -af
```

Базы и сертификаты при этом сохранятся во внешнем хранилище.

Если изменялись только статические файлы, пересборка не нужна:

```bash
docker restart telegram-simple-bot
```
