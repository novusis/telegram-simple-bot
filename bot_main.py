# -*- coding: utf-8 -*-
import signal
import sys
import traceback
import asyncio
from aiogram import F
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, KeyboardButton, LabeledPrice, PreCheckoutQuery, BufferedInputFile
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

import utils
from data.game_config import GameConfig
from data.message_template import MessageTemplate
from models.db_invoices import Invoice
from simple_analytics import SimpleAnalytics
from simple_resources import SimpleResources

from simple_game import SimapleGame
from utils import convert_seconds_to_hm
import time

# Initialize bot and dispatcher
VERSION = '0.0.1'
API_TOKEN = GameConfig.get_app_config('token')

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

template_engine = MessageTemplate('data/messages.json')
simple_analytics = SimpleAnalytics(GameConfig.get_app_config('db_analytic_uri'))
resources = SimpleResources(GameConfig.get_app_config('db_resources_uri'))

game = SimapleGame(template_engine, lambda user: simple_analytics.set_login(user.external_id))
top_count = 15
wait_followers = {}

START_GAME = template_engine.get('button_start_game')
BONUSES = template_engine.get('button_bonuses')
TOP = template_engine.get('button_top', top_count)


#
#   FUNCTIONS
#

async def draw_top(chat_id, external_id):
    top_players = game.get_top_players()
    r = ""
    if top_players:
        for i, player in enumerate(top_players, start=1):
            name = player.full_name_limit  # обрезаем имя, если оно более 30 символов
            line = f"{i}. {name}"
            level = str(player.max_map_level)
            num_dots = 26 - len(line) - len(level)
            line = line.ljust(num_dots + len(line), '.')  # добавляем точки справа
            line += f"{level}\n"  # добавляем номер уровня в конце строки 
            r += line
    else:
        r = "no players..."

    if external_id:
        if game.get_user(external_id):
            buttons = [[InlineKeyboardButton(text=template_engine.get("action_start_game"), callback_data=f"action_start_game")]]
        else:
            buttons = [[]]
        await bot.send_message(chat_id, template_engine.get("message_top_text", top_count, r), parse_mode='html', reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    else:
        await bot.send_message(chat_id, template_engine.get("message_top_text", top_count, r), parse_mode='html')


async def start_game(message: types.Message):
    user = game.get_self_user(message.from_user.id, message.chat.id)
    if user:
        await start_new_game(message.chat.id, message.from_user.id)
    else:
        user = game.register_user(message.from_user.id, message.from_user.username, message.from_user.first_name, message.chat.id)
        user_to_follower_id = wait_followers.pop(user.id, None)
        if user_to_follower_id:
            await add_follower(message.chat.id, user, user_to_follower_id)
        reply_markup = get_shop_button_view()
        await message.answer(template_engine.get("new_registration", user.external_id), parse_mode='html', reply_markup=reply_markup)
        # analytics.new_registration(message.from_user.id)


async def start_new_game(chat_id, external_id):
    user = game.get_user(external_id)
    if user:
        # level = game.get_level(user)
        # if level.map_level != 1:
        #     markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="YES", callback_data=f"yes_restart"),
        #                                                     InlineKeyboardButton(text="NO", callback_data=f"no_restart")]])
        #     await bot.send_message(chat_id, template_engine.get("restart_question"), parse_mode='html', reply_markup=markup)
        #     return
        # await bot.send_message(chat_id, template_engine.get("play_the_game", user.full_name), parse_mode='html')
        # await make_game_level(chat_id, user)
        game.new_game(user)
        await bot.send_message(chat_id, template_engine.get("play_the_game", user.username))
        simple_analytics.set_player(user.external_id)
    else:
        await bot.send_message(chat_id, template_engine.get("error_no_user", external_id))
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


async def show_followers(chat_id, username):
    user = game.get_user_old_for_start(username, chat_id)
    try:
        followers = game.followers.filter_by_field('username', user.username)
        r = f"{template_engine.get('your_followers')}\n"
        bonus_timeout_h = GameConfig.get_bonus_for_followers("bonus_timeout_h")
        bonus_login_timeout_h = GameConfig.get_bonus_for_followers("bonus_last_login_timeout_h")
        bonus_coins = GameConfig.get_bonus_for_followers("bonus_coins")
        bonus_max_followers = GameConfig.get_bonus_for_followers("bonus_max_followers")
        for follower in followers:
            f_user = game.users.get(follower.user_id)
            if f_user:
                timer = bonus_timeout_h * 60 * 60 - (int(time.time()) - follower.took_bonus_time)
                play_today = ""

                if not f_user.has_game_today():
                    play_today = f" {template_engine.get('follower_no_played', f_user.username)} "

                if timer > 0:
                    r += f"<b>{f_user.full_name}</b> - {play_today}{template_engine.get('next_bonus_in', convert_seconds_to_hm(timer))}\n"
                else:
                    if play_today == "":
                        r += f"<b>{f_user.full_name}</b> - {template_engine.get('bonus_is_ready', bonus_coins)}\n"
                    else:
                        r += f"<b>{f_user.full_name}</b> - {play_today}\n"

        if len(followers) == 0:
            r = template_engine.get('no_followers', username, bonus_timeout_h, bonus_login_timeout_h, bonus_max_followers)
        await bot.send_message(chat_id, r, parse_mode='html')
    except Exception as e:
        traceback.print_exc()
        utils.log_error(f".show_followers error: <{e}>")


async def make_channel_post(chat_id, channel_message_id):
    channel_chat_id = GameConfig.get_app_config('content_channel_chat_id')
    if channel_chat_id == 0 or channel_message_id == 0:
        return
    await bot.forward_message(chat_id=chat_id, from_chat_id=channel_chat_id, message_id=channel_message_id)


#
# Bot Actions
#

@dp.message(Command('sendphoto'))
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


@dp.message(Command('restart'))
async def restart(message: types.Message):
    username = message.from_user.username
    user = game.get_user_old(username)

    if user:
        print(f".add_follower_command > user <{user.username}> is restarted>")
        await start_new_game(message.chat.id, username)
    else:
        await bot.send_message(message.chat.id, template_engine.get("error_no_user", username), parse_mode='html')


@dp.message(Command('add_follower'))
async def add_follower_command(message: types.Message):
    print(f".add_follower > message <{message.text}>")
    username = message.from_user.username
    user = game.get_user(message.from_user.id)
    if user:
        split = message.text.strip().split(" ", 1)
        if len(split) == 1 or split[1] == "":
            await bot.send_message(message.chat.id, template_engine.get("username_is_empty"), parse_mode='html')
            return
        follower_username = split[1]
        user_to_follower = game.get_user_by_external_id(follower_username)
        if user_to_follower:
            await add_follower(message.chat.id, user, user_to_follower.id)
        else:
            utils.log_error(f".add_follower_command error: no user for follow <{follower_username}>")
    else:
        await bot.send_message(message.chat.id, template_engine.get("error_no_user", username), parse_mode='html')
        return


async def add_follower(chat_id, user, user_to_follower_id, double=True):
    user_to_follow = game.users.get(user_to_follower_id)
    if user_to_follow:
        if user.id == user_to_follow.user_to_follower_id:
            await bot.send_message(chat_id, template_engine.get("follower_himself_error", user_to_follow.username), parse_mode='html')
            return True
        if game.add_user_to_followers(user, user_to_follow):
            await bot.send_message(chat_id, template_engine.get("added_follower", user_to_follow.full_name), parse_mode='html')
        else:
            await bot.send_message(chat_id, template_engine.get("user_exists_followers", user_to_follow.full_name), parse_mode='html')
        if double:
            if game.add_user_to_followers(user_to_follow, user):
                await bot.send_message(user_to_follow.chat_id, template_engine.get("added_follower", user.full_name), parse_mode='html')
    else:
        print(f".add_follower > {template_engine.get('error_no_user', user_to_follower_id)}")
        # await bot.send_message(chat_id, template_engine.get("error_no_user", follower_username), parse_mode='html')
        pass
    return False


async def buttons_keyboard_action(message: types.Message):
    try:
        if message.from_user.username is None:
            await message.answer(template_engine.get("error_no_username"), parse_mode='html')
            return
        result = True
        if message.text in [START_GAME]:
            await start_game(message)
        elif message.text == BONUSES:
            await show_followers(message.chat.id, message.from_user.username)
            markup = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text=template_engine.get("open_your_invite_url"), url=template_engine.get("bot_invite_url", message.from_user.username))]])
            bonus_timeout_h = GameConfig.get_bonus_for_followers("bonus_timeout_h")
            bonus_login_timeout_h = GameConfig.get_bonus_for_followers("bonus_last_login_timeout_h")
            bonus_coins = GameConfig.get_bonus_for_followers("bonus_coins")
            bonus_max_followers = GameConfig.get_bonus_for_followers("bonus_max_followers")
            await bot.send_message(message.chat.id, template_engine.get('bonus_for_followers_invite', message.from_user.username, bonus_timeout_h, bonus_login_timeout_h, bonus_max_followers),
                                   parse_mode='html', reply_markup=markup)
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
        user = game.get_user(message.from_user.id)
        if user:
            if await add_follower(message.chat.id, user, referral_code):
                return
        else:
            wait_followers[message.from_user.id] = referral_code

    print(f'# > start chat.id <{message.chat.id}> user <{message.from_user.id}|{message.from_user.username}> referral_code: <{referral_code}>')
    sys.stdout.flush()

    try:
        builder = ReplyKeyboardBuilder()
        bt_start_game = types.KeyboardButton(text=START_GAME)

        # channel_message_id = 0
        # settings = GameConfig.get_game_settings()
        # if 'channel_start_message_id' in settings:
        #     channel_message_id = int(settings['channel_start_message_id'])
        # await make_channel_post(message.chat.id, channel_message_id)
        await bot.send_message(chat_id=message.chat.id, text=f'<code><b>beta v{VERSION}</b></code>', parse_mode='html')
        # if 'start_music' in settings:
        #     await resources.post_resource(bot, message.chat.id, resources.AUDIO, settings['start_music'], template_engine.get("main_music"), {'title': 'Main Song', 'performer': 'Treasure Trip'})

        user = game.get_self_user(message.from_user.id, message.chat.id)
        if user:
            bt_top = KeyboardButton(text=TOP)
            bt_bonuses = KeyboardButton(text=BONUSES)
            builder.add(bt_start_game, bt_bonuses, bt_top)
            await message.answer(template_engine.get(f'start_welcome_back', user.full_name), parse_mode='html', reply_markup=builder.as_markup(resize_keyboard=True))
            simple_analytics.set_player(message.from_user.id)
        else:
            bt_top = KeyboardButton(text=TOP)
            builder.add(bt_start_game, bt_top)
            await message.answer(template_engine.get('start_first', message.from_user.username), parse_mode='html', reply_markup=builder.as_markup(resize_keyboard=True))
    except Exception as e:
        traceback.print_exc()
        print(f"\033[91m.start > ERROR <{e}>\033[0m")


