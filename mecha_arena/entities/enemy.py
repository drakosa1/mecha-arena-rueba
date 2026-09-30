"""
MECHA ARENA - entities/enemy.py
===============================================================
OMEGA-7: el Mecha controlado por la computadora.

La entidad no decide nada: delega el comportamiento en un controlador de IA
(``systems.ai.EnemyAI``) a traves de una interfaz minima. Asi se puede
cambiar el comportamiento sin tocar el Mecha, y anadir otro tipo de rival
(aliado, entrenador, jefe) solo requiere implementar la misma interfaz.
"""

from __future__ import annotations

from mecha_arena.domain.mecha import Faction, Mecha, MechaPalette, MechaStats
from mecha_arena.domain.weapon import HEAVY_CANNON, PLASMA_RIFLE, WeaponSpec

#: Interfaz minima que debe cumplir un controlador de comportamiento.
AI_PROTOCOL = ("update", "reset")


class Enemy(Mecha):
    """
    OMEGA-7: rival de la arena.

    Lleva dos armas: el canon pesado (cuerpo a cuerpo) y el rifle de plasma
    (a distancia). El ataque se divide entre ambas segun la distancia y el
    estado del combate, que es justo lo que decide ``EnemyAI``.
    """

    def __init__(
        self,
        x: float,
        y: float,
        name: str = "OMEGA-7",
        stats: MechaStats = None,          # type: ignore[assignment]
        weapon_spec: WeaponSpec = HEAVY_CANNON,
        ranged_weapon: WeaponSpec = PLASMA_RIFLE,
    ) -> None:
        base_stats = stats or MechaStats(
            max_health=110.0,
            attack=12.0,
            defense=3.0,
            move_speed=300.0,
            jump_force=760.0,
            move_accel=2400.0,
            body_width=52,
            body_height=96,
        )
        palette = MechaPalette(
            primary=(168, 62, 74),
            secondary=(92, 30, 48),
            metal=(150, 146, 162),
            visor=(255, 196, 90),
            accent=(255, 132, 96),
            glow=(255, 120, 90),
        )
        super().__init__(
            name=name,
            faction=Faction.ENEMY,
            stats=base_stats,
            palette=palette,
            weapon_spec=weapon_spec,
            x=x,
            y=y,
            facing=-1,
            secondary_spec=ranged_weapon,
        )

        #: Distancia a la que cuerpo a cuerpo resulta comodo.
        self.preferred_range = self.stats.body_width * 1.05
        #: Distancia de la que se considera "corto alcance" para el rifle.
        self.ranged_range = 320.0
        #: Controlador de comportamiento. ``None`` = aproximacion basica.
        self.ai = None

    # ------------------------------------------------------------------
    # Comportamiento
    # ------------------------------------------------------------------
    def _think(self, delta_time: float, world) -> None:
        """
        Punto unico de entrada del comportamiento.

        Si hay un controlador de IA conectado, manda el; si no, se aplica la
        aproximacion basica de la FASE 1.
        """
        if self.ai is not None:
            self.ai.update(self, delta_time, world)
        else:
            self._basic_approach(world.player)

    def _basic_approach(self, target) -> None:
        """FASE 1: caminar hacia el jugador y golpear si esta al alcance."""
        if not self.can_act or target is None or not target.is_alive:
            self.move_intent = None
            return

        self.face_towards(target.x)
        if abs(target.x - self.x) > self.preferred_range:
            self.move_intent = self.facing * self.stats.move_speed
        else:
            self.move_intent = None
            self.try_attack()

    # ------------------------------------------------------------------
    # API para la IA
    # ------------------------------------------------------------------
    def set_ai(self, ai_controller) -> None:
        """Conecta un controlador de comportamiento (FASE 2)."""
        for method in AI_PROTOCOL:
            if not callable(getattr(ai_controller, method, None)):
                raise TypeError(
                    f"El controlador de IA debe implementar '{method}()'"
                )
        self.ai = ai_controller
        ai_controller.reset()

    def reset_for_round(self, x: float, y: float) -> None:
        """Prepara al enemigo para el inicio de una ronda."""
        self.respawn(x, y)
        if self.ai is not None:
            self.ai.reset()
