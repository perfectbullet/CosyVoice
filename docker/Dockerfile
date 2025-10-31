# ==================================================================
# 阶段 1: 基础系统和 Conda 环境
# ==================================================================
FROM nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04 AS conda-stage

ARG VENV_NAME="cosyvoice"
ENV VENV=$VENV_NAME
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

SHELL ["/bin/bash", "--login", "-c"]

# 使用阿里云镜像源
RUN sed -i 's@/archive.ubuntu.com/@/mirrors.aliyun.com/@g' /etc/apt/sources.list && \
    sed -i 's@/security.ubuntu.com/@/mirrors.aliyun.com/@g' /etc/apt/sources.list

# 安装系统依赖（使用 apt 缓存）
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update -y --fix-missing && \
    apt-get install -y git build-essential curl wget ffmpeg unzip git-lfs sox libsox-dev && \
    git lfs install

# 使用构建时绑定挂载，不会增加镜像层大小
RUN --mount=type=bind,source=./Miniforge3-Linux-x86_64.sh,target=/tmp/miniforge.sh \
    /bin/bash /tmp/miniforge.sh -b -p /opt/conda && \
    ln -s /opt/conda/etc/profile.d/conda.sh /etc/profile.d/conda.sh

ENV PATH=/opt/conda/bin:$PATH

# 配置 Conda
RUN conda config --add channels conda-forge && \
    conda config --set channel_priority strict

# 创建 Conda 环境并安装 pynini（使用 conda 缓存）
RUN --mount=type=cache,target=/opt/conda/pkgs \
    conda create -y -n ${VENV} python=3.10 && \
    conda install -y -n ${VENV} -c conda-forge pynini==2.1.5 && \
    conda clean -afy

# ==================================================================
# 阶段 2: Pip 依赖安装
# ==================================================================
FROM conda-stage AS pip-stage

ARG VENV_NAME="cosyvoice"
ENV VENV=$VENV_NAME
ENV CONDA_DEFAULT_ENV=${VENV}
ENV PATH=/opt/conda/bin:/opt/conda/envs/${VENV}/bin:$PATH

WORKDIR /workspace

# 先复制 requirements.txt（利用 Docker 层缓存）
WORKDIR /workspace/CosyVoice

COPY ./requirements.txt ./

# 关键：将虚拟环境的 bin 目录放在 PATH 最前面
ENV PATH=/opt/conda/envs/${VENV}/bin:$PATH

RUN python --version && \
    python -c "import sys; print(f'Python路径: {sys.executable}')" && \
    pip --version
# 安装 Python 依赖（使用 pip 缓存挂载）
# 步骤 2: 从本地 wheel 安装（完全离线，快速）
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=bind,source=./wheel_packages,target=/tmp/wheel_packages \
    set -e && \
    echo "========================================" && \
    echo "步骤 2: 从本地 wheel 包安装" && \
    echo "========================================" && \
    pip install \
        --no-index \
        --find-links /tmp/wheel_packages \
        -r requirements.txt && \
    echo "========================================" && \
    echo "安装完成！已安装的包：" && \
    pip list && \
    echo "========================================"

# ==================================================================
# 阶段 3: 最终镜像
# ==================================================================
FROM pip-stage AS final

ENV VENV=$VENV_NAME
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV CONDA_DEFAULT_ENV=${VENV}
ENV PATH=/opt/conda/bin:/opt/conda/envs/${VENV}/bin:$PATH
# 关键：将虚拟环境的 bin 目录放在 PATH 最前面
ENV PATH=/opt/conda/envs/${VENV}/bin:$PATH

SHELL ["/bin/bash", "--login", "-c"]

WORKDIR /workspace/CosyVoice

# 配置 conda 自动激活
RUN echo "source /opt/conda/etc/profile.d/conda.sh" >> /opt/nvidia/entrypoint.d/100.conda.sh && \
    echo "source /opt/conda/etc/profile.d/conda.sh" >> ~/.bashrc && \
    echo "conda activate ${VENV}" >> /opt/nvidia/entrypoint.d/110.conda_default_env.sh && \
    echo "conda activate ${VENV}" >> ~/.bashrc

CMD ["/bin/bash"]