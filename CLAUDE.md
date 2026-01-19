# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CosyVoice is a multilingual Text-to-Speech (TTS) system supporting Chinese, English, Japanese, Korean, and Chinese dialects. The project contains **two major model versions**:

- **CosyVoice 1.0** (300M): Uses TransformerLM with flow matching decoder
- **CosyVoice 2.0** (0.5B): Uses Qwen2-based LLM with causal masked diffusion, achieves 150ms latency

**Recommended**: Always use `CosyVoice2-0.5B` for better performance.

## Essential Setup

### Submodule Dependency
**ALWAYS** add Matcha-TTS to Python path before importing CosyVoice:
```python
import sys
sys.path.append('third_party/Matcha-TTS')
```

If submodule is missing: `git submodule update --init --recursive`

### Environment Setup
```bash
conda create -n cosyvoice python=3.10
conda activate cosyvoice
pip install -r requirements.txt
```

### Model Download
```python
from modelscope import snapshot_download
snapshot_download('iic/CosyVoice2-0.5B', local_dir='pretrained_models/CosyVoice2-0.5B')
```

## Common Commands

### Run WebUI
```bash
python webui.py --port 50000 --model_dir pretrained_models/CosyVoice2-0.5B
```

### Run Production TTS Service (with Docker)
```bash
docker-compose up -d --build
```

### Run Training
```bash
python cosyvoice/bin/train.py \
    --train_engine deepspeed \
    --config examples/libritts/cosyvoice2/conf/cosyvoice2.yaml \
    --train_data train.parquet \
    --cv_data cv.parquet \
    --model_dir exp/cosyvoice2
```

### Test Streaming TTS
```bash
python tts_service/test_streaming.py
```

## Architecture Overview

### Model Version Detection
Models are distinguished by config file (`cosyvoice.yaml` vs `cosyvoice2.yaml`). Use the correct class:

```python
# CosyVoice2-0.5B (RECOMMENDED) - contains cosyvoice2.yaml
cosyvoice = CosyVoice2('pretrained_models/CosyVoice2-0.5B', load_jit=False, load_trt=False, load_vllm=False, fp16=False)

# CosyVoice-300M variants - contains cosyvoice.yaml
cosyvoice = CosyVoice('pretrained_models/CosyVoice-300M-SFT')
```

### Model Components (CosyVoice2)
- **llm**: Qwen2LM - Text to speech token prediction
- **flow**: CausalMaskedDiffWithXvec - Speech tokens to mel-spectrogram (streaming-capable)
- **hift**: HiFTGenerator - Mel to waveform (HiFi-GAN variant)

Streaming is controlled by `chunk_size: 25` tokens and `static_chunk_size` in encoder/decoder.

### Inference Modes

**CosyVoice 1.0 modes:**
1. `inference_sft(tts_text, spk_id)` - Pre-trained voices
2. `inference_zero_shot(tts_text, prompt_text, prompt_speech_16k)` - 3s voice cloning
3. `inference_cross_lingual(tts_text, prompt_speech_16k)` - Cross-lingual synthesis
4. `inference_instruct(tts_text, spk_id, instruct_text)` - Natural language control (Instruct model only)

**CosyVoice 2.0 modes:**
- Same as v1 except `inference_instruct2(tts_text, instruct_text, prompt_speech_16k)` for instruction mode
- All methods support `zero_shot_spk_id=''` for pre-registered speakers

**Important**: All inference methods are **generators** - iterate to get audio chunks:
```python
for i, result in enumerate(cosyvoice.inference_zero_shot(text, prompt_text, prompt_audio)):
    torchaudio.save(f'output_{i}.wav', result['tts_speech'], cosyvoice.sample_rate)
```

### Frontend Processing Pipeline (`cosyvoice/cli/frontend.py`)
1. **Text normalization**: Uses `ttsfrd` (if installed) or `wetext` fallback
2. **Tokenization**: Text -> token IDs via `self.tokenizer.encode()`
3. **Speaker embedding**: Audio -> 192-dim vector via `campplus.onnx`
4. **Speech tokenization**: Audio -> discrete tokens via `speech_tokenizer_v1/v2.onnx`

