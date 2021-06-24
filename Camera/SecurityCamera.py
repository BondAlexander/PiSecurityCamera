import io
import time
import picamera
from os import remove, mkdir, listdir, path
import shutil
from time import sleep
import socket
import sys
import threading
import pickle
import cv2


RESOLUTION = (1280, 720)
FPS = 20

PORT = 8001

FORMAT = 'utf-8'
SIZE = 12
FRAME_NUM = 12

DISCONECT_MESSAGE = 'EXIT'
SUCCESS_MSG = bytes(f'{"SUCCESS":<10}', 'utf-8')
FAILURE_MSG = bytes(f'{"FAILURE":<10}', 'utf-8')
SIZE_MSG = bytes(f'SIZE', 'utf-8')

av_read = []
av_send_size = []
av_send_num = []
av_send_img = []

def writer():
    class SplitFrames(object):
        def __init__(self):
            self.frame_num = 0
            self.output = None

        def write(self, buf):
            if buf.startswith(b'\xff\xd8'):
                # Start of new frame; close the old one (if any) and
                # open a new output
                if self.output:
                    self.output.close()
                self.frame_num += 1
                self.output = io.open('tmp/image%02d.jpg' % self.frame_num, 'wb')
            self.output.write(buf)
    
    try:
        with picamera.PiCamera(resolution=RESOLUTION, framerate=FPS) as camera:
            camera.start_preview()
            # Give the camera some warm-up time
            time.sleep(2)
            output = SplitFrames()
            start = time.time()
            camera.start_recording(output, format='mjpeg')
            camera.wait_recording(10)
            camera.stop_recording()
            finish = time.time()
    except KeyboardInterrupt:
        pass
    finally:
        print('Captured %d frames at %.2ffps' % (output.frame_num,output.frame_num / (finish - start)))


def reader(server_address,_):
    
    # Connect to server
    while True:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            client_socket.connect((server_address, PORT))
        except ConnectionRefusedError:
            sys.stdout.flush()
            sys.stdout.write('\t[Reader]Trying to connect to server...\r')
        else:
            print('\t[Reader]Connected To Server                 ')
            break
    try:
        while True:
            # Wait for frames
            while len(listdir('tmp')) == 0:
                pass

            for frame in listdir('tmp'):
                send_picture(f'tmp/{frame}', client_socket, frame.split('image')[-1].split('.')[0])
                remove(f'tmp/{frame}')
    except KeyboardInterrupt:
        print()
    finally:
        sum_read = 0
        sum_size = 0
        sum_num = 0
        sum_frame = 0
        for i in range(len(av_read)):
            sum_read += av_read[i]
            sum_size += av_send_size[i]
            sum_num += av_send_num[i]
            sum_frame += av_send_img[i-1]
        print('======STATS=======')
        print(f'Average read time: {sum_read/len(av_read)}')
        print(f'Average size time: {sum_size/len(av_send_size)}')
        print(f'Average num time: {sum_num/len(av_send_num)}')
        print(f'Average frame time: {sum_frame/len(av_send_img)}')

        average_run = (sum_read/len(av_read) + sum_size/len(av_send_size) + sum_num/len(av_send_num) + sum_frame/len(av_send_img)) 
        possible_framerate = 1 / average_run
        print(f'\nAverage Send Time: {average_run}')
        print(f'Possible Framerate: {possible_framerate}')

            
def send_picture(frame_path, client_socket, frame_num):
    start_time = time.time()

    bytes_io = open(frame_path, 'rb')

    img_bytes = bytes_io.read()
    bytes_io.close()

    av_read.append(time.time() - start_time)
    start_time = time.time()


    # Send Frame Size
    while True:
        client_socket.send(bytes(f'{"SIZE" + str(len(img_bytes)):<{SIZE+4}}', 'utf-8'))
        status = client_socket.recv(10)
        if status == SUCCESS_MSG:
            av_send_size.append(time.time() - start_time)
            start_time = time.time()
            break
        elif status == FAILURE_MSG:
            continue

    # Send Frame Number
    while True:
        client_socket.send(bytes(f'{"NUM" + str(frame_num):<{FRAME_NUM+3}}', 'utf-8'))
        status = client_socket.recv(10)
        if status == SUCCESS_MSG:
            av_send_num.append(time.time() - start_time)
            start_time = time.time()
            break
        elif status == FAILURE_MSG:
            continue

    # Send Frame
    while True:
        client_socket.send(img_bytes)
        
        status = client_socket.recv(10)
        
        if status == SUCCESS_MSG:
            break
        elif status == FAILURE_MSG:
            print('\tResending frame')
            continue
    
    av_send_img.append(time.time() - start_time)
    print(f'[Reader] Sent frame {int(frame_num)}({len(img_bytes)} bytes)')
    




# MAIN
SERVER_ADDRESS = '10.0.0.198'

if 'tmp' not in listdir():
    mkdir('tmp')
elif len(listdir()) > 0:
    shutil.rmtree('tmp')
    mkdir('tmp')


threading.Thread(target=writer).start()
reader(SERVER_ADDRESS, None)
