好的，我会基于你现有的 Dockerfile 来调整 docker-compose.yml 文件，整合 MongoDB 和 TTS 服务。

## 调整后的 docker-compose.yml

```yaml
name: cosyvoice-tts-stack

services:
  # MongoDB 服务
  mongodb:
    image: mongo:7.0
    container_name: tts_mongodb
    restart: unless-stopped
    ports:
      - "27017:27017"
    environment:
      MONGO_INITDB_ROOT_USERNAME: admin
      MONGO_INITDB_ROOT_PASSWORD: tts_password_2024
      MONGO_INITDB_DATABASE: tts_service
    volumes:
      - mongodb_data:/data/db
      - mongodb_config:/data/configdb
    networks:
      - cosyvoice-network
    healthcheck:
      test: echo 'db.runCommand("ping").ok' | mongosh localhost:27017/test --quiet
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 20s

  # CosyVoice TTS 服务
  cosyvoice:
    image: cosyvoice:v1.1
    build:
      context: .
      dockerfile: Dockerfile
    container_name: cosyvoice_tts_service
    # 修改启动命令为运行 FastAPI 服务
    command: python /opt/CosyVoice/tts_service/main.py
    ports:
      - "50000:50000"  # 保留原有端口
      - "50001:50001"  # 保留原有端口
      - "8000:8000"    # FastAPI 服务端口
    volumes:
      # 时区同步
      - /etc/localtime:/etc/localtime:ro
      - /etc/timezone:/etc/timezone:ro
      
      # TTS 服务代码（新增）
      - ./tts_service:/opt/CosyVoice/tts_service
      
      # 音频输出目录（新增）
      - ./data/audio_outputs:/opt/CosyVoice/data/audio_outputs
      - ./data/speaker_audios:/opt/CosyVoice/data/speaker_audios
      
      # 原有挂载
      - ./runtime:/opt/CosyVoice/runtime
      - ./pretrained_models:/opt/CosyVoice/pretrained_models
      - ./data:/opt/CosyVoice/data
      - ./vllm_example.py:/opt/CosyVoice/vllm_example.py
      - ./webui.py:/opt/CosyVoice/webui.py
      - ./README.md:/opt/CosyVoice/README.md
      - ./requirements.txt:/opt/CosyVoice/requirements.txt
      - ./wheel_packages:/opt/CosyVoice/wheel_packages
      - ./cosyvoice:/opt/CosyVoice/cosyvoice
      - ./asset:/asset
      - ./examples:/opt/CosyVoice/examples
      - ./tools:/opt/CosyVoice/tools
      - ./modelscope_hub:/root/.cache/modelscope/hub
    environment:
      - TZ=Asia/Shanghai
      - LANG=zh_CN.UTF-8
      - PYTHONUNBUFFERED=1
      # MongoDB 配置（新增）
      - MONGODB_URL=mongodb://admin:tts_password_2024@mongodb:27017/
      - MONGODB_DB_NAME=tts_service
      # 模型和输出路径配置（新增）
      - MODEL_PATH=/opt/CosyVoice/pretrained_models/CosyVoice2-0.5B
      - AUDIO_OUTPUT_DIR=/opt/CosyVoice/data/audio_outputs
      - SPEAKER_AUDIO_DIR=/opt/CosyVoice/data/speaker_audios
    depends_on:
      mongodb:
        condition: service_healthy
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    restart: unless-stopped
    networks:
      - cosyvoice-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

volumes:
  mongodb_data:
    driver: local
  mongodb_config:
    driver: local

networks:
  cosyvoice-network:
    driver: bridge
```

## 调整后的项目目录结构

```bash
cosyvoice_project/
├── Dockerfile                    # 你现有的 Dockerfile（不修改）
├── docker-compose.yml            # 新的 docker-compose.yml
├── requirements.txt              # 需要添加新依赖
├── tts_service/                  # TTS 服务代码目录（新增）
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── models.py
│   ├── database.py
│   ├── tts_engine.py
│   └── task_worker.py
├── data/
│   ├── audio_outputs/            # 音频输出目录（新增）
│   └── speaker_audios/           # 说话人音频目录（新增）
├── pretrained_models/
│   └── CosyVoice2-0.5B/
├── cosyvoice/
├── runtime/
└── ...（其他现有文件）
```

