"""
MECHA ARENA - systems/ai.py
===============================================================
Inteligencia artificial de OMEGA-7.

Implementa una maquina de estados finitos con las siguientes decisiones:

    APPROACH  acortar distancia hasta el cuerpo a cuerpo
    ENGAGE    golpear con el arma pesada cuando esta a tiro
    STALK     mantener la distancia media y disparar el rifle de plasma
    RETREAT   retroceder para recoverarse y evitar el castigo del jugador
    DODGE     saltar para esquivar un proyectil enemigo

Encima de la maquina hay dos ajustes que hacen que el rival no sea un robot
predecible:

    - ``reaction_time``: el enemigo no reacciona al instante, decide cada
      cierto tiempo. Sin este retardo esquivaria cualquier proyectil y seria
      invencible.
    - ``aggression`` y ``ranged_skill``: con valores altos ataca mas y dispara
      mas a distancia.

El controlador no dibuja ni toca pygame: solo fija ``move_intent``, llama a
los metodos de ataque del Mecha y pide proyectiles al mundo.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from mecha_arena.domain.weapon import PRIMARY, SECONDARY
from mecha_arena.settings import MUZZLE_FLASH_TIME


class AIState(Enum):
    """Estados posibles del rival."""

    APPROACH = "approach"
    ENGAGE = "engage"
    STALK = "stalk"
    RETREAT = "retreat"
    DODGE = "dodge"


@dataclass(frozen=True)
class AIProfile:
    """
    Ajustes de dificultad de la IA.

    Es inmutable: cada ronda usa un perfil distinto construido con
    :func:`profile_for_round`, lo que hace trivial mostrar la dificultad
    creciente en el HUD o en el menu.
    """

    name: str
    reaction_time: float = 0.22   # segundos entre decisiones
    aggression: float = 0.55      # 0.0 pasivo .. 1.0 agresivo
    ranged_skill: float = 0.35    # probabilidad de elegir disparo a distancia
    dodge_chance: float = 0.30    # probabilidad de esquivar un proyectil
    speed_scale: float = 1.0      # multiplicador de velocidad de aproximacion
    retreat_ratio: float = 0.35   # vida por debajo de la cual se retira mas


def profile_for_round(round_number: int) -> AIProfile:
    """
    Devuelve el perfil de dificultad de una ronda concreta.

    Cada ronda el rival es un poco mas rapido, decide antes y ataca mas.
    """
    level = max(0, round_number - 1)
    return AIProfile(
        name=f"NIVEL {level + 1}",
        reaction_time=max(0.08, 0.24 - level * 0.04),
        aggression=min(0.95, 0.55 + level * 0.12),
        ranged_skill=min(0.85, 0.35 + level * 0.12),
        dodge_chance=min(0.8, 0.30 + level * 0.1),
        speed_scale=min(1.25, 1.0 + level * 0.08),
        retreat_ratio=max(0.15, 0.35 - level * 0.05),
    )


class EnemyAI:
    """
    Controlador de comportamiento de OMEGA-7.

    Uso:
        enemy = Enemy(...)
        enemy.set_ai(EnemyAI(profile_for_round(1)))
    """

    def __init__(self, profile: Optional[AIProfile] = None) -> None:
        self.profile = profile or AIProfile(name="ENTRENAMIENTO")
        self.state = AIState.APPROACH
        self._decision_timer = 0.0
        self._retreat_timer = 0.0
        self._strafe_dir = 1
        self._strafe_timer = 0.0
        self._dodge_cooldown = 0.0
        self._last_health_ratio = 1.0

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------
    def reset(self) -> None:
        """Reinicia la IA al comienzo de una ronda."""
        self.state = AIState.APPROACH
        self._decision_timer = 0.0
        self._retreat_timer = 0.0
        self._strafe_dir = 1 if random.random() < 0.5 else -1
        self._strafe_timer = random.uniform(0.6, 1.2)
        self._dodge_cooldown = 0.0
        self._last_health_ratio = 1.0

    def set_profile(self, profile: AIProfile) -> None:
        """Cambia la dificultad en caliente (nueva ronda)."""
        self.profile = profile
        self.reset()

    # ------------------------------------------------------------------
    # Bucle principal
    # ------------------------------------------------------------------
    def update(self, enemy, delta_time: float, world) -> None:
        """
        Actualiza el comportamiento del enemigo.

        Se ejecuta una vez por fotograma, antes de la fisica.
        """
        target = world.player
        if not enemy.can_act or target is None or not target.is_alive:
            enemy.move_intent = None
            return

        enemy.face_towards(target.x)
        self._last_health_ratio = enemy.health_ratio
        self._tick_timers(delta_time)
        self._detect_incoming_threat(enemy, world)

        # La decision se renueva cada ``reaction_time`` segundos.
        if self._decision_timer <= 0.0:
            self._decide(enemy, target, world)
            self._decision_timer = self.profile.reaction_time * random.uniform(0.7, 1.3)

        self._act(enemy, target, world)

    @property
    def is_enraged(self) -> bool:
        """True cuando el rival esta por debajo del umbral de vida baja."""
        return self._last_health_ratio < self.profile.retreat_ratio

    def _tick_timers(self, delta_time: float) -> None:
        if self._decision_timer > 0.0:
            self._decision_timer = max(0.0, self._decision_timer - delta_time)
        if self._retreat_timer > 0.0:
            self._retreat_timer = max(0.0, self._retreat_timer - delta_time)
        if self._strafe_timer > 0.0:
            self._strafe_timer = max(0.0, self._strafe_timer - delta_time)
        if self._dodge_cooldown > 0.0:
            self._dodge_cooldown = max(0.0, self._dodge_cooldown - delta_time)

    # ------------------------------------------------------------------
    # Percepcion
    # ------------------------------------------------------------------
    def _detect_incoming_threat(self, enemy, world) -> None:
        """
        Salta a estado DODGE si un proyectil viene hacia el.

        Se compara la direccion del proyectil con la direccion que lleva al
        enemigo (no con la orientacion del enemigo, que mira justo al lado
        contrario). Asi el rival detecta el disparo antes de que le llegue.
        """
        # Sin enfriamiento el rival esquivaria en cadena y seria invencible.
        if self._dodge_cooldown > 0.0 or not enemy.on_ground:
            return

        for projectile in world.projectiles:
            if projectile.owner is enemy.faction or not projectile.alive:
                continue
            # Solo los proyectiles que se desplazan hacia el enemigo.
            heading = 1 if projectile.vx > 0 else -1
            toward_enemy = 1 if enemy.x >= projectile.x else -1
            if heading != toward_enemy:
                continue
            gap = abs(projectile.x - enemy.x)
            if gap < enemy.body_width * 3.0 and random.random() < self.profile.dodge_chance:
                self.state = AIState.DODGE
                self._decision_timer = self.profile.reaction_time
                self._dodge_cooldown = random.uniform(0.55, 0.95)
                return

    def _decide(self, enemy, target, world) -> None:
        """Elige el siguiente estado segun la distancia y la situacion."""
        distance = abs(target.x - enemy.x)
        vertical_gap = target.y - enemy.y

        # 1. Retirada breve: solo mientras dure el temporizador, o con una
        #    probabilidad baja cuando la vida es escasa. Si se evaluara la
        #    vida en cada decision, el rival se retiraria sin volver nunca.
        if self._retreat_timer > 0.0:
            self.state = AIState.RETREAT
            return
        if (
            self.is_enraged
            and distance < enemy.body_width * 2.0
            and random.random() < 0.35 * (1.0 - self.profile.aggression)
        ):
            self.state = AIState.RETREAT
            self._retreat_timer = random.uniform(0.3, 0.6)
            return

        # 2. Cuerpo a cuerpo si esta a tiro de la espada.
        if distance <= enemy.preferred_range * 1.6:
            self.state = AIState.ENGAGE
            return

        # 3. A distancia: disparo con el rifle o aproximacion.
        wants_ranged = (
            self.ranged_ready(enemy)
            and random.random() < self.profile.ranged_skill
        )
        if wants_ranged and distance <= enemy.ranged_range:
            self.state = AIState.STALK
            return

        # 4. Perseguir. Si el jugador esta en alto, salta para alcanzarlo.
        self.state = AIState.APPROACH
        if vertical_gap < -60.0 and distance < 260.0 and enemy.on_ground:
            if random.random() < self.profile.dodge_chance:
                enemy.try_jump()

    def ranged_ready(self, enemy) -> bool:
        """True si el arma secundaria del enemigo esta lista para disparar."""
        weapon = enemy.loadout.weapon_of(SECONDARY)
        return weapon is not None and weapon.spec.is_ranged and weapon.can_fire

    # ------------------------------------------------------------------
    # Accion
    # ------------------------------------------------------------------
    def _act(self, enemy, target, world) -> None:
        """Ejecuta el estado actual: fija intencion de movimiento y ataca."""
        distance = abs(target.x - enemy.x)

        if self.state is AIState.ENGAGE:
            self._act_engage(enemy, distance, world)
        elif self.state is AIState.STALK:
            self._act_stalk(enemy, distance, world)
        elif self.state is AIState.RETREAT:
            self._act_retreat(enemy, distance)
        elif self.state is AIState.DODGE:
            self._act_dodge(enemy, target)
        else:  # APPROACH
            self._act_approach(enemy, target, distance)

    def _act_approach(self, enemy, target, distance: float) -> None:
        """Avanza hacia el jugador acelerando si esta lejos."""
        speed = enemy.stats.move_speed * self.profile.speed_scale
        if distance > 260.0:
            speed *= 1.12
        if self.is_enraged:
            speed *= 1.15  # con poca vida, el rival se vuelve mas agresivo
        enemy.move_intent = enemy.facing * speed

    def _act_engage(self, enemy, distance: float, world) -> None:
        """Cuerpo a cuerpo: golpe corto y retirada para no encajar castigo."""
        if distance > enemy.preferred_range:
            enemy.move_intent = enemy.facing * enemy.stats.move_speed * self.profile.speed_scale
            return

        enemy.move_intent = None
        if enemy.equip(PRIMARY) and enemy.try_attack():
            # Aviso visual sincronizado con el inicio del golpe: el anillo se
            # contrae justo cuando el arma impacta.
            world.spawn_telegraph(enemy)
            # Tras conectar, se aparta un momento (evita golpe contra golpe).
            if random.random() < 0.4:
                self.state = AIState.RETREAT
                self._retreat_timer = random.uniform(0.25, 0.5)

    def _act_stalk(self, enemy, distance: float, world) -> None:
        """Mantiene la distancia media y dispara de vez en cuando."""
        # Se mueve en lateral para ser un blanco mas dificil.
        if self._strafe_timer <= 0.0:
            self._strafe_dir *= -1
            self._strafe_timer = random.uniform(0.7, 1.4)

        speed = enemy.stats.move_speed * 0.55 * self.profile.speed_scale
        if distance > enemy.ranged_range * 0.9:
            enemy.move_intent = enemy.facing * speed
        elif distance < enemy.preferred_range * 2.0:
            enemy.move_intent = -enemy.facing * speed
        else:
            enemy.move_intent = self._strafe_dir * speed * 0.5

        if not self.ranged_ready(enemy):
            return
        if random.random() > self.profile.ranged_skill * 0.5 + 0.2:
            return

        if enemy.equip(SECONDARY, hold=0.4) and enemy.weapon.fire():
            enemy.muzzle_flash = MUZZLE_FLASH_TIME
            world.spawn_telegraph(enemy)
            world.spawn_projectile(enemy, enemy.weapon.spec)

    def _act_retreat(self, enemy, distance: float) -> None:
        """Retrocede un momento para resetear el castigo del jugador."""
        enemy.move_intent = -enemy.facing * enemy.stats.move_speed * 0.85
        # La retirada siempre tiene final: al expirar, vuelve al combate.
        if self._retreat_timer <= 0.0 or distance > 220.0:
            self._retreat_timer = 0.0
            self.state = AIState.ENGAGE if distance < 160.0 else AIState.APPROACH
            self._decision_timer = 0.0

    def _act_dodge(self, enemy, target) -> None:
        """Salta hacia atras para esquivar y recupera el control."""
        if enemy.on_ground:
            enemy.try_jump()
            enemy.move_intent = -enemy.facing * enemy.stats.move_speed * 0.7
        else:
            # En el aire mantiene la inercia hasta aterrizar. El cambio de
            # estado llega cuando expira el temporador de decision.
            enemy.move_intent = -enemy.facing * enemy.stats.move_speed * 0.3
