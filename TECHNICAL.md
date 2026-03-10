# Technical Documentation

Developer reference for the Air Hockey codebase — architecture, algorithms, and design decisions.

## Project Structure

```
main.py       – Game class, state machine, main loop, procedural audio, rendering
settings.py   – All constants: physics, display, arenas, AI tuning, colors
entities.py   – Paddle, Puck, PowerUp, Particle, ParticleSystem
ai.py         – AIController with 3 difficulty levels
network.py    – TCP networking: GameServer, GameClient, wire protocol
ui.py         – Menus, HUD, Button/Selector components, text input
```

## Architecture Overview

The game is a single-class controller (`Game` in `main.py`) using a state machine pattern. All game state lives on the `Game` instance — entities, scores, timers, network handles. The main loop runs at 60 FPS with a capped delta time (`dt = min(tick/1000, 0.05)`) to prevent physics explosions.

Module responsibilities:
- **settings.py** — Single source of truth for all tunable parameters. No logic, only constants.
- **entities.py** — Pure game objects with `update(dt)` and `draw(surface)` methods. No knowledge of game state or other entities.
- **ai.py** — Stateless per-frame: given (paddle, puck), returns (ax, ay, boost).
- **network.py** — Threaded I/O with queue-based message passing. No pygame dependency.
- **ui.py** — Menu screens and HUD. Each menu class has `handle_event()`, `update()`, `draw()`.

## Game Loop & State Management

### States

The `Game` class defines 9 states:

| State | Description |
|---|---|
| `menu` | Main menu — mode selection, settings |
| `online_menu` | Host/Join selection |
| `online_host_lobby` | Host waiting for client connection |
| `online_client_lobby` | Client entering IP and connecting |
| `countdown` | Pre-round countdown (1 second) |
| `playing` | Active gameplay with physics |
| `goal` | Brief pause after goal (1.5 seconds) |
| `paused` | Pause overlay (ESC key) |
| `end` | Match over — shows winner and scores |

### Frame Update Cycle

```
run()
  ├── dt = clock.tick(60) / 1000, capped at 0.05s
  ├── pygame.event.get() → _handle_event() routes to current state
  ├── UI update (mouse hover for buttons)
  ├── update(dt) — physics, AI, network, collisions
  └── draw() — arena, entities, particles, HUD, overlays
```

### State Transitions

- `menu` → `playing` (via `countdown`) on mode select
- `menu` → `online_menu` → `online_host_lobby` or `online_client_lobby`
- `playing` → `goal` on score → `countdown` → `playing`
- `playing` → `paused` on ESC (host only in online)
- `playing` → `end` when match conditions met
- `end` → `menu` or replay

## Physics

### Paddle Movement

Paddles use acceleration-based movement:
1. Input provides normalized direction `(ax, ay)` in [-1, 1]
2. Acceleration: `velocity += direction * PADDLE_ACCELERATION(2400) * dt`
3. Friction/drag: `velocity *= PADDLE_FRICTION(0.88)` per frame
4. Speed clamped to `PADDLE_MAX_SPEED(420)` × arena multiplier × boost multiplier
5. Position clamped to own half of rink (top or bottom of center line)

Mouse mode bypasses acceleration — the paddle tracks the cursor directly, with velocity derived from position delta for collision response.

### Puck Physics

- Per-frame friction: `velocity *= PUCK_FRICTION(0.997)` — very low drag for air hockey feel
- Max speed: `PUCK_MAX_SPEED(900) + rally_extra_speed`, scaled by arena `puck_speed_mult`
- Wall restitution: `0.85` — loses 15% speed on wall bounce
- Paddle restitution: `1.05` — gains 5% speed on paddle hit

### Impulse-Based Paddle-Puck Collisions

`Puck.collide_paddle()` in `entities.py:272`:

1. **Detection** — Circle-circle overlap: `dist < puck.radius + paddle.radius`
2. **Separation** — Push puck out along normal by overlap amount
3. **Skip if separating** — Dot product of relative velocity with normal must be negative
4. **Impulse calculation** — Elastic collision formula with restitution `e`:
   ```
   j = -(1 + e) * rel_v_normal / (1/puck_mass + 1/paddle_mass)
   ```
   Puck mass = 1.0, paddle mass = 2.0, so the paddle imparts more momentum.
