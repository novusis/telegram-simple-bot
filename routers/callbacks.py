import sys

from aiogram import Router
from aiogram import types

import utils
from data.game_config import GameConfig

router = Router()


@router.callback_query(lambda callback: True)
async def callback_message(callback: types.CallbackQuery):
    import bot_main
    game = bot_main.game
    bot = bot_main.bot
    templator = bot_main.templator
    if callback.game_short_name:
        await callback.answer(callback.game_short_name, url=GameConfig.app_url(game.get_app_url_version()))
    if not callback.data:
        return
    action = callback.data.split('|')[0]
    user_name = "@" + callback.from_user.username if callback.from_user.username != "" else callback.from_user.first_name
    chat_id = callback.message.chat.id
    message_id = callback.message.message_id
    external_id = callback.from_user.id

    if action == "delete_user_yes":
        game.delete_user(external_id)
        await bot.delete_message(chat_id, int(message_id))
        await bot.send_message(chat_id, templator.get("delete_user_complete", user_name))
        return
    elif action == "delete_user_no":
        await bot.delete_message(chat_id, int(message_id))
        await bot.send_message(chat_id, templator.get("delete_user_stop", user_name))
        return

    if action == 'shop_item_star':
        star_shop_item_id = callback.data.split('|')[1]
        user = game.get_user(external_id)
        invoice_id = game.start_buy_shop_item_stars(user, star_shop_item_id, 'game_shop')
        await bot_main.send_invoice(callback, invoice_id, user)
        return

    sys.stdout.flush()

    user = game.get_user(external_id)
    if not user:
        utils.log_error(f".callback_message error: user not found <{user_name}>")
        await bot_main.start_new_game(chat_id, external_id)
        return

    if action == "collect_bonus":
        game.collect_bonus(user)
        await bot.edit_message_text(callback.message.html_text + "\n" + templator.get('balance_view', user.coins), chat_id, message_id)
        return

    print("NO ACTION")
    await bot.answer_callback_query(callback.id, templator.get("no_action"))
