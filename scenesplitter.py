import configparser
import datetime
import ffmpeg
import inspect 
import json
import os
import sys
import time
import videoscanner
from alive_progress import alive_bar

if os.name == 'nt':
    delimeter = '\\'
else:
    delimeter = '/'

scriptPath = os.path.realpath(os.path.dirname(__file__))
config = configparser.ConfigParser()
config.read(scriptPath + delimeter + 'config.ini')

divisor = int(config['scenesplitter']['median divisor'])
minLength = int(config['scenesplitter']['clip minimum'])
    
try:
	if (sys.argv[1] == "--debug"):
		lineEnd = "\n"
	else:
		lineEnd = "\r"
except:
	lineEnd = "\r"

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

def getScenes(json_filename, totalFrames, frameRate=30, divisor=divisor, clip_min=int(minLength)):
    minimum_clip_frames = clip_min*frameRate
    with open(json_filename) as json_file:
        json_data = json.load(json_file)
        number_of_frames = int(json_data['analysis']['total frames'])
        print(str(number_of_frames)+ " TOTAL FRAMES")
        frame = 0
        print("RGB Threshold value:",json_data['analysis']['median_rgb']/divisor)
        scene_rgb = scale_number(json_data['analysis']['median_rgb'],0,255,json_data['analysis']['min_rgb'],json_data['analysis']['max_rgb'])/divisor
        print("RGB Threshold adjusted to",scene_rgb)
        rgb = 256
        scene_list = []
        selected_frame_data = json_data['frames'][0]
        #print("FRAME NUMBER "+str(frame)+" SELECTED, RGB = "+str(rgb),end='\r')
        with alive_bar(number_of_frames, force_tty=True) as bar:
            while frame < totalFrames-1:
                if frame == 0:
                    start_frame_data = selected_frame_data
                    scene_number = 1
                else:
                    frame += 1
                    bar()
                    try:
                        start_frame_data = json_data['frames'][frame]
                    except IndexError:
                        break
                    scene_number = scene_number + 1
                while frame <= (start_frame_data['f'] + minimum_clip_frames):
                    frame += 1
                    try:
                        last_frame_data = json_data['frames'][frame]
                    except IndexError:
                        break
                    bar()
                    rgb = scale_number(float(last_frame_data['rgb']),0,255,json_data['analysis']['min_rgb'],json_data['analysis']['max_rgb'])
                    #print("FRAME NUMBER "+str(frame)+" SELECTED, RGB = "+str(rgb),end='\r')
                while float(rgb) > scene_rgb:
                    frame += 1
                    bar()
                    try:
                        last_frame_data = json_data['frames'][frame]
                    except IndexError:
                        break
                    rgb = scale_number(float(last_frame_data['rgb']),0,255,json_data['analysis']['min_rgb'],json_data['analysis']['max_rgb'])
                    #print("FRAME NUMBER "+str(frame)+" SELECTED, RGB = "+str(rgb),end='\r')
                    if frame < 2:
                        while not (json_data['frames'][frame-1]['rgb'] > json_data['frames'][frame]['rgb'] < json_data['frames'][frame+1]['rgb'] < json_data['frames'][frame+2]['rgb']):
                            frame += 1
                            bar()
                            #print("FRAME NUMBER "+str(frame)+" SELECTED, RGB = "+str(rgb),end='\r')
                            last_frame_data = json_data['frames'][frame]
                            rgb = scale_number(float(last_frame_data['rgb']),0,255,json_data['analysis']['min_rgb'],json_data['analysis']['max_rgb'])                        
                    elif frame > totalFrames-2:
                        try:
                            while not (json_data['frames'][frame-1]['rgb'] > json_data['frames'][frame]['rgb']):
                                frame += 1
                                bar()
                                #print("FRAME NUMBER "+str(frame)+" SELECTED, RGB = "+str(rgb),end='\r')
                                last_frame_data = json_data['frames'][frame]
                                rgb = scale_number(float(last_frame_data['rgb']),0,255,json_data['analysis']['min_rgb'],json_data['analysis']['max_rgb'])                                            
                        except IndexError:
                            last_frame_data = json_data['frames'][frame-1]
                            rgb = scale_number(float(last_frame_data['rgb']),0,255,json_data['analysis']['min_rgb'],json_data['analysis']['max_rgb'])                            
                    else:
                        try:
                            while not (json_data['frames'][frame-2]['rgb'] > json_data['frames'][frame-1]['rgb'] > json_data['frames'][frame]['rgb'] < json_data['frames'][frame+1]['rgb'] < json_data['frames'][frame+2]['rgb']):
                                frame += 1
                                #print("FRAME NUMBER "+str(frame)+" SELECTED, RGB = "+str(rgb),end='\r')
                                last_frame_data = json_data['frames'][frame]
                                rgb = scale_number(float(last_frame_data['rgb']),0,255,json_data['analysis']['min_rgb'],json_data['analysis']['max_rgb'])
                                bar()
                        except IndexError:
                            #print("FRAME NUMBER "+str(frame)+" SELECTED, RGB = "+str(rgb),end='\r')
                            last_frame_data = json_data['frames'][frame-1]
                            rgb = scale_number(float(last_frame_data['rgb']),0,255,json_data['analysis']['min_rgb'],json_data['analysis']['max_rgb'])
                    #print("FRAME NUMBER "+str(frame)+" SELECTED, RGB = "+str(rgb),end='\r')
                scene_data = {'scene':scene_number,'start_frame':start_frame_data['f'],'start_time':start_frame_data['ts'],'end_frame':last_frame_data['f'],'end_time':last_frame_data['ts']}
                #print(scene_data)
                scene_list.append(scene_data)
    print(scene_number,"SCENES DETECTED")
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

