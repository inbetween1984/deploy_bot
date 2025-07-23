from dotenv import load_dotenv
import os

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
VPS_HOST = os.getenv('VPS_HOST')
VPS_USERNAME = os.getenv('VPS_USERNAME')
VPS_PASSWORD = os.getenv('VPS_PASSWORD')
VPS_KEY_PATH = os.getenv('VPS_KEY_PATH')
TARGET_DIR = os.getenv('TARGET_DIR', '/home/users/repos')
BACKUP_DIR = os.getenv('BACKUP_DIR', '/backups')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'default_password')
DEFAULT_PORT = 1234