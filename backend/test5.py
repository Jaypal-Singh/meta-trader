import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import json

async def main():
    db = AsyncIOMotorClient('mongodb://localhost:27017/').metatrader
    users = await db.users.find().to_list(100)
    for u in users:
        print(f"User: {u['username']}")
        config = u.get('watchlist_config', {})
        print(json.dumps(config, indent=2))

if __name__ == '__main__':
    asyncio.run(main())
