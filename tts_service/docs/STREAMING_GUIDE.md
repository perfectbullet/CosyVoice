# CosyVoice TTS 流式接口使用指南

## 项目结构重构说明

代码已重构为模块化的路由结构：

```
tts_service/
├── main.py              # FastAPI 应用入口（简化版）
├── config.py            # 配置管理
├── database.py          # 数据库操作
├── models.py            # 数据模型
├── tts_engine.py        # TTS 引擎封装（增加流式支持）
├── task_worker.py       # 异步任务处理
└── routers/             # 路由模块（新增）
    ├── __init__.py
    ├── tasks.py         # TTS 任务相关端点
    ├── speakers.py      # 说话人管理端点
    └── streaming.py     # 流式合成端点（新增）
```

## 流式接口使用方法

### 1. 启动流式合成

**端点**: `POST /streaming/synthesize`

**请求体**:
```json
{
  "text": "你好，欢迎使用流式语音合成服务",
  "spk_id": "speaker_001"
}
```

**响应**:
```json
{
  "stream_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "合成已启动"
}
```

### 2. 获取流式音频

**端点**: `GET /streaming/audio/{stream_id}`

这是一个 **Server-Sent Events (SSE)** 端点，会持续推送音频数据。

#### 使用 curl 测试

```bash
# 1. 先启动合成
curl -X POST "http://localhost:50002/streaming/synthesize" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "你好，这是一个流式合成测试",
    "spk_id": "your_speaker_id"
  }'

# 获取返回的 stream_id，然后：

# 2. 接收流式音频
curl -N "http://localhost:50002/streaming/audio/{stream_id}"
```

#### 使用 Python 客户端

```python
import requests
import json
import base64
import wave
import io

# 1. 启动合成
response = requests.post(
    "http://localhost:50002/streaming/synthesize",
    json={
        "text": "你好，这是流式合成测试",
        "spk_id": "your_speaker_id"
    }
)
stream_id = response.json()["stream_id"]
print(f"Stream ID: {stream_id}")

# 2. 接收流式音频
audio_chunks = []
url = f"http://localhost:50002/streaming/audio/{stream_id}"

with requests.get(url, stream=True) as r:
    for line in r.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith('data: '):
                data = json.loads(line[6:])
                
                if data['type'] == 'audio_chunk':
                    # 解码 base64 音频数据
                    audio_bytes = base64.b64decode(data['data'])
                    audio_chunks.append(audio_bytes)
                    print(f"Received chunk: {len(audio_bytes)} bytes")
                
                elif data['type'] == 'complete':
                    print("Stream completed")
                    break
                
                elif data['type'] == 'error':
                    print(f"Error: {data['data']}")
                    break

# 3. 合并并保存音频
if audio_chunks:
    complete_audio = b''.join(audio_chunks)
    with open('output_streaming.wav', 'wb') as f:
        f.write(complete_audio)
    print(f"Saved {len(complete_audio)} bytes to output_streaming.wav")
```

#### 使用 JavaScript (浏览器)

```javascript
async function streamTTS() {
  // 1. 启动合成
  const response = await fetch('http://localhost:50002/streaming/synthesize', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      text: '你好，这是流式合成测试',
      spk_id: 'your_speaker_id'
    })
  });
  
  const { stream_id } = await response.json();
  console.log('Stream ID:', stream_id);
  
  // 2. 使用 EventSource 接收流式数据
  const eventSource = new EventSource(
    `http://localhost:50002/streaming/audio/${stream_id}`
  );
  
  const audioChunks = [];
  
  eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    if (data.type === 'audio_chunk') {
      // 解码 base64 音频
      const audioData = atob(data.data);
      const audioArray = new Uint8Array(audioData.length);
      for (let i = 0; i < audioData.length; i++) {
        audioArray[i] = audioData.charCodeAt(i);
      }
      audioChunks.push(audioArray);
      console.log('Received chunk:', audioArray.length, 'bytes');
    } 
    else if (data.type === 'complete') {
      console.log('Stream completed');
      eventSource.close();
      
      // 合并音频并播放
      const completeAudio = new Blob(audioChunks, { type: 'audio/wav' });
      const audioUrl = URL.createObjectURL(completeAudio);
      const audio = new Audio(audioUrl);
      audio.play();
    } 
    else if (data.type === 'error') {
      console.error('Error:', data.data);
      eventSource.close();
    }
  };
  
  eventSource.onerror = (error) => {
    console.error('EventSource error:', error);
    eventSource.close();
  };
}

streamTTS();
```

## API 端点总览

### 任务相关 (`/tasks`)
- `POST /tasks` - 创建TTS任务（异步）
- `GET /tasks/{task_id}` - 查询任务详情
- `GET /tasks` - 获取任务列表
- `GET /tasks/detail/list` - 获取任务详细列表
- `GET /tasks/{task_id}/audio` - 下载完整音频文件

### 说话人管理 (`/speakers`)
- `POST /speakers` - 注册说话人（上传音频）
- `GET /speakers/task/{task_id}` - 查询说话人注册任务状态
- `GET /speakers/{spk_id}` - 查询说话人信息
- `GET /speakers` - 获取说话人列表

### 流式合成 (`/streaming`) **[新增]**
- `POST /streaming/synthesize` - 启动流式合成
- `GET /streaming/audio/{stream_id}` - 获取流式音频（SSE）

### 系统信息
- `GET /` - 服务信息
- `GET /health` - 健康检查

## 流式合成 vs 异步任务

| 特性 | 流式合成 | 异步任务 |
|------|----------|----------|
| 响应速度 | 实时流式返回 | 任务完成后下载 |
| 使用场景 | 实时对话、低延迟需求 | 批量处理、离线合成 |
| 音频存储 | 不存储 | 持久化存储 |
| 接口类型 | SSE (Server-Sent Events) | REST API |
| 任务追踪 | 无需数据库 | 基于 MongoDB |

## 技术实现细节

### 流式引擎 (tts_engine.py)

```python
# 流式合成方法
async def synthesize_streaming(
    self, 
    text: str, 
    spk_id: str, 
    stream_id: str
) -> None:
    """
    流式合成语音，通过队列推送音频块
    - 使用 CosyVoice2 的 stream=True 模式
    - 在后台线程中运行推理
    - 通过 Queue 传递音频数据
    """
```

### 队列管理

- 每个流式请求创建独立的 `Queue`
- 音频块通过队列传递到 SSE 端点
- 请求完成或客户端断开时自动清理队列

### 音频格式

- 输出格式：PCM (int16)
- 采样率：24000Hz (CosyVoice2)
- 通过 base64 编码传输

## 注意事项

1. **说话人必须提前注册**：流式合成要求 `spk_id` 已在系统中注册
2. **网络连接**：SSE 需要长连接，确保网络稳定
3. **浏览器兼容性**：所有现代浏览器都支持 EventSource API
4. **并发限制**：每个 stream_id 只能被一个客户端消费
5. **清理机制**：客户端断开连接时，服务端会自动清理资源

## 性能优化

- 使用异步 I/O 避免阻塞
- 后台线程处理模型推理
- 队列缓冲机制平衡生产和消费速度
- 自动清理过期的流队列

## 错误处理

所有错误会通过 SSE 推送：
```json
{
  "type": "error",
  "data": "错误信息"
}
```

常见错误：
- 说话人不存在
- 文本为空
- 模型推理失败
- 网络连接中断