@dp.message(Command('delete'))
async def delete(message: types.Message):
    user = game.get_user(message.from_user.id)
    if user:
        markup = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text='Yes', callback_data=f'delete_user_yes'),
                                                              types.InlineKeyboardButton(text='No', callback_data=f'delete_user_no')]])
        await message.answer(f' <b>Treasure Trip</b> {user.full_name} do you wanna remove user? say "yes" or "no"!', parse_mode='html', reply_markup=markup)
    else:
        await message.answer(f' <b>Treasure Trip</b> @{message.from_user.username} no user!', parse_mode='html')


@dp.message(Command('show_followers'))
async def show_followers_command(message: types.Message):
    await show_followers(message.chat.id, message.from_user.username)


@dp.message(Command('author'))
async def author_command(message: types.Message):
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Sponsor Co-life", url='https://co-lifeprofit.tilda.ws/')]])
    await message.reply(template_engine.get("about_info"), parse_mode='html', reply_markup=markup)


# @dp.message(Command('help'))
# async def help_command(message: types.Message):
#     # await bot.send_message(message.chat.id, template_engine.get("help_text"), parse_mode='html')
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
#     await bot.send_message(message.chat.id, template_engine.get("help_text2", difficulty_step, "".join(enemies), start_lives, start_coins, start_armor, "".join(items), "".join(enemies_full)), parse_mode='html')


