"""
流式TTS合成测试脚本
"""
import requests
import json
import base64
import sys
import os
import struct

# 配置
BASE_URL = "http://192.168.8.230:50002"
SPEAKER_ID = "胡桃"  # 请替换为你的说话人ID
TEST_TEXT = "你好，这是一个流式语音合成测试。今天天气真不错。请替换为你的说话人ID"

def text_generator():
    yield '收到好友从远方寄来的生日礼物，'
    yield '那份意外的惊喜与深深的祝福'
    yield '让我心中充满了甜蜜的快乐，'
    yield '笑容如花儿般绽放。'

def add_wav_header(pcm_data: bytes, sample_rate: int = 16000, num_channels: int = 1, sample_width: int = 2) -> bytes:
    """
    为原始 PCM 数据添加 WAV 文件头
    
    Args:
        pcm_data: 原始 PCM 字节数据
        sample_rate: 采样率（Hz），默认 16000
        num_channels: 声道数，默认 1（单声道）
        sample_width: 采样宽度（字节），默认 2（16bit）
    
    Returns:
        完整的 WAV 文件数据（包含 RIFF 头）
    """
    num_frames = len(pcm_data) // (num_channels * sample_width)
    byte_rate = sample_rate * num_channels * sample_width
    block_align = num_channels * sample_width
    
    # WAV 文件头结构
    wav_header = b'RIFF'
    wav_header += struct.pack('<I', 36 + len(pcm_data))  # 文件大小 - 8
    wav_header += b'WAVE'
    
    # fmt 子块
    wav_header += b'fmt '
    wav_header += struct.pack('<I', 16)  # fmt 块大小
    wav_header += struct.pack('<H', 1)   # 音频格式（1 = PCM）
    wav_header += struct.pack('<H', num_channels)
    wav_header += struct.pack('<I', sample_rate)
    wav_header += struct.pack('<I', byte_rate)
    wav_header += struct.pack('<H', block_align)
    wav_header += struct.pack('<H', sample_width * 8)  # 位深度
    
    # data 子块
    wav_header += b'data'
    wav_header += struct.pack('<I', len(pcm_data))
    wav_header += pcm_data
    
    return wav_header



def test_streaming_tts():
    """测试流式TTS合成"""
    print("=" * 60)
    print("流式TTS合成测试")
    print("=" * 60)
    
    # Step 1: 启动流式合成
    print(f"\n[1/3] 启动流式合成...")
    print(f"文本: {TEST_TEXT}")
    print(f"说话人: {SPEAKER_ID}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/streaming/synthesize",
            json={
                "text": TEST_TEXT,
                "spk_id": SPEAKER_ID
            },
            timeout=10
        )
        response.raise_for_status()
        
        result = response.json()
        stream_id = result["stream_id"]
        print(f"✓ 合成已启动")
        print(f"  Stream ID: {stream_id}")
        
    except requests.exceptions.RequestException as e:
        print(f"✗ 启动失败: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"  错误详情: {e.response.text}")
        return False
    
    # Step 2: 接收流式音频
    print(f"\n[2/3] 接收流式音频...")
    
    audio_chunks = []
    chunk_count = 0
    total_bytes = 0
    
    try:
        url = f"{BASE_URL}/streaming/audio/{stream_id}"
        
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            
            for line in r.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    
                    if line_str.startswith('data: '):
                        data = json.loads(line_str[6:])
                        
                        if data['type'] == 'audio_chunk':
                            # 解码 base64 音频数据
                            audio_bytes = base64.b64decode(data['data'])
                            audio_chunks.append(audio_bytes)
                            chunk_count += 1
                            total_bytes += len(audio_bytes)
                            
                            # 每收到5个块打印一次进度
                            if chunk_count % 5 == 0:
                                print(f"  已接收 {chunk_count} 个音频块，共 {total_bytes:,} 字节")
                        
                        elif data['type'] == 'complete':
                            print(f"✓ 流式传输完成")
                            print(f"  总块数: {chunk_count}")
                            print(f"  总大小: {total_bytes:,} 字节")
                            break
                        
                        elif data['type'] == 'error':
                            print(f"✗ 服务端错误: {data['data']}")
                            return False
        
    except requests.exceptions.RequestException as e:
        print(f"✗ 接收失败: {e}")
        return False
    
    # Step 3: 保存音频文件
    if audio_chunks:
        print(f"\n[3/3] 保存音频文件...")
        
        output_file = "test_streaming_output.wav"
        complete_audio = b''.join(audio_chunks)
        
        try:
            # 添加 WAV 文件头
            # 服务器发送的是 PCM 数据，采样率 16000Hz，单声道，16bit
            audio_with_header = add_wav_header(complete_audio, sample_rate=16000, num_channels=1, sample_width=2)
            
            with open(output_file, 'wb') as f:
                f.write(audio_with_header)
            
            file_size = os.path.getsize(output_file)
            print(f"✓ 音频已保存")
            print(f"  文件: {output_file}")
            print(f"  大小: {file_size:,} 字节")
            
        except Exception as e:
            print(f"✗ 保存失败: {e}")
            return False
    else:
        print(f"\n✗ 没有接收到音频数据")
        return False
    
    print(f"\n{'=' * 60}")
    print("测试完成！")
    print("=" * 60)
    return True


def check_service():
    """检查服务是否运行"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        response.raise_for_status()
        result = response.json()
        
        if result.get("model_loaded"):
            print("✓ 服务正常运行，模型已加载")
            return True
        else:
            print("✗ 服务运行中，但模型未加载")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"✗ 无法连接到服务: {e}")
        print(f"  请确保服务已启动: python tts_service/main.py")
        return False


def check_speaker_exists(spk_id: str):
    """检查说话人是否存在"""
    try:
        response = requests.get(f"{BASE_URL}/speakers/{spk_id}", timeout=5)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ 说话人存在: {spk_id}")
            print(f"  音频文件: {result.get('audio_filename')}")
            return True
        elif response.status_code == 404:
            print(f"✗ 说话人不存在: {spk_id}")
            print(f"  请先注册说话人: POST /speakers")
            return False
        else:
            print(f"✗ 查询失败: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"✗ 查询失败: {e}")
        return False


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("CosyVoice 流式TTS测试")
    print("=" * 60 + "\n")
    
    # 检查服务状态
    print("[前置检查] 检查服务状态...")
    if not check_service():
        sys.exit(1)
    
    print()
    
    # 检查说话人
    print("[前置检查] 检查说话人...")
    if not check_speaker_exists(SPEAKER_ID):
        print(f"\n提示: 请修改脚本中的 SPEAKER_ID 变量为你的说话人ID")
        sys.exit(1)
    
    print()
    
    # 运行测试
    success = test_streaming_tts()
    
    sys.exit(0 if success else 1)
