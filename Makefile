# Название образа
IMAGE_NAME=simple-bot-1
# Название контейнера
CONTAINER_NAME=python-container-for-simple-bot
# Название Docker volume
VOLUME_NAME=simple-bot-data

create_volume:
	docker volume create $(VOLUME_NAME)

build:
	docker build -t $(IMAGE_NAME) .

run: create_volume
	docker run -d --name $(CONTAINER_NAME) -v $(VOLUME_NAME):/app/db $(IMAGE_NAME)