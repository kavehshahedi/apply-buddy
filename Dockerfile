FROM python:3.12.7-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    CHROME_BIN=/usr/bin/chromium \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver

RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    chromium-common \
    chromium-sandbox \
    pandoc \
    texlive-latex-base \
    texlive-latex-extra \
    texlive-fonts-recommended \
    texlive-fonts-extra \
    texlive-latex-recommended \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir "poetry==2.4.1" && poetry config virtualenvs.in-project true

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-interaction --no-ansi --no-root

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

COPY . .

RUN mkdir -p /app/data/cv /app/data/output /app/chrome-profile

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]