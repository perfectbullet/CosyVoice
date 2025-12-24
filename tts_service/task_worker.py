import asyncio
import logging
import os
from datetime import datetime
import httpx
from tts_service.database import db
from tts_service.models import TaskStatus, SpeakerTaskStatus
from tts_service.tts_engine import tts_engine
from tts_service.config import settings

logger = logging.getLogger(__name__)


class TaskWorker:
    def __init__(self):
        self.running = False
        self.task_queue = asyncio.Queue()
        self.speaker_task_queue = asyncio.Queue()

    async def start(self):
        """启动任务处理器"""
        self.running = True
        logger.info("任务处理器已启动")

        # 启动TTS任务处理协程
        asyncio.create_task(self._process_tts_tasks())
        # 启动说话人注册任务处理协程
        asyncio.create_task(self._process_speaker_tasks())

    async def _process_tts_tasks(self):
        """处理TTS任务"""
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
                logger.error(f"TTS任务处理器错误: {e}")

    async def _process_speaker_tasks(self):
        """处理说话人注册任务"""
        while self.running:
            try:
                task_id = await asyncio.wait_for(
                    self.speaker_task_queue.get(),
                    timeout=1.0
                )
                await self.process_speaker_task(task_id)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"说话人注册任务处理器错误: {e}")

    async def stop(self):
        """停止任务处理器"""
        self.running = False
        logger.info("任务处理器已停止")

    async def add_task(self, task_id: str):
        """添加TTS任务到队列"""
        await self.task_queue.put(task_id)
        logger.info(f"TTS任务已加入队列: {task_id}")

    async def add_speaker_task(self, task_id: str):
        """添加说话人注册任务到队列"""
        await self.speaker_task_queue.put(task_id)
        logger.info(f"说话人注册任务已加入队列: {task_id}")

    async def process_speaker_task(self, task_id: str):
        """处理说话人注册任务"""
        try:
            task = await db.get_speaker_task(task_id)
            if not task:
                logger.error(f"说话人注册任务不存在: {task_id}")
                return

            logger.info(f"开始处理说话人注册任务: {task_id}")

            await db.update_speaker_task(task_id, {"status": SpeakerTaskStatus.RUNNING})

            prompt_text = task.prompt_text

            # 如果 prompt_text 为空，调用 ASR 服务识别音频文本
            if not prompt_text or prompt_text.strip() == "":
                logger.info(f"prompt_text 为空，调用 ASR 服务识别音频: {task.audio_path}")
                try:
                    async with httpx.AsyncClient(timeout=120.0) as client:
                        with open(task.audio_path, 'rb') as audio_f:
                            files = {'audio': (task.audio_filename, audio_f, 'audio/wav')}
                            data = {
                                'host': settings.ASR_HOST,
                                'port': settings.ASR_PORT,
                                'is_ssl': settings.ASR_IS_SSL,
                                'mode': settings.ASR_MODE
                            }
                            response = await client.post(
                                f"{settings.ASR_SERVICE_URL}/transcribe",
                                files=files,
                                data=data
                            )
                            
                            if response.status_code == 200:
                                result = response.json()
                                if result.get('code') == 0:
                                    prompt_text = result.get('text', '')
                                    logger.info(f"ASR 识别成功: {prompt_text}")
                                else:
                                    raise Exception(f"ASR 识别失败: {result}")
                            else:
                                raise Exception(f"ASR 服务请求失败: {response.status_code}, {response.text}")
                except Exception as e:
                    error_msg = f"调用 ASR 服务失败: {str(e)}"
                    logger.error(error_msg)
                    if os.path.exists(task.audio_path):
                        os.remove(task.audio_path)
                    await db.update_speaker_task(task_id, {
                        "status": SpeakerTaskStatus.FAILED,
                        "description": error_msg
                    })
                    return
                
                # 如果识别后仍为空，返回错误
                if not prompt_text or prompt_text.strip() == "":
                    error_msg = "无法识别音频文本"
                    logger.error(error_msg)
                    if os.path.exists(task.audio_path):
                        os.remove(task.audio_path)
                    await db.update_speaker_task(task_id, {
                        "status": SpeakerTaskStatus.FAILED,
                        "description": error_msg
                    })
                    return

            # 添加说话人
            success = await tts_engine.add_speaker(task.spk_id, prompt_text, task.audio_path)

            if success:
                # 保存说话人信息到数据库
                from tts_service.models import SpeakerInfo
                speaker = SpeakerInfo(
                    spk_id=task.spk_id,
                    prompt_text=prompt_text,
                    audio_path=task.audio_path
                )
                await db.create_speaker(speaker)

                await db.update_speaker_task(task_id, {
                    "status": SpeakerTaskStatus.DONE,
                    "prompt_text": prompt_text,
                    "description": "说话人注册成功"
                })
                logger.info(f"说话人注册任务完成: {task_id}")
            else:
                # 如果添加失败，删除已保存的音频文件
                if os.path.exists(task.audio_path):
                    os.remove(task.audio_path)
                await db.update_speaker_task(task_id, {
                    "status": SpeakerTaskStatus.FAILED,
                    "description": "添加说话人失败"
                })
                logger.error(f"说话人注册任务失败: {task_id}")

        except Exception as e:
            error_msg = f"说话人注册任务处理异常: {str(e)}"
            logger.error(f"{error_msg}, task_id: {task_id}")

            import traceback
            traceback.print_exc()

            # 清理音频文件
            try:
                task = await db.get_speaker_task(task_id)
                if task and os.path.exists(task.audio_path):
                    os.remove(task.audio_path)
            except:
                pass

            await db.update_speaker_task(task_id, {
                "status": SpeakerTaskStatus.FAILED,
                "description": error_msg
            })

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