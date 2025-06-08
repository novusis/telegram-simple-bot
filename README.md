# Простой шаблон для телеграм бота

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