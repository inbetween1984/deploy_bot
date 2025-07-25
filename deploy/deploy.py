import re
import paramiko
from telegram import Update
from telegram.ext import ContextTypes
from config import VPS_HOST, VPS_USERNAME, VPS_KEY_PATH, TARGET_DIR, DEFAULT_PORT, VPS_PASSWORD
from utils.ssh import connect_ssh

async def check_docker_file(ssh: paramiko.SSHClient, repo_path: str, update: Update) -> tuple[bool, bool, int]:
    """Проверяет наличие docker-compose.yml и Dockerfile, извлекает порт из Dockerfile."""
    stdin, stdout, stderr = ssh.exec_command(f'test -f {repo_path}/docker-compose.yml && echo "exists"')
    has_docker_compose = stdout.read().decode().strip() == 'exists'
    await update.message.reply_text(f'Отладка: docker-compose.yml существует: {has_docker_compose}')

    stdin, stdout, stderr = ssh.exec_command(f'test -f {repo_path}/Dockerfile && echo "exists"')
    has_dockerfile = stdout.read().decode().strip() == 'exists'
    await update.message.reply_text(f'Отладка: Dockerfile существует: {has_dockerfile}')

    port = DEFAULT_PORT
    if has_dockerfile:
        stdin, stdout, stderr = ssh.exec_command(f'cat {repo_path}/Dockerfile')
        dockerfile_content = stdout.read().decode()
        expose_match = re.search(r'EXPOSE\s+(\d+)', dockerfile_content)
        if expose_match:
            port = int(expose_match.group(1))
            await update.message.reply_text(f'Отладка: Порт из Dockerfile: {port}')
        else:
            await update.message.reply_text(f'Отладка: Порт EXPOSE не найден, используется порт по умолчанию: {port}')

    return has_docker_compose, has_dockerfile, port

async def update_repository(ssh: paramiko.SSHClient, repo_path: str, repo_url: str, update: Update) -> bool:
    """Обновляет репозиторий: выполняет git pull, если он существует, или git clone, если нет."""
    stdin, stdout, stderr = ssh.exec_command(f'test -d {repo_path} && echo "exists"')
    repo_exists = stdout.read().decode().strip() == 'exists'

    if repo_exists:
        await update.message.reply_text('Репозиторий уже существует, выполняю git pull...')
        command = f'cd {repo_path} && git pull'
    else:
        await update.message.reply_text('Клонирую репозиторий...')
        command = f'ssh-agent bash -c "ssh-add ~/.ssh/id_rsa; cd {TARGET_DIR} && git clone {repo_url}"'

    stdin, stdout, stderr = ssh.exec_command(command)
    exit_status = stdout.channel.recv_exit_status()
    error = stderr.read().decode()

    if exit_status != 0:
        action = 'git pull' if repo_exists else 'клонировании репозитория'
        await update.message.reply_text(f'Ошибка при {action}: {error}')
        return False
    return True

async def deploy_container(ssh: paramiko.SSHClient, repo_path: str, repo_name: str, has_docker_compose: bool,
                           port: int, update: Update) -> bool:
    """Собирает и запускает Docker контейнер."""
    await update.message.reply_text('Выполняю сборку и запуск контейнера...')

    if has_docker_compose:
        command = f'cd {repo_path} && docker-compose up --build -d'
    else:
        command = f'cd {repo_path} && docker build -t {repo_name.lower()} . && docker run -d -p {port}:{port} {repo_name.lower()}'

    stdin, stdout, stderr = ssh.exec_command(command)
    stdout.channel.settimeout(300)
    error = stderr.read().decode()

    if error and "DEPRECATED" not in error:
        await update.message.reply_text(f'Ошибка при развертывании: {error}')
        return False
    await update.message.reply_text(f'Репозиторий успешно развернут на порту {port}!')
    return True

async def handle_deploy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду деплоя или текстовое сообщение с SSH-ссылкой."""
    message_text = update.message.text
    github_ssh_pattern = r'git@github\.com:[\w-]+/[\w-]+\.git'
    if not re.match(github_ssh_pattern, message_text):
        await update.message.reply_text(
            'Пожалуйста, отправьте действительную SSH ссылку на GitHub репозиторий (например: git@github.com:username/repository.git).')
        return

    await update.message.reply_text('Начинаю развертывание репозитория...')

    ssh = None
    try:
        ssh = connect_ssh(VPS_HOST, VPS_USERNAME, VPS_PASSWORD, VPS_KEY_PATH)
        ssh.exec_command(f'mkdir -p {TARGET_DIR}')

        repo_name = message_text.split('/')[-1].replace('.git', '')
        repo_path = f'{TARGET_DIR}/{repo_name}'
        await update.message.reply_text(f'Отладка: Путь к репозиторию: {repo_path}')

        if not await update_repository(ssh, repo_path, message_text, update):
            ssh.close()
            return

        has_docker_compose, has_dockerfile, port = await check_docker_file(ssh, repo_path, update)
        if not has_docker_compose and not has_dockerfile:
            await update.message.reply_text('В репозитории отсутствует Dockerfile или docker-compose.yml')
            ssh.close()
            return

        await deploy_container(ssh, repo_path, repo_name, has_docker_compose, port, update)

        ssh.close()

    except Exception as e:
        await update.message.reply_text(f'Произошла ошибка: {str(e)}')
        if ssh:
            ssh.close()
