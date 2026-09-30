"""
MECHA ARENA - domain/combat.py
===============================================================
CombateSystem: arbitro de los intercambios de golpes.

Responsabilidades:
    - Aplicar las reglas de golpe cuerpo a cuerpo y de proyectil.
    - Recoger los eventos de combate (impactos, proyectiles, caidas) que la
      UI convertira en destellos, particulas y sonido.
    - Gestionar el marcador de rondas y el resultado del combate.

No conoce pygame: recibe los impactos ya resueltos por ``systems.collision``
y devuelve una lista de eventos. Asi la logica de combate es testeable.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from mecha_arena.domain.mecha import DamageReport
from mecha_arena.settings import ROUNDS_TO_WIN, ROUND_TIME


class CombatEventType(str, Enum):
    """Tipos de evento que la capa de presentacion sabe representar."""

    MELEE_HIT = "melee_hit"
    PROJECTILE_HIT = "projectile_hit"
    DODGE = "dodge"
    DEATH = "death"
    ROUND_START = "round_start"
    ROUND_END = "round_end"
    MATCH_END = "match_end"


@dataclass
class CombatEvent:
    """Evento de combate ya resuelto, listo para ser dibujado."""

    event_type: CombatEventType
    position: tuple = (0.0, 0.0)
    amount: float = 0.0
    critical: bool = False
    direction: int = 1
    attacker: str = ""
    defender: str = ""


class RoundResult(str, Enum):
    """Resultado de una ronda."""

    ONGOING = "ongoing"
    PLAYER_WINS = "player_wins"
    ENEMY_WINS = "enemy_wins"


@dataclass
class RoundState:
    """Marcador de una ronda concreta."""

    number: int = 1
    player_score: int = 0
    enemy_score: int = 0
    time_left: float = ROUND_TIME
    state: RoundResult = RoundResult.ONGOING
    ended_by_timeout: bool = False

    @property
    def is_over(self) -> bool:
        return self.state is not RoundResult.ONGOING


class CombatSystem:
    """
    Arbitro del combate.

    Recibe el jugador y el enemigo, aplica las reglas de impacto delegando en
    el sistema de colisiones, y mantiene el estado de las rondas.
    """

    def __init__(self, player, enemy, rounds_to_win: int = ROUNDS_TO_WIN) -> None:
        self.player = player
        self.enemy = enemy
        self.rounds_to_win = rounds_to_win
        self.round = RoundState()
        self.events: List[CombatEvent] = []
        self._match_over = False

    # ------------------------------------------------------------------
    # Resolucion de impactos
    # ------------------------------------------------------------------
    def resolve_melee(self) -> None:
        """Aplica los golpes cuerpo a cuerpo de ambos Mecha en este fotograma."""
        from mecha_arena.systems import collision

        # El que ataca primero es el que conecta: el rival ya no puede
        # responder en el mismo fotograma por la invulnerabilidad breve.
        player_first = self.player.weapon.is_swinging and not self.player.swing_connected
        order = [(self.player, self.enemy), (self.enemy, self.player)]
        if not player_first:
            order.reverse()

        for attacker, defender in order:
            report = collision.resolve_melee_hit(attacker, defender)
            if report is not None and report.hit_landed:
                self._emit_melee(attacker, defender, report)

    def resolve_projectiles(self, projectiles: List) -> None:
        """Aplica los impactos de proyectil y retira los que ya no estan vivos."""
        from mecha_arena.systems import collision

        mechas = [self.player, self.enemy]
        for projectile, report in collision.resolve_projectile_hits(projectiles, mechas):
            if report.hit_landed:
                self.events.append(
                    CombatEvent(
                        event_type=CombatEventType.PROJECTILE_HIT,
                        position=(report.impact_x, report.impact_y),
                        amount=report.dealt,
                        critical=report.critical,
                        direction=projectile.direction,
                        attacker=projectile.owner_name,
                        defender=(
                            self.enemy.name
                            if projectile.owner is self.player.faction
                            else self.player.name
                        ),
                    )
                )
                if report.killed:
                    self._emit_death(self.enemy if projectile.owner is self.player.faction else self.player)

        projectiles[:] = [p for p in projectiles if p.alive]

    def _emit_melee(self, attacker, defender, report: DamageReport) -> None:
        """Registra el evento visual de un golpe cuerpo a cuerpo."""
        self.events.append(
            CombatEvent(
                event_type=CombatEventType.MELEE_HIT,
                position=(report.impact_x, report.impact_y),
                amount=report.dealt,
                critical=report.critical,
                direction=attacker.facing,
                attacker=attacker.name,
                defender=defender.name,
            )
        )
        if report.killed:
            self._emit_death(defender)

    def _emit_death(self, dead_mecha) -> None:
        """Registra la caida de un Mecha."""
        self.events.append(
            CombatEvent(
                event_type=CombatEventType.DEATH,
                position=(dead_mecha.x, dead_mecha.y - dead_mecha.body_height / 2),
                attacker=(
                    self.player.name if dead_mecha is self.enemy else self.enemy.name
                ),
                defender=dead_mecha.name,
            )
        )

    # ------------------------------------------------------------------
    # Rondas
    # ------------------------------------------------------------------
    def tick_round(self, delta_time: float) -> None:
        """Avanza el reloj de la ronda y evalua su fin por tiempo."""
        if self.round.is_over:
            return
        self.round.time_left = max(0.0, self.round.time_left - delta_time)
        if self.round.time_left <= 0.0:
            # Al agotarse el tiempo gana quien conserve mas vida.
            if self.player.health_ratio >= self.enemy.health_ratio:
                self._end_round(RoundResult.PLAYER_WINS, by_timeout=True)
            else:
                self._end_round(RoundResult.ENEMY_WINS, by_timeout=True)

    def check_round_end(self) -> Optional[RoundResult]:
        """Comprueba si algun Mecha ha muerto y cierra la ronda."""
        if self.round.is_over:
            return self.round.state

        if not self.player.is_alive and not self.enemy.is_alive:
            result = (
                RoundResult.PLAYER_WINS
                if self.player.health_ratio >= self.enemy.health_ratio
                else RoundResult.ENEMY_WINS
            )
        elif not self.enemy.is_alive:
            result = RoundResult.PLAYER_WINS
        elif not self.player.is_alive:
            result = RoundResult.ENEMY_WINS
        else:
            return None

        self._end_round(result)
        return result

    def _end_round(self, result: RoundResult, by_timeout: bool = False) -> None:
        """Cierra la ronda, suma el marcador y avisa del fin de combate."""
        self.round.state = result
        self.round.ended_by_timeout = by_timeout
        if result is RoundResult.PLAYER_WINS:
            self.round.player_score += 1
        else:
            self.round.enemy_score += 1

        self.events.append(
            CombatEvent(
                event_type=CombatEventType.ROUND_END,
                position=(self.player.x, self.player.y - self.player.body_height),
                amount=self.round.time_left,
                attacker=(
                    self.player.name
                    if result is RoundResult.PLAYER_WINS
                    else self.enemy.name
                ),
            )
        )

        if self._player_reached_target() or self._enemy_reached_target():
            self._match_over = True
            self.events.append(
                CombatEvent(
                    event_type=CombatEventType.MATCH_END,
                    position=(self.player.x, self.player.y - self.player.body_height),
                    attacker=(
                        self.player.name
                        if result is RoundResult.PLAYER_WINS
                        else self.enemy.name
                    ),
                )
            )

    def _player_reached_target(self) -> bool:
        return self.round.player_score >= self.rounds_to_win

    def _enemy_reached_target(self) -> bool:
        return self.round.enemy_score >= self.rounds_to_win

    # ------------------------------------------------------------------
    # Estado
    # ------------------------------------------------------------------
    @property
    def match_over(self) -> bool:
        return self._match_over

    @property
    def winner_name(self) -> Optional[str]:
        """Nombre del Mecha ganador del combate, si lo hay."""
        if not self._match_over:
            return None
        if self.round.player_score > self.round.enemy_score:
            return self.player.name
        return self.enemy.name

    @property
    def match_winner(self):
        """Mecha ganador del combate, o ``None`` si aun no ha terminado."""
        if not self._match_over:
            return None
        if self.round.player_score > self.round.enemy_score:
            return self.player
        return self.enemy

    def start_next_round(self) -> None:
        """Prepara el marcador para la siguiente ronda."""
        self.round.number += 1
        self.round.time_left = ROUND_TIME
        self.round.state = RoundResult.ONGOING
        self.round.ended_by_timeout = False

    def consume_events(self) -> List[CombatEvent]:
        """Devuelve y limpia los eventos pendientes de este fotograma."""
        pending = self.events
        self.events = []
        return pending
