import json
import sqlite3
from copy import copy

import utils

# Model example:
"""
class UserFollower:
    Fields = {
        "user_id": ["INTEGER", 0],
        "username": ["TEXT", ""],
        "took_bonus_time": ["INTEGER", ""]
        "content_list": ["JSON", []],
        "content_dict": ["JSON", {}]
    }

    def __init__(self, id, user_id, username, took_bonus_time, content_list, content_dict):
        self.id = id
        self.user_id = user_id
        self.username = username
        self.took_bonus_time = int(took_bonus_time)
        self.content_list = int(content_list)
        self.content_dict = int(content_dict)

    def __getitem__(self, item):
        return getattr(self, item)

    def __setitem__(self, key, value):
        return setattr(self, key, value)
"""


class QueryOptions:
    SORT_ASC = 'ASC'
    SORT_DESC = 'DESC'

    def __init__(self, order_by=None, order_direction='ASC', limit=None, offset=None):
        self.order_by = order_by
        self.order_direction = order_direction  # 'ASC' и 'DESC'
        self.limit = limit
        self.offset = offset


class BufferedInfoManager:
    """
    Buffers DBInfo updates so reads do not immediately write back to SQLite.
    The public read methods mirror ModelManager enough for existing code that
    reads game.info directly.
    """

    def __init__(self, info_manager, batch_size=100, flush_interval_seconds=30):
        self.info_manager = info_manager
        self.batch_size = batch_size
        self.flush_interval_seconds = flush_interval_seconds
        self.pending = {}
        self.pending_events = 0
        self.last_flush_time = utils.now_unix_time()

    def record_get(self, table_name, target_id):
        self._record(table_name, target_id, get_count=1)

    def record_set(self, table_name, target_id):
        self._record(table_name, target_id, set_count=1)
        self.flush(force=True)

    def record_delete(self, table_name, target_id):
        self._record(table_name, target_id, delete=True)
        self.flush(force=True)

    def flush(self, force=False):
        if not self.pending:
            return

        now = utils.now_unix_time()
        if not force and self.pending_events < self.batch_size and now - self.last_flush_time < self.flush_interval_seconds:
            return

        pending_items = list(self.pending.items())
        self.pending = {}
        self.pending_events = 0
        self.last_flush_time = now

        for key, pending_info in pending_items:
            table_name, target_id = key
            stored_items = self.info_manager.filter_by_fields({
                'table_name': table_name,
                'target_id': target_id
            })
            if stored_items:
                info = stored_items[0]
                self._merge_info(info, pending_info)
            else:
                info = pending_info
            self.info_manager.set(info)

    def all(self, query_options=None):
        items = self.info_manager.all(query_options)
        return self._apply_pending_to_items(items)

    def get(self, id):
        item = self.info_manager.get(id)
        if not item:
            return None
        return self._apply_pending_to_item(item)

    def filter_by_field(self, field_name, field_value, query_options=None):
        items = self.info_manager.filter_by_field(field_name, field_value, query_options)
        return self._apply_pending_to_items(items, {field_name: field_value})

    def filter_by_fields(self, fields_dict, query_options=None):
        items = self.info_manager.filter_by_fields(fields_dict, query_options)
        return self._apply_pending_to_items(items, fields_dict)

    def set(self, model):
        return self.info_manager.set(model)

    def delete(self, id):
        return self.info_manager.delete(id)

    def _record(self, table_name, target_id, get_count=0, set_count=0, delete=False):
        if target_id is None:
            return

        current_time = utils.now_unix_time()
        key = (table_name, target_id)
        info = self.pending.get(key)
        if not info:
            initial_set_time = current_time if get_count or set_count else 0
            info = DBInfo(None, table_name, target_id, current_time, initial_set_time, 0, 0, 0, 0)
            self.pending[key] = info

        if set_count:
            info.set_time = current_time
            info.set_count += set_count
        if get_count:
            info.get_time = current_time
            info.get_count += get_count
        if delete:
            info.delete_time = current_time

        self.pending_events += get_count + set_count + (1 if delete else 0)
        self.flush()

    def _apply_pending_to_items(self, items, fields_filter=None):
        result = []
        seen_keys = set()

        for item in items:
            item = self._apply_pending_to_item(item)
            seen_keys.add((item.table_name, item.target_id))
            result.append(item)

        for key, pending_info in self.pending.items():
            if key in seen_keys:
                continue
            if fields_filter and not self._matches_filter(pending_info, fields_filter):
                continue
            result.append(copy(pending_info))

        return result

    def _apply_pending_to_item(self, item):
        key = (item.table_name, item.target_id)
        pending_info = self.pending.get(key)
        item = copy(item)
        if pending_info:
            self._merge_info(item, pending_info)
        return item

    @staticmethod
    def _matches_filter(info, fields_filter):
        for field, value in fields_filter.items():
            if getattr(info, field) != value:
                return False
        return True

    @staticmethod
    def _merge_info(info, pending_info):
        if not info.create_time:
            info.create_time = pending_info.create_time
        if pending_info.set_time:
            info.set_time = pending_info.set_time
        if pending_info.get_time:
            info.get_time = pending_info.get_time
        if pending_info.delete_time:
            info.delete_time = pending_info.delete_time
        info.set_count += pending_info.set_count
        info.get_count += pending_info.get_count


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
            processed_record = self._deserialize_fields(record)
            return self._make_model(processed_record)
        return None

    def set(self, model):
        fields_and_value = {}

        for field in model.Fields:
            value = model[field]
            field_type = model.Fields[field][0]

            # Сериализуем списки в JSON перед сохранением
            if field_type == "JSON":
                fields_and_value[field] = json.dumps(value) if value is not None else json.dumps([])
            else:
                fields_and_value[field] = value

        # if model.id is None to create, if no to update
        if model.id is None:
            model.id = self.db.create_record(self.table_name, fields_and_value)
        else:
            self.db.update_record(self.table_name, model.id, fields_and_value)

        if self.info:
            self.info.record_set(self.table_name, model.id)

        return model.id

    def _deserialize_fields(self, record):
        """
        Deserialization from a database based on types defined in Fields model
        """
        result = []
        fields = list(self.model_class.Fields.values())

        for index, value in enumerate(record):
            if 0 < index <= len(fields) and fields[index - 1][0] == "JSON":
                if value == "":
                    result.append(fields[index - 1][1])
                else:
                    result.append(json.loads(value))
            else:
                result.append(value)

        return result

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
            self.info.record_delete(self.table_name, id)

    def delete_by_field(self, filed, value):
        items = self.filter_by_field(filed, value)
        if items:
            for item in items:
                self.delete(item.id)

    def _make_model(self, record):
        model = self.model_class(*record)
        if self.info:
            self.info.record_get(self.table_name, model.id)
        return model


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
