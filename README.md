# Air Hockey

A feature-rich air hockey game built with Python and Pygame. Play locally against a friend, challenge the AI, practice solo, or compete over LAN.

## Features

- **4 Game Modes** — Local 1v1, vs AI, Practice, and LAN Multiplayer
- **3 AI Difficulties** — Easy (follows puck), Medium (linear prediction), Hard (bounce prediction with wall reflections)
- **5 Power-Ups** — Bigger paddle, Shrink opponent, Speed boost, Magnet, and Freeze
- **3 Arena Themes** — Classic, Ice Rink (fast & slippery), Rough (slow & controlled)
- **Match Options** — First to N goals or timed matches (60/90/120 seconds)
- **Particle Effects & Screen Shake** — Hit sparks, goal explosions, puck trails, and camera shake on hard hits
- **Procedural Audio** — All sound effects synthesized at runtime, no external audio files needed
- **Physics** — Spin/english on the puck, rally speed-up, per-arena friction and restitution

## Requirements

- Python 3
- Pygame 2.6.1

## Installation

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Running

```bash
python main.py
```

## Controls

| Action | Player 1 (Bottom) | Player 2 (Top, Local 1v1) |
|--------|-------------------|---------------------------|
| Move | WASD or Mouse | Arrow Keys |
| Boost | Left Shift | Right Shift |

- **ESC** — Pause game
- In vs AI and Practice modes, arrow keys also control Player 1

## LAN Multiplayer

1. One player selects **Host** from the Online menu — the game displays your local IP address
2. The other player selects **Join** and enters the host's IP address
3. The host starts the match once the client connects

The host controls the bottom paddle and the client controls the top paddle. Host runs authoritative physics — both players need to be on the same local network.

## Project Structure

```
air_hockey/
├── main.py           # Game loop, state management, rendering
├── settings.py       # Constants: physics, colors, network, AI, arenas
├── entities.py       # Paddle, Puck, PowerUp, Particle classes
├── ai.py             # AI controller with 3 difficulty modes
├── network.py        # TCP game server and client
├── ui.py             # Menus, buttons, HUD
└── requirements.txt  # Dependencies
```
