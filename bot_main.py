# -*- coding: utf-8 -*-
import signal
import traceback
import asyncio
from secrets import token_hex

from aiogram import F
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, InlineQueryResultType
from aiogram.types import Message, LabeledPrice, PreCheckoutQuery, InlineQueryResultGame

import utils
from data.game_config import GameConfig
from data.simple_templator import SimpleTemplator
from keyboards import Keyboards
from models.db_invoices import Invoice
from routers import commands, callbacks, messages, admins
from simple_analytics import SimpleAnalytics
from simple_resources import SimpleResources

from simple_game import GameController
from utils import convert_seconds_to_hm
import time

# Initialize bot and dispatcher

VERSION = '0.0.6'
API_TOKEN = GameConfig.app('token')

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

templator = SimpleTemplator(GameConfig.app('templates_data'), 'en')
simple_analytics = SimpleAnalytics(GameConfig.app('db_analytic_uri'))
resources = SimpleResources(GameConfig.app('db_resources_uri'))

game = GameController(templator, lambda user: simple_analytics.set_login(user.external_id))

buttons = Keyboards(game, templator)

top_count = 15
wait_followers = {}

START_GAME = templator.get('button_start_game')
BONUSES = templator.get('button_bonuses')
TOP = templator.get('button_top', top_count)

print(f". VERSION <{VERSION}>")


async def draw_top(chat_id):
    top_players = game.get_top_players(top_count)
    r = ""
    if top_players:
        for i, player in enumerate(top_players, start=1):
            name = player.name  # обрезаем имя, если оно более 30 символов
            line = f"{i}. {name}"
            level = str(player.scores)
            num_dots = 26 - len(line) - len(level)
            line = line.ljust(num_dots + len(line), '.')  # добавляем точки справа
            line += f"{level}\n"  # добавляем номер уровня в конце строки 
            r += line
    else:
        r = "no players..."

    await bot.send_message(chat_id, templator.get("message_top_text", top_count, r))


async def set_edit_view_message(chat_id, level, text):
    if level.message_id != "":
        try:
            await bot.edit_message_text(text, chat_id, int(level.message_id), disable_web_page_preview=True)
            level.message_id = ""
        except Exception as e:
            print(f"\033[91m.set_edit_view_message error > message_id <{level.message_id}> is error: {e}\033[0m")
            await bot.send_message(chat_id, text, disable_web_page_preview=True)
            level.message_id = ""


async def show_followers(chat_id, external_id):
    user = game.get_self_user(external_id, chat_id)
    try:
        followers = game.followers.filter_by_field('user_to_follow_id', user.id)
        r = f"{templator.get('your_followers')}\n"
        bonus_timeout_h = GameConfig.bonus_for_followers("bonus_timeout_h")
        bonus_login_timeout_h = GameConfig.bonus_for_followers("bonus_last_login_timeout_h")
        bonus_coins = GameConfig.bonus_for_followers("bonus_coins")
        bonus_max_followers = GameConfig.bonus_for_followers("bonus_max_followers")
        coins = 0
        for follower in followers:
            f_user = game.users.get(follower.user_id)
            if f_user:
                timer = bonus_timeout_h * 60 * 60 - (int(time.time()) - follower.took_bonus_time)
                play_today = ""

                if game.user_has_game_today(f_user):
                    if timer < 0 and coins < bonus_coins * bonus_max_followers:
                        coins += bonus_coins
                else:
                    play_today = f" {templator.get('follower_no_played', f_user.username)} "

                if timer > 0:
                    r += f"<b>{f_user.name}</b> - {play_today}{templator.get('next_bonus_in', convert_seconds_to_hm(timer))}\n"
                else:
                    if play_today == "":
                        r += f"<b>{f_user.name}</b> - {templator.get('bonus_is_ready', bonus_coins)}\n"
                    else:
                        r += f"<b>{f_user.name}</b> - {play_today}\n"
            else:
                game.followers.delete(follower.id)

        if len(followers) == 0:
            r = templator.get('no_followers', user.name, bonus_timeout_h, bonus_login_timeout_h, bonus_max_followers)
        await bot.send_message(chat_id, r, reply_markup=buttons.collect_bonus(coins))
    except Exception as e:
        traceback.print_exc()
        utils.log_error(f".show_followers error: <{e}>")


async def make_channel_post(chat_id, channel_message_id):
    channel_chat_id = GameConfig.app('content_channel_chat_id')
    if channel_chat_id == 0 or channel_message_id == 0:
        return
    await bot.forward_message(chat_id=chat_id, from_chat_id=channel_chat_id, message_id=channel_message_id)


#
# Bot Actions
#

# @dp.message(Command('sendcontent'))
# async def send_photo(message: Message):
#     print(f".send_photo > message <{message}>")
#     await resources.post_resource(bot, message.chat.id, resources.AUDIO, 'https://storage.googleapis.com/treasure-trip/media/music_first_them.mp3')
# await resources.post_resource(bot, message.chat.id, resources.PHOTO, 'https://storage.googleapis.com/treasure-trip/media/test_image.jpg')
# await resources.post_resource(bot, message.chat.id, resources.ANIMATION, 'https://storage.googleapis.com/treasure-trip/media/start_game_tutorial.mp4')
# await resources.post_resource(bot, message.chat.id, resources.ANIMATION, 'https://storage.googleapis.com/treasure-trip/media/start_promo_1.mp4')
# photo_url = 'https://storage.googleapis.com/treasure-trip/test_image.jpg'
# answer = await bot.send_photo(chat_id=message.chat.id, photo=photo_url)
# file_id = 'AgACAgQAAxkDAAIWsmZ9KzInrtJL-D1almGcYFS7hB9yAAI8tDEbt3_sU0-DPjDVT0sQAQADAgADcwADNQQ'
# answer = await bot.send_photo(chat_id=message.chat.id, photo=file_id)
# print(f".send_photo > answer <{answer.photo[0].file_id}>")


