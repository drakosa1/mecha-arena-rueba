"""
MECHA ARENA - ui/fx.py
===============================================================
Efectos visuales de impacto y particulas simples.

Todo se genera por codigo (circulos y rectangulos), sin imagenes externas.
El sistema es deliberadamente pequeno: una lista de particulas con posicion,
velocidad, vida y color, actualizada y dibujada en cada fotograma.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List, Tuple

import pygame

Color = Tuple[int, int, int]


@dataclass
class Particle:
    """Particula individual: chispas, humo o destellos de impacto."""

    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    color: Color
    radius: float = 3.0
    gravity: float = 900.0
    drag: float = 0.9

    def update(self, delta_time: float) -> None:
        """Integra la particula y consume su vida."""
        self.vy += self.gravity * delta_time
        self.vx *= self.drag ** (delta_time * 60)
        self.x += self.vx * delta_time
        self.y += self.vy * delta_time
        self.life -= delta_time

    @property
    def alive(self) -> bool:
        return self.life > 0.0

    @property
    def fade(self) -> float:
        """Opacidad relativa: 1.0 al nacer, 0.0 al morir."""
        return max(0.0, min(1.0, self.life / self.max_life))


class ParticleSystem:
    """
   Gestor de particulas de la arena.

    Agrupa los efectos en familias (impacto, muerte, energia, polvo) con un
    metodo de generacion cada una, para que la logica de combate solo tenga
    que pedir "un impacto aqui" sin conocer los detalles del efecto.
    """

    def __init__(self) -> None:
        self._particles: List[Particle] = []
        self._floaters: List[Tuple[float, float, str, Color, float, float]] = []
        self._ripples: List[Tuple[float, float, float, Color]] = []

    # ------------------------------------------------------------------
    # Generadores de efectos
    # ------------------------------------------------------------------
    def spawn_impact(self, x: float, y: float, direction: int, critical: bool = False) -> None:
        """Chispas de impacto en la superficie de un golpe."""
        count = 16 if critical else 10
        speed = 340.0 if critical else 220.0
        for _ in range(count):
            angle = random.uniform(-math.pi * 0.9, math.pi * 0.9)
            magnitude = random.uniform(speed * 0.4, speed)
            color = (255, 240, 200) if critical else (200, 225, 255)
            self._particles.append(
                Particle(
                    x=x,
                    y=y,
                    vx=math.cos(angle) * magnitude * (1.0 if direction > 0 else -1) * 0.6
                    + direction * magnitude * 0.4,
                    vy=math.sin(angle) * magnitude - 60.0,
                    life=random.uniform(0.18, 0.42),
                    max_life=0.42,
                    color=color,
                    radius=random.uniform(1.5, 3.5),
                    gravity=1100.0,
                )
            )
        self._ripples.append((x, y, 6.0, (255, 255, 255) if critical else (170, 210, 255)))

    def spawn_energy_burst(self, x: float, y: float, direction: int) -> None:
        """Nube de energia al impactar un proyectil."""
        for _ in range(12):
            angle = random.uniform(0, math.tau)
            magnitude = random.uniform(80.0, 260.0)
            self._particles.append(
                Particle(
                    x=x,
                    y=y,
                    vx=math.cos(angle) * magnitude,
                    vy=math.sin(angle) * magnitude,
                    life=random.uniform(0.2, 0.5),
                    max_life=0.5,
                    color=(150, 225, 255),
                    radius=random.uniform(1.5, 4.0),
                    gravity=260.0,
                    drag=0.86,
                )
            )
        self._ripples.append((x, y, 10.0, (150, 225, 255)))

    def spawn_death(self, x: float, y: float) -> None:
        """Explosion de un Mecha derrotado."""
        for _ in range(34):
            angle = random.uniform(0, math.tau)
            magnitude = random.uniform(120.0, 460.0)
            warm = random.random() < 0.5
            self._particles.append(
                Particle(
                    x=x + random.uniform(-14, 14),
                    y=y + random.uniform(-30, 30),
                    vx=math.cos(angle) * magnitude,
                    vy=math.sin(angle) * magnitude - 120.0,
                    life=random.uniform(0.4, 1.0),
                    max_life=1.0,
                    color=(255, 190, 110) if warm else (255, 120, 90),
                    radius=random.uniform(2.0, 5.0),
                    gravity=760.0,
                    drag=0.9,
                )
            )
        self._ripples.append((x, y, 16.0, (255, 170, 90)))

    def spawn_charge(self, x: float, y: float, color: Color) -> None:
        """Anillo que se contrae: avisa de que va a haber un ataque."""
        self._ripples.append((x, y, 44.0, color))
        for _ in range(8):
            angle = random.uniform(0, math.tau)
            self._particles.append(
                Particle(
                    x=x + math.cos(angle) * 46.0,
                    y=y + math.sin(angle) * 46.0,
                    vx=-math.cos(angle) * 150.0,
                    vy=-math.sin(angle) * 150.0,
                    life=0.28,
                    max_life=0.28,
                    color=color,
                    radius=2.0,
                    gravity=0.0,
                    drag=0.9,
                )
            )

    def spawn_dust(self, x: float, y: float, direction: int) -> None:
        """Polvo levantado al aterrizar o al arrancar."""
        for _ in range(7):
            self._particles.append(
                Particle(
                    x=x + random.uniform(-10, 10),
                    y=y,
                    vx=direction * random.uniform(20.0, 90.0),
                    vy=-random.uniform(20.0, 70.0),
                    life=random.uniform(0.25, 0.55),
                    max_life=0.55,
                    color=(120, 130, 170),
                    radius=random.uniform(2.0, 5.0),
                    gravity=180.0,
                    drag=0.88,
                )
            )

    def spawn_damage_number(self, x: float, y: float, amount: float, critical: bool) -> None:
        """Numero de dano flotante que sube y se desvanece."""
        self._floaters.append(
            (
                x + random.uniform(-8, 8),
                y,
                f"{int(round(amount))}",
                (255, 226, 120) if critical else (255, 245, 220),
                0.0,
                0.85,
            )
        )

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------
    def update(self, delta_time: float) -> None:
        """Actualiza particulas, ondas y numeros flotantes."""
        for particle in self._particles:
            particle.update(delta_time)
        self._particles = [p for p in self._particles if p.alive]

        updated: List[Tuple[float, float, str, Color, float, float]] = []
        for x, y, text, color, age, life in self._floaters:
            age += delta_time
            if age < life:
                updated.append((x, y, text, color, age, life))
        self._floaters = updated

        self._ripples = [
            (x, y, radius + delta_time * 90.0, color) for x, y, radius, color in self._ripples
        ]
        self._ripples = [(x, y, r, c) for x, y, r, c in self._ripples if r < 60.0]

    def clear(self) -> None:
        """Borra todos los efectos (usado al reiniciar de ronda)."""
        self._particles.clear()
        self._floaters.clear()
        self._ripples.clear()

    @property
    def count(self) -> int:
        return len(self._particles)

    # ------------------------------------------------------------------
    # Dibujo
    # ------------------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        """Dibuja ondas, particulas y numeros de dano."""
        for x, y, radius, color in self._ripples:
            alpha = max(0, int(200 * (1.0 - radius / 60.0)))
            ring = pygame.Surface((int(radius * 2) + 4, int(radius * 2) + 4), pygame.SRCALPHA)
            pygame.draw.circle(
                ring, (*color, alpha), (int(radius) + 2, int(radius) + 2), int(radius), width=2
            )
            surface.blit(ring, (x - radius - 2, y - radius - 2))

        for particle in self._particles:
            alpha = int(235 * particle.fade)
            if alpha <= 0:
                continue
            dot = pygame.Surface((6, 6), pygame.SRCALPHA)
            pygame.draw.circle(
                dot,
                (*particle.color, alpha),
                (3, 3),
                max(1, int(particle.radius * particle.fade)),
            )
            surface.blit(dot, (particle.x - 3, particle.y - 3))

        self._draw_floaters(surface)

    def _draw_floaters(self, surface: pygame.Surface) -> None:
        """Dibuja los numeros de dano con desplazamiento vertical."""
        from mecha_arena.ui.fonts import render_text

        for x, y, text, color, age, life in self._floaters:
            progress = age / life
            offset = int(-34 * progress)
            alpha = 1.0 - progress
            shade = (
                int(color[0] * alpha + 20 * (1 - alpha)),
                int(color[1] * alpha + 20 * (1 - alpha)),
                int(color[2] * alpha + 30 * (1 - alpha)),
            )
            render_text(surface, text, 20, (int(x), int(y) + offset), shade, bold=True, anchor="center")
