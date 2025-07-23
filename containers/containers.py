import paramiko
from telegram import Update
from telegram.ext import ContextTypes
from auth.auth import Auth
from utils.ssh import connect_ssh, execute_ssh_command
from utils.telegram import send_unauthorized_message, send_paginated_message
from config import VPS_HOST, VPS_USERNAME, VPS_KEY_PATH, VPS_PASSWORD


async def list_containers(ssh: paramiko.SSHClient, update: Update):
    """Показывает список всех контейнеров."""
    command = 'docker ps -a --format "{{.ID}}\t{{.Names}}\t{{.Ports}}\t{{.Status}}"'
    stdout, stderr, exit_status = execute_ssh_command(ssh, command)

    if exit_status != 0:
        await update.message.reply_text(f"Ошибка при получении списка контейнеров: {stderr}")
        return

    containers = stdout.strip().split("\n")
    if not containers or containers == ['']:
        await update.message.reply_text("Контейнеры не найдены.")
        return

    response = "Контейнеры:\nID\tИмя\tПорты\tСтатус\n" + "\n".join(containers)
    await send_paginated_message(update, response)


async def start_container(ssh: paramiko.SSHClient, container_id: str, update: Update):
    """Запускает указанный контейнер."""
    command = f'docker start {container_id}'
    stdout, stderr, exit_status = execute_ssh_command(ssh, command)

    if exit_status != 0:
        await update.message.reply_text(f"Ошибка при запуске контейнера {container_id}: {stderr}")
        return

    await update.message.reply_text(f"Контейнер {container_id} успешно запущен.")


async def stop_container(ssh: paramiko.SSHClient, container_id: str, update: Update):
    """Останавливает указанный контейнер."""
    command = f'docker stop {container_id}'
    stdout, stderr, exit_status = execute_ssh_command(ssh, command)

    if exit_status != 0:
        await update.message.reply_text(f"Ошибка при остановке контейнера {container_id}: {stderr}")
        return

    await update.message.reply_text(f"Контейнер {container_id} успешно остановлен.")


async def remove_container(ssh: paramiko.SSHClient, container_id: str, update: Update):
    """Останавливает и удаляет указанный контейнер."""
    command = f'docker inspect --format="{{{{.State.Running}}}}" {container_id}'
    stdout, stderr, exit_status = execute_ssh_command(ssh, command)

    if exit_status != 0:
        await update.message.reply_text(f"Ошибка при проверке статуса контейнера {container_id}: {stderr}")
        return

    if stdout.strip() == "true":
        command = f'docker stop {container_id}'
        stdout, stderr, exit_status = execute_ssh_command(ssh, command)
        if exit_status != 0:
            await update.message.reply_text(f"Ошибка при остановке контейнера {container_id}: {stderr}")
            return

    command = f'docker rm {container_id}'
    stdout, stderr, exit_status = execute_ssh_command(ssh, command)

    if exit_status != 0:
        await update.message.reply_text(f"Ошибка при удалении контейнера {container_id}: {stderr}")
        return

    await update.message.reply_text(f"Контейнер {container_id} успешно удален.")


async def container_logs(ssh: paramiko.SSHClient, container_id: str, update: Update):
    """Показывает последние 50 строк логов указанного контейнера."""
    command = f'docker logs --tail 50 {container_id}'
    stdout, stderr, exit_status = execute_ssh_command(ssh, command)

    if exit_status != 0:
        await update.message.reply_text(f"Ошибка при получении логов контейнера {container_id}: {stderr}")
        return

    logs = stdout.strip()
    if not logs:
        await update.message.reply_text(f"Логи для контейнера {container_id} пусты.")
        return

    await send_paginated_message(update, f"Логи контейнера {container_id}:\n{logs}")


async def container_stats(ssh: paramiko.SSHClient, update: Update):
    """Показывает статистику использования ресурсов всеми контейнерами."""
    command = 'docker stats --no-stream --format "{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}"'
    stdout, stderr, exit_status = execute_ssh_command(ssh, command)

    if exit_status != 0:
        await update.message.reply_text(f"Ошибка при получении статистики: {stderr}")
        return

    stats = stdout.strip().split("\n")
    if not stats or stats == ['']:
        await update.message.reply_text("Контейнеры не найдены.")
        return

    response = "Статистика контейнеров:\nИмя\tCPU\tПамять\tСеть\n" + "\n".join(stats)
    await send_paginated_message(update, response)


