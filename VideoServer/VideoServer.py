#!/usr/bin/env python3

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
import pickle


RESOLUTION = (1920, 1080)
FPS = 24

PORT = 8001
SIZE = 10
FRAME_NUM = 10
DISCONECT_MESSAGE = 'EXIT'
FORMAT = 'utf-8'
SUCCESS_MSG = bytes(f'{"SUCCESS":<10}', 'utf-8')
FAILURE_MSG = bytes(f'{"FAILURE":<10}', 'utf-8')



def start_instance(conn, addr):
    # conn.setblocking(False)
    print(f'\t{addr[0]} Connected')
    # Prepare folder to record security footage
    if not 'frames' in os.listdir():
        os.mkdir('frames')
    else:
        shutil.rmtree('frames')
        os.mkdir('frames')
    version = 0
    name_approved = False
    while not name_approved:
        output_file_name = f'{addr[0]}_v{version}.mp4'
        if output_file_name in os.listdir():
            version += 1
        else:
            name_approved = True

    # Set up cv2 attributes
    fourcc = VideoWriter_fourcc(*'mp4v')
    video = VideoWriter(output_file_name, fourcc, FPS, RESOLUTION)

    
    try:
        frames_written = 0
        frame = b''
        all_frames = []
        new_frame = True
        frame_size = 0
        attempt = 0
        recv_time_array = []

        # Poll for frames
        while True:
            recv_time = time.time()

            if new_frame:
                message = conn.recv(16)
                try:
                    frame_size = int(message[4:SIZE + 4]) - 10
                except ValueError as e:
                    conn.send(FAILURE_MSG)
                else:
                    conn.send(SUCCESS_MSG)
                message = conn.recv(15)
                try:
                    frame_num = int(message[3:SIZE + 3])
                except ValueError as e:
                    conn.send(FAILURE_MSG)
                else:
                    new_frame = False
                    conn.send(SUCCESS_MSG)
                
                continue
            else:
                
                message = conn.recv(frame_size)
                frame += message
                

            if len(frame) >= frame_size:
                conn.send(SUCCESS_MSG)
                
                image = imdecode(np.asarray(bytearray(frame), dtype="uint8"), IMREAD_COLOR)

                all_frames.append({'frame_num': frame_num, 'frame':image})
                
                frame = b''
                new_frame = True
                recv_time_array.append(time.time() - recv_time)


    except BrokenPipeError:
        print(f'Writing footage to {output_file_name}')
    except ConnectionResetError:
        print(f'Writing footage to {output_file_name}')

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
