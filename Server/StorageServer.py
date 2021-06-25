import io
from posix import listdir
import socket
from cv2 import VideoWriter, VideoWriter_fourcc, cvtColor, COLOR_RGB2BGR, IMREAD_COLOR, imdecode
import numpy as np
import shutil
import time
import os
from threading import Thread

RESOLUTION = (1280, 720)
FPS = 20

PORT = 8002
LEGAL_PORTS = [8005, 8006, 8007, 8008]
FORMAT = 'utf-8'
FOURCC = VideoWriter_fourcc(*'DIVX')
SUCCESS_MSG = bytes(f'{"SUCCESS":<10}', 'utf-8')
FAILURE_MSG = bytes(f'{"FAILURE":<10}', 'utf-8')


def merge_clip(ip_addr):
    date_formatted = "6.24.2021"
    output_file_path = f'Footage/{ip_addr}/{date_formatted}.mp4'
    tmp_clip_file_path = f'.tmp/{ip_addr}/clip.mp4'
    if os.path.exists(output_file_path):
        os.system(f'mencoder {output_file_path} {tmp_clip_file_path} -ovc copy -oac copy -of lavf format=mp4 -o {output_file_path}')
    else:
        shutil.copyfile(tmp_clip_file_path, output_file_path)

def start_instance(conn, addr):
    print(f'\t{addr[0]} Connected')
    # Prepare folder to record security footage
    if not os.path.exists(f'.tmp/{addr[0]}'):
        os.mkdir(f'.tmp/{addr[0]}')
    if not os.path.exists(f'Footage/{addr[0]}'):
        os.mkdir(f'Footage/{addr[0]}')
    date_formatted = "6.24.2021"
    output_file_path = f'Footage/{addr[0]}/{date_formatted}.mp4'
    tmp_clip_file_path = f'.tmp/{addr[0]}/clip.mp4'

    video = VideoWriter(tmp_clip_file_path, FOURCC, FPS, RESOLUTION)
    
    frame = b''
    all_frames = []
    new_frame = True
    recv_time_array = []

    # Poll for frames
    while True:
        recv_time = time.time()

        if new_frame:
            frame_num = 0
            frame_size = 0
            message = conn.recv(30)
            try:
                frame_size = int(message[4:15])
                if frame_size == 0:
                    conn.send(FAILURE_MSG)
                    continue
            except ValueError as e:
                conn.send(FAILURE_MSG)
                continue
            try:
                frame_num = int(message[18:])
            except ValueError as e:
                conn.send(FAILURE_MSG)
            else:
                new_frame = False
                conn.send(SUCCESS_MSG)
            
            continue
        else:
            try:
                message = conn.recv(frame_size)
            except ValueError:
                print('value error')
                conn.send(FAILURE_MSG)
            else:
                frame += message
            
        if len(frame) > frame_size :
            conn.send(FAILURE_MSG)
            frame = b''
        elif len(frame) == frame_size:
            recv_time_array.append(time.time() - recv_time)

            # TODO REMOVE THIS TRY BLOCK AFTER HASHING
            try:
                image = imdecode(np.asarray(bytearray(frame), dtype="uint8"), IMREAD_COLOR)
            except Exception as e:
                conn.send(FAILURE_MSG)
                continue
            else: 
                all_frames.append({'frame_num': frame_num, 'frame':image})
                # TODO make if statement to see if len(all_frames) / FPS == 7
                # If true then spin up process to append clip to main footage for day
                # Then send success msg
                if len(all_frames) / FPS == 1:
                    def sort_frames(i):
                        return int(i['frame_num'])
                    all_frames.sort(key=sort_frames)
                    for frame in all_frames:
                        video.write(frame['frame'])
                    video.release()
                    merge_clip(addr[0])
                    all_frames = []
                conn.send(SUCCESS_MSG)

                frame = b''
                new_frame = True
                

def main():
    
    # Set up socket server
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(("0.0.0.0", PORT))
    server_socket.listen(0)

    # Poll for joining security cameras
    serving = True
    while serving:
        conn, addr = server_socket.accept()
        Thread(target=start_instance, args=(conn, addr)).start()
        
if __name__ == '__main__':
    main()
