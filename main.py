"""
MECHA ARENA - punto de entrada raiz.
===============================================================
Uso:  python main.py

Este archivo es un lanzador minimo: anade la carpeta del proyecto al
ruta de busqueda y delega en ``mecha_arena.app``. Asi el juego se puede
ejecutar con un solo comando desde la raiz del repositorio.
"""

from __future__ import annotations

import os
import sys

# Anade la raiz del proyecto al path para poder importar el paquete.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def main() -> None:
    """Arranca el juego y captura errores de inicio con un mensaje claro."""
    try:
        from mecha_arena.app import Game
    except ImportError as error:  # pragma: no cover - fallo de entorno
        print("No se pudo iniciar MECHA ARENA.")
        print("Comprueba que pygame-ce esta instalado:  pip install pygame-ce")
        raise SystemExit(1) from error

    try:
        Game().run()
    except KeyboardInterrupt:
        print("\nMECHA ARENA cerrado.")


if __name__ == "__main__":
    main()