## 需要添加的依赖到 requirements.txt

在你现有的 `requirements.txt` 文件末尾添加：

```bash
cat >> requirements.txt << 'EOF'

# FastAPI TTS Service Dependencies
fastapi==0.104.1
uvicorn[standard]==0.24.0
motor==3.3.2
pymongo==4.6.0
python-multipart==0.0.6
aiofiles==23.2.1
pydantic-settings==2.1.0
EOF
```

## TTS 服务代码文件

### 1. tts_service/**init**.py

```bash
mkdir -p tts_service
cat > tts_service/__init__.py << 'EOF'
"""CosyVoice TTS Service"""
__version__ = "1.0.0"
EOF
```

### 2. tts_service/config.py

```python
cat > tts_service/config.py << 'EOF'
import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # MongoDB 配置
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://admin:tts_password_2024@mongodb:27017/")
    MONGODB_DB_NAME: str = os.getenv("MONGODB_DB_NAME", "tts_service")
    
    # 模型配置
    MODEL_PATH: str = os.getenv("MODEL_PATH", "/opt/CosyVoice/pretrained_models/CosyVoice2-0.5B")
    
    # 音频输出配置
    AUDIO_OUTPUT_DIR: str = os.getenv("AUDIO_OUTPUT_DIR", "/opt/CosyVoice/data/audio_outputs")
    SPEAKER_AUDIO_DIR: str = os.getenv("SPEAKER_AUDIO_DIR", "/opt/CosyVoice/data/speaker_audios")
    
    # 服务配置
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # CosyVoice 根目录
    COSYVOICE_ROOT: str = "/opt/CosyVoice"
    
    class Config:
        env_file = ".env"

settings = Settings()
EOF
```

### 3. tts_service/models.py

```python
cat > tts_service/models.py << 'EOF'
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from enum import Enum

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"

class TTSTask(BaseModel):
    task_id: str = Field(..., description="任务ID")
    text: str = Field(..., description="待转换文本")
    spk_id: str = Field(..., description="说话人ID")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="任务状态")
    audio_path: Optional[str] = Field(None, description="音频文件路径")
    description: Optional[str] = Field(None, description="任务描述或错误信息")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="更新时间")

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "tts_20241030_123456_abc123",
                "text": "你好，这是一个测试文本",
                "spk_id": "my_zero_shot_spk",
                "status": "done"
            }
        }

class SpeakerInfo(BaseModel):
    spk_id: str = Field(..., description="说话人ID")
    prompt_text: Optional[str] = Field(None, description="提示文本")
    audio_path: str = Field(..., description="参考音频路径")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")

class TaskCreateRequest(BaseModel):
    text: str = Field(..., description="待转换的文本", min_length=1)
    spk_id: str = Field(..., description="说话人ID")

    class Config:
        json_schema_extra = {
            "example": {
                "text": "收到好友从远方寄来的生日礼物，那份意外的惊喜与深深的祝福让我心中充满了甜蜜的快乐。",
                "spk_id": "my_zero_shot_spk"
            }
        }

class TaskCreateResponse(BaseModel):
    task_id: str = Field(..., description="任务ID")
    message: str = Field(default="任务创建成功", description="响应消息")

class TaskListResponse(BaseModel):
    task_ids: list[str] = Field(..., description="最近10条任务ID列表")
    total: int = Field(..., description="返回的任务数量")
EOF
```

### 4. tts_service/database.py

```python
cat > tts_service/database.py << 'EOF'
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
EOF
```

### 5. tts_service/tts_engine.py

