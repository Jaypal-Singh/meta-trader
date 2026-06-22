import asyncio
import certifi
import motor.motor_asyncio
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI, tlsCAFile=certifi.where())
db = client.metatrader

async def clear_data():
    await db.orders.delete_many({})
    await db.funds.update_many({}, {"$set": {"balance": 100000.0, "used_margin": 0.0}})
    print("Dummy orders cleared and funds reset.")

if __name__ == "__main__":
    asyncio.run(clear_data())
