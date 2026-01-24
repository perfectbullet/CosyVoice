FROM cosyvoice:v1.6

ARG VENV_NAME="cosyvoice"
ENV VENV=$VENV_NAME
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

SHELL ["/bin/bash", "--login", "-c"]

ARG VENV_NAME="cosyvoice"
ENV VENV=$VENV_NAME
ENV CONDA_DEFAULT_ENV=${VENV}
ENV PATH=/opt/conda/bin:/opt/conda/envs/${VENV}/bin:$PATH

WORKDIR /workspace/CosyVoice
# COPY ./requirements.txt ./

# 关键：将虚拟环境的 bin 目录放在 PATH 最前面
ENV PATH=/opt/conda/envs/${VENV}/bin:$PATH

RUN python --version && \
    python -c "import sys; print(f'Python路径: {sys.executable}')" && \
    pip --version

RUN pip install redis==5.0.0

CMD ["/bin/bash"]