```python
cat > tts_service/tts_engine.py << 'EOF'
import sys
import os
import logging
import asyncio
from typing import Optional
import torchaudio

from tts_service.config import settings

# 添加 CosyVoice 路径
sys.path.insert(0, settings.COSYVOICE_ROOT)
sys.path.insert(0, os.path.join(settings.COSYVOICE_ROOT, 'third_party', 'Matcha-TTS'))

from cosyvoice.cli.cosyvoice import CosyVoice2
from cosyvoice.utils.file_utils import load_wav

logger = logging.getLogger(__name__)

class TTSEngine:
    def __init__(self):
        self.model: Optional[CosyVoice2] = None
        self.sample_rate: int = 22050
    
    async def initialize(self):
        """初始化模型"""
        try:
            logger.info(f"正在加载模型: {settings.MODEL_PATH}")
            
            loop = asyncio.get_event_loop()
            self.model = await loop.run_in_executor(
                None,
                lambda: CosyVoice2(
                    settings.MODEL_PATH,
                    load_jit=False,
                    load_trt=False,
                    load_vllm=False,
                    fp16=False
                )
            )
            
            self.sample_rate = self.model.sample_rate
            logger.info(f"模型加载成功，采样率: {self.sample_rate}")
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            raise
    
    async def add_speaker(self, spk_id: str, prompt_text: str, audio_path: str) -> bool:
        """添加说话人"""
        try:
            prompt_speech_16k = load_wav(audio_path, 16000)
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.model.add_zero_shot_spk(
                    prompt_text,
                    prompt_speech_16k,
                    spk_id
                )
            )
            
            if result:
                await loop.run_in_executor(None, self.model.save_spkinfo)
                logger.info(f"说话人已添加: {spk_id}")
                return True
            
            return False
        except Exception as e:
            logger.error(f"添加说话人失败: {e}")
            return False
    
    async def synthesize(self, text: str, spk_id: str, output_path: str) -> bool:
        """合成语音"""
        try:
            logger.info(f"开始合成: spk_id={spk_id}, text_length={len(text)}")
            
            loop = asyncio.get_event_loop()
            
            def do_inference():
                output = None
                for i, j in enumerate(self.model.inference_zero_shot(
                    text,
                    '',
                    '',
                    zero_shot_spk_id=spk_id,
                    stream=False
                )):
                    if i == 0:
                        output = j['tts_speech']
                        break
                return output
            
            tts_speech = await loop.run_in_executor(None, do_inference)
            
            if tts_speech is None:
                logger.error("推理返回空结果")
                return False
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            await loop.run_in_executor(
                None,
                lambda: torchaudio.save(output_path, tts_speech, self.sample_rate)
            )
            
            logger.info(f"音频已保存: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"合成失败: {e}")
            import traceback
            traceback.print_exc()
            return False

tts_engine = TTSEngine()
EOF
```

### 6. tts_service/task_worker.py

```python
cat > tts_service/task_worker.py << 'EOF'
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
EOF
```

### 7. tts_service/main.py (FastAPI 主应用)

```python
cat > tts_service/main.py << 'EOF'
import logging
import os
import asyncio
import uuid
from datetime import datetime
from contextlib import asynccontextmanager

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
        
        task_id = f"tts_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
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
        if not audio_file.filename.lower().endswith(('.wav', '.mp3', '.flac')):
            raise HTTPException(status_code=400, detail="仅支持 WAV、MP3、FLAC 格式")
        
        audio_filename = f"{spk_id}.wav"
        audio_path = os.path.join(settings.SPEAKER_AUDIO_DIR, audio_filename)
        
        async with aiofiles.open(audio_path, 'wb') as f:
            content = await audio_file.read()
            await f.write(content)
        
        success = await tts_engine.add_speaker(spk_id, prompt_text, audio_path)
        
        if not success:
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
EOF
```

## 启动步骤

```bash
# 1. 创建必要的目录
mkdir -p data/audio_outputs data/speaker_audios

# 2. 安装额外的 Python 依赖（如果还没有构建镜像）
# 将上面提到的依赖添加到 requirements.txt

# 3. 构建并启动服务
docker-compose up --build -d

# 4. 查看日志
docker-compose logs -f cosyvoice

# 5. 等待服务启动（大约 1-2 分钟）
# 访问 API 文档: http://localhost:8000/docs
```

## 快速测试

```bash
# 健康检查
curl http://localhost:8000/health

# 上传说话人（需要准备测试音频）
curl -X POST "http://localhost:8000/speakers" \
  -F "spk_id=test_spk" \
  -F "prompt_text=这是测试文本" \
  -F "audio_file=@test.wav"

# 创建任务
curl -X POST "http://localhost:8000/tasks" \
  -H "Content-Type: application/json" \
  -d '{"text":"你好，这是测试", "spk_id":"test_spk"}'

# 查询任务
curl http://localhost:8000/tasks/任务ID
```

这个方案保留了你现有的 Dockerfile，只调整了 docker-compose.yml 并添加了必要的 TTS 服务代码。所有代码都按照你的目录结构进行了适配。