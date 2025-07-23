import os

import paramiko

def connect_ssh(host: str, username: str, password: str, key_path: str) -> paramiko.SSHClient:
    """Устанавливает SSH-соединение."""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, username=username, password=password, key_filename=key_path)
    return ssh

def execute_ssh_command(ssh: paramiko.SSHClient, command: str) -> tuple[str, str, int]:
    """Выполняет SSH-команду и возвращает stdout, stderr и exit_status."""
    stdin, stdout, stderr = ssh.exec_command(command)
    exit_status = stdout.channel.recv_exit_status()
    return stdout.read().decode(), stderr.read().decode(), exit_status


def download_file(ssh: paramiko.SSHClient, remote_path: str, local_path: str):
    """Скачивает файл через SFTP."""
    sftp = ssh.open_sftp()
    try:
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        sftp.get(remote_path, local_path)
    finally:
        sftp.close()


def upload_file(ssh: paramiko.SSHClient, local_path: str, remote_path: str):
    """Загружает файл на VPS через SFTP."""
    sftp = ssh.open_sftp()
    try:
        sftp.put(local_path, remote_path)
    finally:
        sftp.close()