FROM python:3.10-slim

# Install OS dependencies for OpenCV, PaddleOCR, PDF, and media libs
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    ffmpeg \
    libx11-6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2️⃣ Install CPU Torch (compatible with numpy 1.x)
RUN pip install --no-cache-dir \
    torch==2.1.0+cpu \
    torchvision==0.16.0+cpu \
    torchaudio==2.1.0+cpu \
    -f https://download.pytorch.org/whl/cpu/torch_stable.html

# 3️⃣ Copy and install backend requirements
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt \
    --extra-index-url https://download.pytorch.org/whl/cpu

# 4️⃣ Copy backend source code
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
