import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager

# 添加父目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0,
                os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'third_party', 'Matcha-TTS'))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tts_service.config import settings
from tts_service.database import db
from tts_service.tts_engine import tts_engine
from tts_service.task_worker import task_worker
from tts_service.routers import tasks, speakers, streaming, websocket

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

# 注册路由
app.include_router(tasks.router)
app.include_router(speakers.router)
app.include_router(streaming.router)
app.include_router(websocket.router)


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.HOST,
        port=settings.PORT,
        ws_ping_interval=20,   # WebSocket ping 间隔（秒）
        ws_ping_timeout=20,    # WebSocket ping 超时（秒）
    )
