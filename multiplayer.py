"""Cliente WebSocket. Eventos de UI devem ser despachados para a thread Kivy."""
import json
import threading
import websocket


class LudaraMultiplayer:
    def __init__(self, ws_base_url, room, token, on_event, on_error=None, on_close=None):
        self.ws_base_url = ws_base_url.rstrip("/")
        self.room = room
        self.token = token
        self.on_event = on_event
        self.on_error = on_error or (lambda error: None)
        self.on_close = on_close or (lambda: None)
        self.app = None
        self.thread = None
        self.connected = False
        self._stop = threading.Event()

    def connect(self):
        if self.thread and self.thread.is_alive():
            return
        url = f"{self.ws_base_url}/ws/{self.room}"
        self.app = websocket.WebSocketApp(
            url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        self.thread = threading.Thread(
            target=lambda: self.app.run_forever(ping_interval=25, ping_timeout=10),
            name="LudaraWebSocket", daemon=True,
        )
        self.thread.start()

    def _send(self, payload):
        app = self.app
        if app is None:
            return False
        try:
            app.send(json.dumps(payload, separators=(",", ":")))
            return True
        except Exception as exc:
            self.on_error(exc)
            return False

    def _on_open(self, _ws):
        self._send({"type": "auth", "token": self.token})

    def _on_message(self, _ws, message):
        try:
            payload = json.loads(message)
        except (TypeError, json.JSONDecodeError):
            self.on_error(ValueError("Mensagem multiplayer inválida"))
            return
        if payload.get("type") == "joined":
            self.connected = True
        self.on_event(payload)

    def _on_error(self, _ws, error):
        self.on_error(error)

    def _on_close(self, _ws, _status, _message):
        self.connected = False
        self.on_close()

    def send_chat(self, message):
        message = str(message).strip()
        if message:
            return self._send({"type": "chat", "message": message[:300]})
        return False

    def send_position(self, x, y, z, yaw=0):
        return self._send({"type": "position", "x": float(x), "y": float(y), "z": float(z), "yaw": float(yaw)})

    def close(self):
        self._stop.set()
        self.connected = False
        if self.app:
            try:
                self.app.close()
            except Exception:
                pass
