FROM python:3.10-slim

WORKDIR /app

RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

ENV HF_ENDPOINT=https://hf-mirror.com

COPY requirements-api.txt .

# 安装 CPU 版本的 PyTorch 和 OmniVoice
# 使用 --extra-index-url 保留 PyTorch 官方源（因为国内镜像可能不同步 PyTorch 的特殊版本）
RUN pip install --no-cache-dir torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/cpu \
    --extra-index-url https://pypi.tuna.tsinghua.edu.cn/simple  # 使用清华源作为后备
RUN pip install --no-cache-dir -r requirements-api.txt \
    --index-url https://pypi.tuna.tsinghua.edu.cn/simple
# 安装 omnivoice 时直接使用国内源加速
RUn pip install --no-cache-dir omnivoice \
    --index-url https://pypi.tuna.tsinghua.edu.cn/simple

COPY app.py .
COPY api.py .
COPY web.py .

EXPOSE 1218 1219

COPY start.sh /start.sh
RUN chmod +x /start.sh

CMD ["/start.sh"]