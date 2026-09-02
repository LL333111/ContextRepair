FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ripgrep \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/contextrepair
COPY pyproject.toml README.md LICENSE ./
COPY contextrepair ./contextrepair
RUN pip install --no-cache-dir .

ENTRYPOINT ["contextrepair"]

