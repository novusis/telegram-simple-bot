import sqlite3
import time

import utils


# Model example:
# class UserFollower:
#     Fields = {
#         "user_id": ["INTEGER", 0],
#         "username": ["TEXT", ""],
#         "took_bonus_time": ["INTEGER", ""]
#     }
# 
#     def __init__(self, id, user_id, username, took_bonus_time):
#         self.id = id
#         self.user_id = user_id
#         self.username = username
#         self.took_bonus_time = int(took_bonus_time)
# 
#     def __getitem__(self, item):
#         return getattr(self, item)
# 
#     def __setitem__(self, key, value):
#         return setattr(self, key, value)

class QueryOptions:
    SORT_ASC = 'ASC'
    SORT_DESC = 'DESC'

    def __init__(self, order_by=None, order_direction='ASC', limit=None, offset=None):
        self.order_by = order_by
        self.order_direction = order_direction  # 'ASC' и 'DESC'
        self.limit = limit
        self.offset = offset


class ModelManager:

    def __init__(self, table_name, model_class, db, info=None):
        self.table_name = table_name
        self.model_class = model_class
        self.db = db
        self.db.init_table(table_name, model_class.Fields)
        self.info = info

    def all(self, query_options=None):
        results = []
        order_by = f"ORDER BY {query_options.order_by} {query_options.order_direction}" if query_options and query_options.order_by else ""

        limit_offset = ""
        if query_options:
            if query_options.limit is not None:
                limit_offset = f"LIMIT {query_options.limit}"
                if query_options.offset is not None:
                    limit_offset += f" OFFSET {query_options.offset}"

        query = f"SELECT * FROM {self.table_name} {order_by} {limit_offset}"

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            records = cursor.fetchall()
            for record in records:
                model_instance = self._make_model(record)
                results.append(model_instance)
        return results

    def get(self, id):
        record = self.db.read_record(self.table_name, id)
        if record:
            return self._make_model(record)
        return None

    def set(self, model):
        fields_and_value = {}

        # if self.info and self.table_name != 'info':
        #     utils.log_stack(f"ModelManager.set > self <{self.table_name}>:\n", limit=5)

        for field in model.Fields:
            fields_and_value[field] = model[field]
        # if model.id is None to create, if no to update
        if model.id is None:
            model.id = self.db.create_record(self.table_name, fields_and_value)
        else:
            self.db.update_record(self.table_name, model.id, fields_and_value)

        self._make_info(model, self._info_set)

        return model.id

    def _make_info(self, model, informer):
        if self.info:
            current_time = utils.now_unix_time()
            targets = self.info.filter_by_fields({'table_name': self.table_name, 'target_id': model.id})
            if len(targets) > 0:
                target = targets[0]
            else:
                target = DBInfo(None, self.table_name, model.id, current_time, current_time, 0, 0, 0, 0)
            informer(target, current_time)
            self.info.set(target)

    def filter_by_field(self, field_name, field_value, query_options=None):
        results = []
        order_by = f"ORDER BY {query_options.order_by} {query_options.order_direction}" if query_options and query_options.order_by else ""

        limit_offset = ""
        if query_options:
            if query_options.limit is not None:
                limit_offset = f"LIMIT {query_options.limit}"
                if query_options.offset is not None:
                    limit_offset += f" OFFSET {query_options.offset}"

        query = f"SELECT * FROM {self.table_name} WHERE {field_name} = ? {order_by} {limit_offset}"

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (field_value,))
            records = cursor.fetchall()
            for record in records:
                model_instance = self._make_model(record)
                results.append(model_instance)
        return results

    def filter_by_fields(self, fields_dict, query_options=None):
        results = []
        order_by = f"ORDER BY {query_options.order_by} {query_options.order_direction}" if query_options and query_options.order_by else ""

        limit_offset = ""
        if query_options:
            if query_options.limit is not None:
                limit_offset = f"LIMIT {query_options.limit}"
                if query_options.offset is not None:
                    limit_offset += f" OFFSET {query_options.offset}"

        field_queries = [f"{field} = ?" for field in fields_dict.keys()]
        query = f"SELECT * FROM {self.table_name} WHERE {' AND '.join(field_queries)} {order_by} {limit_offset}"

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(fields_dict.values()))
            records = cursor.fetchall()
            for record in records:
                model_instance = self._make_model(record)
                results.append(model_instance)
        return results

    def delete(self, id):
        self.db.delete_record(self.table_name, id)
        if self.info:
            targets = self.info.filter_by_fields({'table_name': self.table_name, 'target_id': id})
            if len(targets) > 0:
                targets[0].delete_time = time.time()
                self.info.set(targets[0])

    def delete_by_field(self, filed, value):
        items = self.filter_by_field(filed, value)
        if items:
            for item in items:
                self.delete(item.id)

    def _make_model(self, record):
        model = self.model_class(*record)
        self._make_info(model, self._info_get)
        return model

    @staticmethod
    def _info_set(target, current_time):
        target.set_time = current_time
        target.set_count += 1

    @staticmethod
    def _info_get(target, current_time):
        target.get_time = current_time
        target.get_count += 1


