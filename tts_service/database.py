from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional, List
from datetime import datetime
import logging
import time

from tts_service.config import settings
from tts_service.models import TTSTask, SpeakerInfo, TaskStatus, SpeakerRegistrationTask, SpeakerTaskStatus

logger = logging.getLogger(__name__)


class Database:
    client: Optional[AsyncIOMotorClient] = None
    # Speaker cache: spk_id -> (SpeakerInfo, timestamp)
    _speaker_cache: dict[str, tuple[SpeakerInfo, float]] = {}
    _cache_ttl: int = 3600  # Cache TTL in seconds (1 hour)

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
        # Invalidate cache for this speaker
        cls._speaker_cache.pop(speaker.spk_id, None)
        logger.info(f"说话人信息已保存: {speaker.spk_id}")

    @classmethod
    async def get_speaker(cls, spk_id: str) -> Optional[SpeakerInfo]:
        """获取说话人信息（带缓存）"""
        # Check cache first
        cached = cls._speaker_cache.get(spk_id)
        if cached:
            speaker_info, timestamp = cached
            age = time.time() - timestamp
            if age < cls._cache_ttl:
                logger.debug(f"缓存命中: {spk_id}")
                return speaker_info
            else:
                # Cache expired, remove it
                cls._speaker_cache.pop(spk_id, None)

        # Query from database
        db = cls.get_database()
        speaker_dict = await db.speakers.find_one({"spk_id": spk_id})
        if speaker_dict:
            speaker_dict.pop('_id', None)
            speaker_info = SpeakerInfo(**speaker_dict)
            # Store in cache
            cls._speaker_cache[spk_id] = (speaker_info, time.time())
            return speaker_info
        return None

    @classmethod
    async def get_recent_speakers(cls, limit: int = 10) -> List[SpeakerInfo]:
        """获取最近的说话人列表"""
        db = cls.get_database()
        cursor = db.speakers.find({}).sort("_id", -1).limit(limit)
        speakers = await cursor.to_list(length=limit)

        speaker_list = []
        for speaker_dict in speakers:
            speaker_dict.pop('_id', None)
            speaker_list.append(SpeakerInfo(**speaker_dict))

        logger.info(f"获取到 {len(speaker_list)} 个说话人")
        return speaker_list

    @classmethod
    async def get_all_speakers(cls) -> List[SpeakerInfo]:
        """获取所有说话人列表"""
        db = cls.get_database()
        cursor = db.speakers.find({}).sort("_id", -1)
        speakers = await cursor.to_list(length=None)

        speaker_list = []
        for speaker_dict in speakers:
            speaker_dict.pop('_id', None)
            speaker_list.append(SpeakerInfo(**speaker_dict))

        logger.info(f"获取到所有 {len(speaker_list)} 个说话人")
        return speaker_list

    @classmethod
    async def get_recent_tasks_detail(cls, limit: int = 10) -> List[TTSTask]:
        """获取最近的任务详细信息列表"""
        db = cls.get_database()
        cursor = db.tasks.find({}).sort("created_at", -1).limit(limit)
        tasks = await cursor.to_list(length=limit)

        task_list = []
        for task_dict in tasks:
            task_dict.pop('_id', None)
            task_list.append(TTSTask(**task_dict))

        logger.info(f"获取到 {len(task_list)} 个任务详情")
        return task_list

    @classmethod
    async def create_speaker_task(cls, task: SpeakerRegistrationTask) -> str:
        """创建说话人注册任务"""
        db = cls.get_database()
        task_dict = task.model_dump()
        task_dict['status'] = task.status.value
        await db.speaker_tasks.insert_one(task_dict)
        logger.info(f"说话人注册任务已创建: {task.task_id}")
        return task.task_id

    @classmethod
    async def get_speaker_task(cls, task_id: str) -> Optional[SpeakerRegistrationTask]:
        """根据任务ID获取说话人注册任务"""
        db = cls.get_database()
        task_dict = await db.speaker_tasks.find_one({"task_id": task_id})
        if task_dict:
            task_dict.pop('_id', None)
            return SpeakerRegistrationTask(**task_dict)
        return None

    @classmethod
    async def update_speaker_task(cls, task_id: str, update_data: dict):
        """更新说话人注册任务"""
        db = cls.get_database()
        update_data['updated_at'] = datetime.utcnow()

        if 'status' in update_data and isinstance(update_data['status'], SpeakerTaskStatus):
            update_data['status'] = update_data['status'].value

        await db.speaker_tasks.update_one(
            {"task_id": task_id},
            {"$set": update_data}
        )
        logger.info(f"说话人注册任务已更新: {task_id}")

db = Database()