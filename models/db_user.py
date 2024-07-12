from models.database import DBModel


class User(DBModel):
    MAX_NAME_LENGTH = 20
    Fields = {
        "bot": ["BLOB", False],
        "external_id": ["TEXT", ""],
        "username": ["TEXT", ""],
        "chat_id": ["INTEGER", 0],
        "name": ["TEXT", ""],
        "scores": ["INTEGER", 0],
        "coins": ["INTEGER", 0],
    }

    def __init__(self, id, bot, external_id, username, chat_id, name, scores, coins):
        self.id = id
        self.bot = bot
        self.external_id = external_id
        self.username = username
        self.chat_id = chat_id
        self.name = name
        self.scores = scores
        self.coins = coins

    def get_username_or_name(self):
        return self.username if self.username else self.name


class UserFollower(DBModel):
    Fields = {
        "user_id": ["INTEGER", 0],
        "user_to_follow_id": ["INTEGER", 0],
        "took_bonus_time": ["INTEGER", ""]
    }

    def __init__(self, id, user_id, user_to_follow_id, took_bonus_time):
        self.id = id
        self.user_id = user_id
        self.user_to_follow_id = user_to_follow_id
        self.took_bonus_time = int(took_bonus_time)
