FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AGI_BACKEND_HOST=0.0.0.0 \
    AGI_BACKEND_PORT=5000

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

# GitHub builds do not include git-ignored model binaries.
# Train and materialize model artifacts during image build when missing.
RUN if [ ! -f /app/models/master_model.pkl ]; then python /app/train_model.py; fi

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import os,urllib.request,sys;port=os.getenv('PORT', os.getenv('AGI_BACKEND_PORT','5000'));url=f'http://127.0.0.1:{port}/api/ready';sys.exit(0 if urllib.request.urlopen(url, timeout=3).getcode()==200 else 1)"

CMD ["sh", "-c", "gunicorn -w 2 -b 0.0.0.0:${PORT:-${AGI_BACKEND_PORT:-5000}} app:app"]
