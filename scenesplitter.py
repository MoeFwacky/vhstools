import configparser
import datetime
import ffmpeg
import inspect 
import json
import math
import numpy as np
import os
import re
import sys
import time
import tkinter as tk
import videoscanner
from alive_progress import alive_bar
from webcolors import CSS3_HEX_TO_NAMES, hex_to_rgb

if os.name == 'nt':
    delimeter = '\\'
else:
    delimeter = '/'

scriptPath = os.path.realpath(os.path.dirname(__file__))
config = configparser.ConfigParser()
config.read(scriptPath + delimeter + 'config.ini')

divisor = float(config['scenesplitter']['median divisor'])
minLength = int(config['scenesplitter']['clip minimum'])
#silence_threshold = int(config['scenesplitter']['silence threshold'])
split_colors = ['black','darkslategray']
audio_change_threshold = int(config['scenesplitter']['audio change threshold'])

#getting rgb color name database
css3_db = CSS3_HEX_TO_NAMES
names = []
rgb_values = []
color_map = {}
for color_hex, color_name in css3_db.items():
    color_map[color_name] = color_hex

try:
	if (sys.argv[1] == "--debug"):
		lineEnd = "\n"
	else:
		lineEnd = "\r"
except:
	lineEnd = "\r"

def rgbFromStr(s):
    r,g,b = int(s[1:3],16), int(s[3:5], 16),int(s[5:7], 16)
    return r,g,b

def nearestColorName(R,G,B,color_map=color_map):
    mindiff = None
    for d in color_map:
        r,g,b = rgbFromStr(color_map[d])
        diff = abs(R-r)*256+abs(G-g)*256+abs(B-b)*256
        if mindiff is None or diff < mindiff:
            mindiff = diff
            mincolorname = d
    return mincolorname

def line(): #get line number
	line = inspect.currentframe().f_back.f_lineno
	line = '%03d' % line
	return line

def clearline(): #clear line for reprinting on same line
	print("\t\t\t\t\t\t\t\t\t\t\t\t\t",end='\r')

def textline(line,text,endLine=lineEnd): #print to terminal including timestamp and line number
	if(endLine==lineEnd):
		clearline()
	print(datetime.datetime.now().strftime("%H:%M:%S")+": "+str(line)+" - " + text,end=endLine)

def convert(seconds): 
    min, sec = divmod(seconds, 60) 
    hour, min = divmod(min, 60) 
    return "%d:%02d:%02d" % (hour, min, sec) 
    
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

def formatDuration(file):
    fileProbe = ffmpeg.probe(file)
    lengthSplit = fileProbe['format']['duration'].split('.')
    lengthSeconds = int(lengthSplit[0])
    lengthFormatted = convert(lengthSeconds)
    return lengthFormatted

def getFrameRate(file):
    fileProbe = ffmpeg.probe(file)
    avgFrameRate = fileProbe['streams'][1]['avg_frame_rate'].split('/')
    try:
        frameRate = int(avgFrameRate[0])/int(avgFrameRate[1])
    except:
        frameRate = 30
    return frameRate

def scale_number(unscaled, to_min, to_max, from_min, from_max):
    return (to_max-to_min)*(unscaled-from_min)/(from_max-from_min)+to_min

def progress(progress_widget,frames_processed,batch_size,progress_label,progress_list):
    if progress_widget is not None and frames_processed % batch_size == 0:
        time_elapsed, frames_per_second, time_remaining = progress_list
        #print(frames_processed)
        #print(progress_widget['maximum'])
        percentage_complete = round((frames_processed/progress_widget['maximum'])*100)
        #print(percentage_complete)
        frames_per_second = "{:.2f}".format(frames_per_second)
        
        progress_label.config(text=str(percentage_complete)+'% '+str(frames_processed)+'/'+str(progress_widget['maximum'])+', '+str(time_elapsed)+'<'+time_remaining+', '+ str(frames_per_second+'/s'))
        progress_widget['value'] = frames_processed
        progress_widget.update()

def get_eta(start_time,f,total_frames):
    seconds_elapsed = time.time() - start_time
    elapsed_minutes, elapsed_seconds = divmod(seconds_elapsed, 60)
    elapsed_hours, elapsed_minutes = divmod(elapsed_minutes, 60)
    if elapsed_hours > 0:
        time_elapsed = "{:02d}:{:02d}:{:02d}".format(round(elapsed_hours), round(elapsed_minutes), round(elapsed_seconds))
    else:
        time_elapsed = "{:02d}:{:02d}".format(round(elapsed_minutes), round(elapsed_seconds))    
    
    frames_per_second = f / seconds_elapsed
    remaining_frames = total_frames - f
    
    if frames_per_second > 0:
        remaining_time = remaining_frames / frames_per_second
    else:
        remaining_time = 0
    
    minutes, seconds = divmod(remaining_time, 60)
    hours, minutes = divmod(minutes, 60)

    if hours > 0:
        time_remaining = "{:02d}:{:02d}:{:02d}".format(round(hours), round(minutes), round(seconds))
    else:
        time_remaining = "{:02d}:{:02d}".format(round(minutes), round(seconds))

    return time_elapsed, frames_per_second, time_remaining

