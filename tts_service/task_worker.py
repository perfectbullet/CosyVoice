import asyncio
import logging
import os
from datetime import datetime
from tts_service.database import db
from tts_service.models import TaskStatus
from tts_service.tts_engine import tts_engine
from tts_service.config import settings

logger = logging.getLogger(__name__)


class TaskWorker:
    def __init__(self):
        self.running = False
        self.task_queue = asyncio.Queue()

    async def start(self):
        """启动任务处理器"""
        self.running = True
        logger.info("任务处理器已启动")

        while self.running:
            try:
                task_id = await asyncio.wait_for(
                    self.task_queue.get(),
                    timeout=1.0
                )
                await self.process_task(task_id)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"任务处理器错误: {e}")

    async def stop(self):
        """停止任务处理器"""
        self.running = False
        logger.info("任务处理器已停止")

    async def add_task(self, task_id: str):
        """添加任务到队列"""
        await self.task_queue.put(task_id)
        logger.info(f"任务已加入队列: {task_id}")

    async def process_task(self, task_id: str):
        """处理单个任务"""
        try:
            task = await db.get_task(task_id)
            if not task:
                logger.error(f"任务不存在: {task_id}")
                return

            logger.info(f"开始处理任务: {task_id}")

            await db.update_task(task_id, {"status": TaskStatus.RUNNING})

            now = datetime.utcnow()
            date_dir = os.path.join(
                settings.AUDIO_OUTPUT_DIR,
                str(now.year),
                f"{now.month:02d}",
                f"{now.day:02d}"
            )
            output_path = os.path.join(date_dir, f"{task_id}.wav")

            success = await tts_engine.synthesize(
                text=task.text,
                spk_id=task.spk_id,
                output_path=output_path
            )

            if success:
                await db.update_task(task_id, {
                    "status": TaskStatus.DONE,
                    "audio_path": output_path,
                    "description": "转换成功"
                })
                logger.info(f"任务完成: {task_id}")
            else:
                await db.update_task(task_id, {
                    "status": TaskStatus.FAILED,
                    "description": "音频合成失败"
                })
                logger.error(f"任务失败: {task_id}")

        except Exception as e:
            error_msg = f"任务处理异常: {str(e)}"
            logger.error(f"{error_msg}, task_id: {task_id}")

            import traceback
            traceback.print_exc()

            await db.update_task(task_id, {
                "status": TaskStatus.FAILED,
                "description": error_msg
            })


task_worker = TaskWorker()