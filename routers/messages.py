from aiogram import Router
from aiogram import F
from aiogram import types

import utils

router = Router()


@router.message(F.text)
async def text_message_handler(message: types.Message):
    import bot_main
    bot = bot_main.bot
    try:
        if await bot_main.buttons_keyboard_action(message):
            return
        if message.text.lower() == 'hello':
            await message.reply(f'Hello {message.from_user.first_name}, welcome to the game!')
        else:
            await bot.delete_message(message.chat.id, message.message_id)

    except Exception as e:
        utils.log_error(f".text_message_handler error: {e}>")
