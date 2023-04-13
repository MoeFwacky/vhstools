import datetime
import ffmpeg
import inspect
import json
import os
import sys

if os.name == 'nt':
    delimeter = '\\'
else:
    delimeter = '/'
    
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

def secondsDuration(file):
    fileProbe = ffmpeg.probe(file)
    lengthSeconds = fileProbe['format']['duration']
    return lengthSeconds

def getFrameRate(file):
    frameRate = ""
    try:
        fileProbe = ffmpeg.probe(file)
        avgFrameRate = fileProbe['streams'][1]['avg_frame_rate'].split('/')
    except:
        frameRate = "N/A"
    if frameRate != "N/A":
        try:
            frameRate = round(int(avgFrameRate[0])/int(avgFrameRate[1]),2)
        except ZeroDivisionError as err:
            print("Framerate Detection Error")
            frameRate = 0
    return frameRate

def selectDirectory(delimeter):
	print("Enter the directory path to scan")
	workingDir = os.getcwd()
	print("Press Enter to use "+workingDir)
	path = input(">:")
	if path == "":
		path = workingDir
	if path[-1] != delimeter:
		path = path + delimeter
	return path

def selectJSON(path):
    dirContents = os.scandir(path)
    dirDict = {}
    k = 1
    for entry in dirContents:
        if entry.name[-4:].lower() in 'json':
            dirDict[k] = entry.name
            print(str(k)+": "+entry.name)
            k = k + 1
    fileSelection = selectFile(k)
    print("\nJSON FILE SELECTED")
    print(path+dirDict[fileSelection])
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
        cont = input("\nContinue with this file? (Y/N) >:")
    print("CONFIRMED!")
    return dirDict[fileSelection]

def selectVideoFile(path, ext):
    dirContents = os.scandir(path)
    dirDict = {}
    k = 1
    for entry in dirContents:
        if entry.name[-3:] in ext:
            dirDict[k] = entry.name
            try:
                lengthFormatted = formatDuration(entry.name)
            except:
                lengthFormatted = "N/A"
            print(str(k)+": "+entry.name+" ------ "+lengthFormatted)
            k = k + 1
    fileSelection = selectFile(k)
    print("\nFILE SELECTED")
    print(path+dirDict[fileSelection])
    try:
        lengthFormatted = formatDuration(dirDict[fileSelection])
    except:
        lengthFormatted = "N/A"
    print("DURATION = "+lengthFormatted)
    try:
        frameRate = getFrameRate(dirDict[fileSelection])
    except:
        frameRate = "N/A"
    print("FRAME RATE = "+str(frameRate)+" FPS")
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
        lengthFormatted = formatDuration(dirDict[fileSelection])
        print("DURATION = "+lengthFormatted)
        frameRate = getFrameRate(dirDict[fileSelection])
        print("FRAME RATE = "+str(frameRate)+" FPS")
        cont = input("\nContinue with this file? (Y/N) >:")
    print("CONFIRMED!")
    return dirDict[fileSelection]

def splitVideo(entry,startSplit,endSplit,outputName):
    prevOutputName = ""
    clearline()
    textline(line(),entry)
    filename = entry
    #do the split
    clearline()
    textline(line(),"SPLITTING THIS FILE: "+filename)
    (
        ffmpeg
        .input(filename, ss=startSplit, to=endSplit)
        .output(outputName, c='copy', loglevel="quiet")
        .run()
    )
    x = 1
    prevOutputName = ""
    
def overlayVideo(inFile,overlayFile,xAxis,yAxis,outputName,overlayStart=None,overlayEnd=None,start=0,end=1):
    clearline()
    if overlayStart != None and overlayEnd != None:
        overlay_file = ffmpeg.input(overlayFile,ss=overlayStart,to=overlayEnd)
    elif overlayStart != None and overlayEnd == None:
        overlay_file = ffmpeg.input(overlayFile,ss=overlayStart)
    elif overlayStart == None and overlayEnd != None:
        overlay_file = ffmpeg.input(overlayFile,to=overlayEnd)
    else:
        overlay_file = ffmpeg.input(overlayFile)
    overlayEnable = 'between(t,'+str(start)+','+str(end)+')'
    (
        ffmpeg
        .input(inFile)
        .overlay(overlay_file,x=xAxis,y=yAxis,eof_action="pass",repeatlast=0,enable=overlayEnable, loglevel="quiet")
        .output(outputName, map='0:a', vcodec='libx264', acodec='aac')
        .run()
    )
    
