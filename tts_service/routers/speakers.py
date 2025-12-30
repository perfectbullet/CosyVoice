"""说话人管理相关的路由"""
import os
import uuid
import logging
from datetime import datetime
import torchaudio
import aiofiles
from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from tts_service.config import settings
from tts_service.database import db
from tts_service.models import (
    SpeakerInfo,
    SpeakerRegistrationTask,
    SpeakerTaskStatus,
    SpeakerTaskCreateResponse
)
from tts_service.task_worker import task_worker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/speakers", tags=["speakers"])


@router.post("", response_model=SpeakerTaskCreateResponse)
async def upload_speaker(
        spk_id: str = Form(...),
        prompt_text: str = Form(""),
        audio_file: UploadFile = File(...)
):
    """
    注册说话人（异步）
    
    参数:
    - spk_id: 说话人ID（唯一标识）
    - prompt_text: 提示文本（可选，如果为空则自动调用ASR识别）
    - audio_file: 说话人参考音频文件
      - 支持格式: WAV、MP3、FLAC
      - 时长要求: 至少3秒，超过20秒会自动截断为20秒
      - 采样率: 任意采样率，系统会自动转换为16000Hz
      - 声道: 支持单声道和立体声，系统会自动转换为单声道
    
    返回:
    - task_id: 说话人注册任务ID
    - message: 包含音频转换详情的说明信息
    - original_format: 原始音频格式
    - original_sample_rate: 原始采样率(Hz)
    - original_duration: 原始音频时长(秒)
    - processed_duration: 处理后音频时长(秒)
    - converted_to_16k: 是否进行了重采样
    
    注意事项:
    - 上传的音频将被转换为 16000Hz 单声道 WAV 格式
    - 如果未提供 prompt_text，系统会自动调用 ASR 服务识别音频内容
    - 任务为异步处理，需通过 /speakers/task/{task_id} 查询处理进度
    """
    try:
        # 检查说话人是否已存在
        existing_speaker = await db.get_speaker(spk_id)
        if existing_speaker:
            raise HTTPException(
                status_code=400,
                detail=f"说话人 {spk_id} 已存在，请使用不同的 spk_id"
            )

        if not audio_file.filename.lower().endswith(('.wav', '.mp3', '.flac', '.m4a')):
            raise HTTPException(status_code=400, detail="仅支持 WAV、MP3、FLAC、M4A 格式")

        # 记录原始音频格式
        original_format = os.path.splitext(audio_file.filename)[1].lower()

        # 生成任务ID
        task_id = f"speaker_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        audio_filename = f"{spk_id}.wav"
        audio_path = os.path.join(settings.SPEAKER_AUDIO_DIR, audio_filename)
        
        # 保存临时文件
        temp_path = audio_path + ".tmp"
        async with aiofiles.open(temp_path, 'wb') as f:
            content = await audio_file.read()
            await f.write(content)
        
        # 音频格式转换和处理
        try:
            # 加载音频文件
            audio_data, sample_rate = torchaudio.load(temp_path)
            original_sample_rate = sample_rate
            original_duration = audio_data.shape[1] / sample_rate
            
            logger.info(f"原始音频 - 格式: {original_format}, 采样率: {original_sample_rate}Hz, 时长: {original_duration:.2f}秒")
            
            # 检查音频时长是否小于3秒
            if original_duration < 3.0:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                raise HTTPException(
                    status_code=400, 
                    detail=f"音频时长不足，当前时长 {original_duration:.2f}秒，要求至少 3 秒"
                )
            
            # 转换为单声道
            if audio_data.shape[0] > 1:
                audio_data = audio_data.mean(dim=0, keepdim=True)
                logger.info("已转换为单声道")
            
            # 如果音频时长大于20秒，截取前20秒
            processed_duration = original_duration
            if original_duration > 20.0:
                logger.info(f"音频时长 {original_duration:.2f}秒 超过20秒，截取前20秒")
                max_samples = int(20.0 * sample_rate)
                audio_data = audio_data[:, :max_samples]
                processed_duration = 20.0
            
            # 重采样到16kHz
            converted_to_16k = False
            target_sr = 16000
            if sample_rate != target_sr:
                logger.info(f"重采样: {sample_rate}Hz -> {target_sr}Hz")
                resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=target_sr)
                audio_data = resampler(audio_data)
                converted_to_16k = True
            
            # 保存为16kHz WAV格式
            torchaudio.save(audio_path, audio_data, target_sr)
            logger.info(f"音频已保存 - 格式: .wav, 采样率: {target_sr}Hz, 时长: {processed_duration:.2f}秒")
            
            # 删除临时文件
            if os.path.exists(temp_path):
                os.remove(temp_path)
        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"处理音频文件时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # 清理临时文件和目标文件
            if os.path.exists(temp_path):
                os.remove(temp_path)
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
            message=f"说话人注册任务已创建，请通过任务ID查询处理进度。音频已从 {original_format}({original_sample_rate}Hz, {original_duration:.2f}秒) 转换为 .wav(16000Hz, {processed_duration:.2f}秒)",
            original_format=original_format,
            original_sample_rate=original_sample_rate,
            original_duration=round(original_duration, 2),
            processed_duration=round(processed_duration, 2),
            converted_to_16k=converted_to_16k
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建说话人注册任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/task/{task_id}", response_model=SpeakerRegistrationTask)
async def get_speaker_task(task_id: str):
    """查询说话人注册任务状态"""
    task = await db.get_speaker_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.get("/{spk_id}", response_model=SpeakerInfo)
async def get_speaker(spk_id: str):
    """查询指定说话人信息"""
    speaker = await db.get_speaker(spk_id)
    if not speaker:
        raise HTTPException(
            status_code=404,
            detail=f"说话人 {spk_id} 不存在"
        )
    return speaker


@router.get("")
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
