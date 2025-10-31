import asyncio
import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

# 添加父目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0,
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'third_party', 'Matcha-TTS'))
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import aiofiles

from tts_service.config import settings
from tts_service.database import db
from tts_service.models import (
    TaskCreateRequest,
    TaskCreateResponse,
    TTSTask,
    TaskStatus,
    TaskListResponse,
    SpeakerInfo
)
from tts_service.tts_engine import tts_engine
from tts_service.task_worker import task_worker

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("正在启动 TTS 服务...")

    await db.connect_db()
    await tts_engine.initialize()
    asyncio.create_task(task_worker.start())

    os.makedirs(settings.AUDIO_OUTPUT_DIR, exist_ok=True)
    os.makedirs(settings.SPEAKER_AUDIO_DIR, exist_ok=True)

    logger.info("TTS 服务启动完成")

    yield

    logger.info("正在关闭 TTS 服务...")
    await task_worker.stop()
    await db.close_db()
    logger.info("TTS 服务已关闭")


app = FastAPI(
    title="CosyVoice2 TTS Service",
    description="基于 CosyVoice2 的文本转语音异步服务",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


@app.get("/")
async def root():
    return {
        "service": "CosyVoice2 TTS Service",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "model_loaded": tts_engine.model is not None
    }


@app.post("/tasks", response_model=TaskCreateResponse)
async def create_task(request: TaskCreateRequest):
    """创建TTS任务"""
    try:
        speaker = await db.get_speaker(request.spk_id)
        if not speaker:
            raise HTTPException(
                status_code=404,
                detail=f"说话人 {request.spk_id} 不存在"
            )

        task_id = f"tts_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        task = TTSTask(
            task_id=task_id,
            text=request.text,
            spk_id=request.spk_id,
            status=TaskStatus.PENDING
        )

        await db.create_task(task)
        await task_worker.add_task(task_id)

        return TaskCreateResponse(task_id=task_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tasks/{task_id}", response_model=TTSTask)
async def get_task(task_id: str):
    """查询任务详情"""
    task = await db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@app.get("/tasks", response_model=TaskListResponse)
async def list_tasks():
    """获取任务列表"""
    task_ids = await db.get_recent_tasks(limit=10)
    return TaskListResponse(task_ids=task_ids, total=len(task_ids))


@app.get("/tasks/{task_id}/audio")
async def get_audio(task_id: str):
    """下载音频文件"""
    task = await db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.status != TaskStatus.DONE:
        raise HTTPException(status_code=400, detail=f"任务状态为 {task.status.value}")

    if not task.audio_path or not os.path.exists(task.audio_path):
        raise HTTPException(status_code=404, detail="音频文件不存在")

    return FileResponse(
        path=task.audio_path,
        media_type="audio/wav",
        filename=f"{task_id}.wav"
    )


@app.post("/speakers")
async def upload_speaker(
        spk_id: str = Form(...),
        prompt_text: str = Form(...),
        audio_file: UploadFile = File(...)
):
    """注册说话人"""
    try:
        # 检查说话人是否已存在
        existing_speaker = await db.get_speaker(spk_id)
        if existing_speaker:
            raise HTTPException(
                status_code=400,
                detail=f"说话人 {spk_id} 已存在，请使用不同的 spk_id"
            )

        if not audio_file.filename.lower().endswith(('.wav', '.mp3', '.flac')):
            raise HTTPException(status_code=400, detail="仅支持 WAV、MP3、FLAC 格式")

        audio_filename = f"{spk_id}.wav"
        audio_path = os.path.join(settings.SPEAKER_AUDIO_DIR, audio_filename)

        async with aiofiles.open(audio_path, 'wb') as f:
            content = await audio_file.read()
            await f.write(content)

        success = await tts_engine.add_speaker(spk_id, prompt_text, audio_path)

        if not success:
            # 如果添加失败，删除已保存的音频文件
            if os.path.exists(audio_path):
                os.remove(audio_path)
            raise HTTPException(status_code=500, detail="添加说话人失败")

        speaker = SpeakerInfo(
            spk_id=spk_id,
            prompt_text=prompt_text,
            audio_path=audio_path
        )
        await db.create_speaker(speaker)

        return {
            "message": "说话人注册成功",
            "spk_id": spk_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"上传说话人失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/speakers/{spk_id}", response_model=SpeakerInfo)
async def get_speaker(spk_id: str):
    """查询指定说话人信息"""
    speaker = await db.get_speaker(spk_id)
    if not speaker:
        raise HTTPException(
            status_code=404,
            detail=f"说话人 {spk_id} 不存在"
        )
    return speaker


@app.get("/speakers")
async def list_speakers(limit: int = 10):
    """获取说话人列表"""
    try:
        speakers = await db.get_recent_speakers(limit=limit)
        return {
            "speakers": speakers,
            "total": len(speakers)
        }
    except Exception as e:
        logger.error(f"获取说话人列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.HOST, port=settings.PORT)