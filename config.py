from dotenv import load_dotenv
import os
import json

load_dotenv()

config = {
    # Параметры Proxmox
    "PROXMOX_HOST": os.getenv("HOST"),
    "PROXMOX_PORT": os.getenv("PORT"),
    "PROXMOX_TOKEN_ID": os.getenv("TOKEN_ID"),
    "PROXMOX_TOKEN_SECRET": os.getenv("TOKEN_SECRET"),
    
    # Токен бота MAX
    "MAX_CHATS": json.loads(os.getenv("MAX_CHATS")),
    "MAX_BOT_TOKEN": os.getenv("MAX_BOT_TOKEN"),
    "MAX_BOT_BASE_URL": "https://platform-api.max.ru",
    
    # Список HTTP-сайтов (JSON)
    "HTTP_SITES": json.loads(os.getenv("HTTP_SITES")),
    
    # Список узлов Proxmox (JSON)
    "NODES": json.loads(os.getenv("NODES")),

    "TIMESLEEP": int(os.getenv("TIMESLEEP")),

    "POSTER_TYPE": os.getenv("POSTER_TYPE"),

    "IMAP_SERVER": os.getenv("IMAP_SERVER"),
    "IMAP_PORT": os.getenv("IMAP_PORT"),
    "SMTP_SERVER": os.getenv("SMTP_SERVER"),
    "SMTP_PORT": os.getenv("SMTP_PORT"),
    "LOGIN": os.getenv("LOGIN"),
    "PASSWORD": os.getenv("PASSWORD"),
    "TO_EMAILS": json.loads(os.getenv("TO_EMAILS")),
    "STATS_TIME": os.getenv("STATS_TIME"),
    "DB_PATH": os.getenv("DB_PATH"),
}

# Вычисляемые параметры на основе уже полученных значений
config["PROXMOX_API_TOKEN"] = f"PVEAPIToken={config['PROXMOX_TOKEN_ID']}={config['PROXMOX_TOKEN_SECRET']}"
config["PROXMOX_BASE_URL"] = f"https://{config['PROXMOX_HOST']}:{config['PROXMOX_PORT']}/api2/json/cluster/resources"


