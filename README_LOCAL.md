# 1. Terminal 1 - Levantar FastAPI

Entrar a:

```text
ligamx-analytics/server
```

Ejemplo Windows:

```bat
cd /d "C:\RUTA\AL\PROYECTO\ligamx-analytics\server"
```

Activar:

```bat
.venv\Scripts\activate
```

Después ejecutar:

```bash
python -m uvicorn api_server:app --host 127.0.0.1 --port 8000
```

Para este proyecto es recomendable trabajar inicialmente sin:

```text
--reload
```

debido a que los modelos se inicializan durante el arranque.

La terminal debe permanecer abierta.

# 2. Terminal 2 - Levantar React

Abrir una segunda terminal.

Desde la raíz:

```bash
npm run dev
```

Vite debería mostrar algo similar a:

```text
VITE ready

Local:
http://127.0.0.1:5173/
```

Abrir:

```text
http://127.0.0.1:5173
```

# 3. AMBIENTE LOCAL - Compilado

La aplicación también puede ejecutarse sin Vite.

En este modo FastAPI entrega:

```text
React
+
Python
```

desde el mismo puerto:

```text

http://127.0.0.1:8000
```

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

# 6. Ejecutar compilado local

Después ejecutar:

```text
INICIAR_MATCHLAB.bat
```

El flujo será:

```text
INICIAR_MATCHLAB.bat
        |
        v
Python
        |
        v
FastAPI
        |
        +-- carga CSV
        |
        +-- carga modelos
        |
        +-- sirve React
        |
        v
http://127.0.0.1:8000
```

En este modo NO se necesita ejecutar:

```bash
npm run dev
```
