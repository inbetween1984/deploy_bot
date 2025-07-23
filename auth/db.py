import sqlite3
import os

class Database:
    def __init__(self, db_path="data/bot.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.init_db()

    def init_db(self):
        """Инициализирует базу данных и создает таблицу users."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    chat_id INTEGER PRIMARY KEY,
                    permissions TEXT
                )
            """)
            conn.commit()

    def user_exists(self, chat_id: int) -> bool:
        """Проверяет, существует ли пользователь в базе."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM users WHERE chat_id = ?", (chat_id,))
            return cursor.fetchone() is not None

    def add_user(self, chat_id: int, permissions: str = ""):
        """Добавляет пользователя с указанными правами (по умолчанию без прав)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO users (chat_id, permissions) VALUES (?, ?)",
                          (chat_id, permissions))
            conn.commit()

    def remove_user(self, chat_id: int):
        """Удаляет пользователя из базы."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE chat_id = ?", (chat_id,))
            conn.commit()

    def update_permissions(self, chat_id: int, permissions: str):
        """Обновляет права пользователя."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET permissions = ? WHERE chat_id = ?",
                          (permissions, chat_id))
            conn.commit()

    def get_user_permissions(self, chat_id: int) -> str:
        """Возвращает права пользователя."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT permissions FROM users WHERE chat_id = ?", (chat_id,))
            result = cursor.fetchone()
            return result[0] if result else ""

    def list_users(self) -> list:
        """Возвращает список всех пользователей и их прав."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT chat_id, permissions FROM users")
            return cursor.fetchall()