import random
import re
import config
import utils
from database import DBModel
from messages.game_config import GameConfig


class User(DBModel):
    MAX_NAME_LENGTH = 20
    Fields = {
        "name": ["TEXT", ""],
        "external_id": ["TEXT", ""],
        "username": ["TEXT", ""],
        "scores": ["INTEGER", 0],
    }

    def __init__(self, id, name, external_id, user_name, chat_id):
        self.id = id
        self.name = name
        self.username = username
        self.name_pref = name_pref
        self.external_id = external_id
        self.scores = scores
        self.coins = coins
        self.energy = energy
        self.lives = lives
        self.level = level
        self.max_coins = max_coins
        self.max_map_level = max_map_level
        self.max_armor = max_armor
        self.max_energy = max_energy
        self.game_data = game_data
        if armor is None:
            armor = 2
        self.armor = armor
        self.kills = kills
        self.last_time_action = last_time_action
        self.bonus_collect = bonus_collect
        self.chat_id = chat_id
        self.select_item = select_item
        self.bot = bot
        self.slot_machine_bet = slot_machine_bet
        # Создаем экземпляр нашего конфига
        self.user_config = GameConfig().get_user_config()

    def new_game(self):
        self.coins = self.user_config['start_coins']
        self.armor = self.user_config['start_armor']
        self.lives = self.user_config['start_lives']
        self.kills = 0
        self.last_time_action = utils.now_unix_time()
        self.bonus_collect = False
        self.select_item = 0

    def add_resource(self, item_id, count, map_log):
        if item_id == GameLevel.COIN:
            self.coins += count
            map_log(GameLevel.COIN, count)
            return True
        if item_id == GameLevel.LIVE:
            self.lives += count
            map_log(GameLevel.LIVE, count)
            return True
        if item_id == GameLevel.ARMOR:
            self.armor += count
            map_log(GameLevel.ARMOR, count)
            return True
        if item_id == GameLevel.ENERGY:
            self.energy += count
            map_log(GameLevel.ENERGY, count)
            return True
        return False

    def has_game_today(self):
        if utils.now_unix_time() - self.last_time_action < config.Config.BONUS_LAST_LOGIN_TIMEOUT_H * 60 * 60:
            return True
        return False

    @property
    def full_name_limit(self):
        if self.name_pref is not None and len(self.name_pref + self.fixed_name) >= self.MAX_NAME_LENGTH:
            return self.shorten_string(self.fixed_name)
        return self.shorten_string(self.full_name)

    @property
    def full_name(self):
        if self.name_pref is None or self.name_pref == "":
            return self.fixed_name
        return f'{self.name_pref} {self.fixed_name}'

    @property
    def fixed_name(self):
        name = self.replace_emoji_with_dot(self.name.capitalize())
        return name

    def replace_emoji_with_dot(self, text):
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags (iOS)
            "\U00002702-\U000027B0"  # Dingbats
            "\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE
        )

        return emoji_pattern.sub('.', text)

    def shorten_string(self, s):
        limit = self.MAX_NAME_LENGTH - 1
        return s[:limit] + (s[limit:] and '.')


