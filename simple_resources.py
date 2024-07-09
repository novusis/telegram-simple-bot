from database import Database, DBModel, ModelManager


class TelegramResources:
    PHOTO = "photo"
    VIDEO = "video"
    ANIMATION = "animation"
    AUDIO = "audio"
    DOCUMENT = "document"
    VOICE = "voice"
    STICKER = "sticker"
    VIDEO_NOTE = "video_note"

    class TelegramFileData(DBModel):
        Fields = {
            "chat_id": ["INTEGER", 0],
            "url": ["TEXT", 0],
            "media_type": ["TEXT", 0],
            "file_id": ["TEXT", ""],
        }

        def __init__(self, id, chat_id: int, url, media_type, file_id):
            self.id = id
            self.chat_id = chat_id
            self.url = url
            self.media_type = media_type
            self.file_id = file_id

    def __init__(self, db_name):
        self.db = Database(db_name)
        self.resources = ModelManager('resources', self.TelegramFileData, self.db)
        # self.db.delete_table('resources')
        # all = self.resources.all()
        # for r in all:
        #     print(f"TelegramResources.__init__ > r <{r}>")

    async def post_resource(self, bot, chat_id: int, media_type, url, caption=None, settings=None):
        """
        Метод post_resource используется для отправки различных типов медиа-содержимого в чат Телеграмм. 
        :param bot: Экземпляр бота, используемого для отправки медиа-содержимого.
        :param chat_id: (str) идентификатор чата, в который отправляется содержимое.
        :param media_type: (str) тип медиа-содержимого, которые нужно отправить. Должен быть одним из следующих значений:
            PHOTO - для фотографий (обычно .jpg или .png)
            VIDEO - для видеофайлов (обычно .mp4)
            ANIMATION - для анимаций (обычно .gif или короткие .mp4 без звука.)
            AUDIO - для аудиофайлов (обычно .mp3 или .wav)
            DOCUMENT - для произвольных файлов
            VOICE - для голосовых сообщений (обычно .ogg, закодированные с кодеком OPUS)
            STICKER - для стикеров (в формате .webp)
            VIDEO_NOTE - для круглых видео сообщений (.mp4)
        :param url: URL-адрес файла или file_id, который отправляется.
        Метод сначала проверяет, отправлялось ли уже такое содержимое в чат. Если это так, то он попытается отправить его через file_id вместо URL.
        :param caption: Подпись
        :param settings: Настройки
        """
        resources = self.resources.filter_by_field('url', url)
        if bool(resources):
            try:
                await self.post_file_id(bot, chat_id, resources[0], caption, settings)
                return
            except Exception as e:
                print(f"TelegramResources.post_resource > error <{e}>")
        await self.post_url(bot, chat_id, self.TelegramFileData(None, chat_id, url, media_type, ""), caption, settings)

    async def post_file_id(self, bot, chat_id, res, caption, settings):
        print(f"TelegramResources.post_file_id > res <{res}>")
        settings = settings or {}
        if res.media_type == self.PHOTO:
            await bot.send_photo(chat_id=chat_id, photo=res.file_id, caption=caption)
        elif res.media_type == self.VIDEO:
            await bot.send_video(chat_id=chat_id, video=res.file_id, caption=caption)
        elif res.media_type == self.ANIMATION:
            await bot.send_animation(chat_id=chat_id, animation=res.file_id, caption=caption)
        elif res.media_type == self.AUDIO:
            title = settings['title'] if 'title' in settings else None
            performer = settings['performer'] if 'performer' in settings else None
            print(f"TelegramResources.post_file_id > title <{title}>")
            print(f"TelegramResources.post_file_id > performer <{performer}>")
            await bot.send_audio(chat_id=chat_id, audio=res.file_id, caption=caption, title=title, performer=performer)
        elif res.media_type == self.DOCUMENT:
            await bot.send_document(chat_id=chat_id, document=res.file_id, caption=caption)
        elif res.media_type == self.VOICE:
            await bot.send_voice(chat_id=chat_id, voice=res.file_id, caption=caption)
        elif res.media_type == self.STICKER:
            await bot.send_sticker(chat_id=chat_id, sticker=res.file_id, caption=caption)
        elif res.media_type == self.VIDEO_NOTE:
            await bot.send_video_note(chat_id=chat_id, video_note=res.file_id, caption=caption)

    async def post_url(self, bot, chat_id, res, caption, settings):
        print(f"TelegramResources.post_url > res <{res}>")
        settings = settings or {}
        answer = None
        if res.media_type == self.PHOTO:
            answer = await bot.send_photo(chat_id=chat_id, photo=res.url, caption=caption)
        elif res.media_type == self.VIDEO:
            answer = await bot.send_video(chat_id=chat_id, video=res.url, caption=caption)
        elif res.media_type == self.ANIMATION:
            answer = await bot.send_animation(chat_id=chat_id, animation=res.url, caption=caption)
        elif res.media_type == self.AUDIO:
            title = settings['title'] if 'title' in settings else None
            performer = settings['performer'] if 'performer' in settings else None
            print(f"TelegramResources.post_file_id > title <{title}>")
            print(f"TelegramResources.post_file_id > performer <{performer}>")
            answer = await bot.send_audio(chat_id=chat_id, audio=res.url, caption=caption, title=title, performer=performer)
        elif res.media_type == self.DOCUMENT:
            answer = await bot.send_document(chat_id=chat_id, document=res.url, caption=caption)
        elif res.media_type == self.VOICE:
            answer = await bot.send_voice(chat_id=chat_id, voice=res.url, caption=caption)
        elif res.media_type == self.STICKER:
            answer = await bot.send_sticker(chat_id=chat_id, sticker=res.url, caption=caption)
        elif res.media_type == self.VIDEO_NOTE:
            answer = await bot.send_video_note(chat_id=chat_id, video_note=res.url, caption=caption)

        if answer is None:
            return

        if answer.photo:
            res.media_type = self.PHOTO
            res.file_id = answer.photo[-1].file_id
            self.resources.set(res)
        elif answer.video:
            res.media_type = self.VIDEO
            res.file_id = answer.video.file_id
            self.resources.set(res)
        elif answer.animation:
            res.media_type = self.ANIMATION
            res.file_id = answer.animation.file_id
            self.resources.set(res)
        elif answer.audio:
            res.media_type = self.AUDIO
            res.file_id = answer.audio.file_id
            self.resources.set(res)
        elif answer.document:
            res.media_type = self.DOCUMENT
            res.file_id = answer.document.file_id
            self.resources.set(res)
        elif answer.voice:
            res.media_type = self.VOICE
            res.file_id = answer.voice.file_id
            self.resources.set(res)
        elif answer.sticker:
            res.media_type = self.STICKER
            res.file_id = answer.sticker.file_id
            self.resources.set(res)
        elif answer.video_note:
            res.media_type = self.VIDEO_NOTE
            res.file_id = answer.video_note.file_id
            self.resources.set(res)
