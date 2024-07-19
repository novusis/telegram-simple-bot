# -*- coding: utf-8 -*-
import signal
import sys
import traceback
import asyncio
from secrets import token_hex

from aiogram import F
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, InlineQueryResultType
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, KeyboardButton, LabeledPrice, PreCheckoutQuery, BufferedInputFile, InlineQueryResultArticle, InlineQueryResultGame, InlineQueryResultPhoto
from aiogram.filters import CommandStart, Command, CommandObject

import utils
from data.game_config import GameConfig
from data.simple_templator import SimpleTemplator
from keyboards import Keyboards
from models.db_invoices import Invoice
from simple_analytics import SimpleAnalytics
from simple_resources import SimpleResources

from simple_game import GameController
from utils import convert_seconds_to_hm
import time

# Initialize bot and dispatcher

VERSION = '0.0.4'
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


#
#   FUNCTIONS
#

async def draw_top(chat_id, external_id):
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


async def start_game(message: types.Message):
    user = game.get_self_user(message.from_user.id, message.chat.id)
    if user:
        await start_new_game(message.chat.id, message.from_user.id)
    else:
        await registration(message)


async def registration(message):
    user = game.register_user(message.from_user.id, message.from_user.username, message.from_user.first_name, message.chat.id)
    user_to_follower_id = wait_followers.pop(user.id, None)
    if user_to_follower_id:
        await add_follower(message.chat.id, user, user_to_follower_id)
    await message.answer(templator.get("new_registration", user.external_id), reply_markup=buttons.shop())
    # analytics.new_registration(message.from_user.id)


async def start_new_game(chat_id, external_id):
    user = game.get_user(external_id)
    if user:
        # level = game.get_level(user)
        # if level.map_level != 1:
        #     markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="YES", callback_data=f"yes_restart"),
        #                                                     InlineKeyboardButton(text="NO", callback_data=f"no_restart")]])
        #     await bot.send_message(chat_id, template_engine.get("restart_question"), reply_markup=markup)
        #     return
        # await bot.send_message(chat_id, template_engine.get("play_the_game", user.name))
        # await make_game_level(chat_id, user)
        game.new_game(user)
        await bot.send_message(chat_id, templator.get("play_the_game", user.username, templator.get("balance_view", user.coins)), reply_markup=buttons.shop())
        simple_analytics.set_player(user.external_id)
    else:
        await bot.send_message(chat_id, templator.get("error_no_user", external_id))
        return


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

@dp.message(Command('sendcontent'))
async def send_photo(message: Message):
    print(f".send_photo > message <{message}>")
    await resources.post_resource(bot, message.chat.id, resources.AUDIO, 'https://storage.googleapis.com/treasure-trip/media/music_first_them.mp3')
    # await resources.post_resource(bot, message.chat.id, resources.PHOTO, 'https://storage.googleapis.com/treasure-trip/media/test_image.jpg')
    # await resources.post_resource(bot, message.chat.id, resources.ANIMATION, 'https://storage.googleapis.com/treasure-trip/media/start_game_tutorial.mp4')
    # await resources.post_resource(bot, message.chat.id, resources.ANIMATION, 'https://storage.googleapis.com/treasure-trip/media/start_promo_1.mp4')
    # photo_url = 'https://storage.googleapis.com/treasure-trip/test_image.jpg'
    # answer = await bot.send_photo(chat_id=message.chat.id, photo=photo_url)
    # file_id = 'AgACAgQAAxkDAAIWsmZ9KzInrtJL-D1almGcYFS7hB9yAAI8tDEbt3_sU0-DPjDVT0sQAQADAgADcwADNQQ'
    # answer = await bot.send_photo(chat_id=message.chat.id, photo=file_id)
    # print(f".send_photo > answer <{answer.photo[0].file_id}>")


@dp.message(Command('add_follower'))
async def add_follower_command(message: types.Message):
    print(f".add_follower > message <{message.text}>")
    username = message.from_user.username
    user = game.get_user(message.from_user.id)
    if user:
        split = message.text.strip().split(" ", 1)
        if len(split) == 1 or split[1] == "":
            await bot.send_message(message.chat.id, templator.get("username_is_empty"))
            return
        follower_username = split[1]
        user_to_follower = game.get_user_by_username(follower_username)
        if user_to_follower:
            await add_follower(message.chat.id, user, user_to_follower.id)
        else:
            utils.log_error(f"add_follower_command error: no user for follow <{follower_username}>")
    else:
        await bot.send_message(message.chat.id, templator.get("error_no_user", username))
        return


