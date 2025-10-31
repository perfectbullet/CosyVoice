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
    PORT: int = 50002

    # CosyVoice 根目录
    COSYVOICE_ROOT: str = "/opt/CosyVoice"

    class Config:
        env_file = ".env"


settings = Settings()