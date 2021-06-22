from fastapi import FastAPI
import uvicorn
import subprocess
import os



app = FastAPI()

@app.get("/start")
def read_root():
    global streamer_pid
    streamer_pid = subprocess.Popen(['python3', 'VideoStreamer.py']).pid
    print('Streamer Started')
    return 'Streamer Started'

@app.get("/start_mine")
def read_root():
    global my_streamer_pid
    my_streamer_pid = subprocess.Popen(['python3', 'MyVideoStreamer.py']).pid
    print('My Streamer Started')
    return 'My Streamer Started'

@app.get("/stop")
def read_root():
    global streamer_pid
    try:
        os.kill(streamer_pid, 2)
    except NameError:
        return 'Streamer Not Running'
    else:
        print('Streamer Terminated')
        return 'Streamer Terminated'

@app.get("/stop_mine")
def read_root():
    global my_streamer_pid
    try:
        os.kill(my_streamer_pid, 2)
    except NameError:
        return 'My Streamer Not Running'
    else:
        print('My Streamer Terminated')
        return 'My Streamer Terminated'

    

if __name__ == '__main__':
    uvicorn.run(app, port=5000, host="0.0.0.0")