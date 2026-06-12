import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_LINK = os.getenv("GROUP_LINK", "https://t.me/+KNqfa8J6F7syZGZi")
GROUP_ID = int(os.getenv("GROUP_ID", "-1003821180443"))
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "7545275828").split(",")]

MAP_POOL = ["Canals", "Raid", "Port", "Legacy", "Castello", "Soar", "Bureau", "Grounded", "Plaza", "Village"]