from cryptography.fernet import Fernet
from datetime import datetime, timedelta
import speech_recognition as sr
from PIL import Image
import pygame.camera
import threading
import msgpack
import pickle
import random
import socket
import pygame
import select
import time
import gzip
import sys
import io
import os



SERVER_ADDRESS = ("localhost", 25589)
FPS = 120


class Button:
    def __init__(self, x, y, width, height, text, font, color, hover_color, text_color=(255, 255, 255)):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.font = font
        self.color = color
        self.hover_color = hover_color
        self.text_color = text_color
        self.clicked = False

    def draw(self, surface):
        mouse_pos = pygame.mouse.get_pos()
        is_hovered = self.rect.collidepoint(mouse_pos)
        pygame.draw.rect(surface, self.hover_color if is_hovered else self.color, self.rect)
        text_surf = self.font.render(self.text, True, self.text_color)
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)

    def is_clicked(self, event_list):
        mouse_pos = pygame.mouse.get_pos()
        for event in event_list:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.rect.collidepoint(mouse_pos):
                    return True
        return False


class AverageByTime:
    def __init__(self, interval: int):
        self.values = []
        self.start_time = time.time()
        self.interval = interval
        self.previous_avg = 0
    
    def add_value(self, value):
        self.values.append(value)
        current_time = time.time()

        if current_time - self.start_time >= self.interval:
            avg = sum(self.values) / len(self.values) if self.values else 0
            self.values.clear()
            self.start_time = current_time
            self.previous_avg = avg
            return avg
        return self.previous_avg


class TotalByTime:
    def __init__(self, interval: int):
        self.values = []
        self.start_time = time.time()
        self.interval = interval
        self.previous_total = 0
    
    def add_value(self, value):
        self.values.append(value)
        current_time = time.time()

        if current_time - self.start_time >= self.interval:
            total = sum(self.values)
            self.values.clear()
            self.start_time = current_time
            self.previous_total = total
            return total
        return self.previous_total
    
    def add_v(self, value):
        self.values.append(value)
    
    def calc_value(self):
        current_time = time.time()

        if current_time - self.start_time >= self.interval:
            total = sum(self.values)
            self.values.clear()
            self.start_time = current_time
            self.previous_total = total
            return total
        return self.previous_total


def resource_path(relative_path):
    base_path = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base_path, relative_path)


