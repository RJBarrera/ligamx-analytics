# ============================================================
# MATCHLAB - RAILWAY
# React + Vite + Python + FastAPI
# ============================================================


# ============================================================
# ETAPA 1 - COMPILAR REACT
# ============================================================

FROM node:22-alpine AS frontend


WORKDIR /frontend


# Copiamos archivos de dependencias
COPY package*.json ./


# Instalamos dependencias
#
# Se usa npm install porque actualmente el proyecto puede
# no tener package-lock.json.
RUN npm install


# Copiamos el proyecto
COPY . .


# Compilamos React + Vite
RUN npm run build



# ============================================================
# ETAPA 2 - PYTHON + FASTAPI
# ============================================================

FROM python:3.12-slim


# Directorio general de la aplicación
WORKDIR /app


# ============================================================
# DEPENDENCIAS PYTHON
# ============================================================

COPY server/requirements.txt /app/server/requirements.txt


RUN pip install \
    --no-cache-dir \
    -r /app/server/requirements.txt



# ============================================================
# COPIAR BACKEND
# ============================================================

COPY server /app/server



# ============================================================
# COPIAR FRONTEND COMPILADO
# ============================================================
#
# Vite creó:
#
# /frontend/dist
#
# FastAPI buscará el frontend en:
#
# /app/web
#
# ============================================================

COPY --from=frontend /frontend/dist /app/web



# ============================================================
# WORKDIR DEL BACKEND
# ============================================================
#
# Esto es importante porque tu proyecto actualmente trabaja
# con imports como:
#
# from prediccion_ligamx import ...
#
# Al ejecutar desde /app/server esos imports siguen funcionando.
#
# ============================================================

WORKDIR /app/server



# ============================================================
# INICIAR FASTAPI
# ============================================================
#
# Railway proporciona automáticamente la variable PORT.
#
# En Railway:
#
# HOST = 0.0.0.0
#
# NO usar 127.0.0.1.
#
# ============================================================

CMD ["sh", "-c", "python -m uvicorn api_server:app --host 0.0.0.0 --port ${PORT:-8000}"]
