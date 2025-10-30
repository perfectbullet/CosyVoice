# syntax=docker/dockerfile:1.6

########################################
# 基础阶段：系统依赖和环境配置
########################################
FROM pytorch/pytorch:2.0.1-cuda11.7-cudnn8-devel AS base

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /opt/CosyVoice

# 使用阿里云镜像源
RUN sed -i 's@/archive.ubuntu.com/@/mirrors.aliyun.com/@g' /etc/apt/sources.list \
    && sed -i 's@/security.ubuntu.com/@/mirrors.aliyun.com/@g' /etc/apt/sources.list

# 安装系统依赖、时区数据和中文语言包
RUN apt-get update -y && apt-get install -y --no-install-recommends \
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
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 设置时区为中国/上海
RUN ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo "Asia/Shanghai" > /etc/timezone

# 设置中文环境变量
ENV LANG=zh_CN.UTF-8
ENV LC_ALL=zh_CN.UTF-8
ENV LANGUAGE=zh_CN:zh
ENV TZ=Asia/Shanghai

# 配置 pip 使用阿里云镜像
ENV PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
ENV PIP_DEFAULT_TIMEOUT=120
ENV PIP_RETRIES=10

########################################
# 依赖构建阶段：安装 Python 依赖
########################################
FROM base AS builder

COPY requirements.txt .
COPY wheel_packages ./wheel_packages

# 使用缓存加速依赖安装
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip \
    && pip install -r requirements.txt -f wheel_packages

########################################
# 最终运行阶段
########################################
FROM base AS runtime

# 从 builder 阶段复制已安装的 Python 包
COPY --from=builder /opt/conda /opt/conda

# 复制项目代码
COPY . /opt/CosyVoice

# 生成 gRPC 代码
RUN cd runtime/python/grpc && \
    python3 -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. cosyvoice.proto

# 设置 Python 环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8

# 暴露端口（根据实际需要调整）
EXPOSE 50000

# 默认命令（根据实际需要调整）
CMD ["bash"]