def overlayImage(inFile,overlayFile,xAxis=30,yAxis=870,outputName="video-output",start=0,end=1):
    clearline()
    overlay_file = ffmpeg.input(overlayFile,ss=start,to=end)
    overlayEnable = 'between(t,'+str(start)+','+str(end)+')'
    (
        ffmpeg
        .input(inFile)
        .overlay(overlay_file,x=xAxis,y=yAxis,eof_action="pass",repeatlast=0,enable=overlayEnable,loglevel="quiet")
        .output(outputName, map='0:a', vcodec='libx264', acodec='aac')
        .run()
    )

def mergeVideos(inFiles,outputName):
    inFiles = inFiles.split(',')
    try:
        f = open("merge.tmp","x",encoding='utf8')
    except:
        os.remove('merge.tmp')
        f = open("merge.tmp","x",encoding='utf8')
    f.close()
    for file in inFiles:
        clearline()
        textline(line(),"PREPARING "+file+" FOR MERGE")
        f = open("merge.tmp","a",encoding='utf8')
        f.write("file \'"+file+"\'\n")
        f.close()
    textline(line(),"MERGING FILES")
    try:
        (
            ffmpeg
            .input('merge.tmp', format='concat', safe=0)
            .output(outputName, vcodec='libx264', loglevel="quiet", preset='fast', crf=11, acodec='aac')
            .run()
        )
    except ffmpeg._run.Error as e:
        clearline()
        textline(line(),str(e))
        clearline()
        textline(line(),str(sys.stderr))
    os.remove('merge.tmp')
    
def processJSON(JSONfile=None, path=None):
    if path == None:
        path = selectDirectory(delimeter)
    if JSONfile == None:
        JSONfile = selectJSON(path)
    j = open(JSONfile,)
    jsonData = json.load(j)
    try:
        for d in jsonData['split']:
            #do the splits
            splitVideo(d['input'],d['inTime'],d['outTime'],d['output'])  
    except:
        pass
    try:
        for d in jsonData['merge']:
            #merge together
            print(d['input'])
            print(d['output'])
            mergeVideos(d['input'],d['output'])
    except Exception as e:
        print(e)
        pass
    try:
        for d in jsonData['overlayVideo']:
            #video overlay
            if d['overlayStart'] != None and d['overlayEnd'] != None:
                overlayVideo(d['input'],d['overlay'],d['xAxis'],d['yAxis'],d['output'],d['overlayStart'],d['overlayEnd'],d['start'],d['end'])
            elif d['overlayStart'] != None and d['overlayEnd'] == None:
                overlayVideo(d['input'],d['overlay'],d['xAxis'],d['yAxis'],d['output'],d['overlayStart'],d['overlayEnd'],d['start'],None)
            elif d['overlayStart'] == None and d['overlayEnd'] != None:
                overlayVideo(d['input'],d['overlay'],d['xAxis'],d['yAxis'],d['output'],d['overlayStart'],d['overlayEnd'],None,d['end'])
            else:
                overlayVideo(d['input'],d['overlay'],d['xAxis'],d['yAxis'],d['output'],d['overlayStart'],d['overlayEnd'],None,None)
    except:
        pass
    try:    
        for d in jsonData['overlayImage']:
            #image overlay
            overlayImage(d['input'],d['overlay'],d['xAxis'],d['yAxis'],d['output'],d['start'],d['end'])
    except:
        pass
    try:
        for d in jsonData['processVideo']:
            #full video processing
            processVideo(d['input'],d['inTime'],d['outTime'],d['regions'],d['intro'],d['endscreens'],d['startEndscreen'],d['xAxisRating'],d['yAxisRating'],d['endRating'],d['startIntro'],d['endIntro'],d['videoFadeIn'],d['videoFadeOut'],d['audioFadeIn'],d['audioFadeOut'],d['output'])
    except:
        pass