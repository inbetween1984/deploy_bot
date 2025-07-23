import paramiko
import os
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from auth.auth import Auth
from utils.ssh import connect_ssh, execute_ssh_command, download_file
from utils.telegram import send_unauthorized_message, send_paginated_message
from config import VPS_HOST, VPS_USERNAME, VPS_KEY_PATH, VPS_PASSWORD, BACKUP_DIR


async def create_backup(ssh: paramiko.SSHClient, path: str, update: Update):
    """Создает архив указанной директории и сохраняет в BACKUP_DIR."""
    command = f'test -d {path} && echo "exists"'
    stdout, stderr, exit_status = execute_ssh_command(ssh, command)
    if exit_status != 0 or stdout.strip() != "exists":
        await update.message.reply_text(f"Директория {path} не существует на сервере.")
        return

    command = f'mkdir -p {BACKUP_DIR}'
    execute_ssh_command(ssh, command)

    dir_name = os.path.basename(path.rstrip("/"))
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_name = f"{dir_name}_{timestamp}.tar.gz"
    backup_path = f"{BACKUP_DIR}/{backup_name}"

    await update.message.reply_text(f"Создаю резервную копию {path}...")
    command = f'tar -czf {backup_path} -C {os.path.dirname(path)} {os.path.basename(path)}'
    stdout, stderr, exit_status = execute_ssh_command(ssh, command)

    if exit_status != 0:
        await update.message.reply_text(f"Ошибка при создании резервной копии: {stderr}")
        return

    await update.message.reply_text(f"Резервная копия создана: {backup_name}")


async def restore_backup(ssh: paramiko.SSHClient, backup_name: str, target_dir: str, update: Update):
    """Восстанавливает архив из BACKUP_DIR в указанную директорию."""
    backup_path = f"{BACKUP_DIR}/{backup_name}"
    command = f'test -f {backup_path} && echo "exists"'
    stdout, stderr, exit_status = execute_ssh_command(ssh, command)
    await update.message.reply_text(
        f"Проверка архива {backup_path}: stdout={stdout.strip()}, stderr={stderr.strip()}, exit_status={exit_status}")
    if exit_status != 0 or stdout.strip() != "exists":
        await update.message.reply_text(f"Архив {backup_name} не найден в {BACKUP_DIR}.")
        return

    if not target_dir.startswith("/"):
        await update.message.reply_text("Пожалуйста, используйте абсолютный путь для target_dir (начинающийся с /).")
        return

    command = f'mkdir -p {target_dir}'
    stdout, stderr, exit_status = execute_ssh_command(ssh, command)
    await update.message.reply_text(
        f"Создание {target_dir}: stdout={stdout.strip()}, stderr={stderr.strip()}, exit_status={exit_status}")
    if exit_status != 0:
        await update.message.reply_text(f"Ошибка при создании директории {target_dir}: {stderr}")
        return

    await update.message.reply_text(f"Восстанавливаю {backup_name} в {target_dir}...")
    command = f'tar -xzf {backup_path} -C {target_dir}'
    await update.message.reply_text(f"Выполняю команду: {command}")
    stdout, stderr, exit_status = execute_ssh_command(ssh, command)
    await update.message.reply_text(
        f"Результат tar: stdout={stdout.strip()}, stderr={stderr.strip()}, exit_status={exit_status}")

    if exit_status != 0:
        await update.message.reply_text(f"Ошибка при восстановлении: {stderr}")
        return

    await update.message.reply_text(f"Архив {backup_name} успешно восстановлен в {target_dir}.")


async def list_backups(ssh: paramiko.SSHClient, update: Update):
    """Показывает список файлов в BACKUP_DIR."""
    command = f'ls -lh {BACKUP_DIR}'
    stdout, stderr, exit_status = execute_ssh_command(ssh, command)

    if exit_status != 0:
        await update.message.reply_text(f"Ошибка при получении списка резервных копий: {stderr}")
        return

    backups = stdout.strip().split("\n")
    if not backups or backups == ['']:
        await update.message.reply_text(f"Резервные копии в {BACKUP_DIR} не найдены.")
        return

    response = f"Резервные копии в {BACKUP_DIR}:\n" + "\n".join(backups)
    await send_paginated_message(update, response)