class Client:
    def __init__(self):
        pygame.init()
        pygame.font.init()
        pygame.camera.init()
        pygame.display.set_caption("cCord Simple Video Platform")
        pygame.display.set_icon(pygame.image.load(resource_path("assets/icon.png")))
        self.res: tuple[int, int] = (1280, 720)
        self.client: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.running: bool = True
        self.window: pygame.Surface = pygame.display.set_mode(self.res)
        self.camera: pygame.camera.Camera = pygame.camera.Camera(pygame.camera.list_cameras()[0], (640, 480))
        self.clock: pygame.time.Clock = pygame.time.Clock()
        self.deltatime: int = 0
        self.data: bytes = b''
        self.buffersize: int = 60000
        self.font: pygame.font.Font = pygame.font.Font(None, 32)
        self.small_font: pygame.font.Font = pygame.font.Font(None, 25)
        self.mic: sr.Microphone = sr.Microphone(0)
        self.server_thread: threading.Thread = threading.Thread(target=self.handle_server)
        self.previous_chats: list[tuple[str, str]] = []
        self.text: str = ""
        self.packets_sent: int = 0
        self.total_packet_size: int = 0
        self.show_debug: bool = False
        self.session_start = time.time()
        self.username: str = ""
        self.camera_button: Button = Button(10, self.res[1] - 170, 256, 64, "Toggle Camera", self.font, ( 40, 40, 40 ), ( 128, 128, 128 ))
        self.show_camera: bool = False
        self.enter_username: bool = True
        self.prefix: str = "Chat"
        self.server_key: bytes = bytes()
        self.sent_data_len: int = 0

        # Averages
        self.average_network: AverageByTime = AverageByTime(1.0)
        self.average_ping: AverageByTime = AverageByTime(10.0)
        
        # Totals
        self.total_packets: TotalByTime = TotalByTime(1.0)
        self.total_packets_size: TotalByTime = TotalByTime(1.0)
        
        # Ping System
        self.ping_start: float = 0.0
        self.ping_end: float = 0.0
        self.ping_time: float = 0.0
        self.PING_EVENT = pygame.USEREVENT + 1

        # This is for the users camera and their frame render + sending data all at once
        self.frame: pygame.Surface = None
        self.raw_frame: bytes = None

        # This is for the other users that are in the call
        self.other_frame: pygame.Surface = None
        self.raw_other_frame: bytes = None
    
    def get_compressed_frame(self, surface: pygame.Surface):
        pil_image = Image.frombytes("RGB", surface.get_size(), pygame.image.tostring(surface, "RGB"))
        buffer = io.BytesIO()
        pil_image.save(buffer, format="JPEG", quality=40)

        jpeg_data = buffer.getvalue()
        return jpeg_data

    def jpeg_bytes_to_surface(self, jpeg_bytes: bytes):
        image_stream = io.BytesIO(jpeg_bytes)
        pil_image = Image.open(image_stream).convert("RGB")

        mode = pil_image.mode
        size = pil_image.size
        data = pil_image.tobytes()
        return pygame.image.fromstring(data, size, mode)

    def render_frame(self, frame: pygame.Surface | None, x: int, y: int):
        """ Renders a frame to the screen """
        if frame:
            try:
                self.window.blit(self.frame, (x, y))
                pygame.draw.rect(self.window, ( 128, 128, 128 ), ( x, y, 640, 480 ), 3)
                return True
            except Exception:
                self.window.blit(self.font.render("No Video - Error", True, (255, 255, 255)), (640 + 280, 240))
                pygame.draw.rect(self.window, (255, 255, 255), (640, 0, 640, 480), 5)
                return False
        else:
            self.window.blit(self.font.render("No Video", True, (255, 255, 255)), (640 + 280, 240))
            pygame.draw.rect(self.window, (255, 255, 255), (640, 0, 640, 480), 5)
            return False
        
    def send_connect(self):
        try:
            data: dict = {
                "type": "connect",
                "content": {}
            }
            self.client.sendto(
                msgpack.packb(
                    pickle.dumps(
                        data
                    )), SERVER_ADDRESS)
        except Exception as e:
            print(f"[ cCord ][ SendConnect ] Error {e}")
    
    def send_disconnect(self):
        try:
            data: dict = {
                "type": "disconnect",
                "content": {}
            }
            self.client.sendto(
                msgpack.packb(
                    pickle.dumps(
                        data
                    )), SERVER_ADDRESS)
        except Exception as e:
            print(f"[ cCord ][ SendConnect ] Error: {e}")
    
    def get_frame(self):
        """ Captures a frame from the camera """
        try:
            if self.show_camera:
                self.frame = pygame.transform.flip(self.camera.get_image(), flip_x=True, flip_y=False)
            else:
                self.frame = pygame.Surface((640, 480))
                self.frame.blit(self.font.render("Video Disabled", True, ( 255, 255, 255 )), ((self.frame.get_size()[0] // 2) - 65, (self.frame.get_size()[1] // 2)))
            compressed_frame = self.get_compressed_frame(self.frame)
            if len(compressed_frame) <= 60000:
                self.raw_frame = compressed_frame
            return True
        except Exception as error:
            print(f"[ cCord ][ Get ] Error: {error}")
            self.previous_chats.append(("cError", f"{error}"))
            return False
    
    def send_ping(self):
        try:
            self.ping_start = time.time()
            self.client.sendto(msgpack.packb(pickle.dumps({"type": "ping", "message": "ignore"})), SERVER_ADDRESS)
            return True
        except Exception as e:
            print(f"[ cCord ][ Ping ] Error: {e}")
            return False
    
    def send_frame(self):
        """ Sends a frame to the server """
        try:
            if self.client.fileno() == -1: return False
            _, writable, _ = select.select([], [self.client], [], 0.1)
            if self.client in writable:
                if self.raw_frame:
                    data = { "type": "frame", "frame": self.raw_frame }
                    edata = msgpack.packb(pickle.dumps(data))
                    fer = Fernet(self.server_key)
                    rdata = fer.encrypt(edata)
                    self.sent_data_len = len(rdata)
                    self.client.sendto(rdata, SERVER_ADDRESS)
                    self.total_packets_size.add_v(self.sent_data_len / 1024)
                    self.total_packets.add_v(1)
                    self.packets_sent += 1
                    self.total_packet_size += self.sent_data_len
                return True
            return False
        except (socket.error, OSError, IOError, TypeError) as error:
            print(f"[ cCord ][ Send ] Error: {error}")
            self.previous_chats.append(("cError", f"{error}"))
            return False
    
    def on_recv(self):
        """ Recieves data from the server """
        try:
            try:
                far = Fernet(self.server_key)
            except Exception as e:
                far = None
            if self.client.fileno() == -1: return False
            readable, _, _ = select.select([self.client], [], [], 0.1)
            if readable:
                rdata, addr = self.client.recvfrom(self.buffersize)
                data = { "type": "" }
                try:data = pickle.loads(msgpack.unpackb(rdata))
                except Exception: pass

                try:
                    edata = far.decrypt(rdata)
                    data = pickle.loads(msgpack.unpackb(edata))
                except Exception: pass

                if not "type" in data: return False
                if data["type"] == "frame":
                    self.raw_other_frame = data["frame"]
                    self.other_frame = self.jpeg_bytes_to_surface(data["frame"])
                
                if data["type"] == "chat":
                    self.previous_chats.append((data["username"], data["message"]))
                
                if data["type"] == "connected":
                    self.server_key = data["key"]
                    print("[ cCord ][ Recv ] Recieved Server Key")
                
                if data["type"] == "pong":
                    self.ping_end = time.time()
                    self.ping_time = (self.ping_end - self.ping_start) * 1000
        except (socket.error, OSError, IOError, TypeError) as error:
            print(f"[ cCord ][ Recv ] Error: {error}")
            self.previous_chats.append(("cError", f"{error}"))

    def init(self):
        """ Connects to the server and makes sure that its actually running also starts the camera """
        try:
            self.client.connect(SERVER_ADDRESS)
            print("[ cCord ] Connected to server!")
            self.server_thread.start()
            self.send_connect()
            self.previous_chats.append(("cCord", "To chat on cCord please enter a username, this will enable your"))
            self.previous_chats.append(("cCord", "camera aswell, please do note that this is all encrypted and"))
            self.previous_chats.append(("cCord", "automated"))

            pygame.time.set_timer(self.PING_EVENT, 2000)
        except (socket.error, OSError) as msg:
            print(f"[ cCord ] Unable to connect to server!\n\t[ cCe ] {msg}")
            self.previous_chats.append(("cCord", "Unable to connect to server"))
            sys.exit()
        try:
            self.camera.start()
        except Exception as e:
            print("[ cCord ] Camera already active!")
            self.previous_chats.append(("cCord", "Camera is already active"))
    
    def handle_server(self):
        """ Handles the server connection by handling sending and recieving frames """
        while self.running:
            self.on_recv()
            if not self.enter_username:
                self.send_frame()
    
    def send_chat(self):
        """ Sends the chat to the server """
        try:
            far = Fernet(self.server_key)
            data = { "type": "chat", "message": f"{self.text}", "username": self.username }
            edata = msgpack.packb(pickle.dumps(data))
            rdata = far.encrypt(edata)
            self.client.sendto(rdata, SERVER_ADDRESS)
        except Exception as e:
            print(f"[ cCord ][ SendChat ] Error: {e}")
            self.previous_chats.append(("cError", f"{e}"))
    
    def render_chat(self):
        """ Renders the chat """
        try:
            if self.enter_username: self.prefix = "Enter Username"
            else: self.prefix = "Chat"
            pygame.draw.rect(self.window, ( 20, 20, 20 ), (640, 480, 640, 480))
            for i, (username, chat) in enumerate(self.previous_chats[-4:]):
                self.window.blit(self.small_font.render(f"({username}) {chat}", True, ( 255, 255, 255 )), ( 650 , 550 + ( i * 25 ) ))
            self.window.blit(self.font.render(f"[ {self.prefix} ] {self.text}", True, ( 255, 255, 255 )), ( 650, 690 ))
        except Exception as e:
            print(f"[ cCord ][ Chat ] Error: {e}")
            self.previous_chats.append(("cError", f"{e}"))

    def run(self):
        """ The main program loop """
        try:
            while self.running:
                self.get_frame()
                self.deltatime = self.clock.tick(FPS)

                # Handles disconnecting from the server by allowing you to use (X) or (Esc)
                events = pygame.event.get()
                for event in events:
                    if self.camera_button.is_clicked(events):
                        self.show_camera = not self.show_camera

                    if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                        self.running = False
                        break
                    
                    elif (event.type == pygame.KEYDOWN and event.key == pygame.K_F5):
                        self.show_debug = not self.show_debug
                    
                    elif (event.type == pygame.KEYDOWN and event.key == pygame.K_BACKSPACE):
                        self.text = self.text[:-1]
                    
                    elif (event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN):
                        if not self.enter_username:
                            self.send_chat()
                            self.text = ""
                        else:
                            self.previous_chats.clear()
                            self.username = self.text
                            self.text = ""
                            self.enter_username = False
                    
                    elif event.type == self.PING_EVENT:
                        self.send_ping()

                    else:
                        if (event.type == pygame.KEYDOWN):
                            self.text += event.unicode

                self.camera_button.draw(self.window)
                self.render_chat()
                pygame.draw.rect(self.window, ( 40, 40, 40 ), ( 0, 480, self.res[0], 60))
                elapsed = time.time() - self.session_start
                minutes = int(elapsed // 60)
                seconds = int(elapsed % 60)
                self.window.blit(self.font.render(f"Session: {minutes:02d}:{seconds:02d}", True, (255, 255, 255)), (10, 500))
                self.window.blit(self.font.render(f"FPS: {self.clock.get_fps() :.0f}", True, (255, 255, 255)), (650, 500))

                self.render_frame(self.frame, 0, 0)
                self.render_frame(self.other_frame, 640, 0)

                if self.show_debug:
                    self.window.blit(self.font.render(f"Packets Sent: {self.packets_sent :,}", True, (0, 255, 0), (0, 0, 0)), (10, 10))
                    self.window.blit(self.font.render(f"Total Packet Size: {self.total_packet_size / 1024 / 1024 :,.2f} MB", True, (0, 255, 0), (0, 0, 0)), (10, 40))
                    self.window.blit(self.font.render(f"Sending Data: {round(self.sent_data_len / 1024, 2)} KB", True, (0, 255, 0), (0, 0, 0)), (10, 70))
                    self.window.blit(self.font.render(f"Ping: {self.ping_time :.2f} ms", True, (0, 255, 0), (0, 0, 0)), (10, 100))
                    self.window.blit(self.font.render(f"Average Data (1s): {round(self.average_network.add_value(self.sent_data_len) / 1024, 2)} KB", True, (0, 255, 0), (0, 0, 0)), (10, 130))
                    self.window.blit(self.font.render(f"Average Ping (10s): {self.average_ping.add_value(self.ping_time) :.2f} ms", True, (0, 255, 0), (0, 0, 0)), (10, 160))
                    self.window.blit(self.font.render(f"Total Packet Size (1s): {round(self.total_packets_size.calc_value() / 1024, 2)} MB", True, (0, 255, 0), (0, 0, 0)), (10, 190))
                    self.window.blit(self.font.render(f"Total Packets (1s): {self.total_packets.calc_value()}", True, (0, 255, 0), (0, 0, 0)), (10, 220))

                pygame.display.update()
                self.window.fill((0, 0, 0))
        except Exception as e:
            print(f"[ cCord ] Error: {e}")
            self.previous_chats.append(("cError", f"{e}"))
        
        finally:
            self.send_disconnect()
            print(f"[ cCord ] Disconnected from server!")
            self.previous_chats.append(("cCord", "Disconnected from the server"))
            self.running = False
            self.server_thread.join(timeout=5)
            self.client.close()
            self.camera.stop()
            pygame.quit()
            sys.exit()



if __name__ == "__main__":
    client = Client()
    client.init()
    client.run()