def saveSplitScene(scene, file, path, startSplit, endSplit):
    fileSplit = file.split('.')
    sceneNumber = "{0:0=5d}".format(scene)

    tape_name_parts = file.split('.')
    #print('.'.join(tape_name_parts))
    tape_name = '.'.join(tape_name_parts[:-1])
    file_extension = tape_name_parts[-1]

    outputFileName = tape_name+"_"+sceneNumber+"."+file_extension
    try:
        (
            ffmpeg
            .input(file, ss=startSplit, to=endSplit)
            .output(path+outputFileName, vcodec='libx264', loglevel="error", preset='fast', crf=11, acodec='aac')
            .run()
        )
    except ffmpeg.Error as e:
        print(e)

def processVideo(videoFile=None, path=os.getcwd()):
    os.chdir(path)
    if path[-1] != delimeter:
        path = path + delimeter
    if videoFile == None:
        videoFile, totalFrames, path = videoscanner.selectVideo()
    frameRate, fileDuration, lengthFormatted = videoscanner.getFrameRateDuration(videoFile)
    totalFrames = float(fileDuration*float(frameRate))

    tape_filename = videoFile.split(delimeter)[-1]
    tape_name_parts = tape_filename.split('.')
    #print('.'.join(tape_name_parts))
    tape_name = '.'.join(tape_name_parts[:-1])
    file_extension = tape_name_parts[-1]
    
    #print(tape_name,"SELECTED!")

    jsonFileName = tape_name+'.json'
    outputPath = path+tape_name+delimeter
    STATS_FILE = path+tape_name+'.json'
    #print("CHECKING FOR FILE AT",STATS_FILE)

    if os.path.exists(STATS_FILE) == False:
        print("JSON DATA FILE NOT FOUND, SCANNING",tape_name)
        filePath = path
        #print(tape_name+file_extension,filePath)
        videoscanner.scanVideo(tape_name+'.'+file_extension,filePath)
    scene_list = getScenes(STATS_FILE,totalFrames,frameRate)
    
    print("Exporting scene files to "+outputPath)
    with alive_bar(int(totalFrames), force_tty=True) as bar2:
        for scene in scene_list:
            startFrame = scene['start_frame']
            endFrame = scene['end_frame']
            #print('ENCODING SCENE',scene['scene'],end=': ')
            sceneDuration = (int(endFrame) - int(startFrame)) / frameRate
            #print('Duration',convert(sceneDuration),end='\t\r')
            if not os.path.exists(outputPath):
                os.makedirs(outputPath)
            saveSplitScene(scene['scene'], videoFile, outputPath, scene['start_frame']/frameRate, scene['end_frame']/frameRate)
            for i in range(int(startFrame),int(endFrame)):
                bar2()
        for r in range(int(endFrame), int(totalFrames)):
            bar2()