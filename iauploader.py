import configparser
import datetime
import internetarchive
import json
import os
import requests
import time

if os.name == 'nt':
    delimeter = '\\'
else:
    delimeter = '/'
scriptPath = os.path.realpath(os.path.dirname(__file__))
config = configparser.ConfigParser()
config.read(os.path.join(scriptPath,'config.ini'))

vhs_json_file = config['directories']['json file']
vhs_directory = config['directories']['video directory']

#Internet Archive API Keys
access_key = config['internet archive']['access key']
secret_key = config['internet archive']['secret key']

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
    metadata['collection'] = "Community movies"
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
    u = internetarchive.upload(tape_name, files=files, metadata=metadata, verbose=True, access_key=access_key, secret_key=secret_key)
    print("UPLOAD COMPLETE AT",datetime.datetime.now())
    
def uploadClipToArchive(file,clip_json_file):
    if file == None:
        directorypath = selectDirectory()
    with open(clip_json_file, 'r') as j:
        tapeData = json.load(j)
    #thisTape = []
    for key,entry in enumerate(tapeData):
        if entry["Filename"] == os.path.basename(file):
            thisClip = entry
            thisKey = key
            if "Uploaded" in thisClip and "internet archive" in thisClip["Uploaded"]:
                existing_url = thisClip["Uploaded"]["internet archive"]["url"]
                print("[ERROR] Archive already exists: "+existing_url)
                return "Archive Already Exists", "This clip has already been uploaded to the Internet Archive on "+thisClip["Uploaded"]["internet archive"]["datetime"]+'\n'+existing_url
            else:
                identifier = thisClip["Tape ID"] + "_" + str(thisClip["Frame Range"][0]) + "-" + str(thisClip["Frame Range"][1])
                response = requests.head("https://archive.org/details/"+identifier)
                if response.status_code == 200:
                    internetarchive.configure(access_key=access_key,secret_key=secret_key)
                    item = internetarchive.get_item(identifier)
                    uploaded_datetime = datetime.datetime.fromisoformat(item.metadata['created']).strftime('%Y-%m-%d %H:%M:%S')
                    uploaded_data = {
                        "internet archive": {
                            "url": "https://archive.org/details/"+identifier,
                            "datetime": uploaded_datetime
                        }
                    }
                    if 'Uploaded' in thisClip:
                        thisClip['Uploaded'].update(uploaded_data)
                    else:
                        thisClip['Uploaded'] = uploaded_data
                    tapeData[thisKey] = thisClip
                    with open(clip_json_file, 'w') as file:
                        json.dump(tapeData, file, indent=4)
                    already_exists = []
                    already_exists.append("Archive Already Exists")
                    already_exists.append("This clip has already been uploaded to the Internet Archive on "+uploaded_datetime+'\n'+"https://archive.org/details/"+identifier)
                    return already_exists[0],already_exists[1]
                else:
                    pass
            
    #tapeSorted = sorted(thisTape, key=lambda d: d['Order on Tape'])
    metadata = {}
    metadata['title'] = thisClip["Title"] + " " + thisClip["Network/Station"]+ " " + thisClip["Air Date"]
    metadata['mediatype'] = 'movies'
    metadata['description'] = thisClip["Network/Station"]+" - "+ thisClip["Location"] + "\n" + thisClip["Description"] + "\n\n" + "Clipped from " + thisClip["Tape ID"] + " frames " + str(thisClip["Frame Range"][0]) +" - "+ str(thisClip["Frame Range"][1])
    metadata['date'] = thisClip["Air Date"]
    tags_split = thisClip["Tags"].split(',')
    tags_string = ""
    for tag in tags_split:
        tag = tag.strip()
        tags_string += tag+';'
    tags_string = tags_string.rstrip(';')
    metadata['subject'] = tags_string
    #metadata['collection'] = "Community movies"
    identifier = thisClip["Tape ID"] + "_" + str(thisClip["Frame Range"][0]) + "-" + str(thisClip["Frame Range"][1])
    for key, value in metadata.items():
        print(key+": "+str(value))
    #print("upload("+tape_name+", files="+str(files)+", metadata="+str(metadata)+", verbose=True)")
    u = internetarchive.upload(identifier, files=[file], metadata=metadata, verbose=True, access_key=access_key, secret_key=secret_key)
    uploaded_url = "https://archive.org/details/"+identifier
    uploaded_datetime = datetime.datetime.now()
    uploaded_data = {
        "internet archive": {
            "url": uploaded_url,
            "datetime": uploaded_datetime.strftime('%Y-%m-%d %H:%M:%S')
        }
    }
    if 'Uploaded' in thisClip:
        thisClip['Uploaded'].update(uploaded_data)
    else:
        thisClip['Uploaded'] = uploaded_data
    tapeData[thisKey] = thisClip
    with open(clip_json_file, 'w') as file:
        json.dump(tapeData, file, indent=4)
    print("Video uploaded successfully! Video URL: "+uploaded_url)
    print("UPLOAD COMPLETE AT "+uploaded_datetime.strftime("%H:%M:%S"),end='\n\n')
    print("-----------------------------------------------------")
    return None