async def handle_containers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /containers."""
    auth = Auth()
    if not auth.is_authorized_user(update.message.from_user.id):
        await update.message.reply_text("Вы не авторизованы. Обратитесь к администратору.")
        return
    if not auth.check_permission(update.message.from_user.id, "containers_list"):
        await send_unauthorized_message(update)
        return

    ssh = None
    try:
        ssh = connect_ssh(VPS_HOST, VPS_USERNAME, VPS_PASSWORD, VPS_KEY_PATH)
        await list_containers(ssh, update)
    except Exception as e:
        await update.message.reply_text(f"Произошла ошибка: {str(e)}")
    finally:
        if ssh:
            ssh.close()


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /start_container <container_id>."""
    auth = Auth()
    if not auth.is_authorized_user(update.message.from_user.id):
        await update.message.reply_text("Вы не авторизованы. Обратитесь к администратору.")
        return
    if not auth.check_permission(update.message.from_user.id, "containers_start"):
        await send_unauthorized_message(update)
        return

    if len(context.args) != 1:
        await update.message.reply_text("Использование: /start_container <container_id>")
        return

    container_id = context.args[0]
    ssh = None
    try:
        ssh = connect_ssh(VPS_HOST, VPS_USERNAME, VPS_PASSWORD, VPS_KEY_PATH)
        await start_container(ssh, container_id, update)
    except Exception as e:
        await update.message.reply_text(f"Произошла ошибка: {str(e)}")
    finally:
        if ssh:
            ssh.close()


async def handle_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /stop <container_id>."""
    auth = Auth()
    if not auth.is_authorized_user(update.message.from_user.id):
        await update.message.reply_text("Вы не авторизованы. Обратитесь к администратору.")
        return
    if not auth.check_permission(update.message.from_user.id, "containers_stop"):
        await send_unauthorized_message(update)
        return

    if len(context.args) != 1:
        await update.message.reply_text("Использование: /stop <container_id>")
        return

    container_id = context.args[0]
    ssh = None
    try:
        ssh = connect_ssh(VPS_HOST, VPS_USERNAME, VPS_PASSWORD, VPS_KEY_PATH)
        await stop_container(ssh, container_id, update)
    except Exception as e:
        await update.message.reply_text(f"Произошла ошибка: {str(e)}")
    finally:
        if ssh:
            ssh.close()


async def handle_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /remove <container_id>."""
    auth = Auth()
    if not auth.is_authorized_user(update.message.from_user.id):
        await update.message.reply_text("Вы не авторизованы. Обратитесь к администратору.")
        return
    if not auth.check_permission(update.message.from_user.id, "containers_remove"):
        await send_unauthorized_message(update)
        return

    if len(context.args) != 1:
        await update.message.reply_text("Использование: /remove <container_id>")
        return

    container_id = context.args[0]
    ssh = None
    try:
        ssh = connect_ssh(VPS_HOST, VPS_USERNAME, VPS_PASSWORD, VPS_KEY_PATH)
        await remove_container(ssh, container_id, update)
    except Exception as e:
        await update.message.reply_text(f"Произошла ошибка: {str(e)}")
    finally:
        if ssh:
            ssh.close()


async def handle_container_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /logs <container_id>."""
    auth = Auth()
    if not auth.is_authorized_user(update.message.from_user.id):
        await update.message.reply_text("Вы не авторизованы. Обратитесь к администратору.")
        return
    if not auth.check_permission(update.message.from_user.id, "containers_list"):
        await send_unauthorized_message(update)
        return

    if len(context.args) != 1:
        await update.message.reply_text("Использование: /logs <container_id>")
        return

    container_id = context.args[0]
    ssh = None
    try:
        ssh = connect_ssh(VPS_HOST, VPS_USERNAME, VPS_PASSWORD, VPS_KEY_PATH)
        await container_logs(ssh, container_id, update)
    except Exception as e:
        await update.message.reply_text(f"Произошла ошибка: {str(e)}")
    finally:
        if ssh:
            ssh.close()


async def handle_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /stats."""
    auth = Auth()
    if not auth.is_authorized_user(update.message.from_user.id):
        await update.message.reply_text("Вы не авторизованы. Обратитесь к администратору.")
        return
    if not auth.check_permission(update.message.from_user.id, "containers_list"):
        await send_unauthorized_message(update)
        return

    ssh = None
    try:
        ssh = connect_ssh(VPS_HOST, VPS_USERNAME, VPS_PASSWORD, VPS_KEY_PATH)
        await container_stats(ssh, update)
    except Exception as e:
        await update.message.reply_text(f"Произошла ошибка: {str(e)}")
    finally:
        if ssh:
            ssh.close()
