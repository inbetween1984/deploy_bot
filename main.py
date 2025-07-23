from telegram import Update
from telegram.ext import Application
from config import TELEGRAM_TOKEN
from commands import register_commands

def main():
    """Запускает бота."""
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    register_commands(application)
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()