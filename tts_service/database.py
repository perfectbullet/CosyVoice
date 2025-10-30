from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional, List
from datetime import datetime
import logging

from tts_service.config import settings
from tts_service.models import TTSTask, SpeakerInfo, TaskStatus

logger = logging.getLogger(__name__)


class Database:
    client: Optional[AsyncIOMotorClient] = None

    @classmethod
    async def connect_db(cls):
        """连接数据库"""
        try:
            cls.client = AsyncIOMotorClient(settings.MONGODB_URL)
            await cls.client.admin.command('ping')
            logger.info("成功连接到 MongoDB")
        except Exception as e:
            logger.error(f"连接 MongoDB 失败: {e}")
            raise

    @classmethod
    async def close_db(cls):
        """关闭数据库连接"""
        if cls.client:
            cls.client.close()
            logger.info("MongoDB 连接已关闭")

    @classmethod
    def get_database(cls):
        """获取数据库实例"""
        return cls.client[settings.MONGODB_DB_NAME]

    @classmethod
    async def create_task(cls, task: TTSTask) -> str:
        """创建任务"""
        db = cls.get_database()
        task_dict = task.model_dump()
        task_dict['status'] = task.status.value
        await db.tasks.insert_one(task_dict)
        logger.info(f"任务已创建: {task.task_id}")
        return task.task_id

    @classmethod
    async def get_task(cls, task_id: str) -> Optional[TTSTask]:
        """根据任务ID获取任务"""
        db = cls.get_database()
        task_dict = await db.tasks.find_one({"task_id": task_id})
        if task_dict:
            task_dict.pop('_id', None)
            return TTSTask(**task_dict)
        return None

    @classmethod
    async def update_task(cls, task_id: str, update_data: dict):
        """更新任务"""
        db = cls.get_database()
        update_data['updated_at'] = datetime.utcnow()

        if 'status' in update_data and isinstance(update_data['status'], TaskStatus):
            update_data['status'] = update_data['status'].value

        await db.tasks.update_one(
            {"task_id": task_id},
            {"$set": update_data}
        )
        logger.info(f"任务已更新: {task_id}")

    @classmethod
    async def get_recent_tasks(cls, limit: int = 10) -> List[str]:
        """获取最近的任务ID列表"""
        db = cls.get_database()
        cursor = db.tasks.find({}, {"task_id": 1, "_id": 0}).sort("created_at", -1).limit(limit)
        tasks = await cursor.to_list(length=limit)
        return [task["task_id"] for task in tasks]

    @classmethod
    async def create_speaker(cls, speaker: SpeakerInfo):
        """创建或更新说话人信息"""
        db = cls.get_database()
        speaker_dict = speaker.model_dump()

        await db.speakers.update_one(
            {"spk_id": speaker.spk_id},
            {"$set": speaker_dict},
            upsert=True
        )
        logger.info(f"说话人信息已保存: {speaker.spk_id}")

    @classmethod
    async def get_speaker(cls, spk_id: str) -> Optional[SpeakerInfo]:
        """获取说话人信息"""
        db = cls.get_database()
        speaker_dict = await db.speakers.find_one({"spk_id": spk_id})
        if speaker_dict:
            speaker_dict.pop('_id', None)
            return SpeakerInfo(**speaker_dict)
        return None


db = Database()