import os
import shlex
import logging
import re
from telegram import Update
from telegram.ext import ContextTypes
from auth.auth import Auth
from utils.ssh import connect_ssh, execute_ssh_command, upload_file, download_file
from config import VPS_HOST, VPS_USERNAME, VPS_KEY_PATH, VPS_PASSWORD

async def handle_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /upload <path_to_dir> с прикрепленным файлом в caption."""

    await update.message.reply_text(
        f"Получена команда: text={update.message.text}, caption={update.message.caption}, document={update.message.document}")

    auth = Auth()
    if not auth.is_authorized_user(update.message.from_user.id):
        await update.message.reply_text("Вы не авторизованы. Обратитесь к администратору.")
        return

    if not auth.check_permission(update.message.from_user.id, "files_upload"):
        await update.message.reply_text("У вас нет прав на загрузку файлов.")
        return

    if not update.message.caption:
        await update.message.reply_text("Пожалуйста, укажите команду /upload <path_to_dir> в подписи к файлу.")
        return

    match = re.match(r'^/upload\s+(\S+)$', update.message.caption)
    if not match:
        await update.message.reply_text("Использование: /upload <path_to_dir> в подписи к файлу")
        return
    path_to_dir = match.group(1)

    if not path_to_dir.startswith("/"):
        await update.message.reply_text("Пожалуйста, используйте абсолютный путь для директории (начинающийся с /).")
        return

    if not update.message.document:
        await update.message.reply_text("Пожалуйста, прикрепите файл к сообщению.")
        return

    document = update.message.document
    if document.file_size > 50 * 1024 * 1024:
        await update.message.reply_text("Файл слишком большой (>50 МБ). Telegram ограничивает размер файлов.")
        return

    ssh = None
    local_path = None
    try:
        ssh = connect_ssh(VPS_HOST, VPS_USERNAME, VPS_PASSWORD, VPS_KEY_PATH)

        command = f'test -d {shlex.quote(path_to_dir)} && test -w {shlex.quote(path_to_dir)} && echo "writable"'
        stdout, stderr, exit_status = execute_ssh_command(ssh, command)
        if exit_status != 0 or stdout.strip() != "writable":
            await update.message.reply_text(
                f"Ошибка: Директория {path_to_dir} не существует или недоступна для записи: {stderr}")
            return

        file = await document.get_file()
        file_name = document.file_name or "uploaded_file"
        local_path = f"/tmp/{file_name}"
        await file.download_to_drive(local_path)

        remote_path = f"{path_to_dir}/{file_name}"
        await update.message.reply_text(f"Загружаю файл {file_name} в {remote_path}...")
        upload_file(ssh, local_path, remote_path)

        os.remove(local_path)
        await update.message.reply_text(f"Файл {file_name} успешно загружен в {remote_path}.")
    except Exception as e:
        await update.message.reply_text(f"Ошибка при загрузке файла: {str(e)}")
        if local_path and os.path.exists(local_path):
            os.remove(local_path)
    finally:
        if ssh:
            ssh.close()


async def handle_download_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /download-file <path_to_file>."""
    auth = Auth()
    if not auth.is_authorized_user(update.message.from_user.id):
        await update.message.reply_text("Вы не авторизованы. Обратитесь к администратору.")
        return
    if not auth.check_permission(update.message.from_user.id, "files_download"):
        await update.message.reply_text("У вас нет прав на скачивание файлов.")
        return

    if len(context.args) != 1:
        await update.message.reply_text("Использование: /download-file <path_to_file>")
        return

    path_to_file = context.args[0]
    if not path_to_file.startswith("/"):
        await update.message.reply_text("Пожалуйста, используйте абсолютный путь для файла (начинающийся с /).")
        return

    ssh = None
    local_path = None
    try:
        ssh = connect_ssh(VPS_HOST, VPS_USERNAME, VPS_PASSWORD, VPS_KEY_PATH)

        command = f'test -f {shlex.quote(path_to_file)} && test -r {shlex.quote(path_to_file)} && echo "readable"'
        stdout, stderr, exit_status = execute_ssh_command(ssh, command)
        if exit_status != 0 or stdout.strip() != "readable":
            await update.message.reply_text(
                f"Ошибка: Файл {path_to_file} не существует или недоступен для чтения: {stderr}")
            return

        command = f'stat -c %s {shlex.quote(path_to_file)}'
        stdout, stderr, exit_status = execute_ssh_command(ssh, command)
        if exit_status != 0:
            await update.message.reply_text(f"Ошибка при проверке размера файла: {stderr}")
            return
        file_size = int(stdout.strip()) / (1024 * 1024)
        if file_size > 50:
            await update.message.reply_text("Файл слишком большой (>50 МБ). Telegram ограничивает размер файлов.")
            return

        file_name = path_to_file.split("/")[-1]
        local_path = f"/tmp/{file_name}"
        await update.message.reply_text(f"Скачиваю файл {path_to_file}...")
        download_file(ssh, local_path)

        with open(local_path, "rb") as f:
            await update.message.reply_document(document=f, filename=file_name)
        os.remove(local_path)
        await update.message.reply_text(f"Файл {file_name} успешно отправлен.")
    except Exception as e:
        await update.message.reply_text(f"Ошибка при скачивании файла: {str(e)}")
        if local_path and os.path.exists(local_path):
            os.remove(local_path)
    finally:
        if ssh:
            ssh.close()
