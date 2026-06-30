import asyncio
import os
from dotenv import load_dotenv
load_dotenv()
import motor.motor_asyncio
import certifi
from bson.objectid import ObjectId

async def main():
    client = motor.motor_asyncio.AsyncIOMotorClient(os.getenv('MONGO_URI'), tlsCAFile=certifi.where())
    db = client.metatrader
    
    res = await db.orders.delete_one({'_id': ObjectId('6a43c6534e5cf9e3d878a87b')})
    print(f"Successfully deleted {res.deleted_count} order(s) from the database.")

if __name__ == "__main__":
    asyncio.run(main())