class GameLevel(DBModel):
    EMPTY = "empty"
    COIN = "coin"
    LIVE = "live"
    ENEMY = "enemy"
    ARMOR = "armor"
    ENERGY = "energy"
    SHOP = "shop"
    ITEMS_SHOP = "items_shop"
    SLOT_MACHINE = "slot_machine"
    Fields = {
        "user_id": ["INTEGER", 0],
        "map_level": ["INTEGER", 0],
        "slot1": ["TEXT", ""],
        "slot2": ["TEXT", ""],
        "slot3": ["TEXT", ""],
        "slot4": ["TEXT", ""],
        "message_id": ["TEXT", ""],
        "enemy_series": ["INTEGER", 0]
    }

    def __init__(self, id, user_id, map_level, slot1, slot2, slot3, slot4, message_id, enemy_series):
        self.has_new_location = False
        self.has_select_shop = False
        self.has_select_items_shop = False
        self.has_select_slot_machine = False
        self.id = id
        self.user_id = user_id
        self.map_level = map_level
        self.slot1 = slot1
        self.slot2 = slot2
        self.slot3 = slot3
        self.slot4 = slot4
        self.message_id = str(message_id)
        self.enemy_series = enemy_series

    def random_item(self):
        current_level = self.get_current_level_config()
        drops = current_level['drops']
        slots = list(drops.keys())
        chance = list(drops.values())
        return random.choices(slots, chance, k=1)[0]

    def collect_all(self, user, collect_item, make_log):
        for slot in ['slot1', 'slot2', 'slot3', 'slot4']:
            item = self[slot]
            if item in [self.ARMOR, self.LIVE, self.COIN, self.ENERGY]:
                self.collect_slot(slot, item, 1, user, make_log)
            elif item in [self.EMPTY, self.SHOP, self.ITEMS_SHOP, self.SLOT_MACHINE]:
                continue
            else:
                if collect_item(user, item, make_log):
                    self[slot] = GameLevel.EMPTY

    def collect_slot(self, slot, item, count, user, make_log):
        if item == 'live':
            user['lives'] += count
        elif item == 'coin':
            user['coins'] += count
        else:
            user[item] += count
        self[slot] = self.EMPTY
        make_log(item, count)

    def go_next(self):
        self.map_level += 1
        self.make()
        self.has_new_location = True

    def make(self):
        if config.Config.TUTORIAL_START and self.map_level < len(config.Config.TUTORIAL_LEVELS):
            slots = config.Config.TUTORIAL_LEVELS[self.map_level]
            print(f"GameLevel.make > TUTORIAL_START [{self.map_level}] get tutorial slots <{slots}>")
            self.slot1 = slots[0]
            self.slot2 = slots[1]
            self.slot3 = slots[2]
            self.slot4 = slots[3]
            return
        self.slot1 = self.random_item()
        self.slot2 = self.random_item()
        self.slot3 = self.random_item()
        self.slot4 = self.random_item()

        all_enemies = GameConfig.get_enemies_config().keys()
        # exception more casino
        casino = 0
        shop = 0
        items_shop = 0
        empty = 0
        enemy = 0
        for slot in [self.slot1, self.slot2, self.slot3, self.slot4]:
            if slot in all_enemies:
                enemy += 1
                # if enemy >= 4 or enemy >= 1 and self.enemy_series > 3:
                # print(f"GameLevel.make > make enemy <{enemy} | {self.enemy_series}>")
                # self.make()
                # return
            if slot == self.EMPTY:
                empty += 1
            if slot == self.SLOT_MACHINE:
                casino += 1
                if casino > 1:
                    self.make()
                    return
            if slot == self.SHOP:
                shop += 1
            if slot == self.ITEMS_SHOP:
                items_shop += 1
                if items_shop > 1:
                    self.make()
                    return
            if empty + casino + shop > 3:
                self.make()
                return

        game_level_config = GameConfig.get_game_level_config()
        difficulty_step = game_level_config['difficulty_step']
        bonus_level = self.map_level < 4 or self.map_level % difficulty_step == 0
        if bonus_level and (enemy + casino + shop + items_shop) > 0:
            self.make()
            return

        if enemy > 0:
            self.enemy_series += 1
            # print(f"GameLevel.make > enemy_series <{self.enemy_series}>")
        else:
            self.enemy_series = 0

    def get_drop(self, enemy):
        game_level_config = GameConfig.get_game_level_config()
        current_level = self.get_current_level_config()
        # this for if nothing enemy in level config, usage base drop info
        if 'chances_of_drop' in current_level:
            drop_data = current_level['chances_of_drop']
            for enemy_key in game_level_config['chances_of_drop'].keys():
                if enemy_key not in drop_data:
                    drop_data[enemy_key] = game_level_config['chances_of_drop'][enemy_key]

            chances_of_drop = drop_data
        else:
            chances_of_drop = game_level_config['chances_of_drop']

        if enemy in chances_of_drop:
            drops = chances_of_drop[enemy]
            slots = list(drops.keys())
            chance = list(drops.values())
            return random.choices(slots, chance, k=1)[0]

        return GameLevel.EMPTY

    def no_resources(self):
        for slot in [self.slot1, self.slot2, self.slot3, self.slot4]:
            if not (slot in [GameLevel.EMPTY, GameLevel.SLOT_MACHINE, GameLevel.SHOP, GameLevel.ITEMS_SHOP]):
                return False
        return True

    def has_enemy(self):
        all_enemies = GameConfig.get_enemies_config().keys()
        for slot in [self.slot1, self.slot2, self.slot3, self.slot4]:
            if slot in all_enemies:
                return True
        return False

    def all_slots_is_empty(self):
        return self.all_slots_is(self.EMPTY)

    def all_slots_is(self, slots):
        for slot in [self.slot1, self.slot2, self.slot3, self.slot4]:
            if slot not in slots:
                return False
        return True

    def get_shop_count(self):
        return self.get_count_types_on_fields(self.SHOP)

    def get_count_types_on_fields(self, slot_type):
        count = 0
        for slot in [self.slot1, self.slot2, self.slot3, self.slot4]:
            if slot in [slot_type]:
                count += 1
        return count

    def has_shop(self):
        return self.get_shop_count() > 0

    def has_items_shop(self):
        return self.get_count_types_on_fields('items_shop') > 0

    def has_slot_machine(self):
        return self.get_count_types_on_fields(self.SLOT_MACHINE) > 0

    def get_enemy_slot(self):
        all_enemies = GameConfig.get_enemies_config().keys()
        for i, slot in enumerate([self.slot1, self.slot2, self.slot3, self.slot4]):
            if slot in all_enemies:
                return f"slot{i + 1}"
        return None

    def get_current_level_config(self):
        levels = GameConfig.get_game_level_config()['levels']
        return levels[self.get_difficulty()]

    def get_difficulty(self):
        game_level_config = GameConfig.get_game_level_config()
        difficulty_step = game_level_config['difficulty_step']
        levels = game_level_config['levels']
        difficulty = int(self.map_level / difficulty_step)
        return min(difficulty, len(levels) - 1)

    def log_slots(self):
        print(f"GameLevel. > slots: <{[self.slot1, self.slot2, self.slot3, self.slot4]}>")


