from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from auth.auth import Auth
from backups.backups import handle_backup, handle_restore, handle_list_backups, handle_download
from containers.containers import handle_containers, handle_start, handle_stop, handle_remove, handle_container_logs, \
    handle_stats
from deploy.deploy import handle_deploy
from files.files import handle_upload, handle_download_file
from logs.logs import handle_logs, handle_tail, handle_monitor_logs, handle_stop_monitoring
from utils.telegram import send_unauthorized_message


def register_commands(application: Application):
    """Регистрирует все команды бота."""
    auth = Auth()

    async def check_auth(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not auth.is_authorized_user(update.message.from_user.id):
            await update.message.reply_text("Вы не авторизованы. Обратитесь к администратору.")
            return False
        return True

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            'Отправьте SSH ссылку на GitHub репозиторий или используйте команды: /containers, /backup, /logs')

    async def whoami(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await auth.handle_whoami(update, context)

    async def init(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await auth.handle_init(update, context)

    async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await check_auth(update, context):
            return
        await auth.handle_add_user(update, context)

    async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await check_auth(update, context):
            return
        await auth.handle_remove_user(update, context)

    async def update_permissions(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await check_auth(update, context):
            return
        await auth.handle_update_permissions(update, context)

    async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await check_auth(update, context):
            return
        await auth.handle_list_users(update, context)

    async def deploy(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await check_auth(update, context):
            return
        if not auth.check_permission(update.message.from_user.id, "deploy"):
            await send_unauthorized_message(update)
            return
        await handle_deploy(update, context)

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('whoami', whoami))
    application.add_handler(CommandHandler('init', init))
    application.add_handler(CommandHandler('add_user', add_user))
    application.add_handler(CommandHandler('remove_user', remove_user))
    application.add_handler(CommandHandler('update_permissions', update_permissions))
    application.add_handler(CommandHandler('list_users', list_users))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, deploy))
    application.add_handler(CommandHandler('containers', handle_containers))
    application.add_handler(CommandHandler('start_container', handle_start))
    application.add_handler(CommandHandler('stop', handle_stop))
    application.add_handler(CommandHandler('remove', handle_remove))
    application.add_handler(CommandHandler('logs', handle_container_logs))
    application.add_handler(CommandHandler('stats', handle_stats))
    application.add_handler(CommandHandler('backup', handle_backup))
    application.add_handler(CommandHandler('restore', handle_restore))
    application.add_handler(CommandHandler('list_backups', handle_list_backups))
    application.add_handler(CommandHandler('download', handle_download))
    application.add_handler(CommandHandler("log_logs", handle_logs))
    application.add_handler(CommandHandler("tail", handle_tail))
    application.add_handler(CommandHandler("monitor_logs", handle_monitor_logs))
    application.add_handler(CommandHandler("stop_monitoring", handle_stop_monitoring))
    application.add_handler(MessageHandler(filters.Document.ALL & filters.CaptionRegex(r'^/upload\s+\S+$'), handle_upload))
    application.add_handler(CommandHandler("download_file", handle_download_file))
