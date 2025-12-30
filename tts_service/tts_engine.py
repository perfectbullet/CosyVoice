import sys
import os
import logging
import asyncio
from typing import Optional
import torchaudio
import torch
import numpy as np

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
        self.sample_rate: Optional[int] = None
        self.output_sample_rate: int = 16000  # 输出采样率（16000Hz）
        self._stream_queues: dict[str, asyncio.Queue] = {}  # 流式合成队列（异步）

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
                try:
                    # 收集所有生成的语音片段
                    audio_segments = []

                    for i, j in enumerate(self.model.inference_zero_shot(
                            text,
                            '',
                            '',
                            zero_shot_spk_id=spk_id,
                            stream=False
                    )):
                        logger.info(f"生成第 {i + 1} 段语音")
                        audio_segments.append(j['tts_speech'])

                    # 如果没有生成任何语音
                    if not audio_segments:
                        logger.error("未生成任何语音片段")
                        return False

                    # 拼接多段语音
                    import torch
                    if len(audio_segments) == 1:
                        complete_audio = audio_segments[0]
                    else:
                        complete_audio = torch.cat(audio_segments, dim=1)
                        logger.info(f"已拼接 {len(audio_segments)} 段语音，总shape: {complete_audio.shape}")

                    # 确保输出目录存在
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)

                    # 保存完整音频
                    torchaudio.save(output_path, complete_audio, self.sample_rate)
                    logger.info(f"音频已保存: {output_path}")

                    return True

                except Exception as e:
                    logger.error(f"推理或保存过程出错: {e}")
                    import traceback
                    traceback.print_exc()
                    return False

            # 在线程池中执行整个推理和保存过程
            success = await loop.run_in_executor(None, do_inference)

            return success

        except Exception as e:
            logger.error(f"合成失败: {e}")
            import traceback
            traceback.print_exc()
            return False


    def create_stream(self, stream_id: str) -> asyncio.Queue:
        """为每个流式请求创建独立的异步队列"""
        queue = asyncio.Queue(maxsize=100)  # 限制队列大小防止内存溢出
        self._stream_queues[stream_id] = queue
        logger.info(f"Created async stream queue for {stream_id}")
        return queue

    def remove_stream(self, stream_id: str):
        """清理流队列"""
        if stream_id in self._stream_queues:
            del self._stream_queues[stream_id]
            logger.info(f"Removed stream queue for {stream_id}")

    async def synthesize_streaming(
        self, 
        text: str, 
        spk_id: str, 
        stream_id: str
    ) -> None:
        """
        流式合成语音（异步版本）
        
        Args:
            text: 要合成的文本
            spk_id: 说话人ID
            stream_id: 流式请求的唯一标识
        """
        async def _synthesize_worker():
            try:
                logger.info(f"Starting streaming synthesis for {stream_id}: spk_id={spk_id}, text_length={len(text)}")
                queue = self._stream_queues.get(stream_id)
                
                if queue is None:
                    logger.error(f"Stream {stream_id} not found")
                    return
                
                # 在线程池中执行同步的模型推理
                loop = asyncio.get_event_loop()
                
                def _model_inference():
                    """同步推理函数（在线程池中执行）"""
                    results = []
                    # 创建重采样器：从24000Hz重采样到16000Hz
                    resampler = torchaudio.transforms.Resample(
                        orig_freq=self.sample_rate,
                        new_freq=self.output_sample_rate
                    )
                    
                    for i, chunk in enumerate(self.model.inference_zero_shot(
                        text,
                        '',
                        '',
                        zero_shot_spk_id=spk_id,
                        stream=True  # 开启流式模式
                    )):
                        audio_data = chunk.get('tts_speech')
                        if audio_data is not None:
                            # 重采样到16000Hz
                            if isinstance(audio_data, torch.Tensor):
                                audio_resampled = resampler(audio_data)
                            else:
                                audio_resampled = audio_data
                            
                            audio_bytes = self._convert_to_pcm_bytes(audio_resampled)
                            if audio_bytes and len(audio_bytes) > 0:
                                results.append((i, audio_bytes))
                    return results
                
                # 在线程池中执行推理
                results = await loop.run_in_executor(None, _model_inference)
                
                # 异步推送结果到队列
                for i, audio_bytes in results:
                    if stream_id not in self._stream_queues:
                        logger.info(f"Stream {stream_id} was cancelled")
                        break
                    
                    logger.info(f"Generated audio chunk {i}: {len(audio_bytes)} bytes")
                    await queue.put({
                        "type": "audio_chunk",
                        "data": audio_bytes,
                    })
                
                # 发送完成信号
                logger.info(f"Streaming synthesis completed for {stream_id}")
                await queue.put({
                    "type": "complete",
                    "data": None,
                })
                
            except Exception as e:
                logger.error(f"Error in streaming synthesis worker: {e}")
                import traceback
                traceback.print_exc()
                if stream_id in self._stream_queues:
                    queue = self._stream_queues[stream_id]
                    await queue.put({
                        "type": "error",
                        "data": str(e),
                    })
        
        # 创建异步任务（而非线程）
        asyncio.create_task(_synthesize_worker())

    def _convert_to_pcm_bytes(self, audio_data) -> bytes:
        """转换音频数据为PCM字节"""
        try:
            if isinstance(audio_data, bytes):
                return audio_data
            
            if isinstance(audio_data, torch.Tensor):
                # 转换为numpy数组
                audio_np = audio_data.cpu().numpy()
                # 确保是int16格式
                if audio_np.dtype != np.int16:
                    audio_np = (audio_np * 32767).astype(np.int16)
                return audio_np.tobytes()
            
            if isinstance(audio_data, np.ndarray):
                if audio_data.dtype != np.int16:
                    audio_data = (audio_data * 32767).astype(np.int16)
                return audio_data.tobytes()
            
            logger.warning(f"Unknown audio data type: {type(audio_data)}")
            return b""
        except Exception as e:
            logger.error(f"Error converting audio: {e}")
            return b""


tts_engine = TTSEngine()
