import datetime
import uuid
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from typing import List, Optional, Dict
import os

class MongoDBService:
    def __init__(self):
        try:
            self.client = AsyncIOMotorClient(os.getenv("MONGODB_URI", "mongodb://localhost:27017"))
            self.db = self.client.prd_builder
            # Test connection
            self.client.admin.command('ping')
            print("MongoDB connected successfully")
        except Exception as e:
            print(f"MongoDB connection failed: {e}")
            self.client = None
            self.db = None
            
    async def save_prd(self, prd_data: Dict) -> str:
        """Save complete PRD to MongoDB"""
        collection = self.db.prds
        
        # Check if PRD already exists
        existing = await collection.find_one({"session_id": prd_data["session_id"]})
        
        if existing:
            # Update existing
            prd_data["updated_at"] = datetime.utcnow()
            prd_data["version"] = existing["version"] + 1
            await collection.update_one(
                {"session_id": prd_data["session_id"]}, 
                {"$set": prd_data}
            )
            return existing["prd_id"]
        else:
            # Insert new
            result = await collection.insert_one(prd_data)
            return str(result.inserted_id)
    
    async def save_chat_history(self, session_id: str, messages: List[Dict]) -> None:
        """Save chat history for a session"""
        collection = self.db.chat_history
        
        # Convert messages to proper format
        chat_messages = [
            {
                "message_id": msg.get("message_id", str(uuid.uuid4())),
                "session_id": session_id,
                "user_id": msg.get("user_id"),
                "content": msg.get("content", ""),
                "timestamp": msg.get("timestamp", datetime.utcnow()),
                "message_type": msg.get("type", "user"),
                "metadata": msg.get("metadata", {})
            }
            for msg in messages
        ]
        
        await collection.insert_many(chat_messages)
    
    async def get_user_prds(self, user_id: str) -> List[Dict]:
        """Get all PRDs for a user"""
        collection = self.db.prds
        cursor = collection.find({"user_id": user_id}).sort("updated_at", -1)
        return await cursor.to_list(length=100)
    
    async def get_prd_by_session(self, session_id: str) -> Optional[Dict]:
        """Get PRD by session ID"""
        collection = self.db.prds
        return await collection.find_one({"session_id": session_id})