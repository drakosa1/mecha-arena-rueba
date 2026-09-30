"""
MECHA ARENA - app.py
===============================================================
Bucle principal del juego y orquestador de sistemas.

``Game`` es el objeto que conoce a todas las capas y las hace colaborar:

    entrada -> entidades -> fisica -> colisiones -> combate -> efectos -> dibujo

Tambien es la ``puerta`` que las entidades usan para pedir cosas al mundo
(por ejemplo, lanzar un proyectil), de modo que estas no necesitan importar
la clase Game.
"""

from __future__ import annotations

from enum import Enum
from typing import List

import pygame

from mecha_arena import settings
from mecha_arena.domain.combat import CombatSystem
from mecha_arena.domain.combat import CombatEventType
from mecha_arena.domain.weapon import WeaponSpec
from mecha_arena.entities.projectile import Projectile
from mecha_arena.entities.roster import build_enemy, build_player
from mecha_arena.profile import PlayerProfile
from mecha_arena.systems import collision, physics
from mecha_arena.systems.ai import EnemyAI, profile_for_round
from mecha_arena.systems.input import InputState
from mecha_arena.ui.arena import Arena
from mecha_arena.ui.fonts import render_text
from mecha_arena.ui.fx import ParticleSystem
from mecha_arena.ui.hud import HUD
from mecha_arena.ui.menu import Menu
from mecha_arena.ui.mecha_renderer import MechaRenderer

#: Posiciones de inicio de cada combatiente.
PLAYER_SPAWN = (300.0, float(settings.FLOOR_Y))
ENEMY_SPAWN = (980.0, float(settings.FLOOR_Y))


class GameState(Enum):
    """Fases del juego: menus fuera de combate y combate dentro."""

    MENU = "menu"             # portada
    FIGHT = "fight"           # combate activo
    INTRO = "intro"           # aviso de inicio de ronda
    ROUND_END = "round_end"   # pausa entre rondas
    MATCH_OVER = "match_over" # fin del combate (resultado en pantalla)


