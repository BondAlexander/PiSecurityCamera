import io
import socket
import struct
from cv2 import VideoWriter, VideoWriter_fourcc, cvtColor, COLOR_RGB2BGR, IMREAD_COLOR, imdecode
import numpy as np
from PIL import Image, ImageDraw
import time
import os
import sys
import shutil
from threading import Thread

RESOLUTION = (1280, 720)
FPS = 20

PORT = 8001
LEGAL_PORTS = [8005, 8006, 8007, 8008]
FORMAT = 'utf-8'
SUCCESS_MSG = bytes(f'{"SUCCESS":<10}', 'utf-8')
FAILURE_MSG = bytes(f'{"FAILURE":<10}', 'utf-8')



def start_instance(conn, addr):
    # conn.setblocking(False)
    print(f'\t{addr[0]} Connected')
    # Prepare folder to record security footage
    date_formatted = ""
    output_file_path = f'Footage/{addr[0]}/{date_formatted}.mp4'

    # Set up cv2 attributes
    fourcc = VideoWriter_fourcc(*'mp4v')
    video = VideoWriter(output_file_path, fourcc, FPS, RESOLUTION)
    
    try:
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
                except ValueError as e:
                    conn.send(FAILURE_MSG)
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
                    conn.send(SUCCESS_MSG)

                    all_frames.append({'frame_num': frame_num, 'frame':image})

                    frame = b''
                    new_frame = True
                


    except BrokenPipeError:
        print(f'Writing footage to {output_file_path}')
    except ConnectionResetError:
        print(f'Writing footage to {output_file_path}')

    finally:
        sum_t = 0
        for t in recv_time_array:
            sum_t += t
        print(f'Average time: {sum_t/len(recv_time_array)}')
        def sort_frames(i):
            return int(i['frame_num'])
        all_frames.sort(key=sort_frames)
        for frame in all_frames:
            video.write(frame['frame'])
        video.release()


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