def getScenes(videoFile,tape_directory,json_filename, totalFrames, frameRate=30, divisor=divisor, clip_min=(minLength),progress_label=None,progress_widget=None):
    minimum_clip_frames = clip_min*frameRate
    with open(json_filename) as json_file:
        try:
            json_data = json.load(json_file)
            number_of_frames = int(json_data['analysis']['total frames'])
            print(str(number_of_frames)+ " TOTAL FRAMES")
            frame = 0
            rgb_threshold = json_data['analysis']['median_rgb']/divisor
            #print("Brightness Threshold value:",rgb_threshold)
            silence_threshold = json_data['analysis']['silence_threshold']
        except:
            print("[ACTION] OLD JSON VERSION DETECT, RE-SCANNING",videoFile)
            videoscanner.scanVideo(videoFile,tape_directory,progress_label=progress_label,progress_widget=progress_widget)            
            with open(json_filename) as json_file:
                json_data = json.load(json_file)
                number_of_frames = int(json_data['analysis']['total frames'])
                #print(str(number_of_frames)+ " TOTAL FRAMES")
                frame = 0
                rgb_threshold = json_data['analysis']['median_rgb']/divisor
                silence_threshold = json_data['analysis']['silence_threshold']            
        print("[INFO] Brightness Threshold value: "+str(rgb_threshold))
        print("[INFO] Silence Threshold value: "+str(silence_threshold))
        scene_rgb = rgb_threshold
        #scene_rgb = scale_number(json_data['analysis']['median_rgb'],0,255,json_data['analysis']['min_rgb'],json_data['analysis']['max_rgb'])/divisor
        #print("RGB Threshold adjusted to",scene_rgb)
        scene_list = []
        selected_frame_data = json_data['frames'][0]
        #print("FRAME NUMBER "+str(frame)+" SELECTED, RGB = "+str(rgb),end='\r')
        if progress_widget != None:
            progress_widget['maximum'] = math.ceil(number_of_frames)
        batch_size = 10  # Adjust the batch size as needed
        loudness_change = 0
        loudness = 0
        start_time = time.time()
        with alive_bar(number_of_frames, force_tty=False) as bar:
            while frame < totalFrames-1:
                if frame == 0:
                    start_frame_data = selected_frame_data
                    scene_number = 1
                else:
                    frame += 1
                    progress_list = get_eta(start_time,frame,number_of_frames)
                    progress(progress_widget,frame,batch_size,progress_label,progress_list)
                    bar()
                    try:
                        start_frame_data = json_data['frames'][frame]
                    except IndexError:
                        bar()
                        break
                    scene_number = scene_number + 1
                rgb = 256
                #colorMatch = False
                while float(rgb) > scene_rgb and frame < totalFrames-1:
                    while frame <= (start_frame_data['f'] + minimum_clip_frames):
                        frame += 1
                        try:
                            last_frame_data = json_data['frames'][frame]
                        except IndexError:
                            progress_list = get_eta(start_time,frame-1,number_of_frames)
                            progress(progress_widget,frame-1,batch_size,progress_label,progress_list)
                            bar()
                            break
                        
                        #rgb = scale_number(float(last_frame_data['rgb']),0,255,json_data['analysis']['min_rgb'],json_data['analysis']['max_rgb'])
                        rgb = last_frame_data['rgb']
                        if frame <=totalFrames-2:
                            trailing_frame_array = [json_data['frames'][frame]['f'],json_data['frames'][frame+1]['f']]
                            trailing_rgb_array = [json_data['frames'][frame-1]['rgb'],json_data['frames'][frame]['rgb']]
                            trailing_slope = float(np.polyfit(trailing_frame_array,trailing_rgb_array,1)[-2])
                            trailing_rgb_trend_up = True if trailing_slope > 0 else False
                        else:
                            trailing_rgb_trend_up = True
                        loudness = last_frame_data['loudness']
                        progress_list = get_eta(start_time,frame-1,number_of_frames)
                        progress(progress_widget,frame-1,batch_size,progress_label,progress_list)
                        bar()

                        loudness = last_frame_data['loudness']
                        loudness_array = []
                        frame_array = []
                        if frame-4 >= 0:
                            loudness_array.append(float(json_data['frames'][frame-4]['loudness']))
                            frame_array.append(json_data['frames'][frame-4]['f'])
                        if frame-3 >= 0:
                            loudness_array.append(float(json_data['frames'][frame-3]['loudness']))
                            frame_array.append(json_data['frames'][frame-3]['f'])
                        if frame-2 >= 0:
                            loudness_array.append(float(json_data['frames'][frame-2]['loudness']))
                            frame_array.append(json_data['frames'][frame-2]['f'])
                        if frame-1 >= 0:
                            loudness_array.append(float(json_data['frames'][frame-1]['loudness']))
                            frame_array.append(json_data['frames'][frame-1]['f'])
                        loudness_array.append(float(json_data['frames'][frame]['loudness']))
                        frame_array.append(json_data['frames'][frame]['f'])
                        loudness_slope = float(np.polyfit(frame_array,loudness_array,1)[-2])
                        loudness_trend_down = True if loudness_slope < 0 else False
                        #print(loudness_trend_down)

                    try:
                        while not (rgb < rgb_threshold and trailing_rgb_trend_up is True and any(l < silence_threshold for l in loudness_array)):
                            frame += 1
                            #print("FRAME NUMBER "+str(frame)+" SELECTED, RGB = "+str(rgb),end='\r')
                            last_frame_data = json_data['frames'][frame]
                            #rgb = scale_number(float(last_frame_data['rgb']),0,255,json_data['analysis']['min_rgb'],json_data['analysis']['max_rgb'])
                            rgb = last_frame_data['rgb']
                            if frame <=totalFrames-3:
                                trailing_frame_array = [json_data['frames'][frame]['f'],json_data['frames'][frame+1]['f']]
                                trailing_rgb_array = [json_data['frames'][frame-1]['rgb'],json_data['frames'][frame]['rgb']]
                                trailing_slope = float(np.polyfit(trailing_frame_array,trailing_rgb_array,1)[-2])
                                trailing_rgb_trend_up = True if trailing_slope > 0 else False
                            else:
                                trailing_rgb_trend_up = True

                            loudness = last_frame_data['loudness']
                            loudness_array = []
                            frame_array = []
                            if frame-4 >= 0:
                                loudness_array.append(float(json_data['frames'][frame-4]['loudness']))
                                frame_array.append(json_data['frames'][frame-4]['f'])
                            if frame-3 >= 0:
                                loudness_array.append(float(json_data['frames'][frame-3]['loudness']))
                                frame_array.append(json_data['frames'][frame-3]['f'])
                            if frame-2 >= 0:
                                loudness_array.append(float(json_data['frames'][frame-2]['loudness']))
                                frame_array.append(json_data['frames'][frame-2]['f'])
                            if frame-1 >= 0:
                                loudness_array.append(float(json_data['frames'][frame-1]['loudness']))
                                frame_array.append(json_data['frames'][frame-1]['f'])
                            loudness_array.append(float(json_data['frames'][frame]['loudness']))
                            frame_array.append(json_data['frames'][frame]['f'])
                            loudness_slope = float(np.polyfit(frame_array,loudness_array,1)[-2])
                            loudness_trend_down = True if loudness_slope < 0 else False
                            
                            loudness = last_frame_data['loudness']
                            progress_list = get_eta(start_time,frame,number_of_frames)
                            progress(progress_widget,frame,batch_size,progress_label,progress_list)                            
                            bar()
                    except IndexError:
                        #print("FRAME NUMBER "+str(frame)+" SELECTED, RGB = "+str(rgb),end='\r')
                        try:
                            last_frame_data = json_data['frames'][frame-1]
                            #rgb = scale_number(float(last_frame_data['rgb']),0,255,json_data['analysis']['min_rgb'],json_data['analysis']['max_rgb'])
                            rgb = last_frame_data['rgb']
                            if frame <=totalFrames-3:
                                trailing_frame_array = [json_data['frames'][frame]['f'],json_data['frames'][frame+1]['f']]
                                trailing_rgb_array = [json_data['frames'][frame-1]['rgb'],json_data['frames'][frame]['rgb']]
                                trailing_slope = float(np.polyfit(trailing_frame_array,trailing_rgb_array,1)[-2])
                                trailing_rgb_trend_up = True if trailing_slope > 0 else False
                            else:
                                trailing_rgb_trend_up = True
                            loudness = last_frame_data['loudness']
                            progress_list = get_eta(start_time,frame-1,number_of_frames)
                            progress(progress_widget,frame-1,batch_size,progress_label,progress_list)
                            bar()
                        except IndexError:
                            break

                scene_data = {'scene':scene_number,'start_frame':start_frame_data['f'],'start_time':start_frame_data['ts'],'end_frame':last_frame_data['f'],'end_time':last_frame_data['ts']}
                #print(scene_data)
                scene_list.append(scene_data)
    print(str(scene_number)+" SCENES DETECTED")
    return scene_list


