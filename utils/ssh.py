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