import configparser
import datetime
import internetarchive
import json
import os
import re
import requests
import time
from internetarchive import ArchiveSession, upload
from requests.exceptions import HTTPError

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
    metadata['collection'] = "opensource_movies"
    metadata['description'] = ''
    
    for thisEntry in tapeSorted:
        metadata['description'] += thisEntry['Segment Start']+' - '+thisEntry['Segment End']
        metadata['description'] += ", "+thisEntry['Programs']
        metadata['description'] += ", "+thisEntry['Network/Station']+" "+thisEntry['Location']
        try:
            metadata['description'] += ", AIR DATE: "+thisEntry['Recording Date']
            airDate = datetime.datetime.strptime(thisEntry['Recording Date'], '%Y-%m-%d')
            try:
                if airDate < metadata['date']:
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
    
def uploadClipToArchive(file,clip_json_file,redirector=None):
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
                    session = internetarchive.ArchiveSession()
                    item = session.get_item(identifier)
                    try:
                        uploaded_datetime = datetime.datetime.fromisoformat(item.metadata['created']).strftime('%Y-%m-%d %H:%M:%S')
                    except KeyError:
                        continue
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
    metadata['description'] = thisClip["Description"] + "\n\nFrom Network/Station: " + thisClip["Network/Station"]+"\nRecorded in "+ thisClip["Location"] + " on " + thisClip["Air Date"] + "\n\n" + "Clipped from " + thisClip["Tape ID"] + " frames " + str(thisClip["Frame Range"][0]) +" - "+ str(thisClip["Frame Range"][1]) 
    metadata['date'] = thisClip["Air Date"]
    tags_split = thisClip["Tags"].split(',')
    tags_string = ""
    for tag in tags_split:
        tag = tag.strip()
        tags_string += tag+';'
    tags_string = tags_string.rstrip(';')
    metadata['subject'] = tags_string
    metadata['collection'] = re.split(', |,',config['internet archive']['collection identifiers'])
    identifier = thisClip["Tape ID"] + "_" + str(thisClip["Frame Range"][0]) + "-" + str(thisClip["Frame Range"][1])
    for key, value in metadata.items():
        print(key+": "+str(value))
    #print("upload("+tape_name+", files="+str(files)+", metadata="+str(metadata)+", verbose=True)")
    attempt = 0
    task_threshold = int(config['internet archive']['task threshold'])
    queued_task_threshold = int(config['internet archive']['queued task threshold'])
    total_seconds_waited = 0
    while True:
        archive_session = ArchiveSession()
        while True:
            # Get the summary of tasks
            tasks_summary = archive_session.get_tasks_summary(params={'color': 'green'})
            #print(tasks_summary)
            # Get the count of running tasks
            num_running_tasks = tasks_summary.get('running', 0)
            num_queued_tasks = tasks_summary.get('queued', 0)

            # Check if the number of running tasks is over the threshold
            if num_running_tasks < task_threshold and num_queued_tasks < queued_task_threshold:
                print(f"Number of running tasks: {num_running_tasks}")
                print(f"Number of queued tasks: {num_queued_tasks}")
                break

            if num_running_tasks > task_threshold:
                print(f"[ACTION] Waiting for running tasks ({num_running_tasks}) to reduce below {task_threshold}...")
                sleep_time_seconds = 60  # Wait for 60 seconds before checking again
            elif num_queued_tasks > queued_task_threshold:
                print(f"[ACTION] Waiting for queued tasks ({num_queued_tasks}) to reduce below {queued_task_threshold}...")
                sleep_time_seconds = 300  # Wait for 300 seconds before checking again                
            seconds_waited = 0
            if redirector:
                while seconds_waited < sleep_time_seconds:
                    redirector.progress_widget['maximum'] = sleep_time_seconds
                    seconds_waited += 1
                    total_seconds_waited += 1
                    redirector.progress_var.set(seconds_waited)
                    seconds_remaining = "{:02d}:{:02d}".format(*divmod(sleep_time_seconds-seconds_waited, 60))
                    formatted_time = "{:02d}:{:02d}".format(*divmod(total_seconds_waited, 60))
                    redirector.progress_label.config(text="[{}<{}]".format(formatted_time, seconds_remaining))
                    time.sleep(1)
            else:
                time.sleep(sleep_time_seconds)
     
        attempt += 1
        try:
            u = internetarchive.upload(identifier, files=[file], metadata=metadata, verbose=True, access_key=access_key, secret_key=secret_key)
            task_id = u[0].headers.get("x-archive-task-id")
            break

        except TimeoutError as e:
            if attempt < 5:
                time.sleep(attempt*attempt)
            else:
                print("[ERROR] "+str(e))
                break
        except HTTPError as e:
            if e.response.status_code == 503:
                print("[ERROR] Service Unavailable (503): The server is currently unable to handle the request. Retrying...")
                if attempt < 5:
                    time.sleep(attempt * 120)
                else:
                    print("[ERROR] Max retries reached.")
                    break

    print("[INFO] Waiting for processing to complete...",end='')
    waiting_loop = 0
    # Wait until all upload tasks are completed
    archive_session = ArchiveSession()
    total_seconds_waited = 0
    while True:
        waiting_loop += 1
        # Fetch all tasks
        tasks = archive_session.get_tasks(identifier=identifier)

        # Check if all tasks are completed
        all_tasks_done = all(task.color == "done" or None for task in tasks)
        #completed_tasks_count = sum(1 for task in tasks if task.color == "done" or None)

        # Check the color status of each task
        completed_tasks_count = 0
        for task in tasks:
            #print(f"Task {task.task_id} color: {task.color}")

            # Check for failure
            if task.color == "red":
                print(f"[ERROR] Upload for task {task.task_id} has failed. Task details: {task}")
                all_tasks_done = False  # Set to False as there is a failure

            # Check for still running (optional, you may choose to omit this)
            elif task.color in ["done", None]:
                completed_tasks_count += 1

        #print(f"{completed_tasks_count} of {len(tasks)} tasks completed.")
        if completed_tasks_count >= len(tasks) / 2:
            print(f"[INFO] At least half of the tasks are completed. Moving on.")
            break
        sleep_time_seconds = int(config['internet archive']['task check interval'])       
        print(f"[ACTION] {completed_tasks_count} of {len(tasks)} tasks completed. Waiting for at least half to complete...")
        seconds_waited = 0
        if redirector:
            while seconds_waited < sleep_time_seconds:
                redirector.progress_widget['maximum'] = sleep_time_seconds
                seconds_waited += 1
                total_seconds_waited += 1
                redirector.progress_var.set(seconds_waited)
                seconds_remaining = sleep_time_seconds - seconds_waited
                formatted_time = "{:02d}:{:02d}".format(*divmod(total_seconds_waited, 60))
                redirector.progress_label.config(text="[{}<{}]".format(formatted_time, seconds_remaining))
                time.sleep(1)
        else:
            time.sleep(sleep_time_seconds)
        
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