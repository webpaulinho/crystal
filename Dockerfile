FROM python:3.11-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8080

# Para debug: inicia o Flask diretamente (não recomendado para produção)
CMD ["python", "main.py"]
