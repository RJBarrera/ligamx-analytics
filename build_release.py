"""build_release"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

## Directorios
ROOT_DIR = Path(__file__).resolve().parent
DIST_DIR = ROOT_DIR / "dist"
SERVER_DIR = ROOT_DIR / "server"
RELEASE_ROOT = ROOT_DIR / "release"
RELEASE_DIR = RELEASE_ROOT / "MatchLab"
RELEASE_WEB = RELEASE_DIR / "web"
RELEASE_SERVER = RELEASE_DIR / "server"


## Utilidades
def titulo(texto):
    """Imprime titulo"""

    print("\n" + "=" * 50)
    print(texto)
    print("=" * 50 + "\n")


def ejecutar(comando):
    """Ejecuta comandos"""

    print(
        "▶",
        " ".join(comando),
    )

    resultado = subprocess.run(
        comando,
        cwd=ROOT_DIR,
        shell=os.name == "nt",
        check=True,
    )

    if resultado.returncode != 0:
        raise RuntimeError("El comando terminó con error: " + " ".join(comando))


## Validaciones
def validar_archivos():
    """Valida existencia de archivos"""

    obligatorios = [
        ROOT_DIR / "package.json",
        SERVER_DIR / "api_server.py",
        SERVER_DIR / "run_server.py",
        SERVER_DIR / "prediccion_ligamx.py",
        SERVER_DIR / "historial_ligamx_2023.csv",
        SERVER_DIR / "requirements.txt",
    ]

    faltantes = [archivo for archivo in obligatorios if not archivo.exists()]

    if faltantes:
        print("❌ Faltan archivos:")

        for archivo in faltantes:
            print(" -", archivo)

        sys.exit(1)


def limpiar_release():
    """Limpia release anterior"""

    titulo("🧹 LIMPIANDO BUILD ANTERIOR")

    if RELEASE_DIR.exists():
        shutil.rmtree(RELEASE_DIR)

    RELEASE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


def compilar_react():
    """Ejecuta compilación de react"""

    titulo("⚛️ COMPILANDO REACT + VITE")

    comando_npm = "npm.cmd" if os.name == "nt" else "npm"

    ejecutar(
        [
            comando_npm,
            "run",
            "build",
        ]
    )

    if not DIST_DIR.exists():
        raise RuntimeError("Vite no generó la carpeta dist.")


def copiar_frontend():
    """Copia FrontEnd"""

    titulo("🌐 COPIANDO FRONTEND")

    shutil.copytree(
        DIST_DIR,
        RELEASE_WEB,
    )

    print(f"✅ Frontend: {RELEASE_WEB}")


def copiar_server():
    """Copia server"""

    titulo("🐍 COPIANDO SERVER PYTHON")

    RELEASE_SERVER.mkdir(
        parents=True,
        exist_ok=True,
    )

    archivos = [
        "api_server.py",
        "run_server.py",
        "prediccion_ligamx.py",
        "historial_ligamx_2023.csv",
        "requirements.txt",
    ]

    for nombre in archivos:
        origen = SERVER_DIR / nombre
        destino = RELEASE_SERVER / nombre

        shutil.copy2(
            origen,
            destino,
        )

        print(f"✅ {nombre}")


def crear_instalador():
    """Crea archivo instalador"""

    contenido = r"""@echo off
title MatchLab - Instalacion

cd /d "%~dp0"

echo.
echo ==================================================
echo MATCHLAB - INSTALACION
echo ==================================================
echo.

where python >nul 2>&1

if errorlevel 1 (
    echo ERROR: Python no se encuentra instalado.
    echo.
    echo Instala Python 3 antes de continuar.
    echo.
    pause
    exit /b 1
)

echo Creando entorno virtual...
python -m venv .venv

if errorlevel 1 (
    echo.
    echo ERROR creando el entorno virtual.
    pause
    exit /b 1
)

echo.
echo Instalando dependencias...
echo.

".venv\Scripts\python.exe" -m pip install --upgrade pip

".venv\Scripts\python.exe" -m pip install -r "server\requirements.txt"

if errorlevel 1 (
    echo.
    echo ERROR instalando dependencias.
    pause
    exit /b 1
)

echo.
echo ==================================================
echo INSTALACION COMPLETADA
echo ==================================================
echo.
echo Ahora puedes ejecutar:
echo INICIAR_MATCHLAB.bat
echo.

pause
"""

    archivo = RELEASE_DIR / "INSTALAR.bat"

    archivo.write_text(
        contenido,
        encoding="utf-8",
    )


def crear_start():
    """Crea archivo start"""

    contenido = r"""@echo off
title MatchLab - Liga MX Analytics

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo MatchLab aun no esta instalado.
    echo.
    echo Ejecuta primero:
    echo INSTALAR.bat
    echo.
    pause
    exit /b 1
)

echo.
echo ==================================================
echo MATCHLAB - LIGA MX ANALYTICS
echo ==================================================
echo.
echo Iniciando servidor...
echo.

".venv\Scripts\python.exe" "server\run_server.py"

pause
"""

    archivo = RELEASE_DIR / "INICIAR_MATCHLAB.bat"

    archivo.write_text(
        contenido,
        encoding="utf-8",
    )


def main():
    """Función principal"""

    titulo("⚽ MATCHLAB - BUILD")

    validar_archivos()
    limpiar_release()
    compilar_react()
    copiar_frontend()
    copiar_server()
    crear_instalador()
    crear_start()

    titulo("✅ BUILD COMPLETADO")
    print("Compilado generado en:")
    print(RELEASE_DIR)
    print("\nEstructura:\n")

    print("MatchLab/")
    print("├── web/")
    print("├── server/")
    print("├── INSTALAR.bat")
    print("└── INICIAR_MATCHLAB.bat\n")


if __name__ == "__main__":
    main()
