FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Railway بيمرر PORT عبر env
ENV PORT=8000
EXPOSE 8000

# الكود بيقرأ PORT من env داخلياً (os.environ.get("PORT", "8000"))
CMD ["python", "beshoy_bot.py"]
