# Use a lightweight, modern Python base
FROM python:3.11-slim

# Prevent Python from buffering stdout so logs flow immediately to Docker
ENV PYTHONUNBUFFERED=1

# Install system dependencies required for ChromaDB and spaCy C++ wheel compilation
RUN apt-get update && apt-get install -y build-essential gcc g++ && rm -rf /var/lib/apt/lists/*

# Set the working directory inside the container
WORKDIR /app

# Install dependencies first (leverages Docker cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- THE ML BAKE IN ---
# Download the embedding model into the image so it never needs the internet again
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Download the specific spaCy language model
RUN python -m spacy download en_core_web_sm

# Lock the ML engines into strict offline mode
ENV TRANSFORMERS_OFFLINE=1
ENV HF_DATASETS_OFFLINE=1

# Copy the rest of the application code
COPY . .

# Expose the FastAPI port
EXPOSE 8000

# Ignite the server
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]