async def buttons_keyboard_action(message: types.Message):
    try:
        result = True
        if message.text in [START_GAME]:
            await commands.start_game(message)
            await bot.send_game(message.chat.id, GameConfig.app('short_game_name'))
        elif message.text == BONUSES:
            await show_followers(message.chat.id, message.from_user.id)
            bonus_timeout_h = GameConfig.bonus_for_followers("bonus_timeout_h")
            bonus_login_timeout_h = GameConfig.bonus_for_followers("bonus_last_login_timeout_h")
            bonus_coins = GameConfig.bonus_for_followers("bonus_coins")
            bonus_max_followers = GameConfig.bonus_for_followers("bonus_max_followers")
            await bot.send_message(message.chat.id, templator.get('bonus_for_followers_invite', message.from_user.id, bonus_timeout_h, bonus_login_timeout_h, bonus_max_followers),
                                   parse_mode='html', reply_markup=buttons.bonus_invite(message.from_user.id))
        elif message.text == TOP:
            await draw_top(message.chat.id, message.from_user.id)
        else:
            result = False
        return result
    except Exception as e:
        print(f".buttons_keyboard_action > Error <{e}>")


async def send_invoice(callback, invoice_id, user):
    shop_item = game.get_stars_shop_item_by_invoice(invoice_id)
    if shop_item:
        title = templator.get("want_buy_for_stars", shop_item.get_goods_view(templator.get))
        prices = [LabeledPrice(label=title, amount=shop_item.price)]
        await bot.send_invoice(callback.message.chat.id, title=title,
                               description=templator.get(f"shop_item_description", user.name),
                               payload=f"buy_{invoice_id}",
                               currency="XTR",
                               prices=prices,
                               provider_token="",
                               start_parameter="treasure_trip_game",
                               request_timeout=30)
        game.set_invoice_status(invoice_id, Invoice.SENT)
        print(f".send_invoice > sent complete <{invoice_id}> item_id {shop_item.item_id}")
    else:
        utils.log_error(f".send_invoice error: no shop item by invoice_id <{invoice_id}>")


async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)
    invoice_id = int(pre_checkout_query.invoice_payload.replace('buy_', '', 1))
    game.set_invoice_status(invoice_id, Invoice.PRE_CHECKOUT)
    print(f".process_pre_checkout > pre_checkout_query <{invoice_id}> PRE_CHECKOUT")


async def answer_all(message: Message):
    print(f".answer_all > message <{message}>")


async def success_payment(message: Message):
    print(f".success_payment > pre_checkout_query <{message.text}>")
    if message.successful_payment:
        print(f".success_payment > message <{message.successful_payment.total_amount}>")
        invoice_id = int(message.successful_payment.invoice_payload.replace('buy_', '', 1))
        print(f".success_payment > invoice_id <{invoice_id}>")
        shop_item = game.complete_invoice(invoice_id, message.successful_payment.telegram_payment_charge_id)
        simple_analytics.set_payments(message.from_user.id, message.successful_payment.total_amount)
        if game.apply_invoice_goods(invoice_id, shop_item):
            user = game.get_user(message.from_user.id)
            print(f".success_payment user <{user.coins}>")
            await bot.send_message(message.chat.id, templator.get("show_user_coins", user.name, user.coins))
        # await make_game_level(message.chat.id, user)
        # level = game.get_level(user)
        # invoice_shop_type = game.invoices.get(invoice_id).shop_type
        # if invoice_shop_type == 'game_shop':
        #     await open_shop(message.chat.id, level, level.message_id, user)
        # elif invoice_shop_type == 'items_shop':
        #     await open_shop(message.chat.id, level, level.message_id, user, True)
        # elif invoice_shop_type == 'slot_machine':
        #     await open_slot_machine(message.chat.id, level, level.message_id, user)


@dp.inline_query(lambda callback: True)
async def inline_query(query: types.InlineQuery):
    if not game.get_user(query.from_user.id, False):
        game.register_user(query.from_user.id, query.from_user.username, query.from_user.first_name, 0)
    game_short_name = GameConfig.app('short_game_name')
    await bot.answer_inline_query(inline_query_id=query.id, results=[InlineQueryResultGame(type=InlineQueryResultType.GAME, id=token_hex(2), game_short_name=game_short_name)])


#
#   START BOT
#

async def online_check():
    # print(f".online_check > start online_check")
    while True:
        await asyncio.sleep(GameConfig.app('online_check_timeout_seconds'))
        # print(f".online_check > 1 online <{game.get_online()}>")
        closed_sessions = game.check_online()
        for telegram_id in closed_sessions.keys():
            session_time = closed_sessions[telegram_id]
            simple_analytics.set_session(telegram_id, session_time)
        #     print(f".online_check > session.key <{telegram_id} = {closed_sessions[telegram_id]}>")
        # print(f".online_check > 2 online <{game.get_online()}>")


async def bot_1():
    await bot.delete_webhook(drop_pending_updates=True)
    dp.include_routers(commands.router, admins.router, callbacks.router, messages.router)
    dp.pre_checkout_query.register(process_pre_checkout)
    dp.message.register(success_payment, F.successful_payment)
    await dp.start_polling(bot, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


async def main():
    await asyncio.gather(bot_1(), online_check())


if __name__ == '__main__':
    asyncio.run(main())


def handle_sigint(_signal, _frame):
    print('SIGINT received, cancelling tasks...')
    for task in asyncio.all_tasks():
        task.cancel()


signal.signal(signal.SIGINT, handle_sigint)
