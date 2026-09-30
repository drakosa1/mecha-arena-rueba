"""
MECHA ARENA - settings.py
===============================================================
Configuracion central del juego.

Un solo lugar para los valores que se ajustan con frecuencia: resolucion,
fisica, arena, tiempos de ronda y mapa de teclas. Ningun otro modulo debe
inventar numeros de juego.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Tuple

import pygame

# ---------------------------------------------------------------------------
# Ventana
# ---------------------------------------------------------------------------
GAME_TITLE = "MECHA ARENA"
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60
FULLSCREEN = False

# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
SAVE_FILE = os.path.join(ASSETS_DIR, "profile.json")

# ---------------------------------------------------------------------------
# Arena
# ---------------------------------------------------------------------------
#: Coordenada Y de la superficie pisable de la arena.
FLOOR_Y = 560
#: Limites horizontales: los combatientes no pueden salir de la arena.
ARENA_LEFT = 70
ARENA_RIGHT = SCREEN_WIDTH - 70
#: Plataformas opcionales: (x, y, ancho, alto).
PLATFORM_RECTS: Tuple[Tuple[int, int, int, int], ...] = (
    (290, 420, 230, 20),
    (760, 420, 230, 20),
)

# ---------------------------------------------------------------------------
# Fisica
# ---------------------------------------------------------------------------
GRAVITY = 2400.0            # px/s^2
MAX_FALL_SPEED = 1500.0     # px/s de velocidad maxima de caida
GROUND_FRICTION = 3400.0    # px/s^2 de frenado sobre el suelo
AIR_CONTROL = 0.55          # factor de aceleracion en el aire (0.0 - 1.0)
BODY_PUSH_STRENGTH = 900.0  # empuje al solaparse dos Mecha

# ---------------------------------------------------------------------------
# Combate
# ---------------------------------------------------------------------------
ROUND_TIME = 60             # segundos por ronda
ROUNDS_TO_WIN = 2           # rondas necesarias para ganar el combate
INTRO_TIME = 1.8            # aviso "RONDA X" antes de poder actuar
ROUND_END_TIME = 3.0        # pausa tras terminar la ronda
MAX_PROJECTILES = 14        # limite de proyectiles vivos por combatiente
ROUND_HEAL_BONUS = 0.0      # vida extra al iniciar cada ronda
#: Duracion del fogonazo del arma de energia (segundos).
MUZZLE_FLASH_TIME = 0.14
#: Duracion del destello blanco al recibir dano (segundos).
HIT_FLASH_TIME = 0.16

# ---------------------------------------------------------------------------
# Colores
# ---------------------------------------------------------------------------
COLOR_BACKGROUND_TOP = (8, 10, 24)
COLOR_BACKGROUND_BOTTOM = (26, 16, 52)
COLOR_FLOOR = (32, 38, 66)
COLOR_FLOOR_LIGHT = (58, 70, 116)
COLOR_PLATFORM = (46, 54, 88)
COLOR_PLATFORM_EDGE = (96, 176, 255)
COLOR_HUD_BG = (14, 18, 38)
COLOR_HUD_BORDER = (70, 96, 158)
COLOR_HP_PLAYER = (86, 232, 160)
COLOR_HP_ENEMY = (255, 92, 106)
COLOR_HP_BACK = (48, 24, 36)
COLOR_TEXT = (226, 236, 255)
COLOR_TEXT_DIM = (138, 156, 196)
COLOR_ACCENT = (108, 208, 255)
COLOR_DANGER = (255, 92, 106)
COLOR_SHADOW = (10, 12, 26, 140)

# ---------------------------------------------------------------------------
# Controles del jugador
# ---------------------------------------------------------------------------

# Las teclas se toman de pygame y no se escriben a mano a proposito: los
# codigos de pygame no son los de ASCII (``pygame.K_a`` es 97, no 65), asi que
# un numero inventado deja esa tecla muda sin avisar de nada. Importar pygame
# aqui no inicializa la libreria ni abre ventana, solo aporta los codigos.
KEY_A = pygame.K_a
KEY_D = pygame.K_d
KEY_W = pygame.K_w
KEY_J = pygame.K_j
KEY_K = pygame.K_k
KEY_ESCAPE = pygame.K_ESCAPE
KEY_SPACE = pygame.K_SPACE
KEY_LEFT = pygame.K_LEFT
KEY_RIGHT = pygame.K_RIGHT
KEY_UP = pygame.K_UP
KEY_DOWN = pygame.K_DOWN
KEY_LSHIFT = pygame.K_LSHIFT
KEY_LCTRL = pygame.K_LCTRL


@dataclass(frozen=True)
class PlayerControls:
    """Mapa de teclas del jugador. Modificarlo aqui afecta a toda la partida."""

    left: int
    right: int
    jump: int
    melee: int
    energy: int
    alt_left: int
    alt_right: int
    alt_jump: int
    alt_melee: int
    alt_energy: int
    pause: int

    def horizontal_keys(self) -> Tuple[int, int]:
        return (self.left, self.alt_left, self.right, self.alt_right)

    def jump_keys(self) -> Tuple[int, int]:
        return (self.jump, self.alt_jump)

    def melee_keys(self) -> Tuple[int, int]:
        return (self.melee, self.alt_melee)

    def energy_keys(self) -> Tuple[int, int]:
        return (self.energy, self.alt_energy)


#: A / D = mover, W = saltar, J = cuerpo a cuerpo, K = disparo de energia.
#: Las flechas, ESPACIO y MAYUS son teclas alternativas.
CONTROLS = PlayerControls(
    left=KEY_A,
    right=KEY_D,
    jump=KEY_W,
    melee=KEY_J,
    energy=KEY_K,
    alt_left=KEY_LEFT,
    alt_right=KEY_RIGHT,
    alt_jump=KEY_UP,
    alt_melee=KEY_SPACE,
    alt_energy=KEY_LSHIFT,
    pause=KEY_ESCAPE,
)
