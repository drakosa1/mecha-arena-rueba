"""
MECHA ARENA - domain/mecha.py
===============================================================
Capa de dominio: el Mecha, robot base de todos los combatientes.

Responsabilidades:
    - Concentrar las estadisticas de combate (vida, ataque, defensa, velocidad).
    - Gestionar el estado fisico basico (posicion, velocidad, suelo).
    - Aplicar y calcular el dano recibido.
    - Definir el flujo de actualizacion por plantilla (Template Method),
      de modo que las subclases solo aporten su comportamiento propio.

Sin pygame: la geometria se expone como coordenadas simples y la capa de
sistemas construye las cajas de colision.
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from mecha_arena.domain.weapon import SECONDARY, Weapon, WeaponLoadout, WeaponSpec

#: Probabilidad de que un impacto resulte en un golpe critico.
CRIT_CHANCE = 0.10
#: Multiplicador de dano de un golpe critico.
CRIT_MULTIPLIER = 1.6
#: Constante de la curva de mitigacion: cuanto mayor, mejor se defiende.
DEFENSE_CONSTANT = 8.0


# ---------------------------------------------------------------------------
# Tipos de apoyo
# ---------------------------------------------------------------------------


class Faction(str, Enum):
    """Bando al que pertenece un Mecha."""

    PLAYER = "player"
    ENEMY = "enemy"
    NEUTRAL = "neutral"

@dataclass(frozen=True)
class MechaStats:
    """Estadisticas base de combate de un Mecha."""

    max_health: float = 100.0
    attack: float = 10.0
    defense: float = 4.0
    move_speed: float = 320.0   # px/s horizontal
    jump_force: float = 780.0   # px/s vertical inicial del salto
    move_accel: float = 2800.0  # px/s^2 de aceleracion en el suelo
    body_width: int = 46
    body_height: int = 86


@dataclass(frozen=True)
class MechaPalette:
    """Colores de las piezas dibujadas por codigo."""

    primary: Tuple[int, int, int]
    secondary: Tuple[int, int, int]
    metal: Tuple[int, int, int]
    visor: Tuple[int, int, int]
    accent: Tuple[int, int, int]
    glow: Tuple[int, int, int]


@dataclass(frozen=True)
class MechaSpec:
    """
    Ficha de un Mecha jugable: identidad, combate, armas y precio.

    Es la unidad de contenido del juego (lo que aparece en el menu de
    seleccion). Las entidades se construyen a partir de una ficha, de modo que
    anadir un Mecha nuevo es anadir una entrada y nada mas.
    """

    key: str
    name: str
    tagline: str
    stats: "MechaStats"
    palette: MechaPalette
    weapon_spec: WeaponSpec
    secondary_spec: Optional[WeaponSpec] = None
    price: int = 0
    difficulty: int = 1     # 1 = facil, 5 = experto

    @property
    def is_free(self) -> bool:
        """True si se puede elegir sin pagar."""
        return self.price <= 0


@dataclass
class DamageReport:
    """Resultado de aplicar un golpe: lo consume la UI para los efectos."""

    dealt: float = 0.0
    blocked: float = 0.0
    critical: bool = False
    killed: bool = False
    impact_x: float = 0.0
    impact_y: float = 0.0

    @property
    def hit_landed(self) -> bool:
        return self.dealt > 0.0


# ---------------------------------------------------------------------------
# Mecha
# ---------------------------------------------------------------------------


class Mecha(ABC):
    """
    Robot de combate base.

    Las coordenadas ``x``/``y`` representan el centro horizontal y la planta
    de los pies, que es la referencia natural para el suelo de la arena.
    """

    def __init__(
        self,
        name: str,
        faction: Faction,
        stats: MechaStats,
        palette: MechaPalette,
        weapon_spec: WeaponSpec,
        x: float = 0.0,
        y: float = 0.0,
        facing: int = 1,
        secondary_spec: Optional[WeaponSpec] = None,
    ) -> None:
        self.name = name
        self.faction = faction
        self.stats = stats
        self.palette = palette
        self.loadout = WeaponLoadout(weapon_spec, secondary_spec)

        # -- Estado fisico ------------------------------------------------
        self.x = float(x)
        self.y = float(y)
        self.vx = 0.0
        self.vy = 0.0
        self.facing = 1 if facing >= 0 else -1
        self.on_ground = False
        #: Velocidad horizontal deseada. ``None`` significa "frenar".
        self.move_intent: Optional[float] = None

        # -- Estado de combate --------------------------------------------
        self.health = stats.max_health
        self.alive = True
        self.hit_flash = 0.0          # destello blanco al recibir dano
        self.invuln_timer = 0.0       # invulnerabilidad breve tras un golpe
        self.swing_connected = False  # un golpe solo puede tocar una vez
        self.energy = 100.0           # energia regenerativa para disparos
        self.muzzle_flash = 0.0       # fogonazo del arma de energia (efecto visual)
        self._equip_hold = 0.0        # tiempo que se mantiene un arma secundaria

        # Posicion de inicio, usada al reiniciar de ronda.
        self._spawn_point = (float(x), float(y))

    # ------------------------------------------------------------------
    # Propiedades de solo lectura
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Armas
    # ------------------------------------------------------------------
    @property
    def weapon(self) -> Weapon:
        """Arma activa en este momento (la que se dibuja y la que golpea)."""
        return self.loadout.current

    @property
    def secondary_spec(self) -> Optional[WeaponSpec]:
        """Ficha tecnica del arma secundaria, si la lleva."""
        return self.loadout.spec_of(SECONDARY)

    def equip(self, key: str, hold: float = 0.0) -> bool:
        """
        Equipa un arma concreta.

        :param hold: segundos que se mantiene equipada antes de volver a la
            principal. Un valor 0 deja el arma puesta de forma permanente.
        :return: True si la ranura existe.
        """
        if not self.loadout.equip(key):
            return False
        self._equip_hold = max(0.0, hold)
        return True

    def equip_primary(self) -> None:
        """Vuelve al arma principal de inmediato."""
        self.loadout.equip_primary()
        self._equip_hold = 0.0

    def try_jump(self) -> bool:
        """Salta si esta en el suelo. :return: True si el salto se lanzo."""
        if not self.can_act or not self.on_ground:
            return False
        self.vy = -self.stats.jump_force
        self.on_ground = False
        return True

    @property
    def health_ratio(self) -> float:
        """Vida actual expresada en 0.0 - 1.0."""
        if self.stats.max_health <= 0:
            return 0.0
        return max(0.0, min(1.0, self.health / self.stats.max_health))

    @property
    def is_alive(self) -> bool:
        return self.alive and self.health > 0.0

    @property
    def is_vulnerable(self) -> bool:
        """True si el Mecha puede recibir dano en este instante."""
        return self.is_alive and self.invuln_timer <= 0.0

    @property
    def can_act(self) -> bool:
        """True si el Mecha puede moverse y atacar (no esta aturdido)."""
        return self.is_alive

    @property
    def body_width(self) -> int:
        return self.stats.body_width

    @property
    def body_height(self) -> int:
        return self.stats.body_height

    @property
    def bounds(self) -> Tuple[float, float, float, float]:
        """Caja del cuerpo en pixeles: (izquierda, arriba, derecha, abajo)."""
        half = self.body_width / 2.0
        return (self.x - half, self.y - self.body_height, self.x + half, self.y)

    @property
    def center(self) -> Tuple[float, float]:
        """Centro del torso, usado como origen de la barra de vida flotante."""
        return (self.x, self.y - self.body_height * 0.55)

    # ------------------------------------------------------------------
    # Flujo de actualizacion
    # ------------------------------------------------------------------
    def update(self, delta_time: float, world) -> None:
        """
        Actualiza el Mecha (plantilla).

        1. Refresca los temporizadores comunes.
        2. Delega el comportamiento propio en :meth:`_think`.
        """
        self._update_timers(delta_time)
        self._think(delta_time, world)

    def _update_timers(self, delta_time: float) -> None:
        """Decrementa los temporizadores de estado comunes a todos los Mecha."""
        self.loadout.update(delta_time)
        self._update_equipment(delta_time)
        if self.hit_flash > 0.0:
            self.hit_flash = max(0.0, self.hit_flash - delta_time)
        if self.muzzle_flash > 0.0:
            self.muzzle_flash = max(0.0, self.muzzle_flash - delta_time)
        if self.invuln_timer > 0.0:
            self.invuln_timer = max(0.0, self.invuln_timer - delta_time)
        if self.swing_connected and not self.weapon.is_swinging:
            # El golpe termino: se rearma para el siguiente.
            self.swing_connected = False

    def _update_equipment(self, delta_time: float) -> None:
        """Vuelve al arma principal cuando expira el tiempo de permanencia."""
        if self._equip_hold <= 0.0:
            return
        self._equip_hold = max(0.0, self._equip_hold - delta_time)
        if self._equip_hold == 0.0:
            self.loadout.equip_primary()

    @abstractmethod
    def _think(self, delta_time: float, world) -> None:
        """Comportamiento especifico de cada robot (jugador o IA)."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Acciones de combate
    # ------------------------------------------------------------------
    def try_attack(self) -> bool:
        """
        Intenta iniciar un ataque con el arma equipada.

        :return: True si el ataque empezo.
        """
        if not self.can_act or not self.weapon.can_fire:
            return False
        if not self.weapon.fire():
            return False
        self.swing_connected = False
        return True

    def take_damage(
        self,
        amount: float,
        attacker_x: Optional[float] = None,
        knockback: float = 0.0,
    ) -> DamageReport:
        """
        Aplica un impacto de ``amount`` puntos.

        La defensa mitiga el dano con una curva asintotica, de forma que
        ningun blindaje vuelve al Mecha invulnerable.

        :return: informe del golpe, con el dano real aplicado.
        """
        if not self.is_vulnerable or amount <= 0.0:
            return DamageReport()

        mitigation = DEFENSE_CONSTANT / (DEFENSE_CONSTANT + max(0.0, self.stats.defense) * 1.6)
        effective = amount * (1.0 - mitigation)
        critical = random.random() < CRIT_CHANCE
        if critical:
            effective *= CRIT_MULTIPLIER

        dealt = min(effective, self.health)
        self.health = max(0.0, self.health - dealt)
        self.hit_flash = 0.16
        self.invuln_timer = 0.10

        report = DamageReport(
            dealt=dealt,
            blocked=amount - effective,
            critical=critical,
            impact_x=self.x,
            impact_y=self.y - self.body_height * 0.5,
        )

        if knockback:
            direction = self._knockback_direction(attacker_x)
            self.apply_knockback(direction, knockback)

        if self.health <= 0.0:
            self.alive = False
            report.killed = True
            self._on_death()
        return report

    def apply_knockback(self, direction: int, force: float) -> None:
        """Empuja al Mecha en horizontal y lo levanta ligeramente."""
        self.vx = max(-1200.0, min(1200.0, self.vx + direction * force))
        if self.on_ground:
            self.vy = -abs(force) * 0.35

    def face_towards(self, target_x: float) -> None:
        """Orienta el Mecha hacia la coordenada X indicada."""
        if abs(target_x - self.x) < 2.0:
            return
        self.facing = 1 if target_x > self.x else -1

    def heal(self, amount: float) -> None:
        """Recupera vida sin superar el maximo."""
        self.health = min(self.stats.max_health, self.health + amount)

    def restore_energy(self, amount: float) -> None:
        """Recupera energia de disparo."""
        self.energy = min(100.0, self.energy + amount)

    def _knockback_direction(self, attacker_x: Optional[float]) -> int:
        """Direccion del empuje: en frente del atacante, o a la derecha."""
        if attacker_x is None:
            return 1 if self.facing < 0 else -1
        return 1 if attacker_x <= self.x else -1

    def _on_death(self) -> None:
        """Enganche ejecutado cuando la vida llega a cero."""
        self.vx = 0.0

    # ------------------------------------------------------------------
    # Gestion de rondas
    # ------------------------------------------------------------------
    def respawn(self, x: Optional[float] = None, y: Optional[float] = None) -> None:
        """Devuelve el Mecha a su punto de inicio con todos los estados limpios."""
        spawn_x, spawn_y = self._spawn_point
        self.x = float(x) if x is not None else spawn_x
        self.y = float(y) if y is not None else spawn_y
        self.vx = 0.0
        self.vy = 0.0
        self.move_intent = None
        self.health = self.stats.max_health
        self.energy = 100.0
        self.alive = True
        self.hit_flash = 0.0
        self.invuln_timer = 0.0
        self.muzzle_flash = 0.0
        self.swing_connected = False
        self.on_ground = False
        self._equip_hold = 0.0
        self.loadout.reset()
