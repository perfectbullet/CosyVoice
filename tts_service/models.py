from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"

class SpeakerTaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"

class SpeakerRegistrationTask(BaseModel):
    task_id: str = Field(..., description="任务ID")
    spk_id: str = Field(..., description="说话人ID")
    prompt_text: Optional[str] = Field(None, description="提示文本")
    audio_filename: str = Field(..., description="音频文件名")
    audio_path: str = Field(..., description="音频临时路径")
    status: SpeakerTaskStatus = Field(default=SpeakerTaskStatus.PENDING, description="任务状态")
    description: Optional[str] = Field(None, description="任务描述或错误信息")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="更新时间")

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "speaker_20241030_123456_abc123",
                "spk_id": "my_speaker",
                "status": "done"
            }
        }

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

class TaskListResponse(BaseModel):
    """任务列表响应（简单版本，仅返回task_id）"""
    task_ids: List[str]
    total: int

class TaskDetailListResponse(BaseModel):
    """任务详细列表响应"""
    tasks: List[TTSTask]
    total: int

class SpeakerTaskCreateResponse(BaseModel):
    task_id: str = Field(..., description="说话人注册任务ID")
    message: str = Field(default="说话人注册任务已创建", description="响应消息")