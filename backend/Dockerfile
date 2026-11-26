FROM python:3.12-slim

WORKDIR /app

# Cai dat thu vien Python
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy toan bo ma nguon backend
COPY . .

EXPOSE 8000

# Chay migration Alembic, khoi tao du lieu mau neu chua co va bat FastAPI server
CMD sh -c "alembic upgrade head && python seed_db.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"