@dp.message(Command('paysupport'))
async def delete_spam(message: Message):
    await bot.send_message(message.chat.id, template_engine.get('paysupport'))


def user_is_admin(username):
    user = game.get_user_old(username)
    return user and user.username in GameConfig.get_app_config('admins')


@dp.message(Command('online'))
async def admin_online(message: Message):
    username = message.from_user.username
    if user_is_admin(username):
        usernames = game.cache_users.keys()
        online = f"Current online: {len(usernames)}"
        for username in usernames:
            user = game.cache_users[username].get_first()
            online += f"\n{user.full_name} <{username}> online: {game.cache_users[username].get_online_time()}"
        
        online += f"\nWaiting user action at {GameConfig.get_app_config('user_online_timeout_seconds')} seconds..."
        await bot.send_message(chat_id=message.chat.id, text=online, parse_mode=None)


@dp.message(Command('cheats'))
async def admin_cheats(message: Message):
    username = message.from_user.username
    if user_is_admin(username):
        mb = InlineKeyboardBuilder()
        mb.button(text=template_engine.get("slot_icon_live"), callback_data=f"cheat_lives")
        mb.button(text=template_engine.get("slot_icon_coin"), callback_data=f"cheat_coins")
        mb.button(text=template_engine.get("slot_icon_armor"), callback_data=f"cheat_armor")
        await bot.send_message(message.chat.id, template_engine.get('cheats_text'), reply_markup=mb.as_markup())


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
            await message.reply(f'Hello {message.from_user.username}, welcome to the <b>Treasure Trip</b> game!', parse_mode='html')
        await bot.delete_message(message.chat.id, message.message_id)

    except Exception as e:
        traceback.print_exc()
        print(f"Error an exception occurred: {e}")


