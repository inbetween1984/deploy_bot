import shlex
from telegram import Update
from telegram.ext import ContextTypes
from auth.auth import Auth
from utils.ssh import connect_ssh, execute_ssh_command
from utils.telegram import send_paginated_message
from config import VPS_HOST, VPS_USERNAME, VPS_KEY_PATH, VPS_PASSWORD


async def handle_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /logs <path> <pattern>."""
    auth = Auth()
    if not auth.is_authorized_user(update.message.from_user.id):
        await update.message.reply_text("Вы не авторизованы. Обратитесь к администратору.")
        return
    if not auth.check_permission(update.message.from_user.id, "logs_view"):
        await update.message.reply_text("У вас нет прав на просмотр логов.")
        return

    if len(context.args) != 2:
        await update.message.reply_text("Использование: /logs <path> <pattern>")
        return

    path, pattern = context.args
    if not path.startswith("/"):
        await update.message.reply_text("Пожалуйста, используйте абсолютный путь для файла логов (начинающийся с /).")
        return

    ssh = None
    try:
        ssh = connect_ssh(VPS_HOST, VPS_USERNAME, VPS_PASSWORD, VPS_KEY_PATH)

        command = f'test -f {shlex.quote(path)} && test -r {shlex.quote(path)} && echo "readable"'
        stdout, stderr, exit_status = execute_ssh_command(ssh, command)
        if exit_status != 0 or stdout.strip() != "readable":
            await update.message.reply_text(f"Ошибка: Файл {path} не существует или недоступен для чтения: {stderr}")
            return

        command = f'grep {shlex.quote(pattern)} {shlex.quote(path)}'
        await update.message.reply_text(f"Выполняю команду: {command}")
        stdout, stderr, exit_status = execute_ssh_command(ssh, command)
        await update.message.reply_text(f"Результат grep: exit_status={exit_status}, stderr={stderr.strip()}")

        if exit_status not in (0, 1):
            await update.message.reply_text(f"Ошибка при поиске в логе: {stderr}")
            return
        if not stdout.strip():
            await update.message.reply_text(f"В файле {path} не найдено строк, соответствующих шаблону '{pattern}'.")
            return

        response = f"Результат поиска в {path} (шаблон: {pattern}):\n{stdout}"
        await send_paginated_message(update, response)
    except Exception as e:
        await update.message.reply_text(f"Произошла ошибка: {str(e)}")
    finally:
        if ssh:
            ssh.close()


async def handle_tail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /tail <path> [n]."""
    auth = Auth()
    if not auth.is_authorized_user(update.message.from_user.id):
        await update.message.reply_text("Вы не авторизованы. Обратитесь к администратору.")
        return
    if not auth.check_permission(update.message.from_user.id, "logs_view"):
        await update.message.reply_text("У вас нет прав на просмотр логов.")
        return

    if len(context.args) not in (1, 2):
        await update.message.reply_text("Использование: /tail <path> [n]")
        return

    path = context.args[0]
    n_lines = context.args[1] if len(context.args) == 2 else "10"

    if not path.startswith("/"):
        await update.message.reply_text("Пожалуйста, используйте абсолютный путь для файла логов (начинающийся с /).")
        return

    try:
        n_lines = int(n_lines)
        if n_lines <= 0:
            await update.message.reply_text("Количество строк должно быть положительным числом.")
            return
    except ValueError:
        await update.message.reply_text("Количество строк должно быть числом.")
        return

    ssh = None
    try:
        ssh = connect_ssh(VPS_HOST, VPS_USERNAME, VPS_PASSWORD, VPS_KEY_PATH)

        command = f'test -f {shlex.quote(path)} && test -r {shlex.quote(path)} && echo "readable"'
        stdout, stderr, exit_status = execute_ssh_command(ssh, command)
        if exit_status != 0 or stdout.strip() != "readable":
            await update.message.reply_text(f"Ошибка: Файл {path} не существует или недоступен для чтения: {stderr}")
            return

        command = f'tail -n {n_lines} {shlex.quote(path)}'
        await update.message.reply_text(f"Выполняю команду: {command}")
        stdout, stderr, exit_status = execute_ssh_command(ssh, command)
        await update.message.reply_text(f"Результат tail: exit_status={exit_status}, stderr={stderr.strip()}")

        if exit_status != 0:
            await update.message.reply_text(f"Ошибка при получении строк лога: {stderr}")
            return
        if not stdout.strip():
            await update.message.reply_text(f"Файл {path} пуст.")
            return

        response = f"Последние {n_lines} строк из {path}:\n{stdout}"
        await send_paginated_message(update, response)
    except Exception as e:
        await update.message.reply_text(f"Произошла ошибка: {str(e)}")
    finally:
        if ssh:
            ssh.close()


