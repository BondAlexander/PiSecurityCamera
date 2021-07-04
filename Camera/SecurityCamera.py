import io
import time
import picamera
from os import remove, mkdir, listdir, path
import shutil
from time import sleep
import socket
import sys
from threading import Thread
import ssl
import datetime
import yaml


c_file = open('../config.yml', 'r')
CONFIG = yaml.load(c_file)
c_file.close()

RESOLUTION = CONFIG['RESOLUTIONS']['720p']
SUCCESS_MSG = bytes(f'{"SUCCESS":<10}', 'utf-8')
FAILURE_MSG = bytes(f'{"FAILURE":<10}', 'utf-8')

class Recorder:
    def __init__(self):
        self.TLS_client_socket = None
        self.frame_num = 0
        self.initiate_connection()
        self.byte_stream = io.BytesIO()
        self.output = RecorderHelper(self)

    def initiate_connection(self):
        CERT_FILE = path.join(path.dirname(__file__), 'keycert.pem')
        context = ssl.SSLContext(ssl.PROTOCOL_TLS)
        context.load_cert_chain(CERT_FILE)
        context.options |= (
            ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1 | ssl.OP_NO_TLSv1_2
        )
        # Connect to server
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.TLS_client_socket = context.wrap_socket(client_socket)
        while True:
            for p in CONFIG['LEGAL_PORTS']:
                    
                try:
                    self.TLS_client_socket.connect((CONFIG['SERVER_ADDR'], p))
                except ConnectionRefusedError:
                    sys.stdout.flush()
                    sys.stdout.write('\t[Reader]Trying to connect to server...\r')
                    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.TLS_client_socket = context.wrap_socket(client_socket)
                else:
                    break
            if self.TLS_client_socket._connected:
                print('\t[Reader]Connected To Server                 ')
                break

    def start_recording(self):
        with picamera.PiCamera(resolution=RESOLUTION, framerate=CONFIG['FRAMERATE']) as camera:
            camera.start_preview()
            # Give the camera some warm-up time
            time.sleep(2)
            recording_start = time.time()
            camera.annotate_background = picamera.Color('black')
            camera.annotate_text = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            camera.start_recording(self.output, format='mjpeg')
            start = datetime.datetime.now()
            while (datetime.datetime.now() - start).seconds < 60**2*24:
                camera.annotate_text = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                camera.wait_recording(0.2)
            camera.stop_recording()
            finish = time.time()
            print('Captured %d frames at %.2ffps' % (self.frame_num, self.frame_num / (finish - recording_start)))

        
    def send_picture(self, img_bytes, frame_num):
        # Create Session Header
        frame_size = len(img_bytes)
        self.frame_num = frame_num
        session_header = bytes(str(f'SIZE{frame_size:<{11}}' + f'NUM{self.output.frame_num:<{12}}'), 'utf-8')
        
        # Send Session Header
        attempt = 0
        while True:
            self.TLS_client_socket.send(session_header)
            status = self.TLS_client_socket.recv(10)
            if status == SUCCESS_MSG:
                break
            elif attempt > 3:
                print('Dropping frame')
                return
            elif status == FAILURE_MSG:
                attempt += 1
                continue
        # Send Frame
        while True:
            self.TLS_client_socket.send(img_bytes)
            status = self.TLS_client_socket.recv(10)
            if status == SUCCESS_MSG:
                break
            elif status == FAILURE_MSG:
                print('\tResending frame')
                continue


class RecorderHelper:
    def __init__(self, recorder):
        self.frame_num = 0
        self.output = None
        self.recorder = recorder

    def write(self, buf):
        self.recorder.send_picture(buf, self.frame_num)
        self.frame_num += 1


# MAIN
if not ssl.HAS_TLSv1_3:
    print('This machine does not support TLS 1.3. Please update OpenSSL')
    exit(0)

SERVER_ADDRESS = '10.0.0.198'

if 'tmp' in listdir():
    shutil.rmtree('tmp')

    mkdir('tmp')
else:
    mkdir('tmp')

Recorder().start_recording()