class UserFollower(DBModel):
    Fields = {
        "user_id": ["INTEGER", 0],
        "username": ["TEXT", ""],
        "took_bonus_time": ["INTEGER", ""]
    }

    def __init__(self, id, user_id, username, took_bonus_time):
        self.id = id
        self.user_id = user_id
        self.username = username
        self.took_bonus_time = int(took_bonus_time)


class UserBag(DBModel):
    Fields = {
        "user_id": ["INTEGER", 0],
        "max_slots": ["INTEGER", 3],
    }

    def __init__(self, id, user_id, max_slots):
        self.id = id
        self.user_id = user_id
        self.max_slots = max_slots


class UserItem(DBModel):
    Fields = {
        "bag_id": ["INTEGER", 0],
        "item_id": ["INTEGER", 3],
        "count": ["INTEGER", 1],
    }

    def __init__(self, id, bag_id, item_id, count):
        self.id = id
        self.bag_id = bag_id
        self.item_id = item_id
        self.count = count


class MapLog(DBModel):
    Fields = {
        "user_id": ["INTEGER", 0],
        "map_level": ["INTEGER", 3],
        "log_type": ["TEXT", ""],
        "value": ["INTEGER", 1],
        "other": ["TEXT", ""],
    }

    def __init__(self, id, user_id, map_level, log_type, value, other):
        self.id = id
        self.user_id = user_id
        self.map_level = map_level
        self.log_type = log_type
        self.value = value
        self.other = other


class ShopInvoice(DBModel):
    STARTED = "started"
    SENT = "SENT"
    PRE_CHECKOUT = "pre_checkout"
    SUCCESS = "success"
    REFUND = "refund"

    Fields = {
        "user_id": ["INTEGER", 0],
        "shop_item_id": ["TEXT", ""],
        "invoice_status": ["TEXT", ""],
        "charge_id": ["TEXT", ""],
        "shop_type": ["TEXT", ""],
    }

    def __init__(self, id, user_id, shop_item_id, invoice_status, charge_id, shop_type):
        self.id = id
        self.user_id = user_id
        self.shop_item_id = shop_item_id
        self.invoice_status = invoice_status
        self.charge_id = charge_id
        self.shop_type = shop_type
