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
        self.sample_rate: Optional[int] = None

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