5. **Spin/english** — Tangential component of paddle velocity curves the puck:
   ```
   tangent = (-normal_y, normal_x)
   puck_velocity += tangent * paddle_tangent_speed * SPIN_FACTOR(0.15)
   ```
6. **Rally speed-up** — Each paddle hit adds `RALLY_SPEED_INCREMENT(8)` to the puck's max speed cap, up to `RALLY_MAX_EXTRA_SPEED(300)`. Resets on goal.

### Wall Collisions

`Puck.collide_walls()` checks bounds in order: left, right, top, bottom. On top/bottom walls, the puck checks if it's within the goal opening (`GOAL_LEFT_X` to `GOAL_RIGHT_X`) — if yes, it's a goal; if no, it bounces with `PUCK_WALL_RESTITUTION(0.85)`.

### Arena Modifiers

Three arenas modify physics parameters:

| Arena | Puck Friction | Paddle Friction | Paddle Speed | Puck Speed |
|---|---|---|---|---|
| Classic | 0.997 | 0.88 | 1.0× | 1.0× |
| Ice Rink | 0.9995 | 0.82 | 1.1× | 1.2× |
| Rough | 0.990 | 0.92 | 0.8× | 0.85× |

Modifiers are applied at match start by setting `paddle.friction_mult`, `paddle.speed_mult`, `puck.friction`, and `puck.speed_mult` on the entities.

## AI System

`AIController` in `ai.py` controls the top-half paddle.

### Difficulty Levels

| Parameter | Easy | Medium | Hard |
|---|---|---|---|
| Reaction delay | 0.25s | 0.12s | 0.04s |
| Speed multiplier | 0.6× | 0.85× | 1.0× |
| Prediction mode | none | linear | bounce |
| Overshoot (random offset) | ±30px | ±12px | ±4px |
| Boost chance | 5% | 15% | 30% |

### Update Loop

Each frame:
1. Increment `reaction_timer` by `dt`
2. When timer exceeds `reaction_delay`, recompute target position and add random noise (overshoot)
3. Compute normalized direction from paddle to target
4. Scale by `max_speed_mult`
5. Decide boost: if puck heading toward AI (`vy < -50`) and paddle far from target (`dist > 100`), randomly boost

### Prediction Algorithms

**None (Easy)** — Follows puck's current X position. Stays on defense line (25% into its half).

**Linear (Medium)** — Projects puck trajectory to defense line: `predicted_x = puck.x + puck.vx * t` where `t = (defense_y - puck.y) / puck.vy`. No wall bounces considered. If puck is within 150px and in AI half, moves directly to puck.

**Bounce (Hard)** — Full trajectory simulation: steps the puck forward at 1/60s intervals for up to 180 steps (3 seconds), reflecting off left/right/top/bottom walls. Stops when the simulated puck reaches the defense zone or enters a goal. If puck is within 120px and in AI half, moves directly to puck for aggressive play.

### Defensive Behavior

When the puck moves away from the AI (`vy > 20`), the AI drifts to its home position (35% into its half) while loosely tracking the puck's X coordinate.

## Networking

### Protocol

TCP with length-prefixed JSON messages:
- **Header**: 4 bytes, network byte order (`!I`) — message length
- **Payload**: UTF-8 JSON, max 1 MB
- `TCP_NODELAY` enabled on all sockets for low latency

### Host-Authoritative Model

The host runs all physics. The client is a thin input sender + state renderer:

```
Client                          Host
  │── input {ax, ay, boost} ──→  │  (every frame)
  │                               │  runs physics, AI, collisions
  │←── state snapshot ──────────  │  (every frame)
  │    applies snapshot to        │
  │    local entities             │
```

### Connection Handshake

1. Client sends `{"type": "join", "version": 1}`
2. Server validates version, responds `{"type": "welcome", "version": 1}`
3. Host lobby shows "Player connected!"
4. Host sends `{"type": "start", "settings": {...}}` when ready
5. Both sides call `start_match("online", settings)`