async def add_follower(chat_id, user, user_to_follower_id, double=True):
    user_to_follow = game.users.get(user_to_follower_id)
    if user_to_follow:
        if user.id == user_to_follow.id:
            await bot.send_message(chat_id, templator.get("follower_himself_error", user_to_follow.username))
            return True
        if game.add_user_to_followers(user, user_to_follow):
            await bot.send_message(chat_id, templator.get("added_follower", user_to_follow.name))
        else:
            await bot.send_message(chat_id, templator.get("user_exists_followers", user_to_follow.name))
        if double:
            if game.add_user_to_followers(user_to_follow, user):
                await bot.send_message(user_to_follow.chat_id, templator.get("added_follower", user.name))
    else:
        print(f".add_follower > {templator.get('error_no_user', user_to_follower_id)}")
        # await bot.send_message(chat_id, template_engine.get("error_no_user", follower_username))
        pass
    return False


async def buttons_keyboard_action(message: types.Message):
    try:
        result = True
        if message.text in [START_GAME]:
            await start_game(message)
            await bot.send_game(message.chat.id, 'stc')
        elif message.text == BONUSES:
            await show_followers(message.chat.id, message.from_user.id)
            bonus_timeout_h = GameConfig.bonus_for_followers("bonus_timeout_h")
            bonus_login_timeout_h = GameConfig.bonus_for_followers("bonus_last_login_timeout_h")
            bonus_coins = GameConfig.bonus_for_followers("bonus_coins")
            bonus_max_followers = GameConfig.bonus_for_followers("bonus_max_followers")
            await bot.send_message(message.chat.id, templator.get('bonus_for_followers_invite', message.from_user.username, bonus_timeout_h, bonus_login_timeout_h, bonus_max_followers),
                                   parse_mode='html', reply_markup=buttons.bonus_invite(message.from_user.id))
        elif message.text == TOP:
            await draw_top(message.chat.id, message.from_user.id)
        else:
            result = False
        return result
    except Exception as e:
        print(f".buttons_keyboard_action > Error <{e}>")


#
# BOT API
#

@dp.message(CommandStart())
async def start(message: types.Message, command: CommandObject):
    referral_code = None
    if command.args:
        if command.args[:2] == "f=":
            referral_code = command.args[2:]

    if referral_code:
        user = game.get_self_user(message.from_user.id, message.chat.id)
        if user:
            if await add_follower(message.chat.id, user, referral_code):
                return
        else:
            wait_followers[message.from_user.id] = referral_code

    # print(f'# > start chat.id <{message.chat.id}> user <{message.from_user.id}|{message.from_user.username}> referral_code: <{referral_code}>')
    sys.stdout.flush()

    try:

        await bot.send_message(chat_id=message.chat.id, text=f'<code><b>beta v{VERSION}</b></code>')
        user = game.get_self_user(message.from_user.id, message.chat.id)
        if user:
            await message.answer(templator.get(f'start_welcome_back', user.name, templator.get("balance_view", user.coins)), reply_markup=buttons.main_menu(START_GAME, BONUSES, TOP))
            simple_analytics.set_player(message.from_user.id)
        else:
            await registration(message)
            await message.answer(templator.get('start_first', message.from_user.username), reply_markup=buttons.main_menu(START_GAME, BONUSES, TOP))
        await bot.send_game(message.chat.id, GameConfig.app('short_game_name'))
    except Exception as e:
        traceback.print_exc()
        print(f"\033[91m.start > ERROR <{e}>\033[0m")


@dp.message(Command('delete'))
async def delete(message: types.Message):
    user = game.get_user(message.from_user.id)
    if user:
        await message.answer(templator.get("delete_user", user.get_username_or_name()), reply_markup=buttons.delete_user())
    else:
        await message.answer(templator.get("error_no_user", message.from_user.username))


@dp.message(Command('show_followers'))
async def show_followers_command(message: types.Message):
    await show_followers(message.chat.id, message.from_user.id)


@dp.message(Command('author'))
async def author_command(message: types.Message):
    await message.reply(templator.get("about_info"), reply_markup=buttons.sponsor("Sponsor Co-life", 'https://co-lifeprofit.tilda.ws/'))


