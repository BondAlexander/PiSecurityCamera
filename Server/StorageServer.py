from posix import listdir
import socket
from cv2 import VideoWriter, VideoWriter_fourcc, cvtColor, COLOR_RGB2BGR, IMREAD_COLOR, imdecode
import numpy as np
import shutil
import os
from threading import Thread
import ssl
import datetime
import yaml


c_file = open('../config.yml', 'r')
CONFIG = yaml.load(c_file, Loader=yaml.SafeLoader)
c_file.close()

RESOLUTION = CONFIG['RESOLUTIONS']['720p']
FOURCC = VideoWriter_fourcc(*'mp4v')
SUCCESS_MSG = bytes(f'{"SUCCESS":<10}', 'utf-8')
FAILURE_MSG = bytes(f'{"FAILURE":<10}', 'utf-8')

class CameraInstance:
    def __init__(self, addr, TLS_server_socket):
        self.addr = addr
        self.TLS_server_socket = TLS_server_socket
        self.frame = _Frame()
        self.clip = _Clip(self.addr)
        print(f'\t{self.addr[0]} Connected')
        self._verify_file_structure()

    def _verify_file_structure(self):
        if not os.path.exists(f'.tmp/{self.addr[0]}'):
            if not os.path.exists('.tmp'):
                os.mkdir('.tmp')
            os.mkdir(f'.tmp/{self.addr[0]}')
        if not os.path.exists(f'Footage/{self.addr[0]}'):
            if not os.path.exists('Footage'):
                os.mkdir('Footage')
            os.mkdir(f'Footage/{self.addr[0]}')

    def _merge_clip_helper(self, ip_addr, tmp_clip_file_path):
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
    
    def merge_clip(self):
        version = 0
        while True:
            if os.path.exists(f'.tmp/{self.addr[0]}/clip_to_add_{version}.mp4'):
                version += 1
            else:
                clip_to_add = f'.tmp/{self.addr[0]}/clip_to_add_{version}.mp4'
                break
        shutil.copy(self.clip.tmp_clip_file_path, clip_to_add)
        Thread(target=self._merge_clip_helper, args=(self.addr[0], clip_to_add)).start()
   
    def process_header(self):
        message = self.TLS_server_socket.recv(30)
        try:
            self.frame.size = int(message[4:15])
            if self.frame.size == 0:
                self.TLS_server_socket.send(FAILURE_MSG)
                return
        except ValueError as e:
            self.TLS_server_socket.send(FAILURE_MSG)
            return
        try:
            self.frame.num = int(message[18:])
        except ValueError as e:
            self.TLS_server_socket.send(FAILURE_MSG)
        else:
            self.frame.new = False
            self.TLS_server_socket.send(SUCCESS_MSG)

    def run(self):
        # Poll for frames
        while True:
            if self.frame.new:
                self.process_header()
                continue
            else:
                message = self.TLS_server_socket.recv(self.frame.size)
                self.frame.append(message)
            if self.frame.is_complete():
                if self.frame.is_valid():
                    self.frame.convert_to_cv2_image()
                    self.clip.add_frame(self.frame)
                    if self.clip.is_finished():
                        self.clip.publish()
                        self.merge_clip()
                        self.clip.reset()
                    self.TLS_server_socket.send(SUCCESS_MSG)
                    self.frame.reset()
                else:
                    self.TLS_server_socket.send(FAILURE_MSG)
            else:
                continue


class _Frame:
    def __init__(self):
        self.frame_bytes = b''
        self.new = True
        self.num = None
        self.size = None
        self.image_object = None

    def is_valid(self):
        if len(self.frame_bytes) > self.size:
            self.retry()
            return False
        else:
            return True

    def is_complete(self):
        if len(self.frame_bytes) == self.size:
            return True

    def append(self, new_bytes):
        self.frame_bytes += new_bytes

    def convert_to_cv2_image(self):
        self.image_object = imdecode(np.asarray(bytearray(self.frame_bytes), dtype="uint8"), IMREAD_COLOR)

    def retry(self):
        self.frame_bytes = b''

    def reset(self):
        self.frame_bytes = b''
        self.new = True
        self.num
        self.size


class _Clip:
    def __init__(self, addr):
        self.all_frames = []
        self.tmp_clip_file_path = f'.tmp/{addr[0]}/clip.mp4'
        self.clip_video = VideoWriter(self.tmp_clip_file_path, FOURCC, CONFIG['FRAMERATE'], RESOLUTION)

    def is_finished(self):
        if len(self.all_frames) / CONFIG['FRAMERATE'] == 7:
            return True

    def add_frame(self, new_frame):
        self.all_frames.append({'frame_num': new_frame.num, 'frame':new_frame.image_object})
    
    def publish(self):
        self.all_frames.sort(key=_sort_frames)
        for f in self.all_frames:
            self.clip_video.write(f['frame'])
        self.clip_video.release()

    def reset(self):
        self.all_frames = []
        self.clip_video = VideoWriter(self.tmp_clip_file_path, FOURCC, CONFIG['FRAMERATE'], RESOLUTION)
    
def _sort_frames(frame):
    return int(frame['frame_num'])


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

    for p in CONFIG['LEGAL_PORTS']:
        try:
            server_socket.bind(("0.0.0.0", p))
        except OSError:
            continue

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
