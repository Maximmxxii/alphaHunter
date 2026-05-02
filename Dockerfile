FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ api/
COPY screener/ screener/
COPY backtesting/ backtesting/
COPY ml/ ml/
COPY smart_money/ smart_money/
COPY utils/ utils/
COPY tools/ tools/

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
