"""WebSocket 流式TTS合成接口"""
import json
import logging
import base64
import asyncio
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
from pydantic import BaseModel

from tts_service.database import db
from tts_service.tts_engine import tts_engine
from tts_service.cache import audio_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/streaming", tags=["websocket"])


class WebSocketSynthesisRequest(BaseModel):
    """WebSocket 合成请求"""
    action: str  # "synthesize"
    text: str
    spk_id: str
    chunk_id: Optional[int] = None  # 可选，用于标识不同文本片段


async def _send_audio_stream(websocket: WebSocket, text: str, spk_id: str, chunk_id: Optional[int]):
    """
    真流式音频发送：支持缓存

    1. 先检查缓存，命中则直接返回
    2. 未命中则执行合成
    3. 合成完成后存储到缓存
    """
    # 1. 尝试从缓存获取
    cached_chunks = await audio_cache.get(spk_id, text)
    if cached_chunks:
        logger.info(f"使用缓存音频: chunk_id={chunk_id}, spk_id={spk_id}")
        for chunk_msg in cached_chunks:
            await websocket.send_json(chunk_msg)
        return

    # 2. 缓存未命中，执行合成
    import torch
    import torchaudio

    # 创建重采样器：从24000Hz重采样到16000Hz
    resampler = torchaudio.transforms.Resample(
        orig_freq=tts_engine.sample_rate,
        new_freq=tts_engine.output_sample_rate
    )

    chunks_to_cache = []
    first_chunk_sent = False
    chunk_index = 0

    try:
        # 直接迭代生成器，每个chunk立即发送
        for chunk in tts_engine.model.inference_zero_shot(
            text,
            '',
            '',
            zero_shot_spk_id=spk_id,
            stream=True
        ):
            # 检查连接状态
            if websocket.client_state != WebSocketState.CONNECTED:
                logger.info(f"WebSocket 连接已断开，停止生成 (chunk_id={chunk_id})")
                break

            audio_data = chunk.get('tts_speech')
            if audio_data is not None:
                # 重采样到16000Hz
                if isinstance(audio_data, torch.Tensor):
                    audio_resampled = resampler(audio_data)
                else:
                    audio_resampled = audio_data

                audio_bytes = tts_engine._convert_to_pcm_bytes(audio_resampled)
                if audio_bytes and len(audio_bytes) > 0:
                    # 编码为 base64
                    audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')

                    chunk_msg = {
                        "type": "audio",
                        "chunk_id": chunk_id,
                        "data": audio_b64,
                        "done": False
                    }
                    chunks_to_cache.append(chunk_msg)

                    await websocket.send_json(chunk_msg)

                    if not first_chunk_sent:
                        logger.info(f"首帧已发送: chunk_id={chunk_id}, spk_id={spk_id}")
                        first_chunk_sent = True

                    chunk_index += 1
                    logger.debug(f"发送音频块 {chunk_index} (chunk_id={chunk_id}): {len(audio_bytes)} bytes")

    except WebSocketDisconnect:
        logger.info(f"WebSocket 连接已断开 (chunk_id={chunk_id})")
        raise
    except Exception as e:
        logger.error(f"音频生成或发送失败: {e}")
        raise

    # 3. 存储到缓存
    if chunks_to_cache:
        await audio_cache.set(spk_id, text, chunks_to_cache)


@router.on_event("startup")
async def startup_event():
    """服务启动时连接缓存"""
    await audio_cache.connect()


@router.on_event("shutdown")
async def shutdown_event():
    """服务关闭时断开缓存"""
    await audio_cache.close()


@router.websocket("/ws")
async def websocket_synthesize(websocket: WebSocket):
    """
    WebSocket 端点：流式TTS合成（真流式实现）

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

            # 执行合成（真流式）
            try:
                logger.info(f"WebSocket 合成请求: chunk_id={chunk_id}, spk_id={spk_id}, text_length={len(text)}")

                # 使用真流式发送：每个chunk生成后立即发送
                await _send_audio_stream(websocket, text, spk_id, chunk_id)

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

            except WebSocketDisconnect:
                logger.info(f"WebSocket 连接在合成过程中断开 (chunk_id={chunk_id})")
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
