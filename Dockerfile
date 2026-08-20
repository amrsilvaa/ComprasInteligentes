# Usar a imagem oficial do Python 3.12 (que é estável e funciona com o pandas)
FROM python:3.12-slim

# Definir o diretório de trabalho dentro do container
WORKDIR /app

# Copiar os arquivos de requisitos primeiro (para aproveitar cache do Docker)
COPY requirements.txt .

# Instalar as dependências sem compilar pandas (usando wheels)
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copiar o resto do código do projeto (backend e frontend)
COPY . .

# Comando para iniciar o servidor Flask
CMD ["python", "backend/app.py"]