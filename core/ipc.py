import socket
import os
import json
from pathlib import Path

SOCKET_PATH = "/tmp/sexta-feira.sock"

class IPC:
    def __init__(self, path=SOCKET_PATH):
        self.path = path
        self.server_socket = None
        self.client_socket = None
    
    def create_server(self):
        if os.path.exists(self.path):
            try:
                os.unlink(self.path)
            except:
                pass
        self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server_socket.bind(self.path)
        self.server_socket.listen(1)
        return self.server_socket
    
    def connect_client(self):
        self.client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.client_socket.connect(self.path)
        return self.client_socket
    
    def send(self, msg):
        try:
            if self.client_socket:
                data = json.dumps(msg).encode('utf-8')
                self.client_socket.sendall(data + b'\n')
                return True
        except Exception as e:
            print(f"IPC send error: {e}")
        return False
    
    def recv(self, sock, timeout=None):
        try:
            if timeout:
                sock.settimeout(timeout)
            data = b''
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b'\n' in data:
                    break
            if timeout:
                sock.settimeout(None)
            if not data:
                return None
            # Remove newline
            data = data.strip()
            if not data:
                return None
            return json.loads(data.decode('utf-8'))
        except Exception as e:
            print(f"IPC recv error: {e}")
            return None
    
    def close(self):
        try:
            if self.client_socket:
                self.client_socket.close()
            if self.server_socket:
                self.server_socket.close()
            if os.path.exists(self.path):
                os.unlink(self.path)
        except:
            pass