# @dp.message(Command('help'))
# async def help_command(message: types.Message):
#     # await bot.send_message(message.chat.id, template_engine.get("help_text"))
#     # {0} levels in location 
#     # {1} enemies 
#     # {2} start lives 
#     # {3} start coins
#     # {4} start armor 
#     # {5} items
#     difficulty_step = GameConfig.get_game_level_config()['difficulty_step']
#     enemies = [template_engine.get(f"slot_icon_{i}") for i in GameConfig.get_enemies_config().keys()]
#     start_lives = GameConfig.get_user_config()['start_lives']
#     start_coins = GameConfig.get_user_config()['start_coins']
#     start_armor = GameConfig.get_user_config()['start_armor']
#     items = [f"{make_item_text(i)}" for i in GameConfig.get_items()]
#     enemies_full = [f"{template_engine.get('help_enemy', template_engine.get(f'slot_icon_{enemy}'), GameConfig.get_enemies_config()[enemy].get('name', ''), GameConfig.get_enemies_config()[enemy].get('damage', 1))}\n"
#                     for enemy in GameConfig.get_enemies_config()]
# 
#     await bot.send_message(message.chat.id, template_engine.get("help_text2", difficulty_step, "".join(enemies), start_lives, start_coins, start_armor, "".join(items), "".join(enemies_full)))


@dp.message(Command('paysupport'))
async def delete_spam(message: Message):
    await bot.send_message(message.chat.id, templator.get('paysupport'))


def user_is_admin(username):
    user = game.get_user_by_username(username)
    return user and user.username in GameConfig.app('admins')


@dp.message(Command('cc'))
async def cc(message: Message):
    username = message.from_user.username
    if user_is_admin(username):
        app_version = game.increment_app_url_version()
        await bot.send_message(message.chat.id, f"set web app version: {app_version}")


@dp.message(Command('online'))
async def admin_online(message: Message):
    username = message.from_user.username
    if user_is_admin(username):
        usernames = game.cache_users.keys()
        online = f"Current online: {len(usernames)}"
        for username in usernames:
            user = game.cache_users[username].get_first()
            online += f"\n{user.name} <{username}> online: {game.cache_users[username].get_online_time()}"

        online += f"\nWaiting user action at {GameConfig.app('user_online_timeout_seconds')} seconds..."
        await bot.send_message(chat_id=message.chat.id, text=online, parse_mode=None)


@dp.message(Command('cheats'))
async def admin_cheats(message: Message):
    username = message.from_user.username
    if user_is_admin(username):
        await bot.send_message(message.chat.id, templator.get('cheats_text'), reply_markup=buttons.cheats())


@dp.message(Command('analytic'))
async def admin_analytic(message: Message):
    username = message.from_user.username
    if user_is_admin(username):
        result = simple_analytics.get_report()
        photo = BufferedInputFile(result[1], 'graph.jpg')
        await bot.send_photo(chat_id=message.chat.id, photo=photo, caption=result[0])


@dp.message(F.text)
async def text_message_handler(message: types.Message):
    try:
        if await buttons_keyboard_action(message):
            return
        if message.text.lower() == 'hello':
            await message.reply(f'Hello {message.from_user.first_name}, welcome to the game!')
        else:
            await bot.delete_message(message.chat.id, message.message_id)

    except Exception as e:
        traceback.print_exc()
        print(f"Error an exception occurred: {e}")


@dp.channel_post()
async def channel_message(message: types.MessageOriginChannel):
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

    # print(f".channel_message message.chat.id <{message.chat.id}>")

    if message.chat.id != GameConfig.app('content_channel_chat_id'):
        return

    all_users = game.users.all()
    for user in all_users:
        if not user.bot and user.username in GameConfig.app('admins'):
            chat_id = user.chat_id
            await bot.forward_message(chat_id=chat_id, from_chat_id=channel_chat_id, message_id=channel_message_id)
            await bot.send_message(chat_id=chat_id, text=f"<code>        \"channel_message_id\": {channel_message_id},</code>")


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


@dp.callback_query(lambda callback: True)
async def callback_message(callback: types.CallbackQuery):
    # callback.game_short_name
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
        await send_invoice(callback, invoice_id, user)
        return

    sys.stdout.flush()

    user = game.get_user(external_id)
    if not user:
        utils.log_error(f".callback_message error: user not found <{user_name}>")
        await start_new_game(chat_id, external_id)
        return

    if action == "collect_bonus":
        game.collect_bonus(user)
        await bot.edit_message_text(callback.message.html_text + "\n" + templator.get('balance_view', user.coins), chat_id, message_id)
        return

    print("NO ACTION")
    await bot.answer_callback_query(callback.id, templator.get("no_action"))


@dp.message(Command('delete'))
async def delete_spam(message: Message):
    await bot.delete_message(message.chat.id, message.message_id)


async def answer_other(message: Message):
    print(f".answer_other: message <{message}>")
    await bot.delete_message(message.chat.id, message.message_id)


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
    print(f".bot_1 main")
    await bot.delete_webhook(drop_pending_updates=True)
    dp.pre_checkout_query.register(process_pre_checkout)
    dp.message.register(success_payment, F.successful_payment)
    dp.message.register(answer_other)
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
