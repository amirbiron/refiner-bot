"""
MongoDB Helper (Optional)
עוזר לעבודה עם MongoDB Atlas
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
import config

logger = logging.getLogger(__name__)


class MongoDBHelper:
    """
    מנהל חיבור ל-MongoDB Atlas
    """
    
    def __init__(self):
        self.client: Optional[MongoClient] = None
        self.db = None
        self.connected = False
        
        if config.MONGODB_URI:
            self.connect()
    
    def connect(self):
        """יצירת חיבור ל-MongoDB"""
        try:
            self.client = MongoClient(
                config.MONGODB_URI,
                serverSelectionTimeoutMS=5000
            )
            
            # בדיקת חיבור
            self.client.admin.command('ping')
            
            self.db = self.client[config.MONGODB_DB_NAME]
            self.connected = True
            
            logger.info(f"✅ Connected to MongoDB: {config.MONGODB_DB_NAME}")
            
        except ConnectionFailure as e:
            logger.error(f"❌ MongoDB connection failed: {e}")
            self.connected = False
        except Exception as e:
            logger.error(f"❌ MongoDB error: {e}")
            self.connected = False
    
    def close(self):
        """סגירת החיבור"""
        if self.client:
            self.client.close()
            self.connected = False
            logger.info("MongoDB connection closed")
    
    # =====================
    # Refinement History
    # =====================
    
    def save_refinement(
        self,
        user_id: int,
        username: str,
        original_text: str,
        refined_text: str,
        published: bool = False
    ) -> Optional[str]:
        """
        שמירת שכתוב בהיסטוריה
        
        Returns:
            document_id if successful, None otherwise
        """
        if not self.connected:
            logger.warning("MongoDB not connected, skipping save")
            return None
        
        try:
            document = {
                "user_id": user_id,
                "username": username,
                "original_text": original_text,
                "refined_text": refined_text,
                "original_length": len(original_text),
                "refined_length": len(refined_text),
                "published": published,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            result = self.db.refinements.insert_one(document)
            
            logger.info(f"✅ Saved refinement: {result.inserted_id}")
            return str(result.inserted_id)
            
        except OperationFailure as e:
            logger.error(f"❌ Failed to save refinement: {e}")
            return None
    
    def update_published_status(self, document_id: str, published: bool = True):
        """
        עדכון סטטוס פרסום
        """
        if not self.connected:
            return False
        
        try:
            from bson import ObjectId
            
            result = self.db.refinements.update_one(
                {"_id": ObjectId(document_id)},
                {
                    "$set": {
                        "published": published,
                        "published_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"❌ Failed to update published status: {e}")
            return False
    
    def get_user_refinements(
        self,
        user_id: int,
        limit: int = 10,
        published_only: bool = False
    ) -> List[Dict]:
        """
        קבלת היסטוריית שכתובים של משתמש
        """
        if not self.connected:
            return []
        
        try:
            query = {"user_id": user_id}
            if published_only:
                query["published"] = True
            
            cursor = self.db.refinements.find(query).sort(
                "created_at", -1
            ).limit(limit)
            
            return list(cursor)
            
        except Exception as e:
            logger.error(f"❌ Failed to get refinements: {e}")
            return []
    
    # =====================
    # Statistics
    # =====================
    
    def get_user_stats(self, user_id: int) -> Dict:
        """
        סטטיסטיקות של משתמש
        """
        if not self.connected:
            return {}
        
        try:
            total = self.db.refinements.count_documents({"user_id": user_id})
            published = self.db.refinements.count_documents({
                "user_id": user_id,
                "published": True
            })
            
            # ממוצע אורך טקסט
            pipeline = [
                {"$match": {"user_id": user_id}},
                {"$group": {
                    "_id": None,
                    "avg_original": {"$avg": "$original_length"},
                    "avg_refined": {"$avg": "$refined_length"}
                }}
            ]
            
            avg_result = list(self.db.refinements.aggregate(pipeline))
            
            stats = {
                "total_refinements": total,
                "published_refinements": published,
                "avg_original_length": int(avg_result[0]["avg_original"]) if avg_result else 0,
                "avg_refined_length": int(avg_result[0]["avg_refined"]) if avg_result else 0
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Failed to get stats: {e}")
            return {}
    
    def get_global_stats(self) -> Dict:
        """
        סטטיסטיקות גלובליות
        """
        if not self.connected:
            return {}
        
        try:
            total_users = len(self.db.refinements.distinct("user_id"))
            total_refinements = self.db.refinements.count_documents({})
            total_published = self.db.refinements.count_documents({"published": True})
            
            return {
                "total_users": total_users,
                "total_refinements": total_refinements,
                "total_published": total_published
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get global stats: {e}")
            return {}


# יצירת instance גלובלי
mongodb = MongoDBHelper() if config.SAVE_HISTORY else None


# Context manager
class MongoDBContext:
    """Context manager לעבודה עם MongoDB"""
    
    def __enter__(self):
        if mongodb and not mongodb.connected:
            mongodb.connect()
        return mongodb
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # לא סוגרים כי אנחנו רוצים connection pool
        pass


# דוגמת שימוש:
if __name__ == "__main__":
    # בדיקה
    db = MongoDBHelper()
    
    if db.connected:
        print("✅ MongoDB connected!")
        
        # שמירת דוגמה
        doc_id = db.save_refinement(
            user_id=123456,
            username="test_user",
            original_text="טקסט מקורי לדוגמה",
            refined_text="טקסט משוכתב לדוגמה",
            published=False
        )
        
        if doc_id:
            print(f"Saved document: {doc_id}")
            
            # סטטיסטיקות
            stats = db.get_user_stats(123456)
            print(f"User stats: {stats}")
        
        db.close()
    else:
        print("❌ MongoDB not connected")
