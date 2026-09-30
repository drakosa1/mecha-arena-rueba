"""
MECHA ARENA - ui/arena.py
===============================================================
La arena: escenario futurista dibujado por codigo.

El fondo estatico (degradado, skyline, paneles y rejilla) se dibuja una sola
vez sobre una superficie cacheada. Solo las luces, el suelo y las plataformas
se redibujan cada fotograma, de modo que el coste por frame es bajo.

Responsabilidades:
    - Fondo tecnologico con profundidad.
    - Suelo de la arena y plataformas.
    - Luces animadas (neones, torres y barrido del suelo).
    - Efecto de camara leve al recibir impactos.
"""

from __future__ import annotations

import math
import random
from typing import List, Tuple

import pygame

from mecha_arena.settings import (
    ARENA_LEFT,
    ARENA_RIGHT,
    COLOR_BACKGROUND_BOTTOM,
    COLOR_BACKGROUND_TOP,
    COLOR_FLOOR,
    COLOR_FLOOR_LIGHT,
    COLOR_PLATFORM,
    COLOR_PLATFORM_EDGE,
    FLOOR_Y,
    PLATFORM_RECTS,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)
from mecha_arena.ui.palette import shade

Color = Tuple[int, int, int]


class Arena:
    """
    Escenario de combate.

    Mantiene las superficies cacheadas y el estado de las luces animadas.
    No conoce a los combatientes: solo dibuja el decorado.
    """

    def __init__(self, width: int = SCREEN_WIDTH, height: int = SCREEN_HEIGHT) -> None:
        self.width = width
        self.height = height
        self.time = 0.0
        self.shake = 0.0
        self._stars: List[Tuple[int, int, int]] = self._build_stars()
        self._background = self._build_background()
        self._lights: List[Tuple[int, int, Color, float, float]] = self._build_lights()
        self._offset = (0, 0)

    # ------------------------------------------------------------------
    # Construccion (una sola vez)
    # ------------------------------------------------------------------
    def _build_stars(self) -> List[Tuple[int, int, int]]:
        """Estrellas de fondo con brillo y tamaño variables."""
        stars = []
        for _ in range(150):
            x = random.randint(0, self.width)
            y = random.randint(0, int(self.height * 0.55))
            size = random.choice([1, 1, 1, 2])
            stars.append((x, y, size))
        return stars

    def _build_lights(self) -> List[Tuple[int, int, Color, float, float]]:
        """Torres de luz del fondo: posicion, color, radio y velocidad."""
        palette = [
            (108, 208, 255),
            (168, 120, 255),
            (255, 150, 110),
            (120, 240, 210),
        ]
        lights = []
        for _ in range(9):
            lights.append(
                (
                    random.randint(ARENA_LEFT, ARENA_RIGHT),
                    random.randint(90, FLOOR_Y - 60),
                    random.choice(palette),
                    random.uniform(2.0, 5.0),
                    random.uniform(0.4, 1.4),
                )
            )
        return lights

    def _build_background(self) -> pygame.Surface:
        """
        Dibuja el fondo estatico: degradado, skyline, paneles y rejilla.

        Se calcula una unica vez y se reutiliza como imagen de fondo.
        """
        surface = pygame.Surface((self.width, self.height)).convert()

        # 1. Degradado vertical del cielo.
        for y in range(self.height):
            progress = y / self.height
            color = (
                int(COLOR_BACKGROUND_TOP[0] + (COLOR_BACKGROUND_BOTTOM[0] - COLOR_BACKGROUND_TOP[0]) * progress),
                int(COLOR_BACKGROUND_TOP[1] + (COLOR_BACKGROUND_BOTTOM[1] - COLOR_BACKGROUND_TOP[1]) * progress),
                int(COLOR_BACKGROUND_TOP[2] + (COLOR_BACKGROUND_BOTTOM[2] - COLOR_BACKGROUND_TOP[2]) * progress),
            )
            pygame.draw.line(surface, color, (0, y), (self.width, y))

        # 2. Estrellas.
        for x, y, size in self._stars:
            brightness = random.randint(90, 200)
            pygame.draw.circle(surface, (brightness, brightness, 235), (x, y), size)

        # 3. Horizonte luminoso detras de la arena.
        glow = pygame.Surface((self.width, 180), pygame.SRCALPHA)
        for index in range(180):
            alpha = int(70 * (1.0 - index / 180.0) ** 2)
            pygame.draw.line(glow, (70, 130, 220, alpha), (0, index), (self.width, index))
        surface.blit(glow, (0, FLOOR_Y - 180))

        # 4. Skyline: tres capas de edificios con distinto tono.
        self._draw_skyline(surface, base_y=FLOOR_Y - 20, count=16, height=210, color=(20, 24, 52))
        self._draw_skyline(surface, base_y=FLOOR_Y - 10, count=12, height=140, color=(26, 30, 62))
        self._draw_skyline(surface, base_y=FLOOR_Y, count=9, height=80, color=(32, 38, 78))

        # 5. Rejilla tecnologica en el suelo (perspectiva falsa).
        self._draw_grid(surface)

        # 6. Barras de interfaz lateral de la arena.
        pygame.draw.rect(surface, (24, 30, 62), pygame.Rect(0, 0, 26, self.height))
        pygame.draw.rect(surface, (24, 30, 62), pygame.Rect(self.width - 26, 0, 26, self.height))
        for y in range(0, self.height, 40):
            pygame.draw.line(surface, (40, 52, 96), (0, y), (26, y))
            pygame.draw.line(surface, (40, 52, 96), (self.width - 26, y), (self.width, y))

        return surface

    def _draw_skyline(
        self, surface: pygame.Surface, base_y: int, count: int, height: int, color: Color
    ) -> None:
        """Capa de edificios con ventanas encendidas."""
        span = (ARENA_RIGHT - ARENA_LEFT) / count
        for index in range(count):
            x = int(ARENA_LEFT + index * span)
            width = int(span * 0.82)
            building_height = int(height * random.uniform(0.45, 1.0))
            top = base_y - building_height
            pygame.draw.rect(surface, color, pygame.Rect(x, top, width, building_height))
            # Antena / detalle superior
            if index % 3 == 0:
                pygame.draw.rect(
                    surface, shade(color, 1.25), pygame.Rect(x + width // 3, top - 22, 4, 22)
                )
            # Ventanas
            for wy in range(top + 12, base_y - 10, 18):
                for wx in range(x + 8, x + width - 8, 14):
                    if random.random() < 0.32:
                        lit = random.choice([(90, 200, 255), (255, 200, 120), (160, 130, 255)])
                        pygame.draw.rect(surface, lit, pygame.Rect(wx, wy, 6, 8))

    def _draw_grid(self, surface: pygame.Surface) -> None:
        """Rejilla en perspectiva bajo la arena."""
        grid_color = (46, 62, 118)
        center_x = self.width // 2
        for row in range(10):
            y = FLOOR_Y + 8 + row * row * 2
            alpha_factor = max(0.15, 1.0 - row / 10.0)
            color = (
                int(grid_color[0] * alpha_factor),
                int(grid_color[1] * alpha_factor),
                int(grid_color[2] * alpha_factor),
            )
            pygame.draw.line(surface, color, (0, y), (self.width, y))
        for column in range(-10, 11):
            x_bottom = center_x + column * 150
            x_top = center_x + column * 26
            pygame.draw.line(
                surface, (34, 46, 92), (x_top, FLOOR_Y), (x_bottom, self.height)
            )

    # ------------------------------------------------------------------
    # Animacion
    # ------------------------------------------------------------------
    def update(self, delta_time: float) -> None:
        """Avanza las luces y amortigua la vibracion de camara."""
        self.time += delta_time
        if self.shake > 0.0:
            self.shake = max(0.0, self.shake - delta_time * 26.0)
            self._offset = (
                random.uniform(-self.shake, self.shake),
                random.uniform(-self.shake, self.shake),
            )
        else:
            self._offset = (0, 0)

    def add_shake(self, amount: float) -> None:
        """Pide una vibracion de camara (impactos y caidas)."""
        self.shake = min(14.0, self.shake + amount)

    @property
    def camera_offset(self) -> Tuple[int, int]:
        """Desplazamiento actual de la camara."""
        return int(self._offset[0]), int(self._offset[1])

    # ------------------------------------------------------------------
    # Dibujo
    # ------------------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        """Dibuja el decorado completo de la arena."""
        surface.blit(self._background, self._offset)
        self._draw_lights(surface)
        self._draw_floor(surface)
        self._draw_platforms(surface)

    def draw_backdrop(self, surface: pygame.Surface, dim: int = 0) -> None:
        """
        Dibuja solo el fondo lejano (cielo, estrellas y luces), sin el suelo.

        Lo reutilizan los menus, que comparten la ambientacion de la arena pero
        necesitan el espacio libre para los paneles. ``dim`` oscurece el fondo
        para que el texto del menu destaque.
        """
        surface.blit(self._background, self._offset)
        self._draw_lights(surface)
        if dim > 0:
            shade_surface = pygame.Surface((surface.get_width(), surface.get_height()), pygame.SRCALPHA)
            shade_surface.fill((4, 6, 16, min(255, dim)))
            surface.blit(shade_surface, (0, 0))

    def _draw_lights(self, surface: pygame.Surface) -> None:
        """Halos de luz pulsantes del fondo."""
        dx, dy = self._offset
        for x, y, color, radius, speed in self._lights:
            pulse = 0.5 + 0.5 * math.sin(self.time * speed)
            current = max(1.0, radius * (0.7 + 0.5 * pulse))
            size = int(current * 8)
            glow = pygame.Surface((size, size), pygame.SRCALPHA)
            for index in range(5, 0, -1):
                alpha = int(14 * pulse)
                pygame.draw.circle(
                    glow,
                    (*color, alpha),
                    (size // 2, size // 2),
                    int(current * index),
                    width=2,
                )
            surface.blit(glow, (x + dx - size // 2, y + dy - size // 2))

    def _draw_floor(self, surface: pygame.Surface) -> None:
        """Plataforma base con linea de energia animada."""
        dx, dy = self._offset
        floor_rect = pygame.Rect(ARENA_LEFT - 40 + dx, FLOOR_Y + dy, ARENA_RIGHT - ARENA_LEFT + 80, 26)
        pygame.draw.rect(surface, COLOR_FLOOR, floor_rect)

        # Bordes metalicos
        pygame.draw.line(
            surface,
            COLOR_FLOOR_LIGHT,
            (floor_rect.left, floor_rect.top),
            (floor_rect.right, floor_rect.top),
            2,
        )
        for x in range(floor_rect.left + 20, floor_rect.right, 46):
            pygame.draw.line(
                surface,
                shade(COLOR_FLOOR, 1.35),
                (x, floor_rect.top + 6),
                (x + 18, floor_rect.bottom - 4),
                2,
            )

        # Linea de energia que recorre el suelo
        sweep_x = ARENA_LEFT + (self.time * 160.0) % (ARENA_RIGHT - ARENA_LEFT)
        pygame.draw.line(
            surface, (120, 230, 255), (sweep_x + dx, floor_rect.top + 3), (sweep_x + dx + 60, floor_rect.top + 3), 3
        )

    def _draw_platforms(self, surface: pygame.Surface) -> None:
        """Plataformas laterales con borde luminoso."""
        dx, dy = self._offset
        for x, y, width, height in PLATFORM_RECTS:
            rect = pygame.Rect(x + dx, y + dy, width, height)
            pygame.draw.rect(surface, COLOR_PLATFORM, rect, border_radius=4)
            pygame.draw.rect(surface, COLOR_PLATFORM_EDGE, rect, width=2, border_radius=4)
            # Ranuras de ventilacion
            for slot in range(4):
                slot_x = rect.left + 18 + slot * (width - 40) // 4
                pygame.draw.rect(
                    surface,
                    shade(COLOR_PLATFORM, 0.72),
                    pygame.Rect(slot_x, rect.top + 5, 20, height - 10),
                )
