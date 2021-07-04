import io
from posix import listdir
import socket
from cv2 import VideoWriter, VideoWriter_fourcc, cvtColor, COLOR_RGB2BGR, IMREAD_COLOR, imdecode
import numpy as np
import shutil
import time
import os
from threading import Thread
import ffmpeg
import ssl
import datetime


# RESOLUTION = (426, 240)
RESOLUTION = (1280, 720)
# RESOLUTION = (1920, 1080)

FPS = 15

PORT = 8001
LEGAL_PORTS = [8005, 8006, 8007, 8008]
FORMAT = 'utf-8'
FOURCC = VideoWriter_fourcc(*'mp4v')
SUCCESS_MSG = bytes(f'{"SUCCESS":<10}', 'utf-8')
FAILURE_MSG = bytes(f'{"FAILURE":<10}', 'utf-8')

class CameraInstance:
    def __init__(self, addr, TLS_server_socket):
        self.addr = addr
        print(f'\t{self.addr[0]} Connected')
        self.verify_file_structure()
        self.tmp_clip_file_path = f'.tmp/{self.addr[0]}/clip.mp4'
        self.TLS_server_socket = TLS_server_socket

    def merge_clip(self, ip_addr, tmp_clip_file_path):
        version = 0
        self.date_formatted = datetime.datetime.now().strftime('%Y-%m-%d')
        output_file_path = f'Footage/{ip_addr}/{self.date_formatted}_v{version}.mkv'
        if os.path.exists(output_file_path):
            os.system(f'mkvmerge -o .tmp/{output_file_path} {output_file_path} \+ {tmp_clip_file_path}')
            print()
            os.remove(output_file_path)
            shutil.copy(f'.tmp/{output_file_path}', output_file_path)
            os.remove(tmp_clip_file_path)
        else:
            shutil.copy(tmp_clip_file_path, output_file_path)

    def verify_file_structure(self):
        # Prepare folder to record security footage
        if not os.path.exists(f'.tmp/{self.addr[0]}'):
            if not os.path.exists('.tmp'):
                os.mkdir('.tmp')
            os.mkdir(f'.tmp/{self.addr[0]}')
        if not os.path.exists(f'Footage/{self.addr[0]}'):
            if not os.path.exists('Footage'):
                os.mkdir('Footage')
            os.mkdir(f'Footage/{self.addr[0]}')

    def run(self):
        video = VideoWriter(self.tmp_clip_file_path, FOURCC, FPS, RESOLUTION)
        frame = b''
        all_frames = []
        new_frame = True
        recv_time_array = []
        # Poll for frames
        while True:
            if new_frame:
                recv_time = time.time()
                message = self.TLS_server_socket.recv(30)
                try:
                    frame_size = int(message[4:15])
                    if frame_size == 0:
                        self.TLS_server_socket.send(FAILURE_MSG)
                        continue
                except ValueError as e:
                    self.TLS_server_socket.send(FAILURE_MSG)
                    continue
                try:
                    frame_num = int(message[18:])
                except ValueError as e:
                    self.TLS_server_socket.send(FAILURE_MSG)
                else:
                    new_frame = False
                    self.TLS_server_socket.send(SUCCESS_MSG)
                continue
            else:
                message = self.TLS_server_socket.recv(frame_size)
                frame += message
            if len(frame) > frame_size :
                self.TLS_server_socket.send(FAILURE_MSG)
                frame = b''
            elif len(frame) == frame_size:
                # TODO REMOVE THIS TRY BLOCK AFTER HASHING
                try:
                    image = imdecode(np.asarray(bytearray(frame), dtype="uint8"), IMREAD_COLOR)
                except Exception as e:
                    self.TLS_server_socket.send(FAILURE_MSG)
                    continue
                else: 
                    all_frames.append({'frame_num': frame_num, 'frame':image})
                    if len(all_frames) / FPS == 7:
                        def sort_frames(i):
                            return int(i['frame_num'])
                        all_frames.sort(key=sort_frames)
                        for frame in all_frames:
                            video.write(frame['frame'])
                        video.release()
                        version = 0
                        while True:
                            if os.path.exists(f'.tmp/{self.addr[0]}/clip_to_add_{version}.mp4'):
                                version += 1
                            else:
                                clip_to_add = f'.tmp/{self.addr[0]}/clip_to_add_{version}.mp4'
                                break
                        shutil.copy(self.tmp_clip_file_path, clip_to_add)
                        Thread(target=self.merge_clip, args=(self.addr[0], clip_to_add)).start()
                        all_frames = []
                        video = VideoWriter(self.tmp_clip_file_path, FOURCC, FPS, RESOLUTION)
                    self.TLS_server_socket.send(SUCCESS_MSG)

                    frame = b''
                    new_frame = True
                    recv_time_array.append(time.time() - recv_time)
            

def main():
    # TLS code borrowed from https://www.agnosticdev.com/blog-entry/python-network-security-networking/ssl-and-tls-updates-python-37
    if not ssl.HAS_TLSv1_3:
        print('This machine does not support TLS 1.3. Please update OpenSSL')
        exit(0)
    CERT_FILE = os.path.join(os.path.dirname(__file__), 'keycert.pem')
    context = ssl.SSLContext(ssl.PROTOCOL_TLS)
    context.load_cert_chain(CERT_FILE)
    context.options |= (
        ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1 | ssl.OP_NO_TLSv1_2
    )
    # Set up socket server
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    server_socket.bind(("0.0.0.0", PORT))
    server_socket.listen(0)

    camera_instances = []
    # Poll for joining security cameras
    serving = True
    while serving:
        conn, addr = server_socket.accept()
        TLS_server_socket = context.wrap_socket(conn, server_side=True)
        camera_instances.append(CameraInstance(addr, TLS_server_socket))
        Thread(target=camera_instances[-1].run).start()
        
        
if __name__ == '__main__':
    main()
