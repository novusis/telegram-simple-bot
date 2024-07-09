from database import DBModel


class User(DBModel):
    MAX_NAME_LENGTH = 20
    Fields = {
        "external_id": ["TEXT", ""],
        "username": ["TEXT", ""],
        "chat_id": ["INTEGER", 0],
        "name": ["TEXT", ""],
        "scores": ["INTEGER", 0],
    }

    def __init__(self, id, external_id, username, chat_id, name, scores):
        self.id = id
        self.external_id = external_id
        self.username = username
        self.chat_id = chat_id
        self.name = name
        self.scores = scores


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
