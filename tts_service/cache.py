"""音频缓存管理模块"""
import json
import hashlib
import logging
from typing import List, Optional
import redis.asyncio as aioredis

from tts_service.config import settings

logger = logging.getLogger(__name__)


class AudioCache:
    """音频缓存管理类

    使用 Redis 缓存已合成的音频，键为 (spk_id, text) 组合。
    缓存命中时直接返回音频数据，无需重新合成。
    """

    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None
        self._enabled = settings.ENABLE_AUDIO_CACHE

    async def connect(self):
        """连接 Redis"""
        if not self._enabled:
            logger.info("音频缓存已禁用")
            return
        try:
            self._redis = await aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=False
            )
            # 测试连接
            await self._redis.ping()
            logger.info(f"音频缓存 Redis 已连接: {settings.REDIS_URL}")
        except Exception as e:
            logger.error(f"音频缓存 Redis 连接失败: {e}")
            self._redis = None

    async def close(self):
        """关闭 Redis 连接"""
        if self._redis:
            await self._redis.close()
            logger.info("音频缓存 Redis 已关闭")

    @staticmethod
    def generate_key(spk_id: str, text: str) -> str:
        """生成缓存键

        Args:
            spk_id: 说话人ID
            text: 文本内容

        Returns:
            缓存键，格式为 tts:audio:{spk_id}:{text_hash}
        """
        normalized_text = text.strip()
        text_hash = hashlib.sha256(normalized_text.encode()).hexdigest()[:16]
        return f"tts:audio:{spk_id}:{text_hash}"

    async def get(self, spk_id: str, text: str) -> Optional[List[dict]]:
        """获取缓存的音频块

        Args:
            spk_id: 说话人ID
            text: 文本内容

        Returns:
            缓存的音频块列表，未命中返回 None
        """
        if not self._enabled or not self._redis:
            return None

        key = self.generate_key(spk_id, text)
        try:
            cached = await self._redis.get(key)
            if cached:
                logger.info(f"音频缓存命中: spk_id={spk_id}, text={text[:20]}...")
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"获取缓存失败: {e}")
        return None

    async def set(self, spk_id: str, text: str, chunks: List[dict]) -> None:
        """缓存音频块

        Args:
            spk_id: 说话人ID
            text: 文本内容
            chunks: 音频块列表
        """
        if not self._enabled or not self._redis:
            return

        if not chunks:
            return

        key = self.generate_key(spk_id, text)
        try:
            data = json.dumps(chunks)
            await self._redis.setex(
                key,
                settings.AUDIO_CACHE_TTL,
                data
            )
            logger.info(f"音频已缓存: spk_id={spk_id}, chunks={len(chunks)}, text={text[:20]}...")
        except Exception as e:
            logger.warning(f"缓存音频失败: {e}")

    async def delete_by_speaker(self, spk_id: str) -> int:
        """删除指定说话人的所有缓存

        Args:
            spk_id: 说话人ID

        Returns:
            删除的键数量
        """
        if not self._enabled or not self._redis:
            return 0

        pattern = f"tts:audio:{spk_id}:*"
        keys = []
        try:
            async for key in self._redis.scan_iter(match=pattern):
                keys.append(key)
            if keys:
                return await self._redis.delete(*keys)
        except Exception as e:
            logger.warning(f"删除缓存失败: {e}")
        return 0

    async def clear_all(self) -> bool:
        """清除所有音频缓存

        Returns:
            是否成功
        """
        if not self._enabled or not self._redis:
            return False

        try:
            # 只删除 tts:audio: 开头的键
            pattern = "tts:audio:*"
            keys = []
            async for key in self._redis.scan_iter(match=pattern):
                keys.append(key)
            if keys:
                await self._redis.delete(*keys)
                logger.info(f"已清除 {len(keys)} 条音频缓存")
                return True
            return False
        except Exception as e:
            logger.warning(f"清除缓存失败: {e}")
            return False

    async def get_stats(self) -> dict:
        """获取缓存统计信息

        Returns:
            统计信息字典
        """
        if not self._enabled or not self._redis:
            return {"enabled": False}

        try:
            # 统计音频缓存键数量
            pattern = "tts:audio:*"
            count = 0
            async for _ in self._redis.scan_iter(match=pattern):
                count += 1

            return {
                "enabled": True,
                "audio_cache_count": count,
                "ttl_seconds": settings.AUDIO_CACHE_TTL
            }
        except Exception as e:
            logger.warning(f"获取缓存统计失败: {e}")
            return {"enabled": True, "error": str(e)}


# 全局缓存实例
audio_cache = AudioCache()
