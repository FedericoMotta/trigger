import os
from dotenv import load_dotenv

load_dotenv()

APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI", "https://google.com/")

# runtime values (main will update these)
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
IG_ID = None
