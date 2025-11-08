FROM python:3.11.9-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Install build deps for some libs (pandas, scipy stack minimal)
RUN apt-get update \
    && apt-get -y upgrade \
    && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        curl \
        python3-venv \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create venv and install pip
RUN python -m venv $VIRTUAL_ENV && pip install --no-cache-dir -U pip setuptools wheel

# Install CPU-only PyTorch wheels first, then sentence-transformers
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch torchvision torchaudio && \
    pip install --no-cache-dir sentence-transformers

# Copy project metadata and install deps
COPY pyproject.toml /app/
RUN python - <<'PY'
import tomllib
with open('pyproject.toml','rb') as f:
    data = tomllib.load(f)
reqs = data.get('project',{}).get('dependencies',[])
print('\n'.join(reqs))
PY
RUN pip install --no-cache-dir -e .

# Copy source
COPY . /app

# Provide default non-secret env by copying example into .env if not present
RUN [ -f "/app/.env" ] || cp /app/.env.example /app/.env || true

EXPOSE 8000

# Use uvicorn from the venv
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
