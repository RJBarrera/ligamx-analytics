# React + Vite + Python + FastAPI

# COMPILAR REACT
FROM node:22-alpine AS frontend

WORKDIR /frontend

# Copiamos archivos de dependencias
COPY package*.json ./

# Instalamos dependencias
RUN npm install

# Copiamos el proyecto
COPY . .

# Compilamos React + Vite
RUN npm run build

# PYTHON + FASTAPI
FROM python:3.12-slim

# Directorio general de la aplicación
WORKDIR /app

# DEPENDENCIAS PYTHON
COPY server/requirements.txt /app/server/requirements.txt

RUN pip install \
    --no-cache-dir \
    -r /app/server/requirements.txt

# COPIAR BACKEND
COPY server /app/server
COPY --from=frontend /frontend/dist /app/web

WORKDIR /app/server

CMD ["sh", "-c", "python -m uvicorn api_server:app --host 0.0.0.0 --port ${PORT:-8000}"]
