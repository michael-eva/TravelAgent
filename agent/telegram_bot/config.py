import os
from dotenv import load_dotenv
load_dotenv()
API_KEY = os.getenv('TELEGRAM_BOT_API')

TOKEN = API_KEY
TIMEZONE = "Australia/Perth"
TIMEZONE_COMMON_NAME = 'Perth'