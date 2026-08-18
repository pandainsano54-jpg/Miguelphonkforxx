FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run main.py which starts both bot and refresher in parallel
CMD ["python", "main.py"]
