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
import httpx
import torchaudio

from tts_service.config import settings
from tts_service.database import db
from tts_service.models import (
    TaskCreateRequest,
    TaskCreateResponse,
    TTSTask,
    TaskStatus,
    TaskListResponse,
    TaskDetailListResponse,
    SpeakerInfo,
    SpeakerRegistrationTask,
    SpeakerTaskStatus,
    SpeakerTaskCreateResponse
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

@app.get("/tasks/detail/list")
async def list_tasks_detail(limit: int = 10):
    """获取任务详细信息列表"""
    try:
        tasks = await db.get_recent_tasks_detail(limit=limit)
        return TaskDetailListResponse(tasks=tasks, total=len(tasks))
    except Exception as e:
        logger.error(f"获取任务详细列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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


@app.post("/speakers", response_model=SpeakerTaskCreateResponse)
async def upload_speaker(
        spk_id: str = Form(...),
        prompt_text: str = Form(""),
        audio_file: UploadFile = File(...)
):
    """
    注册说话人（异步）
    
    参数:
    - spk_id: 说话人ID
    - prompt_text: 提示文本（可选）
    - audio_file: 说话人参考音频文件（支持 WAV 采样率: 16000Hz）, 音频时长大于20s会被截断为20s。
    
    """
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

        # 生成任务ID
        task_id = f"speaker_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        audio_filename = f"{spk_id}.wav"
        audio_path = os.path.join(settings.SPEAKER_AUDIO_DIR, audio_filename)

        # 保存音频文件
        async with aiofiles.open(audio_path, 'wb') as f:
            content = await audio_file.read()
            await f.write(content)
        
        # 检查音频时长并处理
        try:
            # 加载音频文件
            audio_data, sample_rate = torchaudio.load(audio_path)
            duration = audio_data.shape[1] / sample_rate
            
            logger.info(f"音频时长: {duration:.2f}秒, 采样率: {sample_rate}Hz")
            
            # 检查音频时长是否小于3秒
            if duration < 3.0:
                if os.path.exists(audio_path):
                    os.remove(audio_path)
                raise HTTPException(
                    status_code=400, 
                    detail=f"音频时长不足，当前时长 {duration:.2f}秒，要求至少 3 秒"
                )
            
            # 如果音频时长大于20秒，截取前20秒
            if duration > 20.0:
                logger.info(f"音频时长 {duration:.2f}秒 超过20秒，截取前20秒")
                max_samples = int(20.0 * sample_rate)
                audio_data = audio_data[:, :max_samples]
                # 保存截取后的音频
                torchaudio.save(audio_path, audio_data, sample_rate)
                logger.info(f"音频已截取并保存，新时长: 20秒")
        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"处理音频文件时出错: {e}")
            if os.path.exists(audio_path):
                os.remove(audio_path)
            raise HTTPException(status_code=500, detail=f"音频文件处理失败: {str(e)}")
        
        # 创建说话人注册任务
        speaker_task = SpeakerRegistrationTask(
            task_id=task_id,
            spk_id=spk_id,
            prompt_text=prompt_text,
            audio_filename=audio_filename,
            audio_path=audio_path,
            status=SpeakerTaskStatus.PENDING
        )

        await db.create_speaker_task(speaker_task)
        await task_worker.add_speaker_task(task_id)

        return SpeakerTaskCreateResponse(
            task_id=task_id,
            message="说话人注册任务已创建，请通过任务ID查询处理进度"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建说话人注册任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/speakers/task/{task_id}", response_model=SpeakerRegistrationTask)
async def get_speaker_task(task_id: str):
    """查询说话人注册任务状态"""
    task = await db.get_speaker_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


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