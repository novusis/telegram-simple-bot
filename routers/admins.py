import asyncio

from aiogram import Router
from aiogram.filters import Command
from aiogram import types
from aiogram.types import BufferedInputFile

from data.game_config import GameConfig

router = Router()


def user_is_admin(username):
    import bot_main
    game = bot_main.game
    user = game.get_user_by_username(username)
    return user and user.username in GameConfig.app('admins')


@router.message(Command('cc'))
async def cc(message: types.Message):
    import bot_main
    game = bot_main.game
    bot = bot_main.bot
    username = message.from_user.username
    if user_is_admin(username):
        app_version = game.increment_app_url_version()
        await bot.send_message(message.chat.id, f"set web app version: {app_version}")


@router.message(Command('online'))
async def admin_online(message: types.Message):
    import bot_main
    game = bot_main.game
    bot = bot_main.bot
    username = message.from_user.username
    if user_is_admin(username):
        usernames = game.cache_users.keys()
        online = f"Current online: {len(usernames)}"
        for username in usernames:
            user = game.cache_users[username].get_first()
            online += f"\n{user.name} <{username}> online: {game.cache_users[username].get_online_time()}"

        online += f"\nWaiting user action at {GameConfig.app('user_online_timeout_seconds')} seconds..."
        await bot.send_message(chat_id=message.chat.id, text=online, parse_mode=None)


@router.message(Command('cheats'))
async def admin_cheats(message: types.Message):
    import bot_main
    templator = bot_main.templator
    bot = bot_main.bot
    buttons = bot_main.buttons
    username = message.from_user.username
    if user_is_admin(username):
        await bot.send_message(message.chat.id, templator.get('cheats_text'), reply_markup=buttons.cheats())


@router.message(Command('analytic'))
async def admin_analytic(message: types.Message):
    import bot_main
    bot = bot_main.bot
    username = message.from_user.username
    if user_is_admin(username):
        result = bot_main.simple_analytics.get_report()
        photo = BufferedInputFile(result[1], 'graph.jpg')
        await bot.send_photo(chat_id=message.chat.id, photo=photo, caption=result[0])


@router.channel_post()
async def channel_message(message: types.MessageOriginChannel):
    import bot_main
    game = bot_main.game
    bot = bot_main.bot
    channel_chat_id = message.chat.id
    channel_message_id = message.message_id

    if message.chat.id == GameConfig.app('news_channel_chat_id'):
        all_users = game.users.all()
        print(f".channel_message > news! <{message.text}>")
        for user in all_users:
            chat_id = user.chat_id
            count = 0
            if not user.bot:
                await bot.forward_message(chat_id=chat_id, from_chat_id=channel_chat_id, message_id=channel_message_id)
                count += 1
                if count % 45 == 0:
                    await asyncio.sleep(10)
            print(f".channel_message > ready to <{count}> messages")
        return

    if message.chat.id != GameConfig.app('content_channel_chat_id'):
        return

    all_users = game.users.all()
    for user in all_users:
        if not user.bot and user.username in GameConfig.app('admins'):
            chat_id = user.chat_id
            await bot.forward_message(chat_id=chat_id, from_chat_id=channel_chat_id, message_id=channel_message_id)
            await bot.send_message(chat_id=chat_id, text=f"<code>        \"channel_message_id\": {channel_message_id},</code>")
