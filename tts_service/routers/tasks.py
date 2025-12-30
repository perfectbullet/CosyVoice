"""TTS 任务相关的路由"""
import os
import uuid
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from tts_service.database import db
from tts_service.models import (
    TaskCreateRequest,
    TaskCreateResponse,
    TTSTask,
    TaskStatus,
    TaskListResponse,
    TaskDetailListResponse,
)
from tts_service.task_worker import task_worker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=TaskCreateResponse)
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


@router.get("/{task_id}", response_model=TTSTask)
async def get_task(task_id: str):
    """查询任务详情"""
    task = await db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.get("", response_model=TaskListResponse)
async def list_tasks():
    """获取任务列表"""
    task_ids = await db.get_recent_tasks(limit=10)
    return TaskListResponse(task_ids=task_ids, total=len(task_ids))


@router.get("/detail/list")
async def list_tasks_detail(limit: int = 10):
    """获取任务详细信息列表"""
    try:
        tasks = await db.get_recent_tasks_detail(limit=limit)
        return TaskDetailListResponse(tasks=tasks, total=len(tasks))
    except Exception as e:
        logger.error(f"获取任务详细列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{task_id}/audio")
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
