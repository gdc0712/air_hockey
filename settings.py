"""
Air Hockey Game - Configuration & Constants
All tweakable game parameters live here.
"""

# ── Display ──────────────────────────────────────────────────────────
SCREEN_WIDTH = 1000
SCREEN_HEIGHT = 600
FPS = 60
WINDOW_TITLE = "Air Hockey"

# ── Table / Rink ─────────────────────────────────────────────────────
TABLE_MARGIN = 40  # pixels from screen edge to rink walls
GOAL_WIDTH = 140  # opening size for each goal (top/bottom centered)
RINK_CORNER_RADIUS = 30
CENTER_LINE_Y = SCREEN_HEIGHT // 2

# Derived rink bounds
RINK_LEFT = TABLE_MARGIN
RINK_RIGHT = SCREEN_WIDTH - TABLE_MARGIN
RINK_TOP = TABLE_MARGIN
RINK_BOTTOM = SCREEN_HEIGHT - TABLE_MARGIN
RINK_WIDTH = RINK_RIGHT - RINK_LEFT
RINK_HEIGHT = RINK_BOTTOM - RINK_TOP
RINK_CENTER_X = SCREEN_WIDTH // 2
RINK_CENTER_Y = SCREEN_HEIGHT // 2

# Goal positions (goals on top and bottom, centered horizontally)
GOAL_LEFT_X = RINK_CENTER_X - GOAL_WIDTH // 2
GOAL_RIGHT_X = RINK_CENTER_X + GOAL_WIDTH // 2
GOAL_DEPTH = 20  # how far the goal extends beyond the wall visually

# ── Paddle ───────────────────────────────────────────────────────────
PADDLE_RADIUS = 28
PADDLE_MAX_SPEED = 420.0  # px/s
PADDLE_ACCELERATION = 2400.0  # px/s^2
PADDLE_FRICTION = 0.88  # velocity multiplier per frame (applied as drag)
PADDLE_MASS = 2.0

# Boost
BOOST_MULTIPLIER = 1.7
BOOST_MAX_ENERGY = 100.0
BOOST_DRAIN_RATE = 50.0  # per second while boosting
BOOST_REGEN_RATE = 15.0  # per second while not boosting

# ── Puck ─────────────────────────────────────────────────────────────
PUCK_RADIUS = 14
PUCK_MAX_SPEED = 900.0
PUCK_INITIAL_SPEED = 0.0  # starts at rest after goal
PUCK_FRICTION = 0.997  # per-frame drag (very low for air hockey feel)
PUCK_MASS = 1.0
PUCK_WALL_RESTITUTION = 0.85  # bounciness off walls
PUCK_PADDLE_RESTITUTION = 1.05  # slight energy gain on paddle hit

# Rally speed-up
RALLY_SPEED_INCREMENT = 8.0  # added per paddle hit
RALLY_MAX_EXTRA_SPEED = 300.0

# Spin / english effect
SPIN_FACTOR = 0.15  # how much tangential paddle velocity curves the puck

# Trail
TRAIL_MIN_SPEED = 250.0  # puck speed threshold to show trail
TRAIL_LENGTH = 12
TRAIL_ALPHA_START = 120

# ── Power-Ups ────────────────────────────────────────────────────────
POWERUP_SPAWN_MIN = 8.0  # seconds
POWERUP_SPAWN_MAX = 14.0
POWERUP_RADIUS = 16
POWERUP_DURATION = 5.0  # seconds each effect lasts
POWERUP_FREEZE_DURATION = 1.0

POWERUP_BIGGER_SCALE = 1.5  # paddle radius multiplier
POWERUP_SMALLER_SCALE = 0.6
POWERUP_SPEED_BOOST_MULT = 1.4

POWERUP_MAGNET_RANGE = 120.0  # pixels
POWERUP_MAGNET_STRENGTH = 200.0  # acceleration toward puck

# Power-up type identifiers
PU_BIGGER = "bigger"
PU_SMALLER = "smaller"
PU_SPEED = "speed"
PU_MAGNET = "magnet"
PU_FREEZE = "freeze"
POWERUP_TYPES = [PU_BIGGER, PU_SMALLER, PU_SPEED, PU_MAGNET, PU_FREEZE]

