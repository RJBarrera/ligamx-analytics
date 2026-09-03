# MatchLab - Liga MX Analytics

---

# 1. Crear entorno virtual

Desde la carpeta server

```bash
python -m venv .venv
```

## 1.2. Activar entorno virtual

### CMD

```bat
.venv\Scripts\activate
```

### PowerShell

```powershell
.\.venv\Scripts\Activate.ps1
```

## 1.3. Dependencias Python

```bash
pip install -r requirements.txt
```

---

# 2. Instalación inicial de React

Desde la raíz del proyecto:

```bash
npm install
```

---

# 3. AMBIENTE LOCAL - Desarrollo

Se utilizan dos terminales.

## 3.1. Terminal 1: Levantar FastAPI

Entrar a:

```bat
cd ligamx-analytics/server
```

Activar:

```bat
.venv\Scripts\activate
```

Después ejecutar:

```bash
python -m uvicorn api_server:app --host 127.0.0.1 --port 8000
```

La terminal debe permanecer abierta.

## 3.2. Terminal 2: Levantar React

Abrir una segunda terminal.

Desde la raíz del proyecto:

```bash
npm run dev
```

---

# 4. Generar compilado

Desde la raíz:

```bash
python build_release.py
```

El proceso realiza:

```text
npm run build
      |
      v
dist/
      |
      v
release/MatchLab/
```

La estructura final queda similar a:

```text
release/
|
+-- MatchLab/
    |
    +-- web/
    |   |
    |   +-- index.html
    |   |
    |   +-- assets/
    |
    +-- server/
    |   |
    |   +-- api_server.py
    |   |
    |   +-- run_server.py
    |   |
    |   +-- prediccion_ligamx.py
    |   |
    |   +-- historial_ligamx_2023.csv
    |   |
    |   +-- requirements.txt
    |
    +-- INSTALAR.bat
    |
    +-- INICIAR_MATCHLAB.bat
```

---

# 5. Primera ejecución del compilado

Entrar a:

```text
release/MatchLab/
```

Ejecutar:

```text
INSTALAR.bat
```

Este archivo:

1. Verifica Python.
2. Crea un entorno virtual.
3. Instala las dependencias.
4. Prepara MatchLab.

Solo debe ejecutarse inicialmente o cuando cambien dependencias importantes.

---