### Message Types

| Type | Direction | Content |
|---|---|---|
| `join` | Client → Host | `{version}` |
| `welcome` | Host → Client | `{version}` |
| `start` | Host → Client | `{settings: {match_mode, match_param, arena, mouse_mode}}` |
| `input` | Client → Host | `{ax, ay, boost}` |
| `state` | Host → Client | Full game state snapshot (positions, velocities, scores, timers, power-up) |
| `disconnect` | Either | Clean shutdown signal |

### State Snapshot

The host serializes every frame (`_build_state_snapshot`):
- Paddle 1 & 2: position, velocity, radius, boost energy, frozen state, active effects
- Puck: position, velocity, active flag
- Scores, match timer, goal timer, countdown timer
- Current game state string
- Power-up (type, position) if present

### Threading

- `GameServer` uses two daemon threads: `_accept_loop` (waits for connection) and `_recv_loop` (reads client input)
- `GameClient` uses one daemon thread: `_recv_loop` (reads state + messages from host)
- Thread-safe communication via `queue.Queue` with small `maxsize` (2–10)
- Input queue uses replace-latest pattern: old input is discarded before putting new input
- State queue uses drain-to-latest pattern: client reads all queued states, keeps only the last

### WSL IP Detection

`get_local_ip()` in `network.py`:
1. Check `/proc/version` for "microsoft" to detect WSL
2. If WSL: call `powershell.exe` to get the Windows host's LAN IP via `Get-NetRoute` + `Get-NetIPAddress`
3. Otherwise: use the UDP socket trick (`connect("8.8.8.8", 80)` then `getsockname()`)
4. Fallback: `127.0.0.1`

## Power-Up System

### Types

| Type | ID | Effect | Target |
|---|---|---|---|
| Bigger Paddle | `bigger` | Radius × 1.5 | Collector |
| Smaller Paddle | `smaller` | Radius × 0.6 | Opponent |
| Speed Boost | `speed` | Paddle speed × 1.4 | Collector |
| Magnet | `magnet` | Attracts puck toward paddle | Collector |
| Freeze | `freeze` | Immobilizes paddle | Opponent |

### Spawning

- Timer counts down from a random interval between `POWERUP_SPAWN_MIN(8s)` and `POWERUP_SPAWN_MAX(14s)`
- Spawns at a random position within the rink (60px margin from walls)
- Only one power-up exists at a time
- Type chosen uniformly at random from all 5 types

### Collection & Duration

- Collected when paddle circle overlaps power-up circle
- Self-buffs (bigger, speed, magnet) last `POWERUP_DURATION(5s)`, tracked in `paddle.effects` dict
- Opponent-targeting effects (smaller, freeze) applied to the other paddle
- Freeze duration is shorter: `POWERUP_FREEZE_DURATION(1s)`
- All effects cleared on goal

### Magnet Attraction Physics

When a paddle has the magnet effect active (`main.py:604`):
```
distance = hypot(paddle - puck)
if 0 < distance < POWERUP_MAGNET_RANGE(120):
    force = POWERUP_MAGNET_STRENGTH(200) * (1 - distance/range)
    puck.velocity += direction_to_paddle * force * dt
```
Linear falloff — strongest at close range, zero at 120px.

## Procedural Audio

All sounds are generated at startup — no audio files needed.

### Tone Generation (`_generate_tone`)

Sine wave with linear decay envelope:
```
envelope = max(0, 1.0 - t / duration)
sample = volume * envelope * 32767 * sin(2π * frequency * t)
```
Output format: 16-bit signed stereo at `SOUND_SAMPLE_RATE(22050)` Hz, packed as `<hh` (little-endian, left+right channels identical).

### Sound Effects

| Sound | Type | Frequency | Duration | Volume |
|---|---|---|---|---|
| hit | Tone | 440 Hz | 50 ms | 0.25 |
| wall | Tone | 330 Hz | 40 ms | 0.15 |
| goal | Tone | 220 Hz | 400 ms | 0.30 |
| countdown | Tone | 660 Hz | 100 ms | 0.20 |
| powerup | Tone | 880 Hz | 80 ms | 0.20 |

