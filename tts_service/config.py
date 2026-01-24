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

    # ASR 服务配置
    ASR_SERVICE_URL: str = os.getenv("ASR_SERVICE_URL", "http://192.168.8.230:30097")
    ASR_HOST: str = os.getenv("ASR_HOST", "192.168.8.230")
    ASR_PORT: str = os.getenv("ASR_PORT", "30097")
    ASR_IS_SSL: str = os.getenv("ASR_IS_SSL", "true")
    ASR_MODE: str = os.getenv("ASR_MODE", "2pass")

    # Redis 缓存配置
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    AUDIO_CACHE_TTL: int = int(os.getenv("AUDIO_CACHE_TTL", "604800"))  # 7天（秒）
    ENABLE_AUDIO_CACHE: bool = os.getenv("ENABLE_AUDIO_CACHE", "true").lower() == "true"

    class Config:
        env_file = ".env"


settings = Settings()