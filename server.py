from cryptography.fernet import Fernet
import threading
import msgpack
import pickle
import socket
import select
import sys



SERVER_ADDRESS = ("localhost", 25589)
ALLOW_SELF_RECALL: bool = True



class Server:
    def __init__(self):
        self.running: bool = True
        self.addrs: list[tuple[str, int]] = []
        self.server: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.backlog: int = 10
        self.buffersize: int = 60000
        self.max_clients: int = 2
        self.server_key: bytes = Fernet.generate_key()
    
    def run(self):
        self.server.bind(SERVER_ADDRESS)
        print(f"[ cCord ] Listening on: {SERVER_ADDRESS}")
        try:
            while self.running:
                try:
                    readable, _, _ = select.select([self.server], [], [], 0.1)
                    if readable:
                        data, addr = self.server.recvfrom(self.buffersize)

                        if addr not in self.addrs:
                            print("[ cCord ] New client connected!")
                            self.addrs.append(addr)
                        
                        dat = None
                        try:
                            dat = pickle.loads(msgpack.unpackb(data))
                            if not "type" in dat and (dat["type"] != "connect" or dat["type" != "disconnect"] or dat["type"] == "ping"): pass
                            if dat["type"] == "connect":
                                print("[ cCord ][ Connect ] Client requested a connection")
                                pack: dict = {
                                    "type": "connected",
                                    "key": self.server_key
                                }
                                rdata = msgpack.packb(pickle.dumps(
                                    pack
                                ))
                                self.server.sendto(rdata, addr)
                            if dat["type"] == "disconnect":
                                print("[ cCord ][ Disconnect ] Client disconnected")
                                self.addrs.remove(addr)
                            if dat["type"] == "ping":
                                self.server.sendto(msgpack.packb(pickle.dumps({ "type": "pong", "content": "responded!" })), addr)
                        except Exception as e:
                            dat = None
                            pass

                        if not dat or dat["type"] != "connect" or dat["type"] != "disconnect" or data["type"] != "ping":
                            for adr in self.addrs[:]:
                                if not ALLOW_SELF_RECALL:
                                    if adr != addr:
                                        try:
                                            _, writable, _ = select.select([], [self.server], [], 0.1)
                                            if self.server in writable:
                                                self.server.sendto(data, adr)
                                        except (BrokenPipeError, ConnectionResetError):
                                            print("[ cCord ] Client disconnected. Removing from list.")
                                            self.addrs.remove(addr)
                                    else:
                                        continue
                                else:
                                    try:
                                        _, writable, _ = select.select([], [self.server], [], 0.1)
                                        if self.server in writable:
                                            self.server.sendto(data, adr)
                                    except (BrokenPipeError, ConnectionResetError):
                                        print("[ cCord ] Client disconnected. Removing from list.")
                                        self.addrs.remove(addr)
                except KeyboardInterrupt:
                    print("[ cCord ] Manual Interrupt Detected")
                    self.running = False
                    break

        except Exception as e:
            print(f"[ cCord ] Server error: {e}")
            self.running = False

        finally:
            print(f"[ cCord ] Closed server!")
            self.running = False
            self.addrs.clear()
            self.server.close()


if __name__ == "__main__":
    server = Server()
    server.run()