### Noise Burst (`_generate_noise_burst`)

Random samples with linear decay — used for hit impact sounds. Currently generated but not used in the sound dict (available for future use).

Audio gracefully degrades: if `pygame.mixer.init()` fails (no audio device), sounds are silently skipped.

## Rendering

### Draw Order

1. Arena background (fill with arena `bg_color`)
2. Rink surface (rounded rectangle with `rink_color`)
3. Center line and circle
4. Wall segments (with goal gaps)
5. Goal areas (dark rectangles behind walls)
6. Goal posts (small circles at goal corners)
7. Power-up (if present) — pulsing glow + icon letter
8. Puck + trail
9. Paddles (outer ring + inner circle + highlight)
10. Particles
11. HUD (scores, timer, boost meters, effect icons, countdown)
12. Goal flash + "GOAL!" text (during `goal` state)
13. Screen shake offset applied to final blit
14. Pause/End overlay (if applicable)

### Screen Shake

Triggered when puck speed exceeds `SCREEN_SHAKE_SPEED_THRESHOLD(500)` on a paddle hit:
- Duration: `SCREEN_SHAKE_DURATION(0.15s)`
- Intensity decays linearly from `SCREEN_SHAKE_INTENSITY(6px)` to 0
- Random offset applied to the game surface blit each frame

### Puck Trail

When `puck.speed >= TRAIL_MIN_SPEED(250)`:
- Stores up to `TRAIL_LENGTH(12)` past positions
- Each trail dot rendered as a translucent circle on a per-pixel alpha surface
- Size and alpha scale up from oldest (smallest/faintest) to newest (largest/brightest)
- Alpha starts at `TRAIL_ALPHA_START(120)` for the newest dot

### Particle System

Emitted on paddle hits (8 particles) and goals (25 particles):
- Random direction, speed in configurable range (default 50–300 px/s)
- Velocity decays by `0.95×` per frame
- Lifetime: `PARTICLE_LIFETIME(0.5s)`
- Size and color fade with remaining lifetime
- Goal particles use the scoring player's color

### Power-Up Visuals

- Pulsing radius: `radius * (1 + 0.15 * sin(timer * 5))`
- Glow: translucent circle at 2× radius with alpha 40
- Icon letter centered on the circle (B/S/F/M/X)

## UI System

### Components

**Button** — Rectangular with rounded corners, hover highlight, centered text. Click detection via `rect.collidepoint()`.

**Selector** — Label + left/right arrow buttons + current value display. Cycles through options list with wrapping.

### Menu Screens

| Screen | Class | Purpose |
|---|---|---|
| Main Menu | `MainMenu` | Mode buttons (Local 1v1, vs AI, Practice, Online), settings selectors (rules, arena, difficulty), mouse toggle |
| Online Menu | `OnlineMenu` | Host Game / Join Game / Back |
| Host Lobby | `HostLobby` | Shows LAN IP:port, connection status, Start/Cancel buttons |
| Join Lobby | `JoinLobby` | Text input for IP address (accepts `0-9`, `.`, `:`), Connect/Cancel buttons, connection status |
| Pause Menu | `PauseMenu` | Resume / Restart / Quit to Menu (semi-transparent overlay) |
| End Screen | `EndScreen` | Winner text, final score, Play Again / Main Menu |

### HUD Elements

- **Scores** — Top-left for P2 (blue), bottom-left for P1 (red)
- **Match info** — Center top: "First to N" or countdown timer (M:SS)
- **Player labels** — Context-aware: "You (Host)"/"Player 2" in online, "Player"/"AI" in vs AI
- **Boost meters** — Horizontal bars at right edge, one per player
- **Effect icons** — Colored squares with abbreviated names and remaining time, stacked vertically
- **Countdown number** — Large centered text during countdown state

### Text Input (Join Lobby)

Character whitelist: `0123456789.:` — max 21 characters. Supports `ip:port` format with optional port (defaults to 5555). Backspace to delete, Enter to connect.
