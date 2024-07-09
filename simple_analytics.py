import io

import matplotlib.pyplot as plt
from datetime import datetime, timedelta

import utils
from models.database import Database, DBModel, ModelManager


class AnalyticsPlayers(DBModel):
    Fields = {
        "player_id": ["INTEGER", 0],
        "registration_date": ["TEXT", ""]
    }

    def __init__(self, id, player_id, registration_date):
        self.id = id
        self.player_id = player_id
        self.registration_date = registration_date


class AnalyticsLogins(DBModel):
    Fields = {
        "player_id": ["INTEGER", 0],
        "login_date": ["TEXT", ""]
    }

    def __init__(self, id, player_id, login_date):
        self.id = id
        self.player_id = player_id
        self.login_date = login_date


class AnalyticsPayments(DBModel):
    Fields = {
        "player_id": ["INTEGER", 0],
        "amount": ["REAL", 0.0],  # Decimal
        "payment_date": ["TEXT", ""]
    }

    def __init__(self, id, player_id, amount, payment_date):
        self.id = id
        self.player_id = player_id
        self.amount = amount
        self.payment_date = payment_date


class AnalyticsSessions(DBModel):
    Fields = {
        "player_id": ["INTEGER", 0],
        "session_length": ["REAL", 0.0]  # Decimal
    }

    def __init__(self, id, player_id, session_length):
        self.id = id
        self.player_id = player_id
        self.session_length = session_length