class Game:
    """
    Aplicacion de juego.

    Responsabilidades:
        - Crear y destruir los recursos de pygame.
        - Actualizar los sistemas en el orden correcto.
        - Traducir eventos de combate en efectos visuales.
        - Gestionar el flujo de rondas.
    """

    def __init__(self) -> None:
        self._init_pygame()

        # --- Progreso persistente ----------------------------------------
        # Se carga antes que las entidades: el Mecha se construye a partir de
        # la ficha elegida y de las mejoras compradas.
        self.profile = PlayerProfile()

        # --- Mundo ------------------------------------------------------
        self.input = InputState()
        self.player = build_player(self.profile.selected, *PLAYER_SPAWN,
                                   self.profile.upgrade_levels())
        self.enemy = build_enemy(*ENEMY_SPAWN)
        # La IA del rival vive en su propio sistema; la entidad solo la usa.
        self.enemy_ai = EnemyAI(profile_for_round(1))
        self.enemy.set_ai(self.enemy_ai)
        self.combat = CombatSystem(self.player, self.enemy)
        self.projectiles: List[Projectile] = []

        # --- Presentacion -----------------------------------------------
        self.arena = Arena()
        self.fx = ParticleSystem()
        self.hud = HUD()
        self.renderer = MechaRenderer()
        self.menu = Menu(self.profile, self.arena)

        # --- Control del flujo -------------------------------------------
        self.state = GameState.MENU
        self.state_timer = settings.INTRO_TIME
        self.time = 0.0
        self.running = True
        #: Creditos ganados en el ultimo combate (se muestran al terminar).
        self.last_reward = 0
        # Ultimo estado de suelo de cada Mecha (para el polvo al aterrizar).
        self._grounded = [True, True]

    # ------------------------------------------------------------------
    # Arranque
    # ------------------------------------------------------------------
    def _init_pygame(self) -> None:
        """Inicializa pygame y crea la ventana."""
        pygame.init()
        pygame.display.set_caption(settings.GAME_TITLE)
        flags = pygame.FULLSCREEN if settings.FULLSCREEN else 0
        self.screen = pygame.display.set_mode((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT), flags)
        self.clock = pygame.time.Clock()

    # ------------------------------------------------------------------
    # Bucle principal
    # ------------------------------------------------------------------
    def run(self) -> None:
        """Ejecuta el juego hasta que se cierra la ventana."""
        while self.running:
            delta_time = self.clock.tick(settings.FPS) / 1000.0
            delta_time = min(delta_time, 1.0 / 30.0)  # evita saltos tras una pausa

            self._handle_events()
            self.input.begin_frame()
            self._update(delta_time)
            self._render()
            self.input.end_frame()

            pygame.display.flip()

        self.shutdown()

    def _handle_events(self) -> None:
        """Procesa la cola de eventos de pygame."""
        for event in pygame.event.get():
            self.input.handle_event(event)
            if event.type == pygame.KEYDOWN and event.key == settings.KEY_ESCAPE:
                # Fuera de combate ESC tambien sirve para cerrar la partida.
                if self.state is GameState.MENU:
                    self.running = False

    # ------------------------------------------------------------------
    # Actualizacion
    # ------------------------------------------------------------------
    def _update(self, delta_time: float) -> None:
        """Avanza el juego segun el estado actual."""
        self.time += delta_time
        self.arena.update(delta_time)
        self.fx.update(delta_time)

        # ESC es la salida universal: dentro de un combate abandona y vuelve al
        # menu (sin cobrar recompensa), y en el menu lo resuelve el propio menu.
        if self.state is not GameState.MENU and self.input.pause_pressed:
            self._abandon_match()
            return

        if self.state is GameState.MENU:
            self._update_menu(delta_time)
        elif self.state is GameState.INTRO:
            self._update_intro(delta_time)
        elif self.state is GameState.FIGHT:
            self._update_fight(delta_time)
        elif self.state is GameState.ROUND_END:
            self._update_round_end(delta_time)
        elif self.state is GameState.MATCH_OVER:
            self._update_match_over(delta_time)

    def _update_menu(self, delta_time: float) -> None:
        """Delega en el menu y aplica la orden que devuelva."""
        order = self.menu.update(self.input, delta_time)
        if order == "play":
            self._start_match()
        elif order == "quit":
            self.running = False

    def _start_match(self) -> None:
        """
        Prepara un combate con el Mecha y las mejoras del perfil.

        Se reconstruyen las entidades porque el Mecha equipado o sus mejoras
        pueden haber cambiado desde el ultimo combate.
        """
        self.player = build_player(self.profile.selected, *PLAYER_SPAWN,
                                   self.profile.upgrade_levels())
        self.player.reset_for_round(*PLAYER_SPAWN)
        self.enemy.reset_for_round(*ENEMY_SPAWN)
        self.combat = CombatSystem(self.player, self.enemy)
        self.enemy_ai = EnemyAI(profile_for_round(1))
        self.enemy.set_ai(self.enemy_ai)
        self.projectiles.clear()
        self.fx.clear()
        self._grounded = [True, True]
        self.state = GameState.INTRO
        self.state_timer = settings.INTRO_TIME

    def _leave_match(self) -> None:
        """Cierra el combate, cobra la recompensa y vuelve a la portada."""
        self.last_reward = self.profile.record_result(
            self.combat.match_winner is self.player,
            self.player.health_ratio,
        )
        self.profile.save()
        self.hud.set_result(self.last_reward)
        self.state = GameState.MENU

    def _abandon_match(self) -> None:
        """
        Abandona el combate en curso y vuelve a la portada.

        No se cobra nada: la recompensa es por terminar el combate, no por
        entrar en el. El progreso (Mecha y mejoras) nunca se pierde.
        """
        self.projectiles.clear()
        self.fx.clear()
        self.state = GameState.MENU

    def _update_intro(self, delta_time: float) -> None:
        """Cuenta atras antes de permitir el combate."""
        self.state_timer -= delta_time
        if self.state_timer <= 0.0:
            self.state = GameState.FIGHT

    def _update_fight(self, delta_time: float) -> None:
        """Simulacion de combate completa."""
        # 1. Intencion de los combatientes (el enemigo usa su IA).
        self.player.update(delta_time, self)
        self.enemy.update(delta_time, self)

        # 2. Fisica: movimiento, gravedad, suelo y limites.
        physics.update_mecha(self.player, delta_time)
        physics.update_mecha(self.enemy, delta_time)
        collision.resolve_body_separation(self.player, self.enemy, delta_time)
        self._detect_landings()

        # 3. Combate.
        self.combat.resolve_melee()
        self._update_projectiles(delta_time)
        self.combat.tick_round(delta_time)

        # 4. Cierre de ronda.
        if self.combat.check_round_end() is not None:
            self._enter_round_end()

    def _update_projectiles(self, delta_time: float) -> None:
        """Avanza, descarta y comprueba los proyectiles del jugador y el enemigo."""
        for projectile in self.projectiles:
            projectile.update(delta_time)
            if collision.hits_static_world(projectile):
                projectile.kill()
                if projectile.y > settings.FLOOR_Y - 40:
                    self.fx.spawn_impact(projectile.x, min(projectile.y, settings.FLOOR_Y), projectile.direction)

        self.combat.resolve_projectiles(self.projectiles)
        self._handle_combat_events()

    def _detect_landings(self) -> None:
        """Genera polvo en el instante en que un Mecha toca el suelo."""
        for index, mecha in enumerate((self.player, self.enemy)):
            was_airborne = not self._grounded[index]
            self._grounded[index] = mecha.on_ground
            if was_airborne and mecha.on_ground:
                self.fx.spawn_dust(mecha.x, mecha.y, mecha.facing)

    def _update_round_end(self, delta_time: float) -> None:
        """Pausa entre rondas y preparacion de la siguiente."""
        self.state_timer -= delta_time
        if self.state_timer > 0.0:
            return

        if self.combat.match_over:
            self.state = GameState.MATCH_OVER
            return

        self.combat.start_next_round()
        self.enemy_ai.set_profile(profile_for_round(self.combat.round.number))
        self._reset_round()
        self.state = GameState.INTRO
        self.state_timer = settings.INTRO_TIME

    def _update_match_over(self, delta_time: float) -> None:
        """
        Muestra el resultado y, al confirmarlo, vuelve a la portada.

        Los creditos se cobran una sola vez al salir del combate, no mientras
        se muestra el resultado, para noAccumularlos por cada pulsacion.
        """
        if self.input.melee_pressed() or self.input.energy_pressed():
            self._leave_match()

    # ------------------------------------------------------------------
    # Mundo
    # ------------------------------------------------------------------
    def spawn_projectile(self, mecha, weapon: WeaponSpec) -> None:
        """
        Lanza un proyectil desde el arma indicada.

        Es la unica forma que tienen las entidades de crear objetos en el
        mundo, lo que evita que进口en la clase Game.
        """
        if len(self.projectiles) >= settings.MAX_PROJECTILES:
            return
        muzzle_x = mecha.x + mecha.facing * (mecha.body_width * 0.5 + 52)
        muzzle_y = mecha.y - mecha.body_height * 0.62
        self.projectiles.append(
            Projectile.from_weapon(
                weapon=weapon,
                origin_x=muzzle_x,
                origin_y=muzzle_y,
                direction=mecha.facing,
                owner=mecha.faction,
                owner_name=mecha.name,
            )
        )

    def spawn_telegraph(self, mecha) -> None:
        """
        Pide el aviso visual previo a un ataque del enemigo.

        La IA llama a este metodo en vez de crear efectos directamente: asi el
        sistema de IA no depende de la capa de presentacion.
        """
        color = mecha.palette.accent
        self.fx.spawn_charge(mecha.x, mecha.y - mecha.body_height * 0.5, color)

    def _reset_round(self) -> None:
        """Coloca a los combatientes en sus marcas y limpia los proyectiles."""
        self.player.reset_for_round(*PLAYER_SPAWN)
        self.enemy.reset_for_round(*ENEMY_SPAWN)
        self.projectiles.clear()
        self._grounded = [True, True]

    def _enter_round_end(self) -> None:
        """Prepara la pausa entre rondas."""
        self.state = GameState.ROUND_END
        self.state_timer = settings.ROUND_END_TIME
        self.arena.add_shake(10.0)

    # ------------------------------------------------------------------
    # Eventos de combate -> efectos
    # ------------------------------------------------------------------
    def _handle_combat_events(self) -> None:
        """
        Convierte los eventos del combate en efectos visuales.

        Los eventos que no tienen representacion (fin de ronda, fin de combate)
        se descartan aqui: la UI de estado los dibuja por su cuenta.
        """
        for event in self.combat.consume_events():
            x, y = event.position
            if event.event_type is CombatEventType.MELEE_HIT:
                self.fx.spawn_impact(x, y, event.direction, event.critical)
                self.fx.spawn_damage_number(x, y - 18, event.amount, event.critical)
                self.arena.add_shake(10.0 if event.critical else 6.0)
            elif event.event_type is CombatEventType.PROJECTILE_HIT:
                self.fx.spawn_energy_burst(x, y, event.direction)
                self.fx.spawn_damage_number(x, y - 18, event.amount, event.critical)
                self.arena.add_shake(4.0)
            elif event.event_type is CombatEventType.DEATH:
                self.fx.spawn_death(x, y)
                self.arena.add_shake(12.0)

    # ------------------------------------------------------------------
    # Dibujo
    # ------------------------------------------------------------------
    def _render(self) -> None:
        """Dibuja un fotograma completo, menu o combate segun el estado."""
        if self.state is GameState.MENU:
            self.menu.draw(self.screen)
            return

        self.arena.draw(self.screen)
        self._draw_shadows()
        self._draw_mechas()
        self._draw_projectiles()
        self.fx.draw(self.screen)
        self.hud.draw(self.screen, self.player, self.enemy, self.combat)
        self._draw_overlays()

    def _draw_shadows(self) -> None:
        """Sombras de apoyo, tambien en las plataformas."""
        for mecha in (self.player, self.enemy):
            self.renderer.draw_shadow(self.screen, mecha, self._floor_under(mecha))

    def _floor_under(self, mecha) -> float:
        """Altura de la superficie que hay justo bajo el Mecha."""
        surfaces = physics.arena_surfaces()
        best = float(settings.FLOOR_Y)
        left, _, right, _ = mecha.bounds
        for s_left, s_top, s_right, _ in surfaces:
            if right <= s_left or left >= s_right:
                continue
            if s_top <= mecha.y + 1.0:
                best = max(best, s_top)
        return best

    def _draw_mechas(self) -> None:
        """Dibuja a los dos Mecha, con el jugador delante."""
        self.renderer.draw(self.screen, self.enemy, self.time)
        self.renderer.draw(self.screen, self.player, self.time)

    def _draw_projectiles(self) -> None:
        """Proyectiles con estela de energia."""
        for projectile in self.projectiles:
            x, y = int(projectile.x), int(projectile.y)
            tail_x, tail_y = int(projectile.tail_x), y
            pygame.draw.line(
                self.screen, projectile.color, (tail_x, tail_y), (x, y), max(2, projectile.radius - 2)
            )
            glow = pygame.Surface((projectile.radius * 4, projectile.radius * 4), pygame.SRCALPHA)
            pygame.draw.circle(
                glow, (*projectile.color, 70), (projectile.radius * 2, projectile.radius * 2), projectile.radius * 2
            )
            self.screen.blit(glow, (x - projectile.radius * 2, y - projectile.radius * 2))
            pygame.draw.circle(self.screen, (255, 255, 255), (x, y), max(2, projectile.radius // 2))

    def _draw_overlays(self) -> None:
        """Avisos de estado: cuenta atras, pausa y ayuda de controles."""
        center_x = settings.SCREEN_WIDTH // 2

        if self.state is GameState.INTRO:
            render_text(
                self.screen,
                f"RONDA {self.combat.round.number}",
                64,
                (center_x, 250),
                settings.COLOR_TEXT,
                anchor="center",
            )
            render_text(
                self.screen,
                "PREPARADOS PARA COMBATIR",
                24,
                (center_x, 320),
                settings.COLOR_ACCENT,
                anchor="center",
            )
        elif self.state is GameState.ROUND_END:
            render_text(
                self.screen,
                f"Ronda {self.combat.round.number + 1} en breve...",
                26,
                (center_x, 340),
                settings.COLOR_TEXT_DIM,
                anchor="center",
            )

        if self.state in (GameState.INTRO, GameState.FIGHT):
            self._draw_controls_hint()

    def _draw_controls_hint(self) -> None:
        """Recordatorio de controles en la parte inferior."""
        hint = "A / D  MOVER     W  SALTAR     J  CUERPO A CUERPO     K  ENERGIA     ESC  VOLVER AL MENU"
        render_text(
            self.screen,
            hint,
            16,
            (settings.SCREEN_WIDTH // 2, settings.SCREEN_HEIGHT - 18),
            settings.COLOR_TEXT_DIM,
            anchor="center",
        )

    # ------------------------------------------------------------------
    # Cierre
    # ------------------------------------------------------------------
    def shutdown(self) -> None:
        """Libera los recursos de pygame."""
        pygame.quit()
