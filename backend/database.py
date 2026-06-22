import motor.motor_asyncio
import os
from dotenv import load_dotenv

load_dotenv()

import certifi

MONGO_URI = os.getenv("MONGO_URI")
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000, tlsCAFile=certifi.where())
db = client.metatrader

users_collection = db.get_collection("users")
credentials_collection = db.get_collection("credentials")
watchlists_collection = db.get_collection("watchlists")
orders_collection = db.get_collection("orders")
