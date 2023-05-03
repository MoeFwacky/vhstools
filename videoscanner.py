import configparser
import datetime
import ffmpeg
import imutils
import io
import json
import math
import numpy as np
import os
import queue
import ray
import statistics
import sys
import time
from alive_progress import alive_bar
from imutils.video import FileVideoStream
from imutils.video import FPS
from pydub import AudioSegment, silence
from pydub.utils import make_chunks

silence_threshold = int(config['scenesplitter']['silence threshold'])
frame_queue = queue.Queue(100)

if os.name == 'nt':
    delimeter = '\\'
else:
    delimeter = '/'

def convert(seconds): 
    try:
        seconds = seconds.split('.')
    except:
        seconds = [seconds,0]
    min, sec = divmod(seconds[0], 60) 
    hour, min = divmod(min, 60)
    return "%d:%02d:%02d.%f" % (hour, min, sec, seconds[1]) 

def selectFile(k):
    fileSelection = input(">:")
    try:
        fileSelection = int(fileSelection)
    except ValueError:
        print("Enter a Number Between 1 and "+str(k-1)+":")
        fileSelection = input(">:")
    while fileSelection >= int(k):
        print("Enter a Number Between 1 and "+str(k-1)+":")
        fileSelection = input(">:")
        try:
            fileSelection = int(fileSelection)
        except ValueError:
            fileSelection = k
    return fileSelection

def write_json(new_data, filename, file_data):
    with open(filename,'w+') as file:
        # First we load existing data into a dict.
        try:
            file_data = json.load(file)
        except:
            file_data = []
        # Join new_data with file_data
        file_data.append(new_data)
        # Sets file's current position at offset.
        #file.seek(0)
        # convert back to json.
        json.dump(file_data, file, indent = 4)

def formatDuration(file):
    fileProbe = ffmpeg.probe(file)
    lengthSeconds = float(fileProbe['format']['duration'])
    lengthFormatted = convert(lengthSeconds)
    return lengthFormatted

def getFrameRateDuration(file):
    fileProbe = ffmpeg.probe(file)
    #print(fileProbe.keys())
    for key in list(fileProbe.keys()):
        if key == 'streams':
            video_stream = next((stream for stream in fileProbe[key] if stream['codec_type'] == 'video'), None)
    framerateSplit = video_stream['r_frame_rate'].split('/')
    frameRate = int(framerateSplit[0])/int(framerateSplit[1])
    #print(frameRate)
    #frameRate = int(avgFrameRate[0])/int(avgFrameRate[1])
    durationSeconds = float(fileProbe['format']['duration'])
    #print(durationSeconds)
    durationFormatted = convert(durationSeconds)
    #print(durationFormatted)
    
    return frameRate, durationSeconds, durationFormatted

def selectVideo():
    print("Enter the working directory path")
    workingDir = os.getcwd()
    print("Press Enter to use "+workingDir)
    path = input(">:")
    if path == "":
        path = workingDir
    if path[-1] != delimeter:
        path = path + delimeter
    dirContents = os.scandir(path)
    dirDict = {}
    extensions = ['mp4','flv','avi']
    k = 1
    for entry in dirContents:
        if entry.name[-3:] in extensions:
            dirDict[k] = entry.name
            lengthFormatted = formatDuration(entry.name)
            print(str(k)+": "+entry.name+" ------ "+lengthFormatted)
            k = k + 1
    fileSelection = selectFile(k)
    print("\nFILE SELECTED")
    print(dirDict[fileSelection])
    frameRate, fileDuration, lengthFormatted = getFrameRateDuration(dirDict[fileSelection])
    print("DURATION = ",lengthFormatted)
    print("FRAME RATE = "+str(round(frameRate,2))+" FPS")
    totalFrames = fileDuration*float(frameRate)
    print('TOTAL FRAMES: ',totalFrames)
    cont = input("\nContinue with this file? (Y/N) >:")
    yn = ['y','Y','Yes','YES','yes','N','n','No','NO','no']
    yes = ['y','Y','Yes','YES','yes']
    no = ['N','n','No','NO','no']
    while cont not in yn:
        print("INVALID ENTRY")
        cont = input("Continue with this file? (Y/N) >:")
    while cont in no:
        print("Enter a Number Between 1 and "+str(k-1)+":")
        fileSelection = selectFile(k)
        print("FILE SELECTED")
        print(dirDict[fileSelection])
        frameRate, fileDuration, lengthFormatted = getFrameRateDuration(dirDict[fileSelection])
        print("DURATION = ",lengthFormatted)
        print("FRAME RATE = "+str(round(frameRate,2))+" FPS")
        totalFrames = float(fileDuration*float(frameRate))
        print('TOTAL FRAMES: ',totalFrames)
        cont = input("\nContinue with this file? (Y/N) >:")
    print("CONFIRMED!")
    return dirDict[fileSelection], totalFrames, path

