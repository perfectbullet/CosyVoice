# syntax=docker/dockerfile:1.6

########################################
# 基础阶段：系统依赖和环境配置
########################################
FROM pytorch/pytorch:2.0.1-cuda11.7-cudnn8-devel AS base

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    LANG=zh_CN.UTF-8 \
    LC_ALL=zh_CN.UTF-8 \
    LANGUAGE=zh_CN:zh \
    TZ=Asia/Shanghai

WORKDIR /opt/CosyVoice

# 使用阿里云镜像源
RUN sed -i 's@/archive.ubuntu.com/@/mirrors.aliyun.com/@g' /etc/apt/sources.list \
    && sed -i 's@/security.ubuntu.com/@/mirrors.aliyun.com/@g' /etc/apt/sources.list

# 安装系统依赖（合并到一个 RUN 层并立即清理）
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean && \
    apt-get update -y && \
    apt-get install -y --no-install-recommends \
        git \
        git-lfs \
        unzip \
        g++ \
        tzdata \
        locales \
        fontconfig \
        fonts-wqy-zenhei \
    && git lfs install \
    && sed -i 's/# zh_CN.UTF-8 UTF-8/zh_CN.UTF-8 UTF-8/' /etc/locale.gen \
    && locale-gen zh_CN.UTF-8 \
    && fc-cache -fv \
    # 关键优化：立即清理 APT 缓存
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /var/cache/apt/* \
    && rm -rf /tmp/* \
    && rm -rf /var/tmp/*

# 设置时区
RUN ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo "Asia/Shanghai" > /etc/timezone

# 配置 pip
ENV PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
ENV PIP_DEFAULT_TIMEOUT=120
ENV PIP_RETRIES=10

########################################
# 依赖构建阶段：安装 Python 依赖
########################################
FROM base AS builder

COPY requirements.txt .
COPY wheel_packages ./wheel_packages

# 关键优化：使用 BuildKit 缓存 + 清理
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt -f wheel_packages && \
    # 清理 pip 临时文件
    rm -rf /tmp/* && \
    # 删除不必要的文件
    find /opt/conda -type d -name '__pycache__' -prune -exec rm -rf {} + && \
    find /opt/conda -type f -name '*.pyc' -delete && \
    find /opt/conda -type f -name '*.pyo' -delete && \
    find /opt/conda -type f -name '*.a' -delete && \
    # 删除测试文件
    find /opt/conda -type d -name 'tests' -prune -exec rm -rf {} + && \
    find /opt/conda -type d -name 'test' -prune -exec rm -rf {} + && \
    # 清理 conda 缓存
    conda clean -ay 2>/dev/null || true && \
    rm -rf /opt/conda/pkgs/*

########################################
# 最终运行阶段（从 runtime 基础镜像开始）
########################################
FROM pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime AS runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    LANG=zh_CN.UTF-8 \
    LC_ALL=zh_CN.UTF-8 \
    LANGUAGE=zh_CN:zh \
    TZ=Asia/Shanghai

WORKDIR /opt/CosyVoice

# 使用阿里云镜像源
RUN sed -i 's@/archive.ubuntu.com/@/mirrors.aliyun.com/@g' /etc/apt/sources.list \
    && sed -i 's@/security.ubuntu.com/@/mirrors.aliyun.com/@g' /etc/apt/sources.list

# 只安装运行时必需的依赖（关键优化：使用 runtime 而非 devel）
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean && \
    apt-get update -y && \
    apt-get install -y --no-install-recommends \
        git \
        unzip \
        tzdata \
        locales \
        fontconfig \
        fonts-wqy-zenhei \
    && sed -i 's/# zh_CN.UTF-8 UTF-8/zh_CN.UTF-8 UTF-8/' /etc/locale.gen \
    && locale-gen zh_CN.UTF-8 \
    && fc-cache -fv \
    # 立即清理
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /var/cache/apt/* \
    && rm -rf /tmp/* \
    && rm -rf /var/tmp/*

# 设置时区
RUN ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo "Asia/Shanghai" > /etc/timezone

# 从 builder 阶段复制已安装并清理过的 Python 包
COPY --from=builder /opt/conda /opt/conda

# 再次清理（防止复制时带入的缓存）
RUN rm -rf /opt/conda/pkgs/* \
    && rm -rf /root/.cache/* \
    && find /opt/conda -type d -name '__pycache__' -prune -exec rm -rf {} + \
    && find /opt/conda -type f -name '*.pyc' -delete \
    && find /opt/conda -type f -name '*.pyo' -delete

# 复制项目代码
COPY ./runtime /opt/CosyVoice/runtime

# 生成 gRPC 代码
RUN cd runtime/python/grpc && \
    python3 -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. cosyvoice.proto && \
    # 清理临时文件
    rm -rf /tmp/* /root/.cache/*

# 暴露端口
EXPOSE 50000

# 健康检查（可选）
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import torch; import grpc" || exit 1

# 默认命令
CMD ["bash"]