class SimpleAnalytics:
    def __init__(self, db_name):
        self.db = Database(db_name)
        # self.db.delete_table('players')
        # self.db.delete_table('logins')
        # self.db.delete_table('payments')
        # self.db.delete_table('sessions')
        self.players = ModelManager('players', AnalyticsPlayers, self.db)
        self.logins = ModelManager('logins', AnalyticsLogins, self.db)
        self.payments = ModelManager('payments', AnalyticsPayments, self.db)
        self.sessions = ModelManager('sessions', AnalyticsSessions, self.db)

        # test_players = 6
        # player_ids = []
        # for data_day in range(0, test_players):
        #     player_ids.append(random.randint(10000, 99999))
        # 
        # test_days_back = [15, 15, 2, 2, 1, 1]
        # test_day = 0
        # for player_id in player_ids:
        #     days = test_days_back[test_day]
        #     test_day += 1
        #     # days = random.randint(0, test_days)
        #     # hours = random.randint(0, 24)
        #     if days == 0:
        #         time = timedelta(days=days, hours=0, minutes=1)
        #     else:
        #         if days == 1:
        #             time = timedelta(days=days, hours=-6)
        #         else:
        #             time = timedelta(days=days, hours=-1)
        #     self.set_player(player_id, utils.get_string_by_utc(datetime.utcnow() - time))
        #     self.set_login(player_id, utils.get_string_by_utc(datetime.utcnow() - time))
        #     session_time = random.random() * 1500
        #     self.set_session(player_id, session_time)
        #     player = self.players.filter_by_field('player_id', player_id)[0]
        # 
        #     if test_day == 2:
        #         time = timedelta(days=6, hours=0)
        #         self.set_login(player_id, utils.get_string_by_utc(datetime.utcnow() - time))
        #         time = timedelta(days=6, hours=1)
        #         self.set_login(player_id, utils.get_string_by_utc(datetime.utcnow() - time))
        #         time = timedelta(days=6, hours=1, minutes=15)
        #         self.set_payments(player_id, 39, utils.get_string_by_utc(datetime.utcnow() - time))
        #     if test_day == 5:
        #         time = timedelta(days=days, hours=1)
        #         self.set_payments(player_id, 39, utils.get_string_by_utc(datetime.utcnow() - time))
        #     if test_day == 6:
        #         time = timedelta(days=days, hours=4)
        #         self.set_payments(player_id, 69, utils.get_string_by_utc(datetime.utcnow() - time))

    def set_player(self, player_id, date=None):
        players = self.players.filter_by_field('player_id', player_id)
        if len(players) > 0:
            return
        if date is None:
            date = utils.get_string_by_utc(datetime.utcnow())
        self.players.set(AnalyticsPlayers(None, player_id, date))

    def set_login(self, player_id, date=None):
        if date is None:
            date = utils.get_string_by_utc(datetime.utcnow())
        self.logins.set(AnalyticsLogins(None, player_id, date))

    def set_payments(self, player_id, amount, date=None):
        if date is None:
            date = utils.get_string_by_utc(datetime.utcnow())
        self.payments.set(AnalyticsPayments(None, player_id, amount, date))

    def set_session(self, player_id, session_length):
        self.sessions.set(AnalyticsSessions(None, player_id, session_length))

    def get_total_players(self):
        query = "SELECT COUNT(*) FROM players"
        result = self.db.query(query)
        return result[0][0] if result else 0

    def get_new_players(self, period):
        query = f"SELECT COUNT(*) FROM players WHERE registration_date > datetime('now', '-{period} days', 'start of day') AND registration_date < datetime('now', 'start of day')"
        result = self.db.query(query)
        return result[0][0] if result else 0

    def get_new_players_per_day(self, period):
        if period == 0:
            query = f"""
                SELECT COUNT(*) 
                FROM players 
                WHERE registration_date >= datetime('now', 'start of day') 
                AND registration_date < datetime('now')
            """
        else:
            query = f"""
                SELECT COUNT(*) 
                FROM players 
                WHERE registration_date >= datetime('now', 'start of day', '-{period} days') 
                AND registration_date < datetime('now', 'start of day', '-{period - 1} days')
            """
        result = self.db.query(query)
        return result[0][0] if result else 0

    def get_active_players(self, period):
        query = f"SELECT COUNT(DISTINCT player_id) FROM logins WHERE login_date > datetime('now', '-{period} days', 'start of day') AND login_date < datetime('now', 'start of day')"
        result = self.db.query(query)
        return result[0][0] if result else 0

    def get_active_players_per_day(self, period):
        if period == 0:
            query = f"""
                SELECT COUNT(DISTINCT player_id) 
                FROM logins 
                WHERE login_date >= datetime('now', 'start of day') 
                AND login_date < datetime('now')
            """
        else:
            query = f"""
                SELECT COUNT(DISTINCT player_id) 
                FROM logins 
                WHERE login_date >= datetime('now', 'start of day', '-{period} days') 
                AND login_date < datetime('now', 'start of day', '-{period - 1} days')
            """
        result = self.db.query(query)
        return result[0][0] if result else 0

    def get_payments(self, period):
        query = f"SELECT COALESCE(SUM(amount), 0) FROM payments WHERE payment_date > datetime('now', '-{period} days', 'start of day') AND payment_date < datetime('now', 'start of day')"
        result = self.db.query(query)
        return result[0][0] if result else 0

    def get_payments_for_plots(self, period):
        query = f"SELECT COALESCE(SUM(amount), 0) FROM payments WHERE payment_date >= datetime('now', '-{period} days')"
        result = self.db.query(query)
        return result[0][0] if result else 0

    def get_payments_per_user(self, period):
        total_players = self.get_total_players()
        total_payments = self.get_payments(period)
        return total_payments / total_players if total_players > 0 else 0

    def get_payments_per_active_user(self, period):
        active_players = self.get_active_players(period)
        total_payments = self.get_payments(period)
        return total_payments / active_players if active_players > 0 else 0

    def get_average_session_length(self):
        query = "SELECT COALESCE(AVG(session_length), 0) FROM sessions"
        result = self.db.query(query)
        return result[0][0] if result else 0

    def generate_report(self):
        # Получение данных
        total_players = self.get_total_players()
        new_players_daily = self.get_new_players(1)
        new_players_weekly = self.get_new_players(7)
        new_players_monthly = self.get_new_players(30)
        active_players_daily = self.get_active_players(1)
        active_players_weekly = self.get_active_players(7)
        active_players_monthly = self.get_active_players(30)
        payments_daily = self.get_payments(1)
        payments_weekly = self.get_payments(7)
        payments_monthly = self.get_payments(30)
        avg_session_length = utils.convert_seconds_to_hms(self.get_average_session_length())

        # Подготовка отчета
        report = {
            "Total Players": total_players,
            "New Players (Daily)": new_players_daily,
            "New Players (Weekly)": new_players_weekly,
            "New Players (Monthly)": new_players_monthly,
            "Active Players (Daily)": active_players_daily,
            "Active Players (Weekly)": active_players_weekly,
            "Active Players (Monthly)": active_players_monthly,
            "Payments (Daily)": payments_daily,
            "Payments (Weekly)": payments_weekly,
            "Payments (Monthly)": payments_monthly,
            "Average Session Length": avg_session_length,
        }

        return report

    def plot_metrics(self):
        total_players = self.get_total_players()
        dates = [datetime.utcnow() - timedelta(days=i) for i in range(30)]
        new_players = [self.get_new_players_per_day(i) for i in range(30)]
        active_players = [self.get_active_players_per_day(i) for i in range(30)]
        payments = [self.get_payments_for_plots(30) - self.get_payments_for_plots(i) for i in range(30)]

        # Построение графиков
        plt.figure(figsize=(14, 8))

        plt.subplot(3, 1, 1)

        bars = plt.bar(dates, new_players, label='New Players')

        for bar in bars:
            yval = bar.get_height()
            if yval > 0:
                plt.text(bar.get_x() + bar.get_width() / 2.5, yval - 0.5, int(yval), va='bottom', color='white')  # va - это выравнивание вертикали
            else:
                plt.text(bar.get_x() + bar.get_width() / 2.5, yval - 0.5, "", va='bottom')  # va - это выравнивание вертикали

        players_month = self.get_new_players(30)
        plt.text(0.01, 0.90, f'All players: {total_players}', transform=plt.gca().transAxes)
        plt.text(0.01, 0.80, f'New players in last month: {players_month}', transform=plt.gca().transAxes)
        plt.text(0.01, 0.70, f'Average new players per day: {players_month / 30:.2f}', transform=plt.gca().transAxes)

        plt.title('New Players Per Days')
        plt.xlabel('')
        plt.ylabel('Number of Players')
        plt.legend()

        plt.subplot(3, 1, 2)
        plt.plot(dates, active_players, label='Active Players')
        plt.title('Active Players Over Time')
        plt.xlabel('')
        plt.ylabel('Number of Players')
        plt.legend()

        plt.subplot(3, 1, 3)
        plt.plot(dates, payments, label='Payments')
        plt.title('Payments Over Time')
        plt.xlabel('')
        plt.ylabel('Total Payments')
        plt.legend()

        plt.tight_layout()
        # plt.show()

        # Создадим байтовый буфер
        buf = io.BytesIO()

        # Сохраняем изображение в буфер
        plt.savefig(buf, format='jpeg')

        # Получаем байты изображения
        return buf.getvalue()

    def get_report(self):
        report = self.generate_report()
        text = "ANALYTICS REPORT\n"
        for key, value in report.items():
            text += f"{key}: {value}\n"
        view_bytes = self.plot_metrics()
        return [text, view_bytes]

# # Пример использования
# analytics = GameAnalytics(Config.DB_ANALYTICS_URI)
# report = analytics.generate_report()
# 
# for key, value in report.items():
#     print(f"{key}: {value}")
# 
# analytics.plot_metrics()
