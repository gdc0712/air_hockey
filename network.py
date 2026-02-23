"""
Air Hockey Game - LAN Multiplayer Networking
Host-authoritative model over TCP with length-prefixed JSON messages.
"""
import json
import socket
import struct
import threading
import queue

from settings import NETWORK_PORT, NETWORK_VERSION

# ── Wire helpers ─────────────────────────────────────────────────────

def _send_msg(sock, data):
    """Send a length-prefixed JSON message. Returns False on failure."""
    try:
        payload = json.dumps(data).encode("utf-8")
        header = struct.pack("!I", len(payload))
        sock.sendall(header + payload)
        return True
    except (OSError, BrokenPipeError):
        return False


def _recv_msg(sock):
    """Receive a length-prefixed JSON message. Returns None on failure."""
    try:
        header = _recv_exact(sock, 4)
        if header is None:
            return None
        length = struct.unpack("!I", header)[0]
        if length > 1_000_000:  # sanity limit
            return None
        payload = _recv_exact(sock, length)
        if payload is None:
            return None
        return json.loads(payload.decode("utf-8"))
    except (OSError, json.JSONDecodeError, struct.error):
        return None


def _recv_exact(sock, n):
    """Read exactly n bytes from socket. Returns None on disconnect."""
    data = bytearray()
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            return None
        data.extend(chunk)
    return bytes(data)


def get_local_ip():
    """Return this machine's LAN IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


# ── GameServer (Host side) ───────────────────────────────────────────

class GameServer:
    """Host-side networking. Accepts one client, receives input, sends state."""

    def __init__(self, port=NETWORK_PORT):
        self.port = port
        self._server_sock = None
        self._client_sock = None
        self._client_connected = False
        self._input_queue = queue.Queue(maxsize=5)
        self._running = False
        self._accept_thread = None
        self._recv_thread = None
        self._error = None

    def start(self):
        """Start listening for a client connection. Returns (success, error_msg)."""
        try:
            self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self._server_sock.bind(("", self.port))
            self._server_sock.listen(1)
            self._server_sock.settimeout(1.0)
            self._running = True
            self._accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
            self._accept_thread.start()
            return True, None
        except OSError as e:
            self._error = str(e)
            return False, str(e)

    def stop(self):
        """Clean shutdown."""
        self._running = False
        if self._client_sock:
            try:
                _send_msg(self._client_sock, {"type": "disconnect"})
            except OSError:
                pass
            try:
                self._client_sock.close()
            except OSError:
                pass
            self._client_sock = None
        if self._server_sock:
            try:
                self._server_sock.close()
            except OSError:
                pass
            self._server_sock = None
        self._client_connected = False

    def is_client_connected(self):
        return self._client_connected

    def get_client_input(self):
        """Non-blocking: returns (ax, ay, boost) or None."""
        try:
            return self._input_queue.get_nowait()
        except queue.Empty:
            return None

    def send_state(self, state_dict):
        """Send game state snapshot to client."""
        if self._client_sock and self._client_connected:
            state_dict["type"] = "state"
            if not _send_msg(self._client_sock, state_dict):
                self._on_client_lost()

    def send_message(self, msg_dict):
        """Send arbitrary message to client."""
        if self._client_sock and self._client_connected:
            if not _send_msg(self._client_sock, msg_dict):
                self._on_client_lost()

    def _accept_loop(self):
        """Wait for one client to connect."""
        while self._running and not self._client_connected:
            try:
                conn, addr = self._server_sock.accept()
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except socket.timeout:
                continue
            except OSError:
                break

            # Expect a join message
            msg = _recv_msg(conn)
            if msg and msg.get("type") == "join" and msg.get("version") == NETWORK_VERSION:
                self._client_sock = conn
                _send_msg(conn, {"type": "welcome", "version": NETWORK_VERSION})
                self._client_connected = True
                # Start receiving input
                self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
                self._recv_thread.start()
            else:
                conn.close()

    def _recv_loop(self):
        """Read input messages from client into queue."""
        while self._running and self._client_connected:
            msg = _recv_msg(self._client_sock)
            if msg is None:
                self._on_client_lost()
                break
            if msg.get("type") == "input":
                # Replace stale input — only latest matters
                try:
                    self._input_queue.get_nowait()
                except queue.Empty:
                    pass
                self._input_queue.put((msg.get("ax", 0), msg.get("ay", 0), msg.get("boost", False)))

    def _on_client_lost(self):
        self._client_connected = False
        if self._client_sock:
            try:
                self._client_sock.close()
            except OSError:
                pass
            self._client_sock = None


# ── GameClient (Client side) ────────────────────────────────────────

class GameClient:
    """Client-side networking. Connects to host, sends input, receives state."""

    def __init__(self):
        self._sock = None
        self._connected = False
        self._state_queue = queue.Queue(maxsize=2)
        self._msg_queue = queue.Queue(maxsize=10)
        self._recv_thread = None
        self._running = False

    def connect(self, host_ip, port=NETWORK_PORT, timeout=5.0):
        """Connect to host. Returns (success, error_msg)."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.settimeout(timeout)
            sock.connect((host_ip, port))
            # Send join
            _send_msg(sock, {"type": "join", "version": NETWORK_VERSION})
            # Wait for welcome
            msg = _recv_msg(sock)
            if msg and msg.get("type") == "welcome":
                self._sock = sock
                self._connected = True
                self._running = True
                self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
                self._recv_thread.start()
                return True, None
            else:
                sock.close()
                return False, "Server rejected connection"
        except socket.timeout:
            return False, "Connection timed out"
        except OSError as e:
            return False, str(e)

    def disconnect(self):
        """Clean shutdown."""
        self._running = False
        self._connected = False
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def is_connected(self):
        return self._connected

    def send_input(self, ax, ay, boost):
        """Send paddle input to host."""
        if self._sock and self._connected:
            if not _send_msg(self._sock, {"type": "input", "ax": ax, "ay": ay, "boost": boost}):
                self._on_disconnected()

    def get_state(self):
        """Non-blocking: returns latest state dict or None."""
        state = None
        try:
            while True:
                state = self._state_queue.get_nowait()
        except queue.Empty:
            pass
        return state

    def get_message(self):
        """Non-blocking: returns next non-state message or None."""
        try:
            return self._msg_queue.get_nowait()
        except queue.Empty:
            return None

    def _recv_loop(self):
        """Read messages from host, route to appropriate queue."""
        while self._running and self._connected:
            msg = _recv_msg(self._sock)
            if msg is None:
                self._on_disconnected()
                break
            if msg.get("type") == "state":
                # Keep only latest state
                try:
                    self._state_queue.get_nowait()
                except queue.Empty:
                    pass
                self._state_queue.put(msg)
            elif msg.get("type") == "disconnect":
                self._on_disconnected()
                break
            else:
                self._msg_queue.put(msg)

    def _on_disconnected(self):
        self._connected = False
        self._msg_queue.put({"type": "disconnect"})
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