# ── AI ───────────────────────────────────────────────────────────────
AI_DIFFICULTY = {
    "easy": {
        "reaction_delay": 0.25,  # seconds of lag
        "max_speed_mult": 0.6,
        "prediction": "none",  # just follows puck y
        "overshoot": 30.0,  # random offset
        "boost_chance": 0.05,
    },
    "medium": {
        "reaction_delay": 0.12,
        "max_speed_mult": 0.85,
        "prediction": "linear",
        "overshoot": 12.0,
        "boost_chance": 0.15,
    },
    "hard": {
        "reaction_delay": 0.04,
        "max_speed_mult": 1.0,
        "prediction": "bounce",  # ray-reflect
        "overshoot": 4.0,
        "boost_chance": 0.30,
    },
}

# ── Match Rules ──────────────────────────────────────────────────────
DEFAULT_GOALS_TO_WIN = 7
DEFAULT_MATCH_TIME = 90  # seconds
GOAL_RESET_PAUSE = 1.5  # seconds for goal animation + countdown
COUNTDOWN_DURATION = 1.0  # seconds for "3-2-1" before puck drops

# ── Arena Themes ─────────────────────────────────────────────────────
ARENAS = {
    "classic": {
        "name": "Classic",
        "puck_friction": 0.997,
        "paddle_friction": 0.88,
        "paddle_speed_mult": 1.0,
        "puck_speed_mult": 1.0,
        "bg_color": (30, 60, 30),
        "rink_color": (50, 100, 50),
        "line_color": (80, 140, 80),
        "wall_color": (120, 80, 40),
        "description": "Standard table. Balanced play.",
    },
    "ice": {
        "name": "Ice Rink",
        "puck_friction": 0.9995,
        "paddle_friction": 0.82,
        "paddle_speed_mult": 1.1,
        "puck_speed_mult": 1.2,
        "bg_color": (20, 30, 50),
        "rink_color": (40, 70, 120),
        "line_color": (80, 130, 200),
        "wall_color": (60, 90, 140),
        "description": "Low friction. Fast puck.",
    },
    "rough": {
        "name": "Rough",
        "puck_friction": 0.990,
        "paddle_friction": 0.92,
        "paddle_speed_mult": 0.8,
        "puck_speed_mult": 0.85,
        "bg_color": (50, 35, 20),
        "rink_color": (90, 65, 40),
        "line_color": (130, 100, 70),
        "wall_color": (70, 50, 30),
        "description": "High friction. Slower paddles.",
    },
}

# ── Particles ────────────────────────────────────────────────────────
PARTICLE_COUNT_HIT = 8
PARTICLE_COUNT_GOAL = 25
PARTICLE_SPEED_MIN = 50.0
PARTICLE_SPEED_MAX = 300.0
PARTICLE_LIFETIME = 0.5  # seconds
PARTICLE_SIZE = 3

# Screen shake
SCREEN_SHAKE_INTENSITY = 6  # max offset pixels
SCREEN_SHAKE_DURATION = 0.15  # seconds
SCREEN_SHAKE_SPEED_THRESHOLD = 500.0  # puck speed to trigger shake

# ── Colors ───────────────────────────────────────────────────────────
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (220, 50, 50)
BLUE = (50, 100, 220)
YELLOW = (240, 220, 60)
GREEN = (60, 200, 80)
ORANGE = (240, 160, 40)
CYAN = (60, 220, 220)
MAGENTA = (200, 60, 200)
GRAY = (140, 140, 140)
DARK_GRAY = (60, 60, 60)
LIGHT_GRAY = (200, 200, 200)

PLAYER1_COLOR = RED
PLAYER2_COLOR = BLUE
PUCK_COLOR = WHITE
POWERUP_COLORS = {
    PU_BIGGER: GREEN,
    PU_SMALLER: MAGENTA,
    PU_SPEED: ORANGE,
    PU_MAGNET: CYAN,
    PU_FREEZE: (150, 200, 255),
}

# ── Sound ────────────────────────────────────────────────────────────
SOUND_ENABLED = True
SOUND_SAMPLE_RATE = 22050
SOUND_VOLUME = 0.3
