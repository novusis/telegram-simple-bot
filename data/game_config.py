import json
import os

import utils


class GameConfig:
    APP_CONFIG_PATH = f"data/app_config_{os.getenv('CONFIG', 'dev')}.json"
    SHOP_CONFIG_PATH = "data/shop_config.json"

    with open(APP_CONFIG_PATH, 'r') as f:
        app_config = json.load(f)

    with open(SHOP_CONFIG_PATH, 'r') as f:
        stars_shop = json.load(f)

    # with open("messages/game_config.json", 'r') as f:
    #     game_config = json.load(f)

    @staticmethod
    def app_url(version):
        return GameConfig.app('app_url') + "?r=" + version

    @staticmethod
    def app(field):
        game_config = GameConfig.APP_CONFIG_PATH
        if not GameConfig.app_config:
            utils.log_error(f"GameConfig.get_app_config > error no app config <{game_config}>")
            return ""

        if 'application' not in GameConfig.app_config:
            utils.log_error(f"GameConfig.get_app_config > error not <application> node in config <{game_config}>")
            return ""

        if field not in GameConfig.app_config['application']:
            utils.log_error(f"GameConfig.get_app_config > error not field <application.{field}> in config <{game_config}>")
            return ""

        return GameConfig.app_config['application'][field]

    @staticmethod
    def bonus_for_followers(field):
        config_url = GameConfig.SHOP_CONFIG_PATH
        if not GameConfig.app_config:
            utils.log_error(f"GameConfig.get_app_config > error no app config <{config_url}>")
            return ""

        if 'bonus_for_followers' not in GameConfig.app_config:
            utils.log_error(f"GameConfig.get_app_config > error not <bonus_for_followers> node in config <{config_url}>")
            return ""

        if field not in GameConfig.app_config['bonus_for_followers']:
            utils.log_error(f"GameConfig.get_app_config > error not field <bonus_for_followers.{field}> in config <{config_url}>")
            return ""

        return GameConfig.app_config['bonus_for_followers'][field]

    @staticmethod
    def get_shop_config(field):
        config_url = f"data/stars_shop.json"
        if not GameConfig.stars_shop:
            utils.log_error(f"GameConfig.get_app_config > error no shop config <{config_url}>")
            return ""

        if field not in GameConfig.stars_shop:
            utils.log_error(f"GameConfig.get_app_config > error not field <{field}> in config <{config_url}>")
            return ""

        return GameConfig.stars_shop[field]

# @staticmethod
# def game_config():
#     return GameConfig.game_config

# @staticmethod
# def get_slot_machine_win_by_result(position):
#     combine = get_slot_machine_combine_by(position)
#     if combine is None:
#         print(f"GameConfig.get_slot_machine_win > error combine symbol <{position}>")
#         return 0
#     win = None
#     results = Counter([combine['first'], combine['second'], combine['third']])
#     if 'seven' in results and results['seven'] == 3:
#         win = get_slot_machine_win('seven')
#     elif 'seven' in results and results['seven'] > 0 and len(results.keys()) == 2:
#         for key in results.keys():
#             if key != 'seven':
#                 win = get_slot_machine_win(key)
#                 break
#     elif 'bar' in results and results['bar'] == 3:
#         win = get_slot_machine_win('bar')
#     elif 'grape' in results and results['grape'] == 3:
#         win = get_slot_machine_win('grape')
#     elif 'lemon' in results and results['lemon'] == 3:
#         win = get_slot_machine_win('lemon')
# 
#     if win is None:
#         return None
#     return win
# 
# @staticmethod
# def get_prefixes():
#     return GameConfig.config["prefixes"]
# 
# @staticmethod
# def get_item_by_id(item_id):
#     for item in GameConfig.config["items"]:
#         if item["id"] == str(item_id):
#             return item
# 
#     # Если ничего не найдено, возвращаем None
#     return None
# 
# @staticmethod
# def get_game_settings():
#     return GameConfig.config.get("game_settings")
# 
# @staticmethod
# def get_game_level_config():
#     return GameConfig.config.get("game_levels")
# 
# @staticmethod
# def get_user_config():
#     return GameConfig.config.get("user")
# 
# @staticmethod
# def get_enemy_config(enemy):
#     return GameConfig.get_enemies_config()[enemy]
# 
# @staticmethod
# def get_enemies_config():
#     return GameConfig.config.get("enemies")
# 
# @staticmethod
# def get_shop_config():
#     return GameConfig.shops_config.get("shop")
# 
# @classmethod
# def get_items(cls):
#     items = list(GameConfig.config.get("items"))
#     i = 0
#     while i < len(items):
#         if not items[i].get('enabled', False):
#             items.pop(i)
#         else:
#             i += 1
#     return items
