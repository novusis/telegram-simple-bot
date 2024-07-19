from aiogram import types
from aiogram.types import InlineKeyboardButton, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


class Keyboards:
    def __init__(self, game, templator):
        self.game = game
        self.templator = templator

    def main_menu(self, start_game, bonuses, top):
        builder = ReplyKeyboardBuilder()
        builder.row(types.KeyboardButton(text=start_game))
        builder.row(KeyboardButton(text=bonuses))
        builder.row(KeyboardButton(text=top))
        return builder.as_markup(resize_keyboard=False)

    def delete_user(self):
        return types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text='Yes', callback_data=f'delete_user_yes'),
                                                            types.InlineKeyboardButton(text='No', callback_data=f'delete_user_no')]])

    def shop(self):
        builder = InlineKeyboardBuilder()
        shop_stars_data = self.game.get_shop_stars_data()
        for shop in shop_stars_data:
            # builder.button(text="20 ⭐️", callback_data=f'add_balance|{user.username}', pay=True)
            builder.row(
                InlineKeyboardButton(text=self.templator.get("action_stars_shop_item", shop.get_goods_view(self.templator.get), str(shop.price)), callback_data=f'shop_item_star|{shop.item_id}', pay=True))
        return builder.as_markup()

    def collect_bonus(self, coins):
        builder = InlineKeyboardBuilder()
        if coins > 0:
            builder.button(text=self.templator.get('collect_followers_bonus', coins), callback_data=f'collect_bonus')
        return builder.as_markup()

    def bonus_invite(self, user_external_id):
        return types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text=self.templator.get("open_your_invite_url"), url=self.templator.get("bot_invite_url", user_external_id))]])

    def sponsor(self, label, url):
        return types.InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=label, url=url)]])

    def cheats(self):
        return (InlineKeyboardBuilder().
                button(text=self.templator.get("slot_icon_live"), callback_data=f"cheat_lives").
                button(text=self.templator.get("slot_icon_coins"), callback_data=f"cheat_coins").
                button(text=self.templator.get("slot_icon_armor"), callback_data=f"cheat_armor").
                as_markup())