def processTempFile(file, horizontalResolution, verticalResolution, aspectRatio, videoCodec, videoCodecPreset, crfValue, audioCodec):
    fileSplit = file.split('.')
    outputFileName = fileSplit[0]+"_cropped."+fileSplit[1]
    (
        ffmpeg
        .input(file)
        .output(outputFileName, vcodec=videoCodec, preset=videoCodecPreset, crf=crfValue, acodec=audioCodec, loglevel="quiet")
        .run()
    )
    return outputFileName

def saveSplitScene(scene, file, path, startSplit, endSplit, frameRate):
    sceneNumber = "{0:0=5d}".format(scene)

    tape_directory, tape_filename = os.path.split(file)
    tape_name = tape_filename.split('.')[0]
    file_extension = tape_filename.split('.')[1]
    pattern = r"_\d+-\d+\."
    match = re.search(pattern,tape_filename)
    if not match:
        outputFileName = tape_name+"_"+str(startSplit)+"-"+str(endSplit)+"."+file_extension
    else:
        frames_range = tape_name.split('_')[1].split('-')
        first_frame = int(frames_range[0]) + startSplit
        last_frame = int(frames_range[0]) + endSplit
        outputFileName = tape_name.split('_')[0]+"_"+str(first_frame)+"-"+str(last_frame)+"."+file_extension
    try:
        (
            ffmpeg
            .input(file, ss=startSplit/frameRate, to=endSplit/frameRate)
            .output(os.path.join(path,outputFileName), vcodec='copy', loglevel="error", acodec='copy')
            .run()
        )
    except ffmpeg.Error as e:
        print(e)

