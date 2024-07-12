import utils
from data.game_config import GameConfig
from models.db_invoices import Invoice
from models.db_user import User, UserFollower
from models.database import ModelManager, Database, QueryOptions, DBInfo


class ShopSlotItem:
    def __init__(self, item_id, count):
        self.item_id = item_id
        self.count = count


class ShopItem:
    def __init__(self, item_id, enable, shop_types, items_type, price):
        self.item_id = item_id
        self.enable = enable
        self.shop_types = shop_types
        self.items_type = items_type
        self.price = price

    def get_goods_view(self, template_get):
        shop_item_view = ""
        for shop_item in self.items_type:
            shop_item_view += f"{template_get(f'slot_icon_{shop_item.item_id}')} {str(shop_item.count)} "
        return shop_item_view


class SimapleGame:

    def __init__(self, template_engine, login_callback):
        self.template_engine = template_engine
        self.login_callback = login_callback
        self.cache_users = utils.CacheManager(login_callback, GameConfig.app('user_online_timeout_seconds'))

        stars_shop = GameConfig.get_shop_config('stars_shop')
        self.SHOP_STARS_DATA = [
            ShopItem(
                item_id=shop_slot['shop_item_id'],
                enable=shop_slot['enable'],
                shop_types=shop_slot['shop_types'],
                items_type=[
                    ShopSlotItem(item['item_id'], item['count'])
                    for item in shop_slot['items']
                ],
                price=shop_slot['price']
            ) for shop_slot in stars_shop
        ]

        self.db = Database(GameConfig.app('db_uri'))
        info = ModelManager('info', DBInfo, self.db)
        self.users = ModelManager('users', User, self.db, info)
        self.followers = ModelManager('user_followers', UserFollower, self.db)
        self.invoices = ModelManager('invoices', Invoice, self.db, info)

        # all_info = info.all()
        # print(f"TTGame all_info len <{len(all_info)}>")
        # for info_item in all_info:
        #     print(f"TTGame allInfo <{info_item}>")

    def get_online(self):
        return self.cache_users.get_online()

    def check_online(self):
        return self.cache_users.check_online()

    def register_user(self, external_id, username, name, chat_id):
        print(f"SimapleGame.register_user register_user <{external_id}><{username}>")
        new_user = User(
            id=None,
            bot=False,
            external_id=external_id,
            username=username,
            name=name,
            chat_id=chat_id,
            scores=0,
            coins=0,
        )
        self.users_set(new_user)
        # self.db.set_user(new_user, True)
        print(f"User {name} registered successfully!")
        return new_user

    def delete_user(self, external_id):
        user = self.get_user(external_id)
        self.cache_users.delete(external_id)
        if user:
            self.followers.delete_by_field('user_id', user.id)
            self.users.delete(user.id)

    def get_self_user(self, external_id, chat_id):
        user = self.get_user(external_id, False)
        if user:
            user.chat_id = chat_id
            self.users.set(user)
            return user

    def get_user(self, external_id, show_error=True):
        if not external_id:
            utils.log_error(f"Error no external_id <{external_id}>")
            return

        external_id = str(external_id)
        user = self.cache_users.get_from_cache(external_id, self.get_user_by_external_id, False)
        if user:
            return user
        else:
            if show_error:
                utils.log_error(f"SimapleGame.get_user error: no user by external_id <{external_id}>")
            return None

    def get_user_by_external_id(self, external_id):
        result = self.users.filter_by_field('external_id', external_id)
        if result:
            return result[0]
        return None

    def get_user_by_username(self, username):
        result = self.users.filter_by_field('username', username)
        if result:
            return result[0]
        return None

    def get_top_players(self, limit=10):
        top_players_list = self.users.filter_by_field('bot', False, QueryOptions("scores", QueryOptions.SORT_DESC, limit))
        return top_players_list

    def get_stars_shop_item_by_invoice(self, invoice_id):
        invoice = self.invoices.get(invoice_id)
        if not invoice:
            print(f"TTGame.get_stars_shop_item_by_invoice > error invoice <{invoice_id}>")
            return None
        item_id = invoice.shop_item_id
        found_item = next((item for item in self.SHOP_STARS_DATA if item.item_id == item_id), None)
        if not found_item:
            print(f"TTGame.get_stars_shop_item_by_invoice > error item id find <{item_id}>")
            return None
        return found_item

    def set_invoice_status(self, invoice_id, status, charge_id=""):
        invoice = self.invoices.get(invoice_id)
        invoice.status = status
        invoice.charge_id = charge_id
        self.invoices.set(invoice)

    def complete_invoice(self, invoice_id, telegram_payment_charge_id):
        shop_item_id = self.invoices.get(invoice_id).shop_item_id
        result = list(filter(lambda item: item.item_id == shop_item_id, self.SHOP_STARS_DATA))[0]
        self.set_invoice_status(invoice_id, Invoice.SUCCESS, telegram_payment_charge_id)
        return result

    def new_game(self, user):
        user.scores = 0

    def collect_bonus(self, user):
        bonus_followers = self.get_bonus_followers(user)
        coins = 0
        for follower in bonus_followers:
            coins += GameConfig.bonus_for_followers('bonus_coins')
            # time to claim bonus
            follower.took_bonus_time = utils.now_unix_time()
            self.followers.set(follower)
        user.coins += coins
        user.bonus_collect = True
        self.save(user)
        return coins

    def get_bonus_followers(self, user):
        followers = self.followers.filter_by_field('user_to_follow_id', user.id)
        followers_ok = []
        for follower in followers:
            user = self.users.get(follower.user_id)
            login_timeout_h = GameConfig.bonus_for_followers('bonus_last_login_timeout_h')
            bonus_timeout_h = GameConfig.bonus_for_followers('bonus_timeout_h')
            bonus_max_followers = GameConfig.bonus_for_followers('bonus_max_followers')
            if user and user.has_game_today() and utils.now_unix_time() - user.last_time_action < login_timeout_h * 60 * 60:
                # check took bonus time
                if utils.now_unix_time() - follower.took_bonus_time > bonus_timeout_h * 60 * 60:
                    followers_ok.append(follower)
            # stop if max users for bonus
            if len(followers_ok) >= bonus_max_followers:
                break

        return followers_ok

    def add_user_to_followers(self, user, user_to_follow):
        followers = self.followers.filter_by_field('user_id', user.id)
        if followers:
            for follower in followers:
                if follower.user_to_follow_id == user_to_follow.id:
                    return False

        current_unix_time = utils.now_unix_time()
        time_to_back = current_unix_time - GameConfig.bonus_for_followers('bonus_timeout_h') * 60 * 60 - 1

        follow_user = UserFollower(
            id=None,
            user_id=user.id,
            user_to_follow_id=user_to_follow.id,
            took_bonus_time=time_to_back
        )
        self.followers.set(follow_user)
        return True

    def start_buy_shop_item_stars(self, user, shop_item_id, shop_type):
        invoices_id = self.invoices.set(Invoice(None, user.id, shop_item_id, Invoice.STARTED, "", shop_type))
        print(f"SimapleGame.start_buy_shop_item_stars start <{shop_item_id}>")
        return invoices_id

    def get_shop_stars_data(self):
        def is_shop_type(shop_item):
            return shop_item.enable

        return list(filter(is_shop_type, self.SHOP_STARS_DATA))

    def apply_invoice_goods(self, invoice_id, shop_item):
        coins = 0
        for item in shop_item.items_type:
            if item.item_id == 'coins':
                coins += item.count
        # result = list(filter(lambda item: item.item_id == 'coins', shop_item.items_type))[0]
        print(f"SimapleGame.apply_invoice_goods invoice_id <{invoice_id}> has coins: +{coins}")
        if coins > 0:
            print(f"SimapleGame.apply_invoice_goods self.invoices.get(invoice_id).user_id <{self.invoices.get(invoice_id).user_id}>")
            user = self.users.get(self.invoices.get(invoice_id).user_id)
            print(f"SimapleGame.apply_invoice_goods user.coins <{user.coins}>")
            user.coins += coins
            print(f"SimapleGame.apply_invoice_goods user.coins <{user.coins}>")
            self.users_set(user)
            return True
        else:
            return False

    def users_set(self, user):
        self.cache_users.set_to_cache(user.external_id, user)
        u = self.get_user(user.external_id)
        self.users.set(user)
