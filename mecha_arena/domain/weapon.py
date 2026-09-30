"""
MECHA ARENA - domain/weapon.py
===============================================================
Capa de dominio: definicion de las armas de la arena.

Este modulo NO importa pygame. Solo trabaja con numeros, cadenas y
enumeraciones, de modo que las reglas de combate pueden probarse sin
abrir ninguna ventana grafica.

Responsabilidades:
    - Describir un arma con una ficha tecnica inmutable (WeaponSpec).
    - Controlar el estado de uso del arma: enfriamiento y animacion de golpe.
    - Exponer un catalogo de armas reutilizable por jugador y enemigos.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Ranuras de arma
# ---------------------------------------------------------------------------

#: Arma por defecto: cuerpo a cuerpo en el caso del jugador.
PRIMARY = "primary"
#: Arma secundaria: energia a distancia.
SECONDARY = "secondary"

# ---------------------------------------------------------------------------
# Tipos
# ---------------------------------------------------------------------------


class WeaponKind(str, Enum):
    """Familia funcional de un arma."""

    MELEE = "melee"     # golpe corto en cuerpo a cuerpo
    ENERGY = "energy"   # disparo a distancia


@dataclass(frozen=True)
class WeaponSpec:
    """
    Ficha tecnica inmutable de un arma.

    Todos los valores estan expresados en unidades de pantalla por segundo
    (px/s) para que el combate sea independiente de los fotogramas.
    """

    name: str
    kind: WeaponKind
    damage: float
    cooldown: float           # segundos que el arma queda bloqueada tras usarse
    reach: int                # alcance del golpe o del proyectil en pixeles
    swing_time: float = 0.22  # duracion de la animacion de golpe
    projectile_speed: float = 0.0
    projectile_radius: int = 6
    projectile_life: float = 1.8
    energy_cost: int = 0      # coste de energia (0 = sin limite)
    knockback: float = 0.0    # empuje aplicado al objetivo (px/s)
    glow: Tuple[int, int, int] = (120, 220, 255)

    @property
    def is_melee(self) -> bool:
        """True si el arma ataca cuerpo a cuerpo."""
        return self.kind is WeaponKind.MELEE

    @property
    def is_ranged(self) -> bool:
        """True si el arma dispara proyectiles."""
        return self.kind is WeaponKind.ENERGY


# ---------------------------------------------------------------------------
# Catalogo de armas
# ---------------------------------------------------------------------------

#: Arma cuerpo a cuerpo estandar: rapida, fiable y con buen empuje.
#: Su valor esta en el DPS: golpea a menudo, aunque poco cada vez.
FUSION_BLADE = WeaponSpec(
    name="Espada de Fusion",
    kind=WeaponKind.MELEE,
    damage=15.0,
    cooldown=0.34,
    reach=88,
    swing_time=0.22,
    knockback=190.0,
    glow=(120, 245, 255),
)

#: Arma pesada: golpe lento pero devastador.
#: El alcance es deliberadamente parecido al de la espada del jugador: si el
#: arma pesada llegase mas lejos, el rival golpearia desde fuera del alcance
#: del jugador y la fight seria injusta.
HEAVY_CANNON = WeaponSpec(
    name="Cañon Pesado",
    kind=WeaponKind.MELEE,
    damage=20.0,
    cooldown=0.72,
    reach=92,
    swing_time=0.34,
    knockback=330.0,
    glow=(255, 190, 90),
)

#: Arma de energia estandar del jugador.
PULSE_CANNON = WeaponSpec(
    name="Cañon de Pulso",
    kind=WeaponKind.ENERGY,
    damage=9.0,
    cooldown=0.42,
    reach=560,
    projectile_speed=780.0,
    projectile_radius=7,
    knockback=90.0,
    glow=(110, 200, 255),
)

#: Arma de energia rapida y ligera, ideal para enemigos a distancia.
PLASMA_RIFLE = WeaponSpec(
    name="Rifle de Plasma",
    kind=WeaponKind.ENERGY,
    damage=7.0,
    cooldown=0.30,
    reach=620,
    projectile_speed=900.0,
    projectile_radius=5,
    knockback=60.0,
    glow=(190, 130, 255),
)

#: Arma de energia potente y lenta.
SHOCK_CANNON = WeaponSpec(
    name="Cañon de Descarga",
    kind=WeaponKind.ENERGY,
    damage=17.0,
    cooldown=0.95,
    reach=700,
    projectile_speed=620.0,
    projectile_radius=11,
    knockback=220.0,
    glow=(255, 120, 90),
)


#: Arma ligera de NIMBO-X: cadencia muy alta a cambio de poco dano.
TWIN_LANCE = WeaponSpec(
    name="Lanza Gemela",
    kind=WeaponKind.MELEE,
    damage=9.0,
    cooldown=0.22,
    reach=76,
    swing_time=0.16,
    knockback=110.0,
    glow=(150, 255, 220),
)

#: Arma de energia de FENIX-01: dispara rapido, con precision de francotirador.
NEEDLE_RIFLE = WeaponSpec(
    name="Rifle de Aguja",
    kind=WeaponKind.ENERGY,
    damage=5.0,
    cooldown=0.20,
    reach=700,
    projectile_speed=1050.0,
    projectile_radius=4,
    knockback=40.0,
    glow=(255, 240, 160),
)


# ---------------------------------------------------------------------------
# Estado de uso del arma
# ---------------------------------------------------------------------------


class Weapon:
    """
    Arma concreta equipada por un Mecha.

    Encapsula el enfriamiento y la animacion de golpe, de forma que el Mecha
    solo necesita preguntar ``puede_atacar()`` y ``usar()``.
    """

    def __init__(self, spec: WeaponSpec) -> None:
        self.spec = spec
        self._cooldown_left = 0.0
        self._swing_left = 0.0

    # -- Consultas ---------------------------------------------------------
    @property
    def name(self) -> str:
        return self.spec.name

    @property
    def can_fire(self) -> bool:
        """True cuando el arma ya termino su enfriamiento."""
        return self._cooldown_left <= 0.0

    @property
    def is_swinging(self) -> bool:
        """True durante la ventana activa de un golpe cuerpo a cuerpo."""
        return self._swing_left > 0.0

    @property
    def swing_ratio(self) -> float:
        """Progreso de la animacion de golpe (0.0 -> 1.0)."""
        if self.spec.swing_time <= 0.0:
            return 0.0
        return 1.0 - (self._swing_left / self.spec.swing_time)

    @property
    def cooldown_ratio(self) -> float:
        """Progreso del enfriamiento (0 = listo, 1 = recien usado)."""
        if self.spec.cooldown <= 0.0:
            return 0.0
        return 1.0 - (self._cooldown_left / self.spec.cooldown)

    # -- Acciones ----------------------------------------------------------
    def update(self, delta_time: float) -> None:
        """Avanza los temporizadores internos del arma."""
        if self._cooldown_left > 0.0:
            self._cooldown_left = max(0.0, self._cooldown_left - delta_time)
        if self._swing_left > 0.0:
            self._swing_left = max(0.0, self._swing_left - delta_time)

    def fire(self) -> bool:
        """
        Intenta usar el arma.

        :return: True si el disparo se lanzo, False si estaba en enfriamiento.
        """
        if not self.can_fire:
            return False
        self._cooldown_left = self.spec.cooldown
        if self.spec.is_melee:
            self._swing_left = self.spec.swing_time
        return True

    def reset(self) -> None:
        """Deja el arma lista (usado al reiniciar una ronda)."""
        self._cooldown_left = 0.0
        self._swing_left = 0.0


class WeaponLoadout:
    """
    Conjunto de armas que lleva un Mecha, con gestion de la activa.

    Permite que un Mecha lleve varias armas sin duplicar codigo de
    enfriamiento: cada ranura tiene su propio :class:`Weapon` y todas se
    actualizan siempre, de modo que cambiar de arma no reinicia el
    enfriamiento de la anterior.
    """

    def __init__(self, primary: WeaponSpec, secondary: Optional[WeaponSpec] = None) -> None:
        self._slots: Dict[str, Weapon] = {PRIMARY: Weapon(primary)}
        self._order: List[str] = [PRIMARY]
        if secondary is not None:
            self._slots[SECONDARY] = Weapon(secondary)
            self._order.append(SECONDARY)
        self.active_key = PRIMARY

    # -- Consulta ---------------------------------------------------------
    @property
    def current(self) -> Weapon:
        """Arma equipada en este momento."""
        return self._slots[self.active_key]

    @property
    def current_key(self) -> str:
        """Ranura del arma equipada."""
        return self.active_key

    @property
    def keys(self) -> List[str]:
        """Ranuras disponibles, en orden de prioridad."""
        return list(self._order)

    def has(self, key: str) -> bool:
        """True si el Mecha lleva un arma en esa ranura."""
        return key in self._slots

    def weapon_of(self, key: str) -> Optional[Weapon]:
        """Arma de una ranura, o ``None`` si no existe."""
        return self._slots.get(key)

    def spec_of(self, key: str) -> Optional[WeaponSpec]:
        """Ficha tecnica del arma de una ranura, o ``None`` si no existe."""
        weapon = self._slots.get(key)
        return None if weapon is None else weapon.spec

    # -- Acciones ---------------------------------------------------------
    def equip(self, key: str) -> bool:
        """
        Equipa el arma de la ranura indicada.

        :return: True si el cambio se realizo.
        """
        if key not in self._slots:
            return False
        self.active_key = key
        return True

    def equip_primary(self) -> None:
        """Vuelve al arma principal."""
        self.active_key = PRIMARY

    def toggle(self) -> bool:
        """Alterna entre las dos armas disponibles."""
        if len(self._order) < 2:
            return False
        index = self._order.index(self.active_key)
        self.active_key = self._order[(index + 1) % len(self._order)]
        return True

    def update(self, delta_time: float) -> None:
        """Avanza los enfriamientos de todas las armas equipadas."""
        for weapon in self._slots.values():
            weapon.update(delta_time)

    def reset(self) -> None:
        """Reinicia TODOS los enfriamientos (nueva ronda)."""
        for weapon in self._slots.values():
            weapon.reset()
        self.active_key = PRIMARY