def processVideo(videoFile=None, path=os.getcwd(),progress_label=None,progress_widget=None):
    os.chdir(path)

    if videoFile == None:
        videoFile, totalFrames, path = videoscanner.selectVideo()
    frameRate, fileDuration, lengthFormatted = videoscanner.getFrameRateDuration(videoFile)
    totalFrames = float(fileDuration*float(frameRate))
    
    tape_filename = os.path.basename(videoFile)
    print(videoFile)
    try:
        tape_directory = os.path.dirname(videoFile)
        
    except:
        tape_directory = path
    if tape_directory == '':
        tape_directory = path
    dirname, tape_name  = os.path.split(videoFile)
    tape_name = tape_name.split('.')[0]
    t, file_extension = os.path.splitext(videoFile)
    
    
    '''tape_name_parts = tape_filename.split('.')
    #print('.'.join(tape_name_parts))
    tape_name = '.'.join(tape_name_parts[:-1])
    file_extension = tape_name_parts[-1]'''
    
    #print(tape_name,"SELECTED!")

    jsonFileName = tape_name+'.json'
    outputPath = os.path.join(tape_directory,tape_name)
    STATS_FILE = os.path.join(tape_directory,jsonFileName)
    #print("CHECKING FOR FILE AT",STATS_FILE)

    if os.path.exists(STATS_FILE) == False:
        print("[ACTION] JSON DATA FILE NOT FOUND, SCANNING",tape_name)
        videoscanner.scanVideo(os.path.join(tape_directory,videoFile),tape_directory,progress_label=progress_label,progress_widget=progress_widget)

    scene_list = getScenes(videoFile,tape_directory,STATS_FILE,totalFrames,frameRate,progress_label=progress_label,progress_widget=progress_widget)
    
    print("[ACTION] Exporting scene files to "+outputPath)
    if progress_widget != None:
        progress_widget['maximum'] = math.ceil(len(scene_list))
    batch_size = 1  # Adjust the batch size as needed
    start_time = time.time()
    with alive_bar(int(len(scene_list)), force_tty=False) as bar2:
        s = 0
        for scene in scene_list:
            startFrame = scene['start_frame']
            endFrame = scene['end_frame']
            #print('ENCODING SCENE',scene['scene'],end=': ')
            sceneDuration = (int(endFrame) - int(startFrame)) / frameRate
            #print('Duration',convert(sceneDuration),end='\t\r')
            if not os.path.exists(outputPath):
                os.makedirs(outputPath)
            saveSplitScene(scene['scene'], videoFile, outputPath, scene['start_frame'], scene['end_frame'], frameRate)
            '''for i in range(int(startFrame),int(endFrame)):
                bar2()'''
            progress_list = get_eta(start_time,s,len(scene_list))
            progress(progress_widget,s,batch_size,progress_label,progress_list)
            bar2()
            s += 1
        '''for r in range(int(endFrame), int(totalFrames)):
            bar2()'''
    print("[ACTION] Scene Split Processing Complete")
