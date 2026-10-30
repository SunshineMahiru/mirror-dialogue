FROM python:3.12-slim

LABEL org.opencontainers.image.title="mirror-dialogue" \
      org.opencontainers.image.description="Mirror-dialogue analysis skill: essays and diaries as mirror dialogues, producing a multi-disciplinary HTML report" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# 依赖全部由 requirements.txt 固定版本；python-docx 用于 .docx 解析
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/output

# 文本目录与产物目录建议以卷挂载：
#   docker run --rm -v "$PWD/texts:/data:ro" -v "$PWD/output:/app/output" \
#     ghcr.io/sunshinemahiru/mirror-dialogue:latest --target-dir /data

ENTRYPOINT ["python", "run.py"]
CMD ["--help"]
