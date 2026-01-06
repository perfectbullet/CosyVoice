"""
WebSocket TTS合成测试脚本
用于测试 ws://192.168.8.230:50002/streaming/ws 接口
"""
import asyncio
import json
import base64
import os
import struct
import time
import websockets

# 配置
WS_URL = "ws://192.168.8.230:50002/streaming/ws"
SPEAKER_ID = "胡桃"  # 请替换为你的说话人ID

# 多个文本片段
TEXT_CHUNKS = [
    {"text": "收到好友从远方寄来的生日礼物，", "chunk_id": 1},
    {"text": "那份意外的惊喜与深深的祝福", "chunk_id": 2},
    {"text": "让我心中充满了甜蜜的快乐，", "chunk_id": 3},
    {"text": "笑容如花儿般绽放。", "chunk_id": 4},
]


def add_wav_header(pcm_data: bytes, sample_rate: int = 16000, num_channels: int = 1, sample_width: int = 2) -> bytes:
    """为原始 PCM 数据添加 WAV 文件头"""
    # num_frames = len(pcm_data) // (num_channels * sample_width)
    byte_rate = sample_rate * num_channels * sample_width
    block_align = num_channels * sample_width
    
    wav_header = b'RIFF'
    wav_header += struct.pack('<I', 36 + len(pcm_data))
    wav_header += b'WAVE'
    
    wav_header += b'fmt '
    wav_header += struct.pack('<I', 16)
    wav_header += struct.pack('<H', 1)
    wav_header += struct.pack('<H', num_channels)
    wav_header += struct.pack('<I', sample_rate)
    wav_header += struct.pack('<I', byte_rate)
    wav_header += struct.pack('<H', block_align)
    wav_header += struct.pack('<H', sample_width * 8)
    
    wav_header += b'data'
    wav_header += struct.pack('<I', len(pcm_data))
    wav_header += pcm_data
    
    return wav_header


async def test_websocket_tts():
    """测试 WebSocket TTS 合成"""
    print("=" * 60)
    print("WebSocket TTS合成测试")
    print("=" * 60)
    print(f"连接地址: {WS_URL}")
    print(f"说话人: {SPEAKER_ID}")
    print()
    
    total_start_time = time.time()
    
    try:
        async with websockets.connect(WS_URL) as websocket:
            print(f"✓ WebSocket 已连接")
            print()
            
            # 处理多个文本片段
            for chunk_info in TEXT_CHUNKS:
                chunk_text = chunk_info["text"]
                chunk_id = chunk_info["chunk_id"]
                
                print(f"[发送] Chunk #{chunk_id}: {chunk_text}")
                request_start_time = time.time()
                
                # 构建请求
                request = {
                    "action": "synthesize",
                    "text": chunk_text,
                    "spk_id": SPEAKER_ID,
                    "chunk_id": chunk_id
                }
                
                # 发送请求
                await websocket.send(json.dumps(request))
                print("  请求已发送")
                
                # 接收响应
                audio_chunks = []
                chunk_count = 0
                total_bytes = 0
                first_chunk_time = None
                
                while True:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=30)
                        response = json.loads(message)
                        
                        if response["type"] == "audio":
                            # 记录首块时间
                            if first_chunk_time is None:
                                first_chunk_time = time.time()
                                ttfb = (first_chunk_time - request_start_time) * 1000
                                print(f"  首字节延迟: {ttfb:.2f}ms")
                            
                            # 解码音频数据
                            audio_bytes = base64.b64decode(response["data"])
                            audio_chunks.append(audio_bytes)
                            chunk_count += 1
                            total_bytes += len(audio_bytes)
                            
                            if chunk_count % 3 == 0:
                                print(f"  已接收 {chunk_count} 块，共 {total_bytes:,} 字节")
                        
                        elif response["type"] == "complete":
                            receive_end_time = time.time()
                            receive_duration = (receive_end_time - request_start_time) * 1000
                            
                            # 合并音频
                            complete_audio = b''.join(audio_chunks)
                            
                            # 保存为 WAV 文件
                            output_file = f"ws_output_chunk_{chunk_id}.wav"
                            audio_with_header = add_wav_header(complete_audio, sample_rate=16000)
                            
                            with open(output_file, 'wb') as f:
                                f.write(audio_with_header)
                            
                            file_size = os.path.getsize(output_file)
                            audio_duration = (len(complete_audio) / (16000 * 2)) if complete_audio else 0
                            
                            print("  ✓ 完成")
                            print(f"    块数: {chunk_count}")
                            print(f"    大小: {file_size:,} 字节")
                            print(f"    耗时: {receive_duration:.2f}ms")
                            print(f"    音频时长: {audio_duration:.2f}s")
                            if audio_duration > 0:
                                rtf = receive_duration / (audio_duration * 1000)
                                print(f"    RTF: {rtf:.2f}x")
                            print(f"    文件: {output_file}")
                            print()
                            break
                        
                        elif response["type"] == "error":
                            print(f"  ✗ 错误: {response.get('data', 'Unknown error')}")
                            break
                    
                    except asyncio.TimeoutError:
                        print("  ✗ 接收超时")
                        break
            
            print("✓ 所有文本合成完成")
            print()
    
    except Exception as e:
        print(f"✗ 连接失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 统计总耗时
    total_end_time = time.time()
    total_duration = (total_end_time - total_start_time) * 1000
    
    print(f"{'=' * 60}")
    print(f"总耗时: {total_duration:.2f}ms")
    print(f"{'=' * 60}")
    
    return True


async def main():
    print("\n" + "=" * 60)
    print("CosyVoice WebSocket TTS 测试")
    print("=" * 60 + "\n")
    
    success = await test_websocket_tts()
    
    return 0 if success else 1


if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
