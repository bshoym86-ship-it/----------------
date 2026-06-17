FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Railway بيمرر PORT عبر env
ENV PORT=8000
EXPOSE 8000

CMD ["python", "-m", "uvicorn", "beshoy_bot:app", "--host", "0.0.0.0", "--port", "8000"]