@dp.channel_post()
async def channel_message(message: types.MessageOriginChannel):
    # print(f".channel_message > message.type <{message.chat.type}>")
    # print(f".channel_message > message.title <{message.chat.title}>")
    # print(f".channel_message > message.text <{message.text}>")

    channel_chat_id = message.chat.id
    channel_message_id = message.message_id

    if message.chat.id == GameConfig.get_app_config('news_channel_chat_id'):
        all_users = game.users.all()
        print(f".channel_message > news! <{message.text}>")
        for user in all_users:
            chat_id = user.chat_id
            count = 0
            if not user.bot:
                await bot.forward_message(chat_id=chat_id, from_chat_id=channel_chat_id, message_id=channel_message_id)
                count += 1
                if count % 50 == 0:
                    await asyncio.sleep(10)
            print(f".channel_message > ready to <{count}> messages")
        return

    if message.chat.id != GameConfig.get_app_config('content_channel_chat_id'):
        return

    all_users = game.users.all()
    for user in all_users:
        if not user.bot and user.username in GameConfig.get_app_config('admins'):
            chat_id = user.chat_id
            print(f".channel_message > channel_message_id <{channel_message_id}>")
            await bot.forward_message(chat_id=chat_id, from_chat_id=channel_chat_id, message_id=channel_message_id)
            # file = types.InputFile('CgACAgIAAyEFAASBXrclAAMUZmwEpxbVYWiyEirVukV_93vfE20AAgRLAAIVR1hL3Y61wYgGBh41BA')
            await bot.send_message(chat_id=chat_id, text=f"<code>        \"channel_message_id\": {channel_message_id},</code>", parse_mode='html')
            # if message.photo:
            #     file_id = message.photo[0].file_id
            #     print(f".channel_message > file_id <{file_id}>")
            #     await bot.send_photo(chat_id=chat_id, photo=file_id)


