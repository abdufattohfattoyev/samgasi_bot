from .database import Database
from datetime import datetime, timedelta
import pytz  # Mahalliy vaqt uchun kutubxona

class UserDatabase(Database):
    def __init__(self, path_to_db: str):
        super().__init__(path_to_db)  # Ota sinfning konstruktorini chaqirish
        self.uzbekistan_tz = pytz.timezone("Asia/Tashkent")  # Mahalliy vaqt zonasini aniqlash

    def _get_current_time(self):
        """Joriy vaqtni olish uchun yordamchi funksiya."""
        return datetime.now(self.uzbekistan_tz)

    def _get_start_of_day(self, date: datetime):
        """Kun boshlanishini olish uchun yordamchi funksiya."""
        return date.replace(hour=0, minute=0, second=0, microsecond=0)

    def create_table_users(self):
        sql = """
            CREATE TABLE IF NOT EXISTS Users(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id BIGINT NOT NULL,
                username VARCHAR(255) NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_active DATETIME NULL,
                is_admin BOOLEAN NOT NULL DEFAULT 0
            );
        """
        self.execute(sql, commit=True)

    def add_user(self, telegram_id: int, username: str = None):
        created_at = self._get_current_time().isoformat()  # Mahalliy vaqt
        if username is None:  # Agar username bo'lmasa, uni bo'sh qilib qo'ying
            username = "Unknown"
        sql = """
            INSERT INTO Users(telegram_id, username, created_at) VALUES(?, ?, ?)
        """
        self.execute(sql, parameters=(telegram_id, username, created_at), commit=True)

    def select_all_users(self):
        sql = """
            SELECT * FROM Users
        """
        return self.execute(sql, fetchall=True)

    def count_users(self):
        sql = """
            SELECT COUNT(*) FROM Users
        """
        return self.execute(sql, fetchone=True)[0]

    def select_user(self, telegram_id: int):
        sql = """
            SELECT * FROM Users WHERE telegram_id = ?
        """
        return self.execute(sql, parameters=(telegram_id,), fetchone=True)

    def get_user_by_id(self, user_id):
        """Foydalanuvchi ID bilan ma'lumotlarni olish"""
        sql = """
            SELECT * FROM Users WHERE telegram_id = ?
        """
        return self.execute(sql, parameters=(user_id,), fetchone=True)

    def count_daily_users(self):
        now = self._get_current_time()
        today_start = self._get_start_of_day(now)
        tomorrow_start = today_start + timedelta(days=1)

        sql = """
            SELECT COUNT(*) FROM Users
            WHERE created_at >= ? AND created_at < ?
        """
        return self.execute(
            sql, parameters=(today_start.isoformat(), tomorrow_start.isoformat()), fetchone=True
        )[0]

    def count_weekly_users(self):
        now = self._get_current_time()
        one_week_ago = now - timedelta(days=7)

        sql = """
            SELECT COUNT(*) FROM Users
            WHERE created_at >= ?
        """
        return self.execute(sql, parameters=(one_week_ago.isoformat(),), fetchone=True)[0]

    def count_monthly_users(self):
        now = self._get_current_time()
        one_month_ago = now - timedelta(days=30)

        sql = """
            SELECT COUNT(*) FROM Users
            WHERE created_at >= ?
        """
        return self.execute(sql, parameters=(one_month_ago.isoformat(),), fetchone=True)[0]

    def update_last_active(self, telegram_id: int):
        last_active = self._get_current_time().isoformat()  # Mahalliy vaqt
        sql = """
            UPDATE Users
            SET last_active = ?
            WHERE telegram_id = ?
        """
        self.execute(sql, parameters=(last_active, telegram_id), commit=True)

    def count_active_daily_users(self):
        now = self._get_current_time()
        today_start = self._get_start_of_day(now)
        tomorrow_start = today_start + timedelta(days=1)

        sql = """
            SELECT COUNT(*) FROM Users
            WHERE last_active >= ? AND last_active < ?
        """
        return self.execute(
            sql, parameters=(today_start.isoformat(), tomorrow_start.isoformat()), fetchone=True
        )[0]

    def count_active_weekly_users(self):
        now = self._get_current_time()
        one_week_ago = now - timedelta(days=7)

        sql = """
            SELECT COUNT(*) FROM Users
            WHERE last_active >= ?
        """
        return self.execute(sql, parameters=(one_week_ago.isoformat(),), fetchone=True)[0]

    def count_active_monthly_users(self):
        now = self._get_current_time()
        one_month_ago = now - timedelta(days=30)

        sql = """
            SELECT COUNT(*) FROM Users
            WHERE last_active >= ?
        """
        return self.execute(sql, parameters=(one_month_ago.isoformat(),), fetchone=True)[0]

    def check_if_admin(self, user_id: int):
        query = "SELECT is_admin FROM Users WHERE telegram_id = ?"
        result = self.execute(query, parameters=(user_id,), fetchone=True)
        return bool(result) and result[0] == 1