class DBModel:
    def __getitem__(self, item):
        return getattr(self, item)

    def __setitem__(self, key, value):
        return setattr(self, key, value)

    def __str__(self):
        output = []
        for attr in vars(self):
            value = getattr(self, attr)
            if attr.endswith("_time"):
                if value != 0:
                    value = utils.convert_unix_timestamp_to_readable(value)
                else:
                    value = "None"
            if value == '':
                value = "None"
            output.append(f"{attr}={value}")
        return f"{type(self).__name__}: {', '.join(output)}"


class DBVar(DBModel):
    Fields = {
        "var_name": ["TEXT", "noname"],
        "var_value": ["TEXT", ""]
    }

    def __init__(self, id, var_name, var_value):
        self.id = id
        self.var_name = var_name
        self.var_value = var_value


class DBInfo(DBModel):
    Fields = {
        "table_name": ["TEXT", 0],
        "target_id": ["INTEGER", 0],
        "create_time": ["INTEGER", 0],
        "set_time": ["INTEGER", 0],
        "get_time": ["INTEGER", 0],
        "set_count": ["INTEGER", 0],
        "get_count": ["INTEGER", 0],
        "delete_time": ["INTEGER", 0]
    }

    def __init__(self, id, table_name, target_id, create_time, set_time, get_time, set_count, get_count, delete_time):
        self.id = id
        self.table_name = table_name
        self.target_id = target_id
        self.create_time = create_time
        self.set_time = set_time
        self.get_time = get_time
        self.set_count = set_count
        self.get_count = get_count
        self.delete_time = delete_time


class Database:
    def __init__(self, db_name):
        self.db_name = db_name

    def get_column_names(self, table_name):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [column[1] for column in cursor.fetchall()]
        conn.close()

        return columns

    def get_connection(self):
        return sqlite3.connect(self.db_name)

    def init_table(self, table_name, fields):
        with self.get_connection() as conn:
            conn.execute(f"CREATE TABLE IF NOT EXISTS {table_name} (id INTEGER PRIMARY KEY AUTOINCREMENT)")
            for field_name, field_props in fields.items():
                field_type, default_value = field_props
                self.add_column(conn, table_name, field_name, field_type, default_value)

    def add_column(self, conn, table_name, new_column, column_type="TEXT", default_value=None):
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [column[1] for column in cursor.fetchall()]
        if new_column not in columns:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {new_column} {column_type}")
            cursor.execute(f"UPDATE {table_name} SET {new_column} = ?", (default_value,))
        cursor.close()

    def create_record(self, table_name, fields):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            columns = ', '.join(fields.keys())
            placeholders = ', '.join('?' * len(fields))
            conn.execute(f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})", tuple(fields.values()))
            conn.commit()
            cursor.execute("SELECT last_insert_rowid();")
            id_of_new_row = cursor.fetchone()[0]
        return id_of_new_row

    def read_record(self, table_name, id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {table_name} WHERE id = ?", (id,))
            record = cursor.fetchone()
            return record

    def update_record(self, table_name, id, fields):
        with self.get_connection() as conn:
            columns = ', '.join(f"{k} = ?" for k in fields.keys())
            conn.execute(f"UPDATE {table_name} SET {columns} WHERE id = ?", (*fields.values(), id))

    def delete_record(self, table_name, id):
        with self.get_connection() as conn:
            conn.execute(f"DELETE FROM {table_name} WHERE id = ?", (id,))
            conn.commit()

    def delete_table(self, table_name):
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute(f"DROP TABLE IF EXISTS {table_name};")
        conn.close()
        print(f"Table <{table_name}> deleted successfully.")

    def query(self, query, params=()):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()
