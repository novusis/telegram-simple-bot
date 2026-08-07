# Название образа
IMAGE_NAME=simple-bot-1
# Название контейнера
CONTAINER_NAME=python-container-for-simple-bot
# Название Docker volume
VOLUME_NAME=simple-bot-data
CERTS_VOLUME_NAME=simple-bot-certs
WEBROOT_DIR=$(CURDIR)/web/webroot

create_volume:
	docker volume create $(VOLUME_NAME)
	docker volume create $(CERTS_VOLUME_NAME)

build:
	docker build -t $(IMAGE_NAME) .

run_local:
	MPLCONFIGDIR=/private/tmp/telegram-simple-bot-mpl CONFIG=local python3 bot_main.py

run: create_volume
	docker run -d --name $(CONTAINER_NAME) -p 8080:8080 -p 8443:8443 -v $(VOLUME_NAME):/app/db -v $(CERTS_VOLUME_NAME):/app/web/certs -v $(WEBROOT_DIR):/app/web/webroot $(IMAGE_NAME)