def read_frame(video, totalFrames):
    f = 0
    with alive_bar(int((totalFrames)), force_tty=True) as bar:
        while f <= totalFrames:
            frame = video.read()
            if frame is None:
                break
            frame_queue.put(frame)
            f += 1
            bar()

def process_frames(videoFile, totalFrames, frameRate):
    fps = FPS().start()
    video = FileVideoStream(videoFile).start()
    audio = AudioSegment.empty()
    file_data = {}
    file_data['frames'] = []
    rgb_values = []
    rgb_min_max = [255,0]
    f = 0
    time_ms = 0

    frame_duration = 1000/frameRate #ms
    print("[ACTION] Extracting audio track from video file")
    audio = AudioSegment.from_file(videoFile)
    print("[ACTION] Splitting audio into",math.ceil(totalFrames),"chunks")
    audio_chunks = make_chunks(audio, frame_duration)
    fps.stop()
    print("[INFO] elapsed time: {:.2f} seconds".format(fps.elapsed()))
    #fps = FPS().start()
    print("[ACTION] Processing Frames")
    with alive_bar(int((totalFrames)), force_tty=True) as bar:
        while f < int((totalFrames)):
            try:
                frame = video.read()
                #print(frame)
                avg_color_per_row = np.average(frame, axis=0)
                avg_color = np.average(avg_color_per_row, axis=0)
                b,g,r = avg_color
                rgb = (0.2126*r)+(0.7152*g)+(0.0722*b)
                if rgb < rgb_min_max[0]:
                    rgb_min_max[0] = rgb
                if rgb > rgb_min_max[1]:
                    rgb_min_max[1] = rgb
                rgb_values.append(rgb)

                loudness = audio_chunks[f].dBFS
                silent = silence.detect_leading_silence(audio_chunks[f],silence_thresh=silence_threshold)
                if silent == math.floor(frame_duration):
                    is_silent = True
                else:
                    is_silent = False
                
                frameData = {'f':f, 'ts':str(datetime.timedelta(seconds=f/frameRate)),'rgb':round(rgb,5),'r':round(r,5),'g':round(g,5),'b':round(b,5),'loudness':loudness, 'silence':is_silent}     
                file_data['frames'].append(frameData)
                if video.Q.qsize() < 5:  # If we are low on frames, give time to producer
                    time.sleep(0.001)  # Ensures producer runs now, so 2 is sufficient
            except Exception as e:
                print(e)
                pass
                
            fps.update()
            f += 1
            time_ms += ((1/frameRate)*1000)
            bar()
        video.stop()
        #fps.stop()
        #print("[INFO] elapsed time: {:.2f} seconds".format(fps.elapsed()))
        #print("[INFO] approx. FPS: {:.2f}".format(fps.fps()))
        
        return file_data, rgb_values, rgb_min_max
    
def scanVideo(videoFile=None, path=os.getcwd(), totalFrames=None):
    os.chdir(path)
    if path[-1] != delimeter:
        path = path + delimeter
    if videoFile == None:
        videoFile, totalFrames, path = selectVideo()
    elif videoFile != None and totalFrames == None:
        frameRate, fileDuration, lengthFormatted = getFrameRateDuration(videoFile)
        #print(frameRate, fileDuration, lengthFormatted)
        totalFrames = float(fileDuration*float(frameRate))
    #print(totalFrames)
    #rayscan = []
    
    
    #@ray.remote
    #def READ_FRAME():
    #read_frame(video, totalFrames)
    #rayscan.append(READ_FRAME.remote())
    #ray.get(rayscan)
    #time.sleep(5)
    file_data, rgb_values, rgb_min_max = process_frames(videoFile, totalFrames, frameRate)
    #rayscan.append(PROCESS_FRAME.remote())
    #print(file_data)
    #print(rgb_values)
    #print(rgb_min_max)
    file_data['analysis'] = {'total frames':totalFrames, 'min_rgb':rgb_min_max[0],'max_rgb':rgb_min_max[1], 'median_rgb':statistics.median(rgb_values)}
    tape_filename = videoFile.split(delimeter)[-1]
    tape_name_parts = tape_filename.split('.')
    #print('.'.join(tape_name_parts))
    tape_name = '.'.join(tape_name_parts[:-1])
    
    jsonFileName = tape_name+'.json'
    STATS_FILE = path+jsonFileName

    with open(STATS_FILE, 'w+') as file:
        json.dump(file_data, file, indent = 1)