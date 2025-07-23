from telegram import Update
from telegram.ext import ContextTypes
from .db import Database
from utils.telegram import send_unauthorized_message
from config import ADMIN_PASSWORD

class Auth:
    def __init__(self, db_path="data/bot.db"):
        self.db = Database(db_path)
        self.admin_password = ADMIN_PASSWORD

    def set_admin_password(self, password: str):
        """Устанавливает пароль для инициализации администратора."""
        self.admin_password = password

    def is_authorized_user(self, chat_id: int) -> bool:
        """Проверяет, есть ли пользователь в базе."""
        return self.db.user_exists(chat_id)

    def check_permission(self, chat_id: int, permission: str) -> bool:
        """Проверяет, есть ли у пользователя указанное разрешение."""
        permissions = self.db.get_user_permissions(chat_id).split(",")
        return permission in permissions or "admin" in permissions

    async def handle_init(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Инициализирует первого администратора с паролем."""
        if self.db.list_users():
            await update.message.reply_text("Инициализация уже выполнена.")
            return

        args = context.args
        if not args or args[0] != self.admin_password:
            await update.message.reply_text("Неверный пароль для инициализации.")
            return

        chat_id = update.message.from_user.id
        self.db.add_user(chat_id, "admin")
        await update.message.reply_text(f"Пользователь {chat_id} назначен администратором.")

    async def handle_add_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Добавляет нового пользователя без прав."""
        chat_id = update.message.from_user.id
        if not self.check_permission(chat_id, "admin"):
            await send_unauthorized_message(update)
            return

        if len(context.args) != 1:
            await update.message.reply_text("Использование: /add_user <chat_id>")
            return

        try:
            new_chat_id = int(context.args[0])
            self.db.add_user(new_chat_id)
            await update.message.reply_text(f"Пользователь {new_chat_id} добавлен без прав.")
        except ValueError:
            await update.message.reply_text("Неверный chat_id. Укажите число.")

    async def handle_remove_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Удаляет пользователя."""
        chat_id = update.message.from_user.id
        if not self.check_permission(chat_id, "admin"):
            await send_unauthorized_message(update)
            return

        if len(context.args) != 1:
            await update.message.reply_text("Использование: /remove_user <chat_id>")
            return

        try:
            target_chat_id = int(context.args[0])
            if not self.db.user_exists(target_chat_id):
                await update.message.reply_text("Пользователь не найден.")
                return
            self.db.remove_user(target_chat_id)
            await update.message.reply_text(f"Пользователь {target_chat_id} удален.")
        except ValueError:
            await update.message.reply_text("Неверный chat_id. Укажите число.")

    async def handle_update_permissions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обновляет права пользователя."""
        chat_id = update.message.from_user.id
        if not self.check_permission(chat_id, "admin"):
            await send_unauthorized_message(update)
            return

        if len(context.args) < 2:
            await update.message.reply_text("Использование: /update_permissions <chat_id> <permissions>")
            return

        try:
            target_chat_id = int(context.args[0])
            permissions = ",".join(context.args[1:])
            valid_permissions = [
                "deploy", "containers_list", "containers_start", "containers_stop",
                "containers_remove", "logs_view", "logs_monitor",
                "backups_create", "backups_download", "backups_restore", "admin"
            ]
            if not all(p in valid_permissions for p in permissions.split(",")):
                await update.message.reply_text(f"Неверные права. Доступные: {', '.join(valid_permissions)}")
                return

            if not self.db.user_exists(target_chat_id):
                await update.message.reply_text("Пользователь не найден.")
                return
            self.db.update_permissions(target_chat_id, permissions)
            await update.message.reply_text(f"Права для {target_chat_id} обновлены: {permissions}")
        except ValueError:
            await update.message.reply_text("Неверный chat_id. Укажите число.")

    async def handle_list_users(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает список пользователей и их прав."""
        chat_id = update.message.from_user.id
        if not self.check_permission(chat_id, "admin"):
            await send_unauthorized_message(update)
            return

        users = self.db.list_users()
        if not users:
            await update.message.reply_text("Пользователей нет.")
            return

        response = "Пользователи:\n"
        for chat_id, permissions in users:
            response += f"- Chat ID: {chat_id}, Права: {permissions or 'нет'}\n"
        await update.message.reply_text(response)

    async def handle_whoami(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает chat_id и права текущего пользователя."""
        chat_id = update.message.from_user.id
        if not self.is_authorized_user(chat_id):
            await update.message.reply_text(f"Ваш chat_id: {chat_id}. Вы не авторизованы.")
            return
        permissions = self.db.get_user_permissions(chat_id)
        await update.message.reply_text(f"Ваш chat_id: {chat_id}, Права: {permissions or 'нет'}")
