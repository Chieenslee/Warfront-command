import socket
import threading
import json
import time
import uuid
import zlib

class NetworkServer:
    def __init__(self, port=19444):
        self.host = "0.0.0.0"
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Giữ port để dùng lại được ngay sau khi tắt server (tránh lỗi Address already in use)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.socket.bind((self.host, self.port))
        except Exception as e:
            print(f"[SERVER] Bind error: {e}")
        self.socket.setblocking(False)
        self.clients = {}  # addr -> {"name": str, "inputs": dict, "last_seen": float, "id": str, "ready": bool}
        self.running = True
        self._last_error = ""
        self._lock = threading.Lock()
        self.state_data = zlib.compress(b'{"status": "lobby"}')
        self.thread = threading.Thread(target=self._listen, daemon=True)
        self.thread.start()

    def _report_error(self, label: str, exc: Exception):
        message = f"{label}: {exc}"
        if message != self._last_error:
            print(f"[SERVER] {message}")
            self._last_error = message

    def _listen(self):
        while self.running:
            try:
                data, addr = self.socket.recvfrom(65536)
                packet = json.loads(zlib.decompress(data).decode("utf-8"))
                with self._lock:
                    client_id = packet.get("id", str(uuid.uuid4()))
                    if addr not in self.clients:
                        old_addr = next((a for a, c in self.clients.items() if c.get("id") == client_id), None)
                        if old_addr is not None:
                            self.clients[addr] = self.clients.pop(old_addr)
                        elif len(self.clients) < 4: # Max 3 remote clients + 1 host loopback
                            self.clients[addr] = {
                                "name": packet.get("name", "Unknown"), 
                                "inputs": {}, 
                                "last_seen": time.time(),
                                "id": client_id,
                                "ready": bool(packet.get("ready", True)),
                            }
                    
                    if addr in self.clients:
                        self.clients[addr]["name"] = packet.get("name", self.clients[addr]["name"])
                        self.clients[addr]["inputs"] = packet.get("inputs", {})
                        self.clients[addr]["last_seen"] = time.time()
                        self.clients[addr]["ready"] = bool(packet.get("ready", True))
                
                # Echo state back
                try:
                    with self._lock:
                        data_to_send = self.state_data
                        
                    state_str = zlib.decompress(data_to_send).decode("utf-8")
                    state = json.loads(state_str)
                    if state.get("status") == "lobby":
                        with self._lock:
                            state.setdefault("players", [c["name"] for c in self.clients.values()])
                            state.setdefault(
                                "lobby_players",
                                [
                                    {
                                        "id": c["id"],
                                        "name": c["name"],
                                        "ready": c.get("ready", True),
                                        "connected": True,
                                    }
                                    for c in self.clients.values()
                                ],
                            )
                        self.socket.sendto(zlib.compress(json.dumps(state).encode("utf-8")), addr)
                    else:
                        self.socket.sendto(data_to_send, addr)
                except Exception as e:
                    self._report_error("send state", e)
            except BlockingIOError:
                time.sleep(0.01)
            except Exception as e:
                self._report_error("receive packet", e)
                
            # Cleanup disconnected
            now = time.time()
            with self._lock:
                disconnected = [a for a, c in self.clients.items() if now - c["last_seen"] > 5.0]
                for a in disconnected:
                    del self.clients[a]

    def get_clients(self) -> dict:
        with self._lock:
            return dict(self.clients)

    def broadcast_state(self, state: dict):
        with self._lock:
            self.state_data = zlib.compress(json.dumps(state).encode("utf-8"))
        
    def stop(self):
        self.running = False
        if threading.current_thread() is not self.thread:
            self.thread.join(timeout=0.12)
        try:
            self.socket.close()
        except OSError as e:
            self._report_error("close socket", e)


class NetworkClient:
    def __init__(self, server_ip, player_name, port=19444):
        self.server_ip = server_ip
        self.port = port
        self.player_name = player_name
        stable_name = player_name.strip().lower() or "player"
        self.client_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"warfront:{socket.gethostname()}:{uuid.getnode()}:{stable_name}"))
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setblocking(False)
        self.server_addr = (self.server_ip, self.port)
        self.running = True
        self.server_state = {}
        self.inputs = {}
        self.connected = False
        self.last_state_time = 0
        self._last_error = ""
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _report_error(self, label: str, exc: Exception):
        message = f"{label}: {exc}"
        if message != self._last_error:
            print(f"[CLIENT] {message}")
            self._last_error = message

    def _loop(self):
        while self.running:
            packet = {"name": self.player_name, "id": self.client_id, "ready": True, "inputs": self.inputs}
            try:
                self.socket.sendto(zlib.compress(json.dumps(packet).encode("utf-8")), self.server_addr)
            except Exception as e:
                self._report_error("send inputs", e)
            
            try:
                data, _ = self.socket.recvfrom(65536)
                self.server_state = json.loads(zlib.decompress(data).decode("utf-8"))
                self.connected = True
                self.last_state_time = time.time()
            except BlockingIOError:
                pass
            except Exception as e:
                self._report_error("receive state", e)
                
            if time.time() - self.last_state_time > 3.0:
                self.connected = False
                
            time.sleep(0.02)

    def update_inputs(self, inputs: dict):
        self.inputs = inputs

    def stop(self):
        self.running = False
        if threading.current_thread() is not self.thread:
            self.thread.join(timeout=0.12)
        try:
            self.socket.close()
        except OSError as e:
            self._report_error("close socket", e)
