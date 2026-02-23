"""
Air Hockey Game - Main entry point
Game class, state management, rendering, and main loop.
"""
import sys
import math
import random
import struct
import pygame

from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT, FPS, WINDOW_TITLE,
    TABLE_MARGIN, GOAL_WIDTH, RINK_CORNER_RADIUS,
    RINK_LEFT, RINK_RIGHT, RINK_TOP, RINK_BOTTOM,
    RINK_CENTER_X, RINK_CENTER_Y, CENTER_LINE_Y,
    GOAL_LEFT_X, GOAL_RIGHT_X, GOAL_DEPTH,
    PADDLE_RADIUS,
    PUCK_RADIUS, PUCK_FRICTION,
    PLAYER1_COLOR, PLAYER2_COLOR, PUCK_COLOR,
    WHITE, BLACK, GRAY, DARK_GRAY, YELLOW, RED,
    ARENAS,
    POWERUP_SPAWN_MIN, POWERUP_SPAWN_MAX, POWERUP_TYPES,
    POWERUP_DURATION, POWERUP_MAGNET_RANGE, POWERUP_MAGNET_STRENGTH,
    PU_BIGGER, PU_SMALLER, PU_SPEED, PU_MAGNET, PU_FREEZE,
    PARTICLE_COUNT_HIT, PARTICLE_COUNT_GOAL,
    SCREEN_SHAKE_INTENSITY, SCREEN_SHAKE_DURATION, SCREEN_SHAKE_SPEED_THRESHOLD,
    GOAL_RESET_PAUSE, COUNTDOWN_DURATION,
    DEFAULT_GOALS_TO_WIN, DEFAULT_MATCH_TIME,
    SOUND_ENABLED, SOUND_SAMPLE_RATE, SOUND_VOLUME,
    PADDLE_FRICTION, PADDLE_MAX_SPEED,
)
from entities import Paddle, Puck, PowerUp, ParticleSystem
from ai import AIController
from ui import MainMenu, PauseMenu, EndScreen, HUD, OnlineMenu, HostLobby, JoinLobby
from network import GameServer, GameClient, get_local_ip


# ── Procedural Sound Generation ─────────────────────────────────────

def _generate_tone(frequency, duration_ms, volume=0.3, sample_rate=SOUND_SAMPLE_RATE):
    """Generate a simple sine wave tone as a pygame Sound object."""
    n_samples = int(sample_rate * duration_ms / 1000)
    buf = bytearray()
    for i in range(n_samples):
        t = i / sample_rate
        # Sine wave with decay envelope
        envelope = max(0, 1.0 - t / (duration_ms / 1000))
        val = int(volume * envelope * 32767 * math.sin(2 * math.pi * frequency * t))
        val = max(-32768, min(32767, val))
        # Stereo: same value for both channels
        buf.extend(struct.pack('<hh', val, val))
    return pygame.mixer.Sound(buffer=bytes(buf))


def _generate_noise_burst(duration_ms, volume=0.2, sample_rate=SOUND_SAMPLE_RATE):
    """Generate a short noise burst for hit sounds."""
    n_samples = int(sample_rate * duration_ms / 1000)
    buf = bytearray()
    for i in range(n_samples):
        envelope = max(0, 1.0 - i / n_samples)
        val = int(volume * envelope * 32767 * (random.random() * 2 - 1))
        val = max(-32768, min(32767, val))
        buf.extend(struct.pack('<hh', val, val))
    return pygame.mixer.Sound(buffer=bytes(buf))


# ── Game Class ───────────────────────────────────────────────────────

