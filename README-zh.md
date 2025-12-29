
[![SVG Banners](https://svg-banners.vercel.app/api?type=origin&text1=CosyVoice🤠&text2=Text-to-Speech%20💖%20Large%20Language%20Model&width=800&height=210)](https://github.com/Akshay090/svg-banners)

## 👉🏻 CosyVoice 👈🏻

**CosyVoice 3.0**: [演示](https://funaudiollm.github.io/cosyvoice3/); [论文](https://arxiv.org/abs/2505.17589); [CV3-Eval](https://github.com/FunAudioLLM/CV3-Eval)

**CosyVoice 2.0**: [演示](https://funaudiollm.github.io/cosyvoice2/); [论文](https://arxiv.org/abs/2412.10117); [魔搭社区](https://www.modelscope.cn/studios/iic/CosyVoice2-0.5B); [HuggingFace](https://huggingface.co/spaces/FunAudioLLM/CosyVoice2-0.5B)

**CosyVoice 1.0**: [演示](https://fun-audio-llm.github.io); [论文](https://funaudiollm.github.io/pdf/CosyVoice_v1.pdf); [魔搭社区](https://www.modelscope.cn/studios/iic/CosyVoice-300M)

## 亮点🔥

**CosyVoice 2.0** 已发布！相较于 1.0 版本，新版本提供了更准确、更稳定、更快、更好的语音生成能力。

### 多语言支持
- **支持的语言**: 中文、英文、日文、韩文、中国方言（粤语、四川话、上海话、天津话、武汉话等）
- **跨语言与混合语言**：支持跨语言和代码切换场景下的零样本语音克隆。

### 超低延迟
- **双向流式支持**: CosyVoice 2.0 集成了离线和流式建模技术。
- **快速首包合成**: 在保持高质量音频输出的同时，实现了低至 150ms 的延迟。

### 高准确率
- **改进的发音**: 与 CosyVoice 1.0 相比，将发音错误率降低了 30% 至 50%。
- **基准测试成果**: 在 Seed-TTS 评估集的困难测试集上取得了最低的字符错误率。

### 强稳定性
- **音色一致性**: 确保零样本和跨语言语音合成的可靠语音一致性。
- **跨语言合成**: 相比 1.0 版本有显著提升。

### 自然体验
- **增强的韵律和音质**: 改进了合成音频的对齐，将 MOS 评估分数从 5.4 提高到 5.53。
- **情感和方言灵活性**: 现在支持更精细的情感控制和口音调整。

## 路线图

- [x] 2025/08
    - [x] 感谢 NVIDIA 张悦凯的贡献，增加了 triton trtllm 运行时支持和 cosyvoice2 组训练支持

- [x] 2025/07
    - [x] 发布 cosyvoice 3.0 评估集

- [x] 2025/05
    - [x] 增加 cosyvoice 2.0 vllm 支持

- [x] 2024/12
    - [x] 25Hz cosyvoice 2.0 发布

- [x] 2024/09
    - [x] 25Hz cosyvoice 基础模型
    - [x] 25Hz cosyvoice 语音转换模型

- [x] 2024/08
    - [x] 用于 LLM 稳定性的重复感知采样 (RAS) 推理
    - [x] 流式推理模式支持，包括用于 RTF 优化的 kv 缓存和 sdpa

- [x] 2024/07
    - [x] 流匹配训练支持
    - [x] 当 ttsfrd 不可用时的 WeTextProcessing 支持
    - [x] Fastapi 服务器和客户端

## 安装

### 克隆和安装

- 克隆仓库
    ``` sh
    git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git
    # 如果由于网络故障导致子模块克隆失败，请运行以下命令直到成功
    cd CosyVoice
    git submodule update --init --recursive
    ```

- 安装 Conda: 请参见 https://docs.conda.io/en/latest/miniconda.html
- 创建 Conda 环境:
    ``` sh
    conda create -n cosyvoice -y python=3.10
    conda activate cosyvoice
    pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host=mirrors.aliyun.com

    # 如果遇到 sox 兼容性问题
    # ubuntu
    sudo apt-get install sox libsox-dev
    # centos
    sudo yum install sox sox-devel
    ```

### 模型下载

我们强烈建议您下载我们预训练的 `CosyVoice2-0.5B` `CosyVoice-300M` `CosyVoice-300M-SFT` `CosyVoice-300M-Instruct` 模型和 `CosyVoice-ttsfrd` 资源。

``` python
# SDK模型下载
from modelscope import snapshot_download
snapshot_download('iic/CosyVoice2-0.5B', local_dir='pretrained_models/CosyVoice2-0.5B')
snapshot_download('iic/CosyVoice-300M', local_dir='pretrained_models/CosyVoice-300M')
snapshot_download('iic/CosyVoice-300M-SFT', local_dir='pretrained_models/CosyVoice-300M-SFT')
snapshot_download('iic/CosyVoice-300M-Instruct', local_dir='pretrained_models/CosyVoice-300M-Instruct')
snapshot_download('iic/CosyVoice-ttsfrd', local_dir='pretrained_models/CosyVoice-ttsfrd')
```

``` sh
# git模型下载，请确保已安装git lfs
mkdir -p pretrained_models
git clone https://www.modelscope.cn/iic/CosyVoice2-0.5B.git pretrained_models/CosyVoice2-0.5B
git clone https://www.modelscope.cn/iic/CosyVoice-300M.git pretrained_models/CosyVoice-300M
git clone https://www.modelscope.cn/iic/CosyVoice-300M-SFT.git pretrained_models/CosyVoice-300M-SFT
git clone https://www.modelscope.cn/iic/CosyVoice-300M-Instruct.git pretrained_models/CosyVoice-300M-Instruct
git clone https://www.modelscope.cn/iic/CosyVoice-ttsfrd.git pretrained_models/CosyVoice-ttsfrd
```

（可选）您可以解压 `ttsfrd` 资源并安装 `ttsfrd` 包以获得更好的文本规范化性能。

请注意，此步骤不是必需的。如果您不安装 `ttsfrd` 包，我们将默认使用 wetext。

``` sh
cd pretrained_models/CosyVoice-ttsfrd/
unzip resource.zip -d .
pip install ttsfrd_dependency-0.1-py3-none-any.whl
pip install ttsfrd-0.4.2-cp310-cp310-linux_x86_64.whl
```

### 基本用法

我们强烈建议使用 `CosyVoice2-0.5B` 以获得更好的性能。
请按照以下代码了解每个模型的详细用法。

``` python
import sys
sys.path.append('third_party/Matcha-TTS')
from cosyvoice.cli.cosyvoice import CosyVoice, CosyVoice2
from cosyvoice.utils.file_utils import load_wav
import torchaudio
```

#### CosyVoice2 用法
```python
cosyvoice = CosyVoice2('pretrained_models/CosyVoice2-0.5B', load_jit=False, load_trt=False, load_vllm=False, fp16=False)

# 注意：如果您想复现 https://funaudiollm.github.io/cosyvoice2 上的结果，请在推理时添加 text_frontend=False
# 零样本用法
prompt_speech_16k = load_wav('./asset/zero_shot_prompt.wav', 16000)
for i, j in enumerate(cosyvoice.inference_zero_shot('收到好友从远方寄来的生日礼物，那份意外的惊喜与深深的祝福让我心中充满了甜蜜的快乐，笑容如花儿般绽放。', '希望你以后能够做的比我还好呦。', prompt_speech_16k, stream=False)):
    torchaudio.save('zero_shot_{}.wav'.format(i), j['tts_speech'], cosyvoice.sample_rate)

# 保存零样本说话人以供将来使用
assert cosyvoice.add_zero_shot_spk('希望你以后能够做的比我还好呦。', prompt_speech_16k, 'my_zero_shot_spk') is True
for i, j in enumerate(cosyvoice.inference_zero_shot('收到好友从远方寄来的生日礼物，那份意外的惊喜与深深的祝福让我心中充满了甜蜜的快乐，笑容如花儿般绽放。', '', '', zero_shot_spk_id='my_zero_shot_spk', stream=False)):
    torchaudio.save('zero_shot_{}.wav'.format(i), j['tts_speech'], cosyvoice.sample_rate)
cosyvoice.save_spkinfo()

# 精细控制，有关支持的控制，请查看 cosyvoice/tokenizer/tokenizer.py#L248
for i, j in enumerate(cosyvoice.inference_cross_lingual('在他讲述那个荒诞故事的过程中，他突然[laughter]停下来，因为他自己也被逗笑了[laughter]。', prompt_speech_16k, stream=False)):
    torchaudio.save('fine_grained_control_{}.wav'.format(i), j['tts_speech'], cosyvoice.sample_rate)

# 指令用法
for i, j in enumerate(cosyvoice.inference_instruct2('收到好友从远方寄来的生日礼物，那份意外的惊喜与深深的祝福让我心中充满了甜蜜的快乐，笑容如花儿般绽放。', '用四川话说这句话', prompt_speech_16k, stream=False)):
    torchaudio.save('instruct_{}.wav'.format(i), j['tts_speech'], cosyvoice.sample_rate)

# 双向流用法，您可以使用生成器作为输入，这在使用文本 LLM 模型作为输入时非常有用
# 注意：您仍然需要一些基本的句子拆分逻辑，因为 LLM 无法处理任意长度的句子
def text_generator():
    yield '收到好友从远方寄来的生日礼物，'
    yield '那份意外的惊喜与深深的祝福'
    yield '让我心中充满了甜蜜的快乐，'
    yield '笑容如花儿般绽放。'
for i, j in enumerate(cosyvoice.inference_zero_shot(text_generator(), '希望你以后能够做的比我还好呦。', prompt_speech_16k, stream=False)):
    torchaudio.save('zero_shot_{}.wav'.format(i), j['tts_speech'], cosyvoice.sample_rate)
```

#### CosyVoice2 vllm 用法
如果您想使用 vllm 进行推理，请安装 `vllm==v0.9.0`。旧版本的 vllm 不支持 CosyVoice2 推理。

请注意，`vllm==v0.9.0` 有很多特定要求，例如 `torch==2.7.0`。如果您的硬件不支持 vllm 或者旧环境被破坏，您可以创建一个新环境。

``` sh
conda create -n cosyvoice_vllm --clone cosyvoice
conda activate cosyvoice_vllm
pip install vllm==v0.9.0 transformers==4.51.3 -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host=mirrors.aliyun.com
python vllm_example.py
```

#### CosyVoice 用法
```python
cosyvoice = CosyVoice('pretrained_models/CosyVoice-300M-SFT', load_jit=False, load_trt=False, fp16=False)
# sft 用法
print(cosyvoice.list_available_spks())
# 将 stream=True 更改为块流推理
for i, j in enumerate(cosyvoice.inference_sft('你好，我是通义生成式语音大模型，请问有什么可以帮您的吗？', '中文女', stream=False)):
    torchaudio.save('sft_{}.wav'.format(i), j['tts_speech'], cosyvoice.sample_rate)

cosyvoice = CosyVoice('pretrained_models/CosyVoice-300M')
# 零样本用法，<|zh|><|en|><|jp|><|yue|><|ko|> 分别代表 中文/英文/日文/粤语/韩文
prompt_speech_16k = load_wav('./asset/zero_shot_prompt.wav', 16000)
for i, j in enumerate(cosyvoice.inference_zero_shot('收到好友从远方寄来的生日礼物，那份意外的惊喜与深深的祝福让我心中充满了甜蜜的快乐，笑容如花儿般绽放。', '希望你以后能够做的比我还好呦。', prompt_speech_16k, stream=False)):
    torchaudio.save('zero_shot_{}.wav'.format(i), j['tts_speech'], cosyvoice.sample_rate)
# 跨语言用法
prompt_speech_16k = load_wav('./asset/cross_lingual_prompt.wav', 16000)
for i, j in enumerate(cosyvoice.inference_cross_lingual('<|en|>And then later on, fully acquiring that company. So keeping management in line, interest in line with the asset that\'s coming into the family is a reason why sometimes we don\'t buy the whole thing.', prompt_speech_16k, stream=False)):
    torchaudio.save('cross_lingual_{}.wav'.format(i), j['tts_speech'], cosyvoice.sample_rate)
# 语音转换用法
prompt_speech_16k = load_wav('./asset/zero_shot_prompt.wav', 16000)
source_speech_16k = load_wav('./asset/cross_lingual_prompt.wav', 16000)
for i, j in enumerate(cosyvoice.inference_vc(source_speech_16k, prompt_speech_16k, stream=False)):
    torchaudio.save('vc_{}.wav'.format(i), j['tts_speech'], cosyvoice.sample_rate)

cosyvoice = CosyVoice('pretrained_models/CosyVoice-300M-Instruct')
# 指令用法，支持 <laughter></laughter><strong></strong>[laughter][breath]
for i, j in enumerate(cosyvoice.inference_instruct('在面对挑战时，他展现了非凡的<strong>勇气</strong>与<strong>智慧</strong>。', '中文男', 'Theo \'Crimson\', is a fiery, passionate rebel leader. Fights with fervor for justice, but struggles with impulsiveness.', stream=False)):
    torchaudio.save('instruct_{}.wav'.format(i), j['tts_speech'], cosyvoice.sample_rate)
```

#### 启动 Web 演示

您可以使用我们的 Web 演示页面快速熟悉 CosyVoice。

有关详细信息，请参见演示网站。

``` python
# 将 iic/CosyVoice-300M-SFT 更改为 sft 推理，或将 iic/CosyVoice-300M-Instruct 更改为指令推理
python3 webui.py --port 50000 --model_dir pretrained_models/CosyVoice-300M
```

#### 高级用法

对于高级用户，我们在 `examples/libritts/cosyvoice/run.sh` 中提供了训练和推理脚本。

#### 构建部署

（可选）如果您需要服务部署，
您可以运行以下步骤。

``` sh
cd runtime/python
docker build -t cosyvoice:v1.0 .
# 如果您想使用指令推理，请将 iic/CosyVoice-300M 更改为 iic/CosyVoice-300M-Instruct
# 对于 grpc 用法
docker run -d --runtime=nvidia -p 50000:50000 cosyvoice:v1.0 /bin/bash -c "cd /opt/CosyVoice/CosyVoice/runtime/python/grpc && python3 server.py --port 50000 --max_conc 4 --model_dir iic/CosyVoice-300M && sleep infinity"
cd grpc && python3 client.py --port 50000 --mode <sft|zero_shot|cross_lingual|instruct>
# 对于 fastapi 用法
docker run -d --runtime=nvidia -p 50000:50000 cosyvoice:v1.0 /bin/bash -c "cd /opt/CosyVoice/CosyVoice/runtime/python/fastapi && python3 server.py --port 50000 --model_dir iic/CosyVoice-300M && sleep infinity"
cd fastapi && python3 client.py --port 50000 --mode <sft|zero_shot|cross_lingual|instruct>
```

#### 使用 Nvidia TensorRT-LLM 进行部署

使用 TensorRT-LLM 加速 cosyvoice2 LLM 可以比 huggingface transformers 实现快 4 倍。
快速开始：

``` sh
cd runtime/triton_trtllm
docker compose up -d
```
有关更多详细信息，您可以查看 [这里](https://github.com/FunAudioLLM/CosyVoice/tree/main/runtime/triton_trtllm)

## 讨论与交流

您可以直接在 [Github Issues](https://github.com/FunAudioLLM/CosyVoice/issues) 上进行讨论。

您也可以扫描二维码加入我们的官方钉钉聊天群。

<img src="./asset/dingding.png" width="250px">

## 致谢

1. 我们借鉴了 [FunASR](https://github.com/modelscope/FunASR) 的大量代码。
2. 我们借鉴了 [FunCodec](https://github.com/modelscope/FunCodec) 的大量代码。
3. 我们借鉴了 [Matcha-TTS](https://github.com/shivammehta25/Matcha-TTS) 的大量代码。
4. 我们借鉴了 [AcademiCodec](https://github.com/yangdongchao/AcademiCodec) 的大量代码。
5. 我们借鉴了 [WeNet](https://github.com/wenet-e2e/wenet) 的大量代码。

## 引用

``` bibtex
@article{du2024cosyvoice,
  title={Cosyvoice: A scalable multilingual zero-shot text-to-speech synthesizer based on supervised semantic tokens},
  author={Du, Zhihao and Chen, Qian and Zhang, Shiliang and Hu, Kai and Lu, Heng and Yang, Yexin and Hu, Hangrui and Zheng, Siqi and Gu, Yue and Ma, Ziyang and others},
  journal={arXiv preprint arXiv:2407.05407},
  year={2024}
}

@article{du2024cosyvoice,
  title={Cosyvoice 2: Scalable streaming speech synthesis with large language models},
  author={Du, Zhihao and Wang, Yuxuan and Chen, Qian and Shi, Xian and Lv, Xiang and Zhao, Tianyu and Gao, Zhifu and Yang, Yexin and Gao, Changfeng and Wang, Hui and others},
  journal={arXiv preprint arXiv:2412.10117},
  year={2024}
}

@article{du2025cosyvoice,
  title={CosyVoice 3: Towards In-the-wild Speech Generation via Scaling-up and Post-training},
  author={Du, Zhihao and Gao, Changfeng and Wang, Yuxuan and Yu, Fan and Zhao, Tianyu and Wang, Hao and Lv, Xiang and Wang, Hui and Shi, Xian and An, Keyu and others},
  journal={arXiv preprint arXiv:2505.17589},
  year={2025}
}

@inproceedings{lyu2025build,
  title={Build LLM-Based Zero-Shot Streaming TTS System with Cosyvoice},
  author={Lyu, Xiang and Wang, Yuxuan and Zhao, Tianyu and Wang, Hao and Liu, Huadai and Du, Zhihao},
  booktitle={ICASSP 2025-2025 IEEE International Conference on Acoustics, Speech and Signal Processing (ICASSP)},
  pages={1--2},
  year={2025},
  organization={IEEE}
}
```

## 免责声明
以上提供的内容仅供学术目的，旨在展示技术能力。部分示例来源于互联网。如果任何内容侵犯了您的权利，请联系我们要求删除。
