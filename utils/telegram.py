from telegram import Update

async def send_unauthorized_message(update: Update):
    """Отправляет сообщение об отсутствии прав."""
    await update.message.reply_text("У вас нет прав для выполнения этой команды.")


async def send_paginated_message(update: Update, text: str, max_length: int = 4000):
    """Отправляет длинное сообщение, разбивая его на части, если превышает max_length."""
    if len(text) <= max_length:
        await update.message.reply_text(text)
        return

    lines = text.split("\n")
    current_message = ""
    for line in lines:
        if len(current_message) + len(line) + 1 > max_length:
            await update.message.reply_text(current_message.strip())
            current_message = line + "\n"
        else:
            current_message += line + "\n"

    if current_message:
        await update.message.reply_text(current_message.strip())