async def monitor_logs_job(context: ContextTypes.DEFAULT_TYPE):
    """Фоновая задача для мониторинга логов."""
    user_id = context.job.data["user_id"]
    path = context.job.data["path"]
    chat_id = context.job.data["chat_id"]

    ssh = None
    try:
        ssh = connect_ssh(VPS_HOST, VPS_USERNAME, VPS_PASSWORD, VPS_KEY_PATH)

        command = f'test -f {shlex.quote(path)} && test -r {shlex.quote(path)} && echo "readable"'
        stdout, stderr, exit_status = execute_ssh_command(ssh, command)
        if exit_status != 0 or stdout.strip() != "readable":
            await context.bot.send_message(chat_id=chat_id,
                                           text=f"Ошибка: Файл {path} не существует или недоступен для чтения: {stderr}")
            context.job.schedule_removal()
            context.user_data.pop(f"monitor_job_{user_id}", None)
            return

        command = f'tail -n 10 {shlex.quote(path)}'
        stdout, stderr, exit_status = execute_ssh_command(ssh, command)
        if exit_status != 0:
            await context.bot.send_message(chat_id=chat_id, text=f"Ошибка при мониторинге лога: {stderr}")
            context.job.schedule_removal()
            context.user_data.pop(f"monitor_job_{user_id}", None)
            return

        last_output = context.job.data.get("last_output", "")
        if stdout.strip() and stdout != last_output:
            new_lines = stdout.strip().split("\n")[-10:]
            response = f"Новые строки в {path}:\n" + "\n".join(new_lines)
            await send_paginated_message(context.bot, chat_id, response)
            context.job.data["last_output"] = stdout
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"Ошибка при мониторинге: {str(e)}")
        context.job.schedule_removal()
        context.user_data.pop(f"monitor_job_{user_id}", None)
    finally:
        if ssh:
            ssh.close()


async def handle_monitor_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /monitor_logs <path> [interval]."""
    auth = Auth()
    if not auth.is_authorized_user(update.message.from_user.id):
        await update.message.reply_text("Вы не авторизованы. Обратитесь к администратору.")
        return
    if not auth.check_permission(update.message.from_user.id, "logs_monitor"):
        await update.message.reply_text("У вас нет прав на мониторинг логов.")
        return

    if len(context.args) not in (1, 2):
        await update.message.reply_text("Использование: /monitor_logs <path> [interval]")
        return

    path = context.args[0]
    interval = float(context.args[1]) if len(context.args) == 2 else 5.0

    if not path.startswith("/"):
        await update.message.reply_text("Пожалуйста, используйте абсолютный путь для файла логов (начинающийся с /).")
        return

    try:
        interval = float(interval)
        if interval < 1.0:
            await update.message.reply_text("Интервал должен быть не менее 1 секунды.")
            return
    except ValueError:
        await update.message.reply_text("Интервал должен быть числом.")
        return

    user_id = update.message.from_user.id
    if f"monitor_job_{user_id}" in context.user_data:
        await update.message.reply_text(
            "У вас уже запущен мониторинг логов. Остановите его с помощью /stop_monitoring.")
        return

    ssh = None
    try:
        ssh = connect_ssh(VPS_HOST, VPS_USERNAME, VPS_PASSWORD, VPS_KEY_PATH)

        command = f'test -f {shlex.quote(path)} && test -r {shlex.quote(path)} && echo "readable"'
        stdout, stderr, exit_status = execute_ssh_command(ssh, command)
        if exit_status != 0 or stdout.strip() != "readable":
            await update.message.reply_text(f"Ошибка: Файл {path} не существует или недоступен для чтения: {stderr}")
            return

        job = context.job_queue.run_repeating(
            monitor_logs_job,
            interval=interval,
            data={"user_id": user_id, "path": path, "chat_id": update.message.chat_id, "last_output": ""},
            name=f"monitor_logs_{user_id}"
        )
        context.user_data[f"monitor_job_{user_id}"] = job
        await update.message.reply_text(
            f"Начался мониторинг {path} (интервал {interval} сек). Для остановки используйте /stop_monitoring.")
    except Exception as e:
        await update.message.reply_text(f"Произошла ошибка: {str(e)}")
    finally:
        if ssh:
            ssh.close()


async def handle_stop_monitoring(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /stop_monitoring."""
    auth = Auth()
    if not auth.is_authorized_user(update.message.from_user.id):
        await update.message.reply_text("Вы не авторизованы. Обратитесь к администратору.")
        return
    if not auth.check_permission(update.message.from_user.id, "logs_monitor"):
        await update.message.reply_text("У вас нет прав на мониторинг логов.")
        return

    user_id = update.message.from_user.id
    job_key = f"monitor_job_{user_id}"
    if job_key not in context.user_data:
        await update.message.reply_text("Нет активного мониторинга логов.")
        return

    job = context.user_data[job_key]
    job.schedule_removal()
    context.user_data.pop(job_key)
    await update.message.reply_text("Мониторинг логов остановлен.")
