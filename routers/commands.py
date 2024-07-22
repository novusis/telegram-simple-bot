import sys

from aiogram import Router
from aiogram.filters import CommandStart, CommandObject, Command
from aiogram import types

import utils

router = Router()


@router.message(CommandStart())
async def start(message: types.Message, command: CommandObject):
    import bot_main
    game = bot_main.game
    bot = bot_main.bot
    templator = bot_main.templator
    START_GAME = bot_main.START_GAME
    BONUSES = bot_main.BONUSES
    TOP = bot_main.TOP

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
            bot_main.wait_followers[message.from_user.id] = referral_code

    # print(f'# > start chat.id <{message.chat.id}> user <{message.from_user.id}|{message.from_user.username}> referral_code: <{referral_code}>')
    sys.stdout.flush()

    try:

        await bot.send_message(chat_id=message.chat.id, text=f'<code><b>beta v{bot_main.VERSION}</b></code>')
        user = game.get_self_user(message.from_user.id, message.chat.id)
        if user:
            await message.answer(templator.get(f'start_welcome_back', user.name, templator.get("balance_view", user.coins)),
                                 reply_markup=bot_main.buttons.main_menu(START_GAME, BONUSES, TOP))
            bot_main.simple_analytics.set_player(message.from_user.id)
        else:
            await registration(message)
            await message.answer(templator.get('start_first', message.from_user.username), reply_markup=bot_main.buttons.main_menu(START_GAME, BONUSES, TOP))
        await bot.send_game(message.chat.id, bot_main.GameConfig.app('short_game_name'))
    except Exception as e:
        bot_main.traceback.print_exc()
        print(f"\033[91m.start > ERROR <{e}>\033[0m")


@router.message(Command('add_follower'))
async def add_follower_command(message: types.Message):
    import bot_main
    game = bot_main.game
    bot = bot_main.bot
    templator = bot_main.templator
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


@router.message(Command('delete'))
async def delete(message: types.Message):
    import bot_main
    game = bot_main.game
    templator = bot_main.templator
    user = game.get_user(message.from_user.id)
    if user:
        await message.answer(templator.get("delete_user", user.get_username_or_name()), reply_markup=bot_main.buttons.delete_user())
    else:
        await message.answer(templator.get("error_no_user", message.from_user.username))


@router.message(Command('show_followers'))
async def show_followers_command(message: types.Message):
    import bot_main
    await bot_main.show_followers(message.chat.id, message.from_user.id)


@router.message(Command('author'))
async def author_command(message: types.Message):
    import bot_main
    templator = bot_main.templator
    await message.reply(templator.get("about_info"), reply_markup=bot_main.buttons.sponsor("Sponsor Co-life", 'https://co-lifeprofit.tilda.ws/'))


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


@router.message(Command('paysupport'))
async def pay_support_command(message: types.Message):
    import bot_main
    await bot_main.bot.send_message(message.chat.id, bot_main.templator.get('paysupport'))


async def start_game(message: types.Message):
    import bot_main
    game = bot_main.game
    user = game.get_self_user(message.from_user.id, message.chat.id)
    if user:
        await start_new_game(message.chat.id, message.from_user.id)
    else:
        await registration(message)


async def start_new_game(chat_id, external_id):
    import bot_main
    game = bot_main.game
    bot = bot_main.bot
    templator = bot_main.templator
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
        await bot.send_message(chat_id, templator.get("play_the_game", user.username, templator.get("balance_view", user.coins)), reply_markup=bot_main.buttons.shop())
        bot_main.simple_analytics.set_player(user.external_id)
    else:
        await bot.send_message(chat_id, templator.get("error_no_user", external_id))
        return


async def registration(message):
    import bot_main
    game = bot_main.game
    templator = bot_main.templator
    user = game.register_user(message.from_user.id, message.from_user.username, message.from_user.first_name, message.chat.id)
    user_to_follower_id = bot_main.wait_followers.pop(user.id, None)
    if user_to_follower_id:
        await add_follower(message.chat.id, user, user_to_follower_id)
    await message.answer(templator.get("new_registration", user.external_id), reply_markup=bot_main.buttons.shop())
    # analytics.new_registration(message.from_user.id)



async def add_follower(chat_id, user, user_to_follower_id, double=True):
    import bot_main
    game = bot_main.game
    bot = bot_main.bot
    templator = bot_main.templator
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
