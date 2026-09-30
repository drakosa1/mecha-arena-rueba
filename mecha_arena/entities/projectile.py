"""
MECHA ARENA - entities/projectile.py
===============================================================
Proyectiles de energia.

Un proyectil es una entidad autonoma con vida limitada: nace en el arma de
un Mecha, avanza en linea recta, puede chocar con el suelo, con las
plataformas y con el rival, y desaparece al expirar.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from mecha_arena.domain.mecha import Faction
from mecha_arena.domain.weapon import WeaponSpec
from mecha_arena.settings import GRAVITY, MAX_FALL_SPEED

#: Balas que no se ven afectadas por la gravedad (energia pura).
AFFECTED_BY_GRAVITY = False


@dataclass
class Projectile:
    """
    Bolt de energia disparado por un Mecha.

    No hereda de Mecha: un proyectil no tiene vida, ni arma, ni IA. Modelarlo
    como una entidad simple evita duplicar la jerarquia y deja el combate
    mas simple de extender.
    """

    x: float
    y: float
    vx: float
    damage: float
    radius: int
    owner: Faction
    owner_name: str
    vy: float = 0.0
    knockback: float = 0.0
    life: float = 1.8
    color: Tuple[int, int, int] = (120, 220, 255)
    direction: int = 1
    alive: bool = True
    gravity_scale: float = 1.0 if AFFECTED_BY_GRAVITY else 0.0

    @classmethod
    def from_weapon(
        cls,
        weapon: WeaponSpec,
        origin_x: float,
        origin_y: float,
        direction: int,
        owner: Faction,
        owner_name: str,
    ) -> "Projectile":
        """
        Crea un proyectil a partir de la ficha tecnica de un arma.

        :param origin_x: punto de salida en X (punta del arma).
        :param origin_y: punto de salida en Y.
        :param direction: 1 hacia la derecha, -1 hacia la izquierda.
        """
        return cls(
            x=origin_x,
            y=origin_y,
            vx=direction * weapon.projectile_speed,
            damage=weapon.damage,
            radius=weapon.projectile_radius,
            owner=owner,
            owner_name=owner_name,
            knockback=weapon.knockback,
            life=weapon.projectile_life,
            color=weapon.glow,
            direction=direction,
        )

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------
    def update(self, delta_time: float) -> None:
        """Avanza el proyectil y consume su tiempo de vida."""
        if not self.alive:
            return

        self.vy += GRAVITY * self.gravity_scale * delta_time
        if self.vy > MAX_FALL_SPEED:
            self.vy = MAX_FALL_SPEED

        self.x += self.vx * delta_time
        self.y += self.vy * delta_time
        self.life -= delta_time

        if self.life <= 0.0:
            self.alive = False

    def kill(self) -> None:
        """Desactiva el proyectil (impacto, salida de pantalla, etc.)."""
        self.alive = False

    # ------------------------------------------------------------------
    # Geometria
    # ------------------------------------------------------------------
    @property
    def rect(self) -> Tuple[float, float, float, float]:
        """Caja del proyectil: (izquierda, arriba, derecha, abajo)."""
        return (
            self.x - self.radius,
            self.y - self.radius,
            self.x + self.radius,
            self.y + self.radius,
        )

    @property
    def tail_x(self) -> float:
        """Punto de la estela, usado por la UI para dibujar el rastro."""
        return self.x - self.direction * self.radius * 2.6

    def collides_with(self, left: float, top: float, right: float, bottom: float) -> bool:
        """Comprueba solapamiento contra una caja dada (test AABB)."""
        p_left, p_top, p_right, p_bottom = self.rect
        return p_left < right and p_right > left and p_top < bottom and p_bottom > top

    def target(self, candidates) -> Optional[object]:
        """Primer objetivo valido de ``candidates`` (lista de Mecha)."""
        for mecha in candidates:
            if mecha.faction is self.owner or not mecha.is_alive:
                continue
            left, top, right, bottom = mecha.bounds
            if self.collides_with(left, top, right, bottom):
                return mecha
        return None