async def download_backup(ssh: paramiko.SSHClient, backup_name: str, update: Update):
    """Скачивает архив через SFTP и отправляет в Telegram."""
    backup_path = f"{BACKUP_DIR}/{backup_name}"
    command = f'test -f {backup_path} && echo "exists"'
    stdout, stderr, exit_status = execute_ssh_command(ssh, command)
    if exit_status != 0 or stdout.strip() != "exists":
        await update.message.reply_text(f"Архив {backup_name} не найден в {BACKUP_DIR}.")
        return

    command = f'stat -c %s {backup_path}'
    stdout, stderr, exit_status = execute_ssh_command(ssh, command)
    if exit_status != 0:
        await update.message.reply_text(f"Ошибка при проверке размера файла: {stderr}")
        return

    file_size = int(stdout.strip()) / (1024 * 1024)  # Размер в МБ
    if file_size > 50:
        await update.message.reply_text("Файл слишком большой (>50 МБ). Telegram ограничивает размер файлов.")
        return

    local_path = f"/tmp/{backup_name}"
    try:
        await update.message.reply_text(f"Скачиваю {backup_name}...")
        download_file(ssh, backup_path, local_path)
        with open(local_path, "rb") as f:
            await update.message.reply_document(document=f, filename=backup_name)
        os.remove(local_path)
        await update.message.reply_text(f"Архив {backup_name} успешно отправлен.")
    except Exception as e:
        await update.message.reply_text(f"Ошибка при скачивании: {str(e)}")
        if os.path.exists(local_path):
            os.remove(local_path)


async def handle_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /backup <path>."""
    auth = Auth()
    if not auth.is_authorized_user(update.message.from_user.id):
        await update.message.reply_text("Вы не авторизованы. Обратитесь к администратору.")
        return
    if not auth.check_permission(update.message.from_user.id, "backups_create"):
        await send_unauthorized_message(update)
        return

    if len(context.args) != 1:
        await update.message.reply_text("Использование: /backup <path>")
        return

    path = context.args[0]
    await update.message.reply_text(f"{path}")
    ssh = None
    try:
        ssh = connect_ssh(VPS_HOST, VPS_USERNAME, VPS_PASSWORD, VPS_KEY_PATH)
        await create_backup(ssh, path, update)
    except Exception as e:
        await update.message.reply_text(f"Произошла ошибка: {str(e)}")
    finally:
        if ssh:
            ssh.close()


async def handle_restore(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /restore <backup_name> [<target_dir>]."""
    auth = Auth()
    if not auth.is_authorized_user(update.message.from_user.id):
        await update.message.reply_text("Вы не авторизованы. Обратитесь к администратору.")
        return
    if not auth.check_permission(update.message.from_user.id, "backups_restore"):
        await send_unauthorized_message(update)
        return

    if len(context.args) != 2:
        await update.message.reply_text("Использование: /restore <backup_name> [<target_dir>]")
        return

    backup_name = context.args[0]
    target_dir = context.args[1]

    ssh = None
    try:
        ssh = connect_ssh(VPS_HOST, VPS_USERNAME, VPS_PASSWORD, VPS_KEY_PATH)
        await restore_backup(ssh, backup_name, target_dir, update)
    except Exception as e:
        await update.message.reply_text(f"Произошла ошибка: {str(e)}")
    finally:
        if ssh:
            ssh.close()


async def handle_list_backups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /list_backups."""
    auth = Auth()
    if not auth.is_authorized_user(update.message.from_user.id):
        await update.message.reply_text("Вы не авторизованы. Обратитесь к администратору.")
        return
    if not auth.check_permission(update.message.from_user.id, "backups_download"):
        await send_unauthorized_message(update)
        return

    ssh = None
    try:
        ssh = connect_ssh(VPS_HOST, VPS_USERNAME, VPS_PASSWORD, VPS_KEY_PATH)
        await list_backups(ssh, update)
    except Exception as e:
        await update.message.reply_text(f"Произошла ошибка: {str(e)}")
    finally:
        if ssh:
            ssh.close()


async def handle_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /download <backup_name>."""
    auth = Auth()
    if not auth.is_authorized_user(update.message.from_user.id):
        await update.message.reply_text("Вы не авторизованы. Обратитесь к администратору.")
        return
    if not auth.check_permission(update.message.from_user.id, "backups_download"):
        await send_unauthorized_message(update)
        return

    if len(context.args) != 1:
        await update.message.reply_text("Использование: /download <backup_name>")
        return

    backup_name = context.args[0]
    ssh = None
    try:
        ssh = connect_ssh(VPS_HOST, VPS_USERNAME, VPS_PASSWORD, VPS_KEY_PATH)
        await download_backup(ssh, backup_name, update)
    except Exception as e:
        await update.message.reply_text(f"Произошла ошибка: {str(e)}")
    finally:
        if ssh:
            ssh.close()
