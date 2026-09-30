"""
MECHA ARENA - entities/player.py
===============================================================
El Mecha controlado por la persona jugadora: TITAN-X.

Responsabilidades:
    - Traducir la entrada del jugador en intencion de juego (mover, saltar,
      atacar).
    - Gestionar la energia que consume el arma de disparo.
    - Alternar entre el arma cuerpo a cuerpo y el arma de energia.
    - Mantener la especificidad del Mecha jugador separada de la IA enemiga.
"""

from __future__ import annotations

from mecha_arena.domain.mecha import Faction, Mecha, MechaPalette, MechaStats
from mecha_arena.domain.weapon import (
    FUSION_BLADE,
    PRIMARY,
    PULSE_CANNON,
    SECONDARY,
    WeaponSpec,
)
from mecha_arena.settings import MUZZLE_FLASH_TIME

#: Coste de energia por disparo y energia regenerada por segundo.
ENERGY_PER_SHOT = 12.0
ENERGY_REGEN = 26.0
#: Tiempo que se ve el cannon de energia tras disparar.
WEAPON_HOLD = 0.28


class Player(Mecha):
    """
    TITAN-X: el Mecha del jugador.

    Hereda todo el comportamiento de combate de :class:`Mecha` y solo implementa
    la reaccion a la entrada humana. Lleva dos armas: la espada de fusion
    (J, cuerpo a cuerpo) y el canon de pulso (K, energia).
    """

    def __init__(
        self,
        x: float,
        y: float,
        name: str = "TITAN-X",
        stats: MechaStats = None,          # type: ignore[assignment]
        weapon_spec: WeaponSpec = FUSION_BLADE,
        energy_weapon: WeaponSpec = PULSE_CANNON,
    ) -> None:
        base_stats = stats or MechaStats(
            max_health=120.0,
            attack=12.0,
            defense=5.0,
            move_speed=340.0,
            jump_force=800.0,
            move_accel=2900.0,
            body_width=48,
            body_height=90,
        )
        palette = MechaPalette(
            primary=(58, 122, 196),
            secondary=(30, 62, 118),
            metal=(176, 190, 214),
            visor=(120, 245, 255),
            accent=(240, 196, 84),
            glow=(108, 208, 255),
        )
        super().__init__(
            name=name,
            faction=Faction.PLAYER,
            stats=base_stats,
            palette=palette,
            weapon_spec=weapon_spec,
            x=x,
            y=y,
            facing=1,
            secondary_spec=energy_weapon,
        )

    # ------------------------------------------------------------------
    # Comportamiento
    # ------------------------------------------------------------------
    def _think(self, delta_time: float, world) -> None:
        """Aplica la entrada del jugador sobre el estado del Mecha."""
        if not self.can_act:
            return

        self._update_energy(delta_time)
        self._handle_movement(world.input)
        self._handle_attacks(world)

    def _update_energy(self, delta_time: float) -> None:
        """Regenera energia de forma continua."""
        self.restore_energy(ENERGY_REGEN * delta_time)

    def _handle_movement(self, input_state) -> None:
        """Fija la intencion de movimiento y gestiona el salto."""
        axis = input_state.move_axis()
        # ``None`` -> frenar. La aceleracion y el frenado los resuelve physics.
        self.move_intent = axis * self.stats.move_speed if axis != 0.0 else None

        if axis != 0.0:
            self.facing = 1 if axis > 0 else -1

        if input_state.jump_pressed():
            self.try_jump()

        # Altura variable: soltar el salto antes corta el impulso.
        if not input_state.jump_held() and self.vy < -220.0:
            self.vy = -220.0

    def _handle_attacks(self, world) -> None:
        """Gestiona J (cuerpo a cuerpo) y K (energia)."""
        input_state = world.input

        if input_state.melee_pressed():
            self._melee_attack()
        if input_state.energy_pressed():
            self._energy_attack(world)

    def _melee_attack(self) -> None:
        """Golpe con el arma cuerpo a cuerpo (J)."""
        if not self.weapon.spec.is_melee or self.weapon.is_swinging:
            return
        self.equip(PRIMARY)
        self.try_attack()

    def _energy_attack(self, world) -> None:
        """Disparo de energia (K), con coste y fogonazo."""
        if self.energy < ENERGY_PER_SHOT or not self.loadout.has(SECONDARY):
            return
        # No se interrumpe un golpe cuerpo a cuerpo en curso.
        if self.loadout.weapon_of(PRIMARY).is_swinging:
            return

        self.equip(SECONDARY, hold=WEAPON_HOLD)
        if not self.weapon.fire():
            return

        self.energy -= ENERGY_PER_SHOT
        self.muzzle_flash = MUZZLE_FLASH_TIME
        world.spawn_projectile(self, self.weapon.spec)

    # ------------------------------------------------------------------
    # Consultas para la interfaz
    # ------------------------------------------------------------------
    @property
    def energy_ratio(self) -> float:
        """Energia disponible expresada en 0.0 - 1.0."""
        return max(0.0, min(1.0, self.energy / 100.0))

    @property
    def can_fire_energy(self) -> bool:
        """True si hay energia y el arma de energia esta lista."""
        weapon = self.loadout.weapon_of(SECONDARY)
        return self.energy >= ENERGY_PER_SHOT and weapon is not None and weapon.can_fire

    def reset_for_round(self, x: float, y: float) -> None:
        """Prepara al jugador para el inicio de una ronda."""
        self.respawn(x, y)