class Game:
    """Main game controller."""

    # States
    STATE_MENU = "menu"
    STATE_PLAYING = "playing"
    STATE_PAUSED = "paused"
    STATE_GOAL = "goal"      # brief pause after goal
    STATE_COUNTDOWN = "countdown"
    STATE_END = "end"
    STATE_ONLINE_MENU = "online_menu"
    STATE_ONLINE_HOST_LOBBY = "online_host_lobby"
    STATE_ONLINE_CLIENT_LOBBY = "online_client_lobby"

    def __init__(self):
        pygame.init()
        self.sound_available = False
        try:
            pygame.mixer.init(frequency=SOUND_SAMPLE_RATE, size=-16, channels=2, buffer=512)
            self.sound_available = True
        except pygame.error:
            print("Warning: No audio device found. Sound disabled.")
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption(WINDOW_TITLE)
        self.clock = pygame.time.Clock()

        # Sounds
        self._init_sounds()

        # UI
        self.menu = MainMenu()
        self.pause_menu = PauseMenu()
        self.end_screen = EndScreen()
        self.hud = HUD()
        self.online_menu = OnlineMenu()
        self.host_lobby = HostLobby()
        self.join_lobby = JoinLobby()

        # Game state
        self.state = self.STATE_MENU
        self.game_mode = None  # "local_1v1", "vs_ai", "practice", "online"

        # Network
        self.network_role = None  # None, "host", "client"
        self.server = None
        self.client = None
        self.client_input = None  # latest input from remote client
        self.match_mode = "first_to"
        self.match_param = DEFAULT_GOALS_TO_WIN
        self.arena_key = "classic"
        self.mouse_mode = False

        # Entities
        self.paddle1 = None  # bottom (Player 1)
        self.paddle2 = None  # top (Player 2 / AI)
        self.puck = None
        self.powerup = None
        self.particles = ParticleSystem()
        self.ai = None

        # Match state
        self.score_p1 = 0
        self.score_p2 = 0
        self.match_timer = 0.0
        self.goal_timer = 0.0
        self.countdown_timer = 0.0
        self.last_scorer = None

        # Power-up spawn timer
        self.powerup_timer = 0.0
        self.powerup_spawn_interval = random.uniform(POWERUP_SPAWN_MIN, POWERUP_SPAWN_MAX)

        # Screen shake
        self.shake_timer = 0.0
        self.shake_offset = (0, 0)

        self.running = True

    def _init_sounds(self):
        """Generate procedural sounds."""
        if not SOUND_ENABLED or not self.sound_available:
            self.sounds = {}
            return
        self.sounds = {
            "hit": _generate_tone(440, 50, 0.25),
            "wall": _generate_tone(330, 40, 0.15),
            "goal": _generate_tone(220, 400, 0.3),
            "countdown": _generate_tone(660, 100, 0.2),
            "powerup": _generate_tone(880, 80, 0.2),
        }

    def _play_sound(self, name):
        if name in self.sounds:
            self.sounds[name].play()

    def start_match(self, mode, settings):
        """Initialize a new match."""
        self.game_mode = mode
        self.match_mode = settings["match_mode"]
        self.match_param = settings["match_param"]
        self.arena_key = settings["arena"]
        self.mouse_mode = settings.get("mouse_mode", False)

        arena = ARENAS.get(self.arena_key, ARENAS["classic"])

        # Create entities
        self.paddle1 = Paddle(RINK_CENTER_X, RINK_BOTTOM - 60, PLAYER1_COLOR, half="bottom")
        self.paddle1.friction_mult = arena["paddle_friction"]
        self.paddle1.speed_mult = arena["paddle_speed_mult"]

        if mode == "practice":
            self.paddle2 = None
        else:
            self.paddle2 = Paddle(RINK_CENTER_X, RINK_TOP + 60, PLAYER2_COLOR, half="top")
            self.paddle2.friction_mult = arena["paddle_friction"]
            self.paddle2.speed_mult = arena["paddle_speed_mult"]

        self.puck = Puck()
        self.puck.friction = arena["puck_friction"]
        self.puck.speed_mult = arena["puck_speed_mult"]

        # AI
        if mode == "vs_ai":
            diff = settings.get("difficulty", "medium")
            self.ai = AIController(diff)
        else:
            self.ai = None

        # Reset scores
        self.score_p1 = 0
        self.score_p2 = 0
        self.match_timer = float(self.match_param) if self.match_mode == "timed" else 0.0
        self.powerup = None
        self.powerup_timer = random.uniform(POWERUP_SPAWN_MIN, POWERUP_SPAWN_MAX)
        self.particles = ParticleSystem()

        # Start with countdown
        self._start_countdown()

    def _start_countdown(self):
        self.state = self.STATE_COUNTDOWN
        self.countdown_timer = COUNTDOWN_DURATION
        self.puck.reset()
        self.paddle1.reset()
        if self.paddle2:
            self.paddle2.reset()

    def _on_goal(self, who):
        """Handle goal scored. who = 'p1' or 'p2'."""
        if who == "p1":
            self.score_p1 += 1
        else:
            self.score_p2 += 1
        self.last_scorer = who

        self._play_sound("goal")

        # Goal particles
        gx = self.puck.x
        gy = self.puck.y
        color = PLAYER1_COLOR if who == "p1" else PLAYER2_COLOR
        self.particles.emit(gx, gy, PARTICLE_COUNT_GOAL, color=color,
                            speed_range=(100, 400))

        # Remove active power-up
        self.powerup = None

        # Clear effects
        self.paddle1.effects.clear()
        self.paddle1.frozen = False
        self.paddle1.radius = self.paddle1.base_radius
        if self.paddle2:
            self.paddle2.effects.clear()
            self.paddle2.frozen = False
            self.paddle2.radius = self.paddle2.base_radius

        # Check for match end
        if self._check_match_end():
            return

        self.state = self.STATE_GOAL
        self.goal_timer = GOAL_RESET_PAUSE

    def _check_match_end(self):
        """Check if the match is over. Returns True if ended."""
        ended = False
        if self.match_mode == "first_to":
            if self.score_p1 >= self.match_param or self.score_p2 >= self.match_param:
                ended = True
        # Timed matches end in the main update loop

        if ended:
            self._end_match()
            return True
        return False

    def _end_match(self):
        """Transition to end screen."""
        if self.score_p1 > self.score_p2:
            if self.game_mode == "online" and self.network_role == "client":
                winner = "Host"
            else:
                winner = "Player 1"
        elif self.score_p2 > self.score_p1:
            if self.game_mode == "vs_ai":
                winner = "AI"
            elif self.game_mode == "online" and self.network_role == "host":
                winner = "Opponent"
            elif self.game_mode == "online" and self.network_role == "client":
                winner = "You"
            else:
                winner = "Player 2"
        else:
            winner = "Draw"

        if self.game_mode == "online" and self.network_role == "host":
            if self.score_p1 > self.score_p2:
                winner = "You"
            elif self.score_p2 > self.score_p1:
                winner = "Opponent"

        self.end_screen.set_result(winner, self.score_p1, self.score_p2)
        self.state = self.STATE_END

    # ── Input ────────────────────────────────────────────────────────

    def _get_p1_input(self, keys):
        """Get Player 1 input (bottom paddle). Returns (ax, ay, boost)."""
        if self.mouse_mode:
            # Mouse mode returns None to signal direct tracking in update()
            return None, None, pygame.mouse.get_pressed()[0]

        ax, ay = 0.0, 0.0
        # WASD always works
        if keys[pygame.K_a]:
            ax -= 1
        if keys[pygame.K_d]:
            ax += 1
        if keys[pygame.K_w]:
            ay -= 1
        if keys[pygame.K_s]:
            ay += 1
        # Arrow keys also work when not in local 1v1 (where P2 needs them)
        if self.game_mode != "local_1v1":
            if keys[pygame.K_LEFT]:
                ax -= 1
            if keys[pygame.K_RIGHT]:
                ax += 1
            if keys[pygame.K_UP]:
                ay -= 1
            if keys[pygame.K_DOWN]:
                ay += 1
        # Normalize diagonal
        mag = math.hypot(ax, ay)
        if mag > 1:
            ax /= mag
            ay /= mag
        boost = keys[pygame.K_LSHIFT]
        return ax, ay, boost

    def _get_p2_input(self, keys):
        """Get Player 2 input (top paddle, local 1v1 only)."""
        ax, ay = 0.0, 0.0
        if keys[pygame.K_LEFT]:
            ax -= 1
        if keys[pygame.K_RIGHT]:
            ax += 1
        if keys[pygame.K_UP]:
            ay -= 1
        if keys[pygame.K_DOWN]:
            ay += 1
        mag = math.hypot(ax, ay)
        if mag > 1:
            ax /= mag
            ay /= mag
        boost = keys[pygame.K_RSHIFT]
        return ax, ay, boost

    def _update_paddle_mouse(self, paddle, dt):
        """Move paddle directly toward mouse for responsive tracking."""
        old_x, old_y = paddle.x, paddle.y

        # Let normal update handle effects, freeze, boost (no directional input)
        paddle.update(dt, 0, 0)

        if paddle.frozen:
            return

        # Override position: track mouse directly
        mx, my = pygame.mouse.get_pos()
        paddle.x = mx
        paddle.y = my
        paddle._clamp_position()

        # Set velocity from actual movement so puck collisions feel right
        if dt > 0:
            paddle.vx = (paddle.x - old_x) / dt
            paddle.vy = (paddle.y - old_y) / dt

    # ── Network ──────────────────────────────────────────────────────

    def _start_hosting(self):
        """Transition to host lobby."""
        self.network_role = "host"
        self.server = GameServer()
        ok, err = self.server.start()
        self.host_lobby.client_connected = False
        self.host_lobby.error = None
        self.host_lobby.status = "Waiting for player..."
        self.host_lobby.status_color = (140, 140, 140)
        if ok:
            self.host_lobby.set_ip(get_local_ip())
            self.state = self.STATE_ONLINE_HOST_LOBBY
        else:
            self.host_lobby.set_ip(get_local_ip())
            self.host_lobby.set_error(err)
            self.state = self.STATE_ONLINE_HOST_LOBBY

    def _start_joining(self):
        """Transition to join lobby."""
        self.network_role = "client"
        self.join_lobby.reset()
        self.state = self.STATE_ONLINE_CLIENT_LOBBY

    def _cleanup_network(self):
        """Shut down any active network connections."""
        if self.server:
            self.server.stop()
            self.server = None
        if self.client:
            self.client.disconnect()
            self.client = None
        self.network_role = None
        self.client_input = None

    def _build_state_snapshot(self):
        """Serialize full game state for sending to client."""
        snap = {
            "p1x": self.paddle1.x, "p1y": self.paddle1.y,
            "p1vx": self.paddle1.vx, "p1vy": self.paddle1.vy,
            "p1r": self.paddle1.radius, "p1boost": self.paddle1.boost_energy,
            "p1frozen": self.paddle1.frozen,
            "p1effects": {k: round(v, 2) for k, v in self.paddle1.effects.items()},
        }
        if self.paddle2:
            snap.update({
                "p2x": self.paddle2.x, "p2y": self.paddle2.y,
                "p2vx": self.paddle2.vx, "p2vy": self.paddle2.vy,
                "p2r": self.paddle2.radius, "p2boost": self.paddle2.boost_energy,
                "p2frozen": self.paddle2.frozen,
                "p2effects": {k: round(v, 2) for k, v in self.paddle2.effects.items()},
            })
        snap.update({
            "px": self.puck.x, "py": self.puck.y,
            "pvx": self.puck.vx, "pvy": self.puck.vy,
            "pactive": self.puck.active,
            "s1": self.score_p1, "s2": self.score_p2,
            "mt": round(self.match_timer, 2),
            "st": self.state,
            "gt": round(self.goal_timer, 2),
            "ct": round(self.countdown_timer, 2),
        })
        if self.powerup:
            snap["pu"] = {"t": self.powerup.type, "x": self.powerup.x, "y": self.powerup.y}
        return snap

    def _apply_state_snapshot(self, snap):
        """Client-side: unpack state snapshot onto local entities."""
        if not self.paddle1 or not self.paddle2 or not self.puck:
            return

        self.paddle1.x = snap["p1x"]
        self.paddle1.y = snap["p1y"]
        self.paddle1.vx = snap["p1vx"]
        self.paddle1.vy = snap["p1vy"]
        self.paddle1.radius = snap["p1r"]
        self.paddle1.boost_energy = snap["p1boost"]
        self.paddle1.frozen = snap["p1frozen"]
        self.paddle1.effects = snap.get("p1effects", {})

        self.paddle2.x = snap["p2x"]
        self.paddle2.y = snap["p2y"]
        self.paddle2.vx = snap["p2vx"]
        self.paddle2.vy = snap["p2vy"]
        self.paddle2.radius = snap["p2r"]
        self.paddle2.boost_energy = snap["p2boost"]
        self.paddle2.frozen = snap["p2frozen"]
        self.paddle2.effects = snap.get("p2effects", {})

        self.puck.x = snap["px"]
        self.puck.y = snap["py"]
        self.puck.vx = snap["pvx"]
        self.puck.vy = snap["pvy"]
        self.puck.active = snap["pactive"]

        # Detect goals for local sound/particles
        old_s1, old_s2 = self.score_p1, self.score_p2
        self.score_p1 = snap["s1"]
        self.score_p2 = snap["s2"]
        if self.score_p1 > old_s1:
            self._play_sound("goal")
            self.particles.emit(self.puck.x, self.puck.y, PARTICLE_COUNT_GOAL,
                                color=PLAYER1_COLOR, speed_range=(100, 400))
        elif self.score_p2 > old_s2:
            self._play_sound("goal")
            self.particles.emit(self.puck.x, self.puck.y, PARTICLE_COUNT_GOAL,
                                color=PLAYER2_COLOR, speed_range=(100, 400))

        self.match_timer = snap["mt"]
        self.goal_timer = snap["gt"]
        self.countdown_timer = snap["ct"]

        # State transitions
        new_state = snap["st"]
        if new_state == self.STATE_END and self.state != self.STATE_END:
            self._end_match()
        elif new_state in (self.STATE_PLAYING, self.STATE_COUNTDOWN,
                           self.STATE_GOAL, self.STATE_PAUSED):
            self.state = new_state

        # Power-up
        if "pu" in snap:
            pu = snap["pu"]
            if self.powerup is None or self.powerup.type != pu["t"]:
                self.powerup = PowerUp(pu["t"], pu["x"], pu["y"])
            else:
                self.powerup.x = pu["x"]
                self.powerup.y = pu["y"]
        else:
            self.powerup = None

    def _client_update(self, dt):
        """Client-side update: send input, receive state, update particles."""
        if not self.client or not self.client.is_connected():
            self._cleanup_network()
            self.state = self.STATE_MENU
            return

        # Send local input to host
        keys = pygame.key.get_pressed()
        ax, ay, boost = self._get_p1_input(keys)
        if ax is None:
            # Mouse mode: convert mouse position to proportional acceleration
            mx, my = pygame.mouse.get_pos()
            if self.paddle2:
                # Client controls P2 (top paddle)
                ax = (mx - self.paddle2.x) * 5.0 / PADDLE_MAX_SPEED
                ay = (my - self.paddle2.y) * 5.0 / PADDLE_MAX_SPEED
                mag = math.hypot(ax, ay)
                if mag > 1:
                    ax /= mag
                    ay /= mag
        self.client.send_input(ax, ay, boost)

        # Receive and apply state
        state = self.client.get_state()
        if state:
            self._apply_state_snapshot(state)

        # Check for disconnect message
        msg = self.client.get_message()
        if msg and msg.get("type") == "disconnect":
            self._cleanup_network()
            self.state = self.STATE_MENU
            return

        # Update local particles
        self.particles.update(dt)
        if self.powerup:
            self.powerup.update(dt)

    # ── Update ───────────────────────────────────────────────────────

    def update(self, dt):
        # Client skips local physics entirely
        if self.game_mode == "online" and self.network_role == "client":
            self._client_update(dt)
            return

        if self.state == self.STATE_COUNTDOWN:
            self.countdown_timer -= dt
            if self.countdown_timer <= 0:
                self.state = self.STATE_PLAYING
                self.puck.active = True
                self.puck.launch()
                self._play_sound("countdown")
            if self.game_mode == "online" and self.network_role == "host":
                self.server.send_state(self._build_state_snapshot())
            return

        if self.state == self.STATE_GOAL:
            self.goal_timer -= dt
            self.particles.update(dt)
            if self.goal_timer <= 0:
                self._start_countdown()
            if self.game_mode == "online" and self.network_role == "host":
                self.server.send_state(self._build_state_snapshot())
            return

        if self.state != self.STATE_PLAYING:
            return

        keys = pygame.key.get_pressed()

        # Player 1 input
        ax1, ay1, boost1 = self._get_p1_input(keys)
        self.paddle1.boosting = boost1
        if ax1 is None:
            # Mouse mode: direct position tracking for responsiveness
            self._update_paddle_mouse(self.paddle1, dt)
        else:
            self.paddle1.update(dt, ax1, ay1)

        # Player 2 / AI / Remote input
        if self.paddle2:
            if self.game_mode == "vs_ai" and self.ai:
                ax2, ay2, boost2 = self.ai.update(dt, self.paddle2, self.puck)
                self.paddle2.boosting = boost2
                self.paddle2.update(dt, ax2, ay2)
            elif self.game_mode == "online" and self.network_role == "host":
                inp = self.server.get_client_input()
                if inp:
                    self.client_input = inp
                if self.client_input:
                    ax2, ay2, boost2 = self.client_input
                    self.paddle2.boosting = boost2
                    self.paddle2.update(dt, ax2, ay2)
                else:
                    self.paddle2.update(dt, 0, 0)
            elif self.game_mode == "local_1v1":
                ax2, ay2, boost2 = self._get_p2_input(keys)
                self.paddle2.boosting = boost2
                self.paddle2.update(dt, ax2, ay2)

        # Magnet effect: attract puck toward paddle
        for paddle in [self.paddle1, self.paddle2]:
            if paddle and PU_MAGNET in paddle.effects:
                dx = paddle.x - self.puck.x
                dy = paddle.y - self.puck.y
                dist = math.hypot(dx, dy)
                if 0 < dist < POWERUP_MAGNET_RANGE:
                    force = POWERUP_MAGNET_STRENGTH * (1 - dist / POWERUP_MAGNET_RANGE)
                    self.puck.vx += (dx / dist) * force * dt
                    self.puck.vy += (dy / dist) * force * dt

        # Puck update
        self.puck.update(dt)

        # Puck-paddle collisions
        for paddle in [self.paddle1, self.paddle2]:
            if paddle and self.puck.collide_paddle(paddle):
                self._play_sound("hit")
                self.particles.emit(
                    self.puck.x, self.puck.y, PARTICLE_COUNT_HIT)
                # Screen shake on hard hits
                if self.puck.speed > SCREEN_SHAKE_SPEED_THRESHOLD:
                    self.shake_timer = SCREEN_SHAKE_DURATION

        # Puck-wall collisions
        wall_result = self.puck.collide_walls()
        if wall_result == "wall":
            self._play_sound("wall")
        elif wall_result == "goal_top":
            # Puck entered top goal = point for Player 1 (bottom)
            self._on_goal("p1")
            return
        elif wall_result == "goal_bottom":
            # Puck entered bottom goal = point for Player 2 (top)
            self._on_goal("p2")
            return

        # Timed match countdown
        if self.match_mode == "timed":
            self.match_timer -= dt
            if self.match_timer <= 0:
                self.match_timer = 0
                self._end_match()
                return

        # Power-up spawning
        self._update_powerups(dt)

        # Particles and screen shake
        self.particles.update(dt)
        if self.shake_timer > 0:
            self.shake_timer -= dt
            intensity = int(SCREEN_SHAKE_INTENSITY * (self.shake_timer / SCREEN_SHAKE_DURATION))
            self.shake_offset = (
                random.randint(-intensity, intensity),
                random.randint(-intensity, intensity),
            )
        else:
            self.shake_offset = (0, 0)

        # Host: send state to client each frame
        if self.game_mode == "online" and self.network_role == "host" and self.server:
            self.server.send_state(self._build_state_snapshot())
            # Check if client disconnected mid-game
            if not self.server.is_client_connected():
                self._cleanup_network()
                self.state = self.STATE_MENU

    def _update_powerups(self, dt):
        """Handle power-up spawning and collection."""
        if self.powerup is None:
            self.powerup_timer -= dt
            if self.powerup_timer <= 0:
                self._spawn_powerup()
                self.powerup_timer = random.uniform(POWERUP_SPAWN_MIN, POWERUP_SPAWN_MAX)
        else:
            self.powerup.update(dt)
            # Check collection by paddles
            for paddle in [self.paddle1, self.paddle2]:
                if paddle and self.powerup and self.powerup.collides_with(paddle):
                    self._collect_powerup(paddle)
                    break

    def _spawn_powerup(self):
        """Spawn a random power-up in a valid location."""
        pu_type = random.choice(POWERUP_TYPES)
        margin = 60
        x = random.uniform(RINK_LEFT + margin, RINK_RIGHT - margin)
        y = random.uniform(RINK_TOP + margin, RINK_BOTTOM - margin)
        self.powerup = PowerUp(pu_type, x, y)

    def _collect_powerup(self, collector):
        """Apply power-up effect when collected by a paddle."""
        pu = self.powerup
        self._play_sound("powerup")

        if pu.type == PU_BIGGER:
            collector.apply_effect(PU_BIGGER)
        elif pu.type == PU_SPEED:
            collector.apply_effect(PU_SPEED)
        elif pu.type == PU_MAGNET:
            collector.apply_effect(PU_MAGNET)
        elif pu.type == PU_SMALLER:
            # Shrink the opponent
            opponent = self.paddle2 if collector == self.paddle1 else self.paddle1
            if opponent:
                opponent.apply_effect(PU_SMALLER)
        elif pu.type == PU_FREEZE:
            # Freeze the opponent
            opponent = self.paddle2 if collector == self.paddle1 else self.paddle1
            if opponent:
                opponent.apply_effect(PU_FREEZE)

        self.powerup = None

    # ── Drawing ──────────────────────────────────────────────────────

    def draw(self):
        if self.state == self.STATE_MENU:
            self.menu.draw(self.screen)
            pygame.display.flip()
            return

        if self.state == self.STATE_ONLINE_MENU:
            self.online_menu.draw(self.screen)
            pygame.display.flip()
            return

        if self.state == self.STATE_ONLINE_HOST_LOBBY:
            self.host_lobby.draw(self.screen)
            pygame.display.flip()
            return

        if self.state == self.STATE_ONLINE_CLIENT_LOBBY:
            self.join_lobby.draw(self.screen)
            pygame.display.flip()
            return

        # Create game surface (for screen shake offset)
        game_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        self._draw_arena(game_surface)

        # Draw entities
        if self.powerup:
            self.powerup.draw(game_surface)

        self.puck.draw(game_surface)
        self.paddle1.draw(game_surface)
        if self.paddle2:
            self.paddle2.draw(game_surface)

        self.particles.draw(game_surface)

        # HUD
        p1_effects = dict(self.paddle1.effects)
        p2_effects = dict(self.paddle2.effects) if self.paddle2 else {}

        # Build labels
        if self.game_mode == "online" and self.network_role == "host":
            labels = ("You (Host)", "Player 2")
        elif self.game_mode == "online" and self.network_role == "client":
            labels = ("Host", "You")
        elif self.game_mode == "vs_ai":
            labels = ("Player", "AI")
        elif self.game_mode == "local_1v1":
            labels = ("P1", "P2")
        else:
            labels = ("Player", "")

        hud_state = {
            "score_p1": self.score_p1,
            "score_p2": self.score_p2,
            "match_mode": self.match_mode,
            "match_param": self.match_param,
            "timer": self.match_timer,
            "boost_p1": self.paddle1.boost_energy,
            "boost_p2": self.paddle2.boost_energy if self.paddle2 else 0,
            "effects_p1": p1_effects,
            "effects_p2": p2_effects,
            "countdown": self.countdown_timer if self.state == self.STATE_COUNTDOWN else 0,
            "labels": labels,
        }
        self.hud.draw(game_surface, hud_state)

        # Goal flash
        if self.state == self.STATE_GOAL and self.goal_timer > GOAL_RESET_PAUSE - 0.3:
            flash = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            alpha = int(200 * (self.goal_timer - (GOAL_RESET_PAUSE - 0.3)) / 0.3)
            flash.fill((255, 255, 255, min(255, alpha)))
            game_surface.blit(flash, (0, 0))

        # Goal text
        if self.state == self.STATE_GOAL:
            font = pygame.font.SysFont(None, 60)
            text = font.render("GOAL!", True, YELLOW)
            game_surface.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2,
                                     SCREEN_HEIGHT // 2 - text.get_height() // 2))

        # Apply screen shake
        self.screen.fill(BLACK)
        self.screen.blit(game_surface, self.shake_offset)

        # Overlays
        if self.state == self.STATE_PAUSED:
            self.pause_menu.draw(self.screen)
        elif self.state == self.STATE_END:
            self.end_screen.draw(self.screen)

        pygame.display.flip()

    def _draw_arena(self, surface):
        """Draw the rink / table."""
        arena = ARENAS.get(self.arena_key, ARENAS["classic"])
        surface.fill(arena["bg_color"])

        # Rink surface
        rink_rect = pygame.Rect(RINK_LEFT, RINK_TOP,
                                RINK_RIGHT - RINK_LEFT, RINK_BOTTOM - RINK_TOP)
        pygame.draw.rect(surface, arena["rink_color"], rink_rect,
                         border_radius=RINK_CORNER_RADIUS)

        # Center line
        pygame.draw.line(surface, arena["line_color"],
                         (RINK_LEFT, CENTER_LINE_Y), (RINK_RIGHT, CENTER_LINE_Y), 2)

        # Center circle
        pygame.draw.circle(surface, arena["line_color"],
                           (RINK_CENTER_X, RINK_CENTER_Y), 50, 2)
        pygame.draw.circle(surface, arena["line_color"],
                           (RINK_CENTER_X, RINK_CENTER_Y), 4)

        # Walls (thick border)
        wall_color = arena["wall_color"]

        # Top wall segments (with goal gap)
        pygame.draw.line(surface, wall_color,
                         (RINK_LEFT, RINK_TOP), (GOAL_LEFT_X, RINK_TOP), 4)
        pygame.draw.line(surface, wall_color,
                         (GOAL_RIGHT_X, RINK_TOP), (RINK_RIGHT, RINK_TOP), 4)

        # Bottom wall segments (with goal gap)
        pygame.draw.line(surface, wall_color,
                         (RINK_LEFT, RINK_BOTTOM), (GOAL_LEFT_X, RINK_BOTTOM), 4)
        pygame.draw.line(surface, wall_color,
                         (GOAL_RIGHT_X, RINK_BOTTOM), (RINK_RIGHT, RINK_BOTTOM), 4)

        # Side walls
        pygame.draw.line(surface, wall_color,
                         (RINK_LEFT, RINK_TOP), (RINK_LEFT, RINK_BOTTOM), 4)
        pygame.draw.line(surface, wall_color,
                         (RINK_RIGHT, RINK_TOP), (RINK_RIGHT, RINK_BOTTOM), 4)

        # Goal areas (visual depth behind wall)
        goal_color_top = (60, 30, 30)
        goal_color_bot = (60, 30, 30)
        # Top goal
        pygame.draw.rect(surface, goal_color_top,
                         (GOAL_LEFT_X, RINK_TOP - GOAL_DEPTH,
                          GOAL_RIGHT_X - GOAL_LEFT_X, GOAL_DEPTH))
        # Bottom goal
        pygame.draw.rect(surface, goal_color_bot,
                         (GOAL_LEFT_X, RINK_BOTTOM,
                          GOAL_RIGHT_X - GOAL_LEFT_X, GOAL_DEPTH))

        # Goal posts
        post_color = (200, 200, 200)
        pygame.draw.circle(surface, post_color, (GOAL_LEFT_X, RINK_TOP), 5)
        pygame.draw.circle(surface, post_color, (GOAL_RIGHT_X, RINK_TOP), 5)
        pygame.draw.circle(surface, post_color, (GOAL_LEFT_X, RINK_BOTTOM), 5)
        pygame.draw.circle(surface, post_color, (GOAL_RIGHT_X, RINK_BOTTOM), 5)

    # ── Main Loop ────────────────────────────────────────────────────

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            dt = min(dt, 0.05)  # cap to prevent physics explosion

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._cleanup_network()
                    self.running = False
                    break

                self._handle_event(event)

            if not self.running:
                break

            # Update mouse-dependent UI
            mouse_pos = pygame.mouse.get_pos()
            if self.state == self.STATE_MENU:
                self.menu.update(mouse_pos)
            elif self.state == self.STATE_ONLINE_MENU:
                self.online_menu.update(mouse_pos)
            elif self.state == self.STATE_ONLINE_HOST_LOBBY:
                self.host_lobby.update(mouse_pos)
                # Poll for client connection
                if self.server and not self.host_lobby.client_connected:
                    if self.server.is_client_connected():
                        self.host_lobby.set_client_connected(True)
            elif self.state == self.STATE_ONLINE_CLIENT_LOBBY:
                self.join_lobby.update(mouse_pos)
                # Poll for start message from host
                if self.client and self.join_lobby.connected:
                    msg = self.client.get_message()
                    if msg:
                        if msg.get("type") == "start":
                            settings = msg.get("settings", {})
                            settings.setdefault("match_mode", "first_to")
                            settings.setdefault("match_param", DEFAULT_GOALS_TO_WIN)
                            settings.setdefault("arena", "classic")
                            settings.setdefault("mouse_mode", self.menu.mouse_mode)
                            self.start_match("online", settings)
                        elif msg.get("type") == "disconnect":
                            self.join_lobby.set_status("Host disconnected", (220, 50, 50))
                            self.join_lobby.connected = False
                            self._cleanup_network()
            elif self.state == self.STATE_PAUSED:
                self.pause_menu.update(mouse_pos)
            elif self.state == self.STATE_END:
                self.end_screen.update(mouse_pos)

            # Game update
            self.update(dt)

            # Draw
            self.draw()

        pygame.quit()
        sys.exit()

    def _handle_event(self, event):
        """Route events to the current state handler."""
        if self.state == self.STATE_MENU:
            result = self.menu.handle_event(event)
            if result == "quit":
                self.running = False
            elif result == "online":
                self.state = self.STATE_ONLINE_MENU
            elif result in ("local_1v1", "vs_ai", "practice"):
                settings = self.menu.get_settings()
                self.start_match(result, settings)

        elif self.state == self.STATE_ONLINE_MENU:
            result = self.online_menu.handle_event(event)
            if result == "host":
                self._start_hosting()
            elif result == "join":
                self._start_joining()
            elif result == "back":
                self.state = self.STATE_MENU

        elif self.state == self.STATE_ONLINE_HOST_LOBBY:
            result = self.host_lobby.handle_event(event)
            if result == "start" and self.host_lobby.client_connected:
                settings = self.menu.get_settings()
                self.server.send_message({
                    "type": "start",
                    "settings": settings,
                })
                self.start_match("online", settings)
            elif result == "cancel":
                self._cleanup_network()
                self.state = self.STATE_ONLINE_MENU

        elif self.state == self.STATE_ONLINE_CLIENT_LOBBY:
            result = self.join_lobby.handle_event(event)
            if result == "connect" and not self.join_lobby.connecting:
                ip = self.join_lobby.ip_input.strip()
                if ip:
                    self.join_lobby.connecting = True
                    self.join_lobby.set_status("Connecting...", (140, 140, 140))
                    self.client = GameClient()
                    ok, err = self.client.connect(ip)
                    if ok:
                        self.join_lobby.connected = True
                        self.join_lobby.connecting = False
                        self.join_lobby.set_status("Connected! Waiting for host to start...",
                                                   (60, 200, 80))
                    else:
                        self.join_lobby.connecting = False
                        self.join_lobby.set_status(f"Failed: {err}", (220, 50, 50))
                        self.client = None
            elif result == "cancel":
                self._cleanup_network()
                self.state = self.STATE_ONLINE_MENU

        elif self.state == self.STATE_PLAYING:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                # Only host can pause in online mode
                if self.game_mode != "online" or self.network_role == "host":
                    self.state = self.STATE_PAUSED

        elif self.state == self.STATE_PAUSED:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.state = self.STATE_PLAYING
            result = self.pause_menu.handle_event(event)
            if result == "resume":
                self.state = self.STATE_PLAYING
            elif result == "restart":
                if self.game_mode == "online":
                    self._cleanup_network()
                    self.state = self.STATE_MENU
                else:
                    settings = self.menu.get_settings()
                    self.start_match(self.game_mode, settings)
            elif result == "quit":
                self._cleanup_network()
                self.state = self.STATE_MENU

        elif self.state == self.STATE_END:
            result = self.end_screen.handle_event(event)
            if result == "replay":
                if self.game_mode == "online":
                    self._cleanup_network()
                    self.state = self.STATE_MENU
                else:
                    settings = self.menu.get_settings()
                    self.start_match(self.game_mode, settings)
            elif result == "menu":
                self._cleanup_network()
                self.state = self.STATE_MENU

        elif self.state == self.STATE_COUNTDOWN:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if self.game_mode != "online" or self.network_role == "host":
                    self.state = self.STATE_PAUSED


# ── Entry Point ──────────────────────────────────────────────────────

if __name__ == "__main__":
    game = Game()
    game.run()
