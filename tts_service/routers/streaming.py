"""流式TTS合成相关的路由"""
import uuid
import json
import base64
import logging
import asyncio
from typing import AsyncGenerator
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from tts_service.database import db
from tts_service.tts_engine import tts_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/streaming", tags=["streaming"])


class StreamingSynthesisRequest(BaseModel):
    """流式合成请求"""
    text: str
    spk_id: str


class StreamingSynthesisResponse(BaseModel):
    """流式合成响应"""
    stream_id: str
    message: str
    sample_rate: int  # 服务端实际输出采样率


@router.post("/synthesize", response_model=StreamingSynthesisResponse)
async def start_streaming_synthesis(request: StreamingSynthesisRequest):
    """
    启动流式合成
    
    请求体:
    {
        "text": "你好，世界",
        "spk_id": "speaker_001"
    }
    
    响应:
    {
        "stream_id": "uuid-xxx",
        "message": "Synthesis started"
    }
    
    使用方式:
    1. POST /streaming/synthesize 启动合成，获取 stream_id
    2. GET /streaming/audio/{stream_id} 通过 SSE 获取音频流
    """
    try:
        text = request.text.strip()
        spk_id = request.spk_id.strip()
        
        if not text:
            raise HTTPException(status_code=400, detail="文本不能为空")
        
        if not spk_id:
            raise HTTPException(status_code=400, detail="说话人ID不能为空")
        
        # 检查说话人是否存在
        speaker = await db.get_speaker(spk_id)
        if not speaker:
            raise HTTPException(
                status_code=404,
                detail=f"说话人 {spk_id} 不存在"
            )
        
        # 生成唯一的流 ID
        stream_id = str(uuid.uuid4())
        
        # 创建流的队列
        tts_engine.create_stream(stream_id)
        
        # 在后台启动合成
        asyncio.create_task(
            tts_engine.synthesize_streaming(
                text=text,
                spk_id=spk_id,
                stream_id=stream_id
            )
        )
        
        logger.info(f"Streaming synthesis started with stream_id: {stream_id}")
        
        return StreamingSynthesisResponse(
            stream_id=stream_id,
            message="合成已启动",
            sample_rate=tts_engine.output_sample_rate  # 返回实际输出采样率
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"启动流式合成失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audio/{stream_id}")
async def stream_audio(stream_id: str):
    """
    SSE 端点：流式返回音频数据（异步队列版本）
    
    使用方式:
    curl -N http://localhost:50002/streaming/audio/stream-id
    
    或在浏览器中使用 EventSource API:
    const eventSource = new EventSource('/streaming/audio/stream-id');
    eventSource.addEventListener('audio_chunk', (event) => {
        const data = JSON.parse(event.data);
        // data.audio 是 base64 编码的音频数据
    });
    """
    
    async def event_generator() -> AsyncGenerator[str, None]:
        """生成 SSE 事件（异步队列版本）"""
        try:
            queue = tts_engine._stream_queues.get(stream_id)
            
            if queue is None:
                yield f"data: {json.dumps({'type': 'error', 'data': '流不存在'})}\n\n"
                return
            
            logger.info(f"SSE client connected for stream {stream_id}")
            
            while True:
                try:
                    # 直接异步获取，无需 run_in_executor
                    message = await asyncio.wait_for(
                        queue.get(), 
                        timeout=1.0
                    )
                    
                    if message["type"] == "audio_chunk":
                        # 将二进制数据转为 base64 编码
                        audio_b64 = base64.b64encode(message["data"]).decode('utf-8')
                        yield f"data: {json.dumps({'type': 'audio_chunk', 'data': audio_b64})}\n\n"
                        logger.debug(f"Sent audio chunk to stream {stream_id}")
                    
                    elif message["type"] == "complete":
                        yield f"data: {json.dumps({'type': 'complete', 'data': None})}\n\n"
                        logger.info(f"Stream {stream_id} completed")
                        break
                    
                    elif message["type"] == "error":
                        yield f"data: {json.dumps({'type': 'error', 'data': message['data']})}\n\n"
                        logger.error(f"Stream {stream_id} error: {message['data']}")
                        break
                
                except asyncio.TimeoutError:
                    # 超时继续等待（不是错误）
                    continue
                except Exception as e:
                    logger.error(f"Error in event generator: {e}")
                    yield f"data: {json.dumps({'type': 'error', 'data': str(e)})}\n\n"
                    break
        
        finally:
            # 清理流
            tts_engine.remove_stream(stream_id)
            logger.info(f"Stream {stream_id} cleaned up")
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
