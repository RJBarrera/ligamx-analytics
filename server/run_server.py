"""run_server"""

import threading
import time
import webbrowser

import uvicorn

from api_server import app

## Configuración
HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}"


def abrir_navegador():
    """Abre navegador"""

    time.sleep(2)
    print(f"🌐 Abriendo MatchLab: {URL}")
    webbrowser.open(URL)


if __name__ == "__main__":

    print("=" * 50)
    print("⚽ MATCHLAB")
    print("=" * 50)
    print(f"🌐 URL: {URL}")
    print("⏹ Para detener: Ctrl + C")
    print("=" * 50)

    navegador_thread = threading.Thread(
        target=abrir_navegador,
        daemon=True,
    )
    navegador_thread.start()

    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_level="info",
    )