## TTS Service Architecture (`tts_service/`)

Production async FastAPI service with MongoDB task queuing:

### Entry Points
- `tts_service/main.py`: FastAPI app with lifespan-based model initialization
- `tts_service/tts_engine.py`: Async `TTSEngine` wrapper using `run_in_executor()` for non-blocking GPU ops
- `tts_service/task_worker.py`: Background worker polling MongoDB for pending tasks

### API Endpoints
- `POST /streaming/synthesize` - Start streaming synthesis, returns `stream_id`
- `GET /streaming/audio/{stream_id}` - SSE stream for audio chunks
- `POST /speakers/register` - Register new zero-shot speaker
- `POST /tasks/synthesize` - Queue async synthesis task
- WebSocket endpoint available for streaming TTS

### Configuration (`.env` file)
```env
MONGODB_URL=mongodb://admin:password@mongodb:27017/
MODEL_PATH=/opt/CosyVoice/pretrained_models/CosyVoice2-0.5B
AUDIO_OUTPUT_DIR=/opt/CosyVoice/data/audio_outputs
SPEAKER_AUDIO_DIR=/opt/CosyVoice/data/speaker_audios
HOST=0.0.0.0
PORT=50002
```

### Async Pattern
Model operations use `loop.run_in_executor()` to prevent blocking FastAPI event loop:
```python
self.model = await loop.run_in_executor(None, lambda: CosyVoice2(...))
```

## Training Configuration

Training uses HyperPyYAML format. Config files in `examples/*/conf/`:
- `examples/libritts/cosyvoice/conf/cosyvoice.yaml` - v1 model config
- `examples/libritts/cosyvoice2/conf/cosyvoice2.yaml` - v2 model config

Training engines: `torch_ddp` or `deepspeed`. DPO/GRPO training available via `--dpo` flag.

## Audio Handling Conventions

- Input audio: 16kHz mono (auto-resampled by `load_wav()`)
- Output audio: 22050Hz (v1) or 24000Hz (v2) - use `cosyvoice.sample_rate`
- Max prompt audio: 30 seconds (hard limit in `_extract_speech_token`)

## vLLM Acceleration (CosyVoice2 Only)

Requires `vllm==v0.9.0` + `torch==2.7.0`:
```python
from vllm import ModelRegistry
from cosyvoice.vllm.cosyvoice2 import CosyVoice2ForCausalLM
ModelRegistry.register_model("CosyVoice2ForCausalLM", CosyVoice2ForCausalLM)
cosyvoice = CosyVoice2('...', load_vllm=True)
```

## Repetition-Aware Sampling (RAS)

Enabled by default in CosyVoice2 for stable LLM inference (see `cosyvoice/utils/common.py`):
```yaml
sampling: !name:cosyvoice.utils.common.ras_sampling
    top_p: 0.8
    top_k: 25
    win_size: 10
    tau_r: 0.1
```

## Common Pitfalls

1. **Wrong model class**: Using `CosyVoice` for v2 models -> assertion error
2. **Missing Matcha-TTS**: Import fails without `sys.path.append('third_party/Matcha-TTS')`
3. **Instruct mode mismatch**: `inference_instruct()` only for `-Instruct` models; CosyVoice2 uses `inference_instruct2()`
4. **Audio length**: Prompt audio >30s causes assertion failure
5. **Stream vs batch**: Set `stream=True` for chunk-by-chunk output (real-time), `False` for full audio
6. **Generator not iterated**: Inference methods return generators; must iterate to get results

## Key Files Reference

| File | Purpose |
|------|---------|
| `cosyvoice/cli/cosyvoice.py` | Main API classes (CosyVoice, CosyVoice2) |
| `cosyvoice/cli/frontend.py` | Text/audio preprocessing pipeline |
| `cosyvoice/cli/model.py` | Model wrapper with kv-cache, TRT, JIT support |
| `tts_service/main.py` | FastAPI app entry point |
| `tts_service/tts_engine.py` | Async model inference wrapper |
| `tts_service/task_worker.py` | MongoDB task consumer |
| `cosyvoice/bin/train.py` | Training entry point |