# Jadvalga is_admin ustunini qo'shish
    def add_is_admin_column(self):
        sql = """
            ALTER TABLE Users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0
        """
        self.execute(sql, commit=True)




    def create_table_referral_rewards(self):
        sql = """
        CREATE TABLE IF NOT EXISTS ReferralRewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            reward_amount DECIMAL(10, 2) NOT NULL DEFAULT 0.0,
            referrals_count INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES Users (id) ON DELETE CASCADE
        );
        """
        self.execute(sql, commit=True)

    def create_table_transaction_history(self):
        sql = """
        CREATE TABLE IF NOT EXISTS TransactionHistory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount DECIMAL(10, 2) NOT NULL,
            transaction_type VARCHAR(50) NOT NULL, -- 'reward', 'withdraw'
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES Users (id)
        );
        """
        self.execute(sql, commit=True)

    def update_referral_reward(self, referrer_id: int, reward_amount: float):
        sql_check = "SELECT * FROM ReferralRewards WHERE user_id = ?"
        reward = self.execute(sql_check, parameters=(referrer_id,), fetchone=True)

        if reward:
            sql_update = """
            UPDATE ReferralRewards 
            SET reward_amount = reward_amount + ?, referrals_count = referrals_count + 1
            WHERE user_id = ?
            """
            self.execute(sql_update, parameters=(reward_amount, referrer_id), commit=True)
        else:
            sql_insert = """
            INSERT INTO ReferralRewards(user_id, reward_amount, referrals_count) VALUES(?, ?, 1)
            """
            self.execute(sql_insert, parameters=(referrer_id, reward_amount), commit=True)

        # Update user balance
        self.update_user_balance(referrer_id, reward_amount)
        # Add transaction history
        self.add_transaction_history(referrer_id, reward_amount, 'reward')

    def withdraw_user_balance(self, user_id: int, amount: float):
        user = self.select_user(id=user_id)
        if user and user[4] >= amount:  # assuming balance is the 5th element
            sql = """
            UPDATE Users
            SET balance = balance - ?
            WHERE id = ?
            """
            self.execute(sql, parameters=(amount, user_id), commit=True)
            self.add_transaction_history(user_id, -amount, 'withdraw')
        else:
            print("Insufficient balance.")

    def add_transaction_history(self, user_id: int, amount: float, transaction_type: str):
        sql = """
        INSERT INTO TransactionHistory(user_id, amount, transaction_type, created_at)
        VALUES (?, ?, ?, ?)
        """
        created_at = datetime.now().isoformat()
        self.execute(sql, parameters=(user_id, amount, transaction_type, created_at), commit=True)

    def get_user_referral_summary(self, user_id: int):
        sql = """
        SELECT reward_amount, referrals_count
        FROM ReferralRewards
        WHERE user_id = ?
        """
        return self.execute(sql, parameters=(user_id,), fetchone=True)

    def get_user_referral_details(self, user_id: int):
        sql = """
        SELECT Users.username, Users.balance, ReferralRewards.reward_amount, ReferralRewards.referrals_count
        FROM Users
        LEFT JOIN ReferralRewards ON Users.id = ReferralRewards.user_id
        WHERE Users.id = ?
        """
        return self.execute(sql, parameters=(user_id,), fetchone=True)

    def count_users_added_since(self, since_time):
        sql = """
        SELECT COUNT(*) FROM Users WHERE created_at >= ?
        """
        return self.execute(sql, parameters=(since_time.isoformat(),), fetchone=True)[0]

    def count_active_users_since(self, since_time):
        sql = """
        SELECT COUNT(*) FROM Users WHERE last_active >= ?
        """
        return self.execute(sql, parameters=(since_time.isoformat(),), fetchone=True)[0]


