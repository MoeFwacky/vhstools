import configparser
import datetime
import internetarchive
import json
import os
import time

if os.name == 'nt':
    delimeter = '\\'
else:
    delimeter = '/'
scriptPath = os.path.realpath(os.path.dirname(__file__))
config = configparser.ConfigParser()
config.read(scriptPath + delimeter + 'config.ini')

vhs_json_file = config['social']['json file']
vhs_directory = config['social']['video directory']

def list_videos(directory):
    all_videos = []

    for video_file in glob.glob(directory+delimeter+"*.mp4"):
        all_videos.append(video_file)
    return all_videos
    
def get_duration(filename):
    video = cv2.VideoCapture(filename)
    frame_count = video.get(cv2.CAP_PROP_FRAME_COUNT)
    fps = video.get(cv2.CAP_PROP_FPS)
    duration = frame_count/fps
    return duration

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

def selectDirectory(delimeter=delimeter):
    print("Enter the directory path to scan")
    workingDir = os.getcwd()
    print("Press Enter to use "+workingDir)
    path = input(">:")
    if path == "":
        path = workingDir
    if path[-1] != delimeter:
        path = path + delimeter
    print("Selected Directory: "+path)
    return path

def uploadToArchive(files):
    if files == None:
        directorypath = selectDirectory()
        #add file selection code
    if len(files)==1:
        tape_name = files[0].split(delimeter)[-1]
        tape_name = tape_name.split('.')[0][0:7]
    elif len(files)>1:
        tape_name = file.split(delimeter)[-2]
    
    j = open(vhs_json_file,)
    tapeData = json.load(j)
    thisTape = []
    for entry in tapeData:
        if entry['Tape_ID'] == tape_name:
            thisTape.append(entry)
    tapeSorted = sorted(thisTape, key=lambda d: d['Order on Tape'])
    metadata = {}
    metadata['title'] = tape_name
    metadata['mediatype'] = 'movies'
    metadata['description'] = ''
    for thisEntry in tapeSorted:
        
        metadata['description'] += thisEntry['Segment Start']+' - '+thisEntry['Segment End']
        metadata['description'] += ", "+thisEntry['Programs']
        metadata['description'] += ", "+thisEntry['Network/Station']+" "+thisEntry['Location']
        try:
            metadata['description'] += ", AIR DATE: "+thisEntry['Recording Date']
            airDate = datetime.datetime.strptime(thisEntry['Recording Date'], '%Y-%m-%d')
            try:
                if airdate < metadata['date']:
                    metadata['date'] = thisEntry['Recording Date']
            except:
                metadata['date'] = thisEntry['Recording Date']
        except Exception as e:
            print(e)
            print("ERROR: AIR DATE NOT FOUND")
        metadata['description'] += "\n"
    
    print(metadata['description'])
    #print("upload("+tape_name+", files="+str(files)+", metadata="+str(metadata)+", verbose=True)")
    u = internetarchive.upload(tape_name, files=files, metadata=metadata, verbose=True)
    print("UPLOAD COMPLETE AT",datetime.datetime.now())