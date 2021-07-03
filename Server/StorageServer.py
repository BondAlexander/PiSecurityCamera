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


# RESOLUTION = (426, 240)
RESOLUTION = (1280, 720)
# RESOLUTION = (1920, 1080)

FPS = 20

PORT = 8000
LEGAL_PORTS = [8005, 8006, 8007, 8008]
FORMAT = 'utf-8'
FOURCC = VideoWriter_fourcc(*'mp4v')
SUCCESS_MSG = bytes(f'{"SUCCESS":<10}', 'utf-8')
FAILURE_MSG = bytes(f'{"FAILURE":<10}', 'utf-8')


def merge_clip(ip_addr, tmp_clip_file_path):
    date_formatted = "6.24.2021"
    version = 0
    output_file_path = f'Footage/{ip_addr}/{date_formatted}_v{version}.mkv'
    if os.path.exists(output_file_path):
        os.system(f'mkvmerge -o .tmp/{output_file_path} {output_file_path} \+ {tmp_clip_file_path}')
        print()
        os.remove(output_file_path)
        shutil.copy(f'.tmp/{output_file_path}', output_file_path)
        os.remove(tmp_clip_file_path)
    else:
        shutil.copy(tmp_clip_file_path, output_file_path)


def start_instance(TLS_server_socket, addr):
    print(f'\t{addr[0]} Connected')
    # Prepare folder to record security footage
    if not os.path.exists(f'.tmp/{addr[0]}'):
        if not os.path.exists('.tmp'):
            os.mkdir('.tmp')
        os.mkdir(f'.tmp/{addr[0]}')
    if not os.path.exists(f'Footage/{addr[0]}'):
        if not os.path.exists('Footage'):
            os.mkdir('Footage')
        os.mkdir(f'Footage/{addr[0]}')
    date_formatted = "6.24.2021"
    output_file_path = f'Footage/{addr[0]}/{date_formatted}.mp4'
    tmp_clip_file_path = f'.tmp/{addr[0]}/clip.mp4'
    video = VideoWriter(tmp_clip_file_path, FOURCC, FPS, RESOLUTION)
    
    frame = b''
    all_frames = []
    new_frame = True
    recv_time_array = []
    try:
        # Poll for frames
        while True:
            if new_frame:
                recv_time = time.time()
                message = TLS_server_socket.recv(30)
                try:
                    frame_size = int(message[4:15])
                    if frame_size == 0:
                        TLS_server_socket.send(FAILURE_MSG)
                        continue
                except ValueError as e:
                    TLS_server_socket.send(FAILURE_MSG)
                    continue
                try:
                    frame_num = int(message[18:])
                except ValueError as e:
                    TLS_server_socket.send(FAILURE_MSG)
                else:
                    new_frame = False
                    TLS_server_socket.send(SUCCESS_MSG)
                continue
            else:

                message = TLS_server_socket.recv(frame_size)
                frame += message
            
            if len(frame) > frame_size :
                TLS_server_socket.send(FAILURE_MSG)
                frame = b''
            elif len(frame) == frame_size:

                # TODO REMOVE THIS TRY BLOCK AFTER HASHING
                try:
                    image = imdecode(np.asarray(bytearray(frame), dtype="uint8"), IMREAD_COLOR)
                except Exception as e:
                    TLS_server_socket.send(FAILURE_MSG)
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
                            if os.path.exists(f'.tmp/{addr[0]}/clip_to_add_{version}.mp4'):
                                version += 1
                            else:
                                clip_to_add = f'.tmp/{addr[0]}/clip_to_add_{version}.mp4'
                                break
                        
                        shutil.copy(tmp_clip_file_path, clip_to_add)
                        Thread(target=merge_clip, args=(addr[0], clip_to_add)).start()
                        all_frames = []
                        video = VideoWriter(tmp_clip_file_path, FOURCC, FPS, RESOLUTION)
                    TLS_server_socket.send(SUCCESS_MSG)

                    frame = b''
                    new_frame = True
                    recv_time_array.append(time.time() - recv_time)
    finally:
        sum_time = 0.0
        for t in recv_time_array:
            sum_time += t
        print(f'Average time per frame: {sum_time/len(recv_time_array)}')

            

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

    # Poll for joining security cameras
    serving = True
    while serving:
        conn, addr = server_socket.accept()
        TLS_server_socket = context.wrap_socket(conn, server_side=True)
        Thread(target=start_instance, args=(TLS_server_socket, addr)).start()
        
if __name__ == '__main__':
    main()