async def send_invoice(callback, invoice_id, user):
    shop_item = game.get_stars_shop_item_by_invoice(invoice_id)
    if shop_item:
        title = template_engine.get("want_buy_for_stars", shop_item.get_goods_view(template_engine.get))
        prices = [LabeledPrice(label=title, amount=shop_item.price)]
        print(f".send_invoice > send invoice <{invoice_id}> item_id {shop_item.item_id}...")
        await bot.send_invoice(callback.message.chat.id, title=title,
                               description=template_engine.get(f"shop_item_description_{shop_item.item_id}", user.full_name),
                               payload=f"buy_{invoice_id}",
                               currency="XTR",
                               prices=prices,
                               provider_token="",
                               start_parameter="treasure_trip_game",
                               request_timeout=30)
        game.set_invoice_status(invoice_id, Invoice.SENT)
        print(f".send_invoice > sent complete <{invoice_id}> item_id {shop_item.item_id}")


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
        # user = game.get_user(message.from_user.id)
        # await make_game_level(message.chat.id, user)
        # level = game.get_level(user)
        # invoice_shop_type = game.invoices.get(invoice_id).shop_type
        # if invoice_shop_type == 'game_shop':
        #     await open_shop(message.chat.id, level, level.message_id, user)
        # elif invoice_shop_type == 'items_shop':
        #     await open_shop(message.chat.id, level, level.message_id, user, True)
        # elif invoice_shop_type == 'slot_machine':
        #     await open_slot_machine(message.chat.id, level, level.message_id, user)


@dp.callback_query(lambda callback: True)
async def callback_message(callback: types.CallbackQuery):
    action = callback.data.split('|')[0]
    username = callback.from_user.username
    chat_id = callback.message.chat.id
    message_id = callback.message.message_id
    external_id = callback.from_user.id

    if action == "delete_user_yes":
        game.delete_user(external_id)
        await bot.delete_message(chat_id, int(message_id))
        await bot.send_message(chat_id, template_engine.get("delete_user_complete", username), parse_mode='html')
        return
    elif action == "delete_user_no":
        await bot.delete_message(chat_id, int(message_id))
        await bot.send_message(chat_id, template_engine.get("delete_user_stop", username), parse_mode='html')
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
        print(f".callback_message > Error user not found <{username}>!")
        await start_new_game(chat_id, username)
        return

    if action == "collect_bonus":
        bonus = game.collect_bonus(user)
        # TODO : 
        print(f".callback_message bonus <{bonus}>")
        await bot.edit_message_text(callback.message.html_text, chat_id, message_id, parse_mode='html')
        return
    
    print("NO ACTION")
    await bot.answer_callback_query(callback.id, template_engine.get("no_action"))


def get_shop_button_view():
    builder = InlineKeyboardBuilder()
    shop_stars_data = game.get_shop_stars_data()
    for shop in shop_stars_data:
        # builder.button(text="20 ⭐️", callback_data=f'add_balance|{user.username}', pay=True)
        builder.row(
            InlineKeyboardButton(text=template_engine.get("action_stars_shop_item", shop.get_goods_view(template_engine.get), str(shop.price)), callback_data=f'shop_item_star|{shop.item_id}', pay=True))

    return builder.as_markup()


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
        await asyncio.sleep(GameConfig.get_app_config('online_check_timeout_seconds'))
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
