"""WebSocket 流式TTS合成接口"""
import json
import logging
import base64
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
from pydantic import BaseModel

from tts_service.database import db
from tts_service.tts_engine import tts_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/streaming", tags=["websocket"])


class WebSocketSynthesisRequest(BaseModel):
    """WebSocket 合成请求"""
    action: str  # "synthesize"
    text: str
    spk_id: str
    chunk_id: Optional[int] = None  # 可选，用于标识不同文本片段


@router.websocket("/ws")
async def websocket_synthesize(websocket: WebSocket):
    """
    WebSocket 端点：流式TTS合成
    
    消息格式：
    {
        "action": "synthesize",
        "text": "要合成的文本",
        "spk_id": "说话人ID",
        "chunk_id": 1  # 可选
    }
    
    返回格式：
    # 音频块
    {
        "type": "audio",
        "chunk_id": 1,
        "data": "<base64_encoded_audio>",
        "done": false
    }
    
    # 完成信号
    {
        "type": "complete",
        "chunk_id": 1
    }
    
    # 错误信号
    {
        "type": "error",
        "chunk_id": 1,
        "data": "错误信息"
    }
    """
    await websocket.accept()
    logger.info("WebSocket 客户端已连接")
    
    try:
        while True:
            # 检查连接是否仍然打开
            if websocket.client_state != WebSocketState.CONNECTED:
                logger.info("WebSocket 连接未打开，退出主循环")
                break
            
            # 接收客户端消息
            try:
                data = await websocket.receive_text()
                request = json.loads(data)
            except WebSocketDisconnect:
                logger.info("WebSocket 连接已断开")
                break
            except json.JSONDecodeError:
                try:
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await websocket.send_json({
                            "type": "error",
                            "data": "Invalid JSON format"
                        })
                except Exception as send_error:
                    logger.warning(f"发送错误消息失败: {send_error}")
                continue
            
            # 处理合成请求
            if request.get("action") != "synthesize":
                await websocket.send_json({
                    "type": "error",
                    "chunk_id": request.get("chunk_id"),
                    "data": "Unknown action, expected 'synthesize'"
                })
                continue
            
            text = request.get("text", "").strip()
            spk_id = request.get("spk_id", "").strip()
            chunk_id = request.get("chunk_id")
            
            # 验证参数
            if not text:
                try:
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await websocket.send_json({
                            "type": "error",
                            "chunk_id": chunk_id,
                            "data": "文本不能为空"
                        })
                except Exception as send_error:
                    logger.warning(f"发送验证错误消息失败: {send_error}")
                continue
            
            if not spk_id:
                try:
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await websocket.send_json({
                            "type": "error",
                            "chunk_id": chunk_id,
                            "data": "说话人ID不能为空"
                        })
                except Exception as send_error:
                    logger.warning(f"发送验证错误消息失败: {send_error}")
                continue
            
            # 检查说话人是否存在
            try:
                speaker = await db.get_speaker(spk_id)
                if not speaker:
                    try:
                        if websocket.client_state == WebSocketState.CONNECTED:
                            await websocket.send_json({
                                "type": "error",
                                "chunk_id": chunk_id,
                                "data": f"说话人 {spk_id} 不存在"
                            })
                    except Exception as send_error:
                        logger.warning(f"发送错误消息失败: {send_error}")
                    continue
            except Exception as e:
                logger.error(f"检查说话人失败: {e}")
                try:
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await websocket.send_json({
                            "type": "error",
                            "chunk_id": chunk_id,
                            "data": f"检查说话人失败: {str(e)}"
                        })
                except Exception as send_error:
                    logger.warning(f"发送错误消息失败: {send_error}")
                continue
            
            # 执行合成
            try:
                logger.info(f"WebSocket 合成请求: chunk_id={chunk_id}, spk_id={spk_id}, text_length={len(text)}")
                
                # 在线程池中执行模型推理
                import asyncio
                loop = asyncio.get_event_loop()
                
                def _model_inference():
                    """同步推理函数（在线程池中执行）"""
                    results = []
                    # 创建重采样器：从24000Hz重采样到16000Hz
                    import torchaudio
                    resampler = torchaudio.transforms.Resample(
                        orig_freq=tts_engine.sample_rate,
                        new_freq=tts_engine.output_sample_rate
                    )
                    
                    for i, chunk in enumerate(tts_engine.model.inference_zero_shot(
                        text,
                        '',
                        '',
                        zero_shot_spk_id=spk_id,
                        stream=True
                    )):
                        audio_data = chunk.get('tts_speech')
                        if audio_data is not None:
                            # 重采样到16000Hz
                            import torch
                            if isinstance(audio_data, torch.Tensor):
                                audio_resampled = resampler(audio_data)
                            else:
                                audio_resampled = audio_data
                            
                            audio_bytes = tts_engine._convert_to_pcm_bytes(audio_resampled)
                            if audio_bytes and len(audio_bytes) > 0:
                                results.append((i, audio_bytes))
                    return results
                
                # 在线程池中执行推理
                results = await loop.run_in_executor(None, _model_inference)
                
                # 发送音频块
                for i, audio_bytes in results:
                    # 检查连接是否仍然打开
                    if websocket.client_state != WebSocketState.CONNECTED:
                        logger.info(f"WebSocket 连接已断开，跳过发送数据 (chunk_id={chunk_id})")
                        break
                    
                    try:
                        # 编码为 base64
                        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
                        
                        await websocket.send_json({
                            "type": "audio",
                            "chunk_id": chunk_id,
                            "data": audio_b64,
                            "done": False
                        })
                        logger.debug(f"发送音频块 {i} (chunk_id={chunk_id}): {len(audio_bytes)} bytes")
                    except WebSocketDisconnect:
                        logger.info(f"WebSocket 连接已断开，停止发送 (chunk_id={chunk_id})")
                        break
                    except Exception as send_error:
                        logger.error(f"发送音频块失败: {send_error}")
                        break
                
                # 发送完成信号
                try:
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await websocket.send_json({
                            "type": "complete",
                            "chunk_id": chunk_id
                        })
                        logger.info(f"WebSocket 合成完成 (chunk_id={chunk_id})")
                    else:
                        logger.info(f"WebSocket 已断开，跳过发送完成信号 (chunk_id={chunk_id})")
                except WebSocketDisconnect:
                    logger.info(f"WebSocket 连接已断开，无法发送完成信号 (chunk_id={chunk_id})")
                    break  # 退出主循环
                except Exception as send_error:
                    error_msg = str(send_error)
                    logger.warning(f"发送完成信号失败: {error_msg}")
                    # 如果是连接相关错误，退出主循环
                    if "close message" in error_msg or "not connected" in error_msg.lower():
                        logger.info(f"检测到连接已关闭，退出主循环")
                        break
                
            except Exception as e:
                logger.error(f"WebSocket 合成失败: {e}")
                import traceback
                traceback.print_exc()
                
                # 只在连接打开时发送错误信息
                if websocket.client_state == WebSocketState.CONNECTED:
                    try:
                        await websocket.send_json({
                            "type": "error",
                            "chunk_id": chunk_id,
                            "data": f"合成失败: {str(e)}"
                        })
                    except WebSocketDisconnect:
                        logger.info(f"发送错误消息时连接已断开")
                        break
                    except Exception as error_send_error:
                        error_msg = str(error_send_error)
                        logger.warning(f"发送错误消息失败: {error_msg}")
                        if "close message" in error_msg or "not connected" in error_msg.lower():
                            logger.info(f"检测到连接已关闭，退出主循环")
                            break
                else:
                    logger.info(f"WebSocket 已断开，跳过发送错误消息 (chunk_id={chunk_id})")
    
    except WebSocketDisconnect:
        logger.info("WebSocket 客户端已断开连接")
    except Exception as e:
        logger.error(f"WebSocket 处理异常: {e}")
        import traceback
        traceback.print_exc()
        # 只在连接打开时才尝试关闭
        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.close(code=1011, reason=str(e))
            except Exception as close_error:
                logger.error(f"关闭 WebSocket 失败: {close_error}")
