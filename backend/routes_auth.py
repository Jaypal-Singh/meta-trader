from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import db
from auth import verify_password, create_access_token, hash_password

router = APIRouter()

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
async def login(req: LoginRequest):
    user = await db.users.find_one({"username": req.username})
    
    # Auto-create first user if DB is empty (Setup Mode)
    if not user:
        count = await db.users.count_documents({})
        if count == 0:
            hashed_pw = hash_password(req.password)
            await db.users.insert_one({"username": req.username, "password": hashed_pw})
            user = {"username": req.username, "password": hashed_pw}
        else:
            raise HTTPException(status_code=400, detail="Invalid username or password")
            
    if not verify_password(req.password, user["password"]):
        raise HTTPException(status_code=400, detail="Invalid username or password")
        
    token = create_access_token({"sub": user["username"]})
    return {"access_token": token, "token_type": "bearer"}
