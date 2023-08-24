import configparser
import datetime
import googleapiclient.discovery
import googleapiclient.errors
import google_auth_oauthlib.flow
import hashlib
import json
import os
import re
import secrets
import threading
import time
import tkinter as tk
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from tkinter import filedialog
from tkinter import messagebox
from tkinter import scrolledtext
from tkinter import ttk

if os.name == 'nt':
    delimeter = '\\'
else:
    delimeter = '/'
scriptPath = os.path.realpath(os.path.dirname(__file__))
config = configparser.ConfigParser()
config.read(os.path.join(scriptPath,'config.ini'))

vhs_json_file = config['directories']['json file']
vhs_directory = config['directories']['video directory']
credentials_path = config['youtube']['credentials path']

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def get_authenticated_youtube_service(credentials_path):
    creds = None

    # Load the existing credentials from the file if available
    if os.path.exists(credentials_path):
        with open(credentials_path, "r") as f:
            credentials_info = json.load(f)
        
        # Check if required fields are present in the credentials_info
        if 'client_id' in credentials_info and 'client_secret' in credentials_info and 'refresh_token' in credentials_info:
            creds = Credentials.from_authorized_user_info(credentials_info)

    # If credentials are not available or invalid, use the client credentials flow
    if not creds or not creds.valid:
        flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_config(
            credentials_info,
            scopes=["https://www.googleapis.com/auth/youtube.upload"]
        )
        creds = flow.run_local_server()

        # Save the obtained credentials to the file
        #credentials_info['installed']["client_id"] = creds.client_id,
        #credentials_info['installed']["client_secret"] = creds.client_secret,
        #credentials_info['installed']["token_uri"] = creds.token_uri,
        #credentials_info['installed']["refresh_token"] = creds.refresh_token
        
        #with open(credentials_path, "w") as f:
        #    json.dump(credentials_info, f)

    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=creds)
    return youtube

#youtube = get_authenticated_youtube_service(credentials_path)

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

def format_time(total_seconds):
    minutes, seconds = divmod(int(total_seconds), 60)
    return f"{minutes:02d}:{seconds:02d}"

def remove_html_tags(text):
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

def perform_upload(file, youtube_metadata, media_file):
    try:
        # Upload the video to YouTube
        request = youtube.videos().insert(part='snippet,status', body=youtube_metadata, media_body=media_file)
        response = None

        # Perform the upload
        response = request.execute()

        print("Video uploaded successfully! Video ID:", response["id"])
        print("UPLOAD COMPLETE AT " + datetime.datetime.now().strftime("%H:%M:%S"), end='\n\n')
    except googleapiclient.errors.HttpError as e:
        error_details = e.resp
        error_message = remove_html_tags(e._get_reason())
        error_code = error_details['status']
        print(f"HTTP Error {error_code}: {error_message}")

def check_response(request, media_file, redirector):
    start_time = time.time()
    while True:
        try:
            status, response = request.next_chunk()
            if status:
                elapsed_time = time.time() - start_time
                bytes_uploaded = media_file.getbytesuploaded()
                total_size = media_file.size()
                progress = bytes_uploaded / total_size
                estimated_completion_time = (elapsed_time / (progress + 1e-9)) * (1 - progress)
                estimated_minutes, estimated_seconds = divmod(int(estimated_completion_time), 60)
                estimated_time_string = f"{estimated_minutes:02d}:{estimated_seconds:02d}"

                if redirector is not None:
                    redirector.progress_widget['maximum'] = 1
                    redirector.progress_var.set(progress)
                    redirector.action_label.config(text="Uploading " + os.path.basename(file) + " to YouTube")
                    redirector.progress_label.config(
                        text=f"Uploaded {int(progress * 100)}%, {format_time(elapsed_time)}<{estimated_time_string}."
                    )
                if response is not None:
                    break  # Video upload is complete

            time.sleep(1)  # Adjust this interval as needed for update frequency
        except Exception as e:
            try:
                error_details = e.resp
                error_message = remove_html_tags(e._get_reason())
                error_code = error_details['status']
                print(f"HTTP Error {error_code}: {error_message}")
            except:
                print("[ERROR] Error checking status")
            break

def uploadToYouTube(file, redirector=None):
    if file is None:
        print("[ERROR] No file selected for upload.")
        return "No File Selected for Upload", "Choose a file to upload before starting"
   
    j = open(vhs_json_file,)
    tapeData = json.load(j)
    
    tape_name = os.path.splitext(os.path.basename(file))[0]
    thisTape = []
    for entry in tapeData:
        if entry['Tape_ID'] == tape_name:
            thisTape.append(entry)
    tapeSorted = sorted(thisTape, key=lambda d: d['Order on Tape'])

    metadata = {}
    metadata['title'] = tape_name
    metadata['description'] = ''
    metadata['tags'] = []
    for thisEntry in tapeSorted:
        metadata['description'] += thisEntry['Segment Start']+' - '+thisEntry['Segment End']
        metadata['description'] += ", "+thisEntry['Programs']
        metadata['description'] += ", "+thisEntry['Network/Station']+" "+thisEntry['Location']
        metadata['tags'].append(thisEntry['Programs'])
        try:
            metadata['description'] += ", AIR DATE: "+thisEntry['Recording Date']
        except Exception as e:
            print(e)
            print("ERROR: AIR DATE NOT FOUND")
        metadata['description'] += "\n"
        metadata['categoryID'] = "22"
    
    print(metadata['description'])
    youtube_metadata = {}
    youtube_metadata['snippet'] = metadata
    youtube_metadata['status'] = {"privacyStatus": "public","selfDeclaredMadeForKids":False}

    try:
        # Upload the video to YouTube
        media_file = MediaFileUpload(file, chunksize=1048576, resumable=True)
        request = youtube.videos().insert(part='snippet,status', body=youtube_metadata, media_body=media_file)
        response = None
        start_time = time.time()
        while response is None:
            status, response = request.next_chunk()
            if status:
                elapsed_time = time.time() - start_time
                progress = status.progress()
                estimated_completion_time = (elapsed_time / (progress + 1e-9)) * (1 - progress)
                estimated_minutes, estimated_seconds = divmod(int(estimated_completion_time), 60)
                estimated_time_string = f"{estimated_minutes:02d}:{estimated_seconds:02d}"
                if redirector is not None:
                    redirector.progress_widget['maximum'] = 1
                    redirector.progress_var.set(progress)
                    redirector.action_label.config(text="Uploading " + os.path.basename(file) + " to YouTube")
                    redirector.progress_label.config(text=f"Uploaded {int(progress * 100)}%, {format_time(elapsed_time)}<{estimated_time_string}.")

        print("Video uploaded successfully! Video URL: "+"https://www.youtube.com/watch?v="+response["id"])
        print("UPLOAD COMPLETE AT " + datetime.datetime.now().strftime("%H:%M:%S"), end='\n\n')
        print("-----------------------------------------------------")
        return None    
    except googleapiclient.errors.HttpError as e:
        error_details = e.resp
        error_message = remove_html_tags(e._get_reason())
        error_code = error_details['status']
        print(f"HTTP Error {error_code}: {error_message}")
        print(datetime.datetime.now().strftime("%H:%M:%S"),end='\n\n')
        print("-----------------------------------------------------")
        if redirector != None:
            redirector.progress_var.set(0)
            redirector.action_label.config(text="")
            redirector.progress_label.config(text="")
        return error_code, error_message
    
def uploadClipToYouTube(file, clip_json_file=None, redirector=None):
    if file is None:
        print("[ERROR] No file selected for upload.")
        return "No File Selected for Upload", "Choose a file to upload before starting"
    
    if clip_json_file is None:
        print("[ERROR] Data file not selected")
        return "No Data File Selected", "Select a Clip Data file before starting."
    
    j = open(clip_json_file,)
    tapeData = json.load(j)
    
    for entry in tapeData:
        if entry["Filename"] == os.path.basename(file):
            thisClip = entry
    
    metadata = {}
    metadata['title'] = thisClip["Title"] + " " + thisClip["Air Date"]
    metadata['description'] =  thisClip["Description"] + "\n" + thisClip["Network/Station"]+" - "+ thisClip["Location"] + "\n" + "Recorded on: "+ thisClip["Air Date"] + "\n\n" + "Clipped from " + thisClip["Tape ID"] + " frames " + str(thisClip["Frame Range"][0]) +" - "+ str(thisClip["Frame Range"][1])
    metadata['tags'] = [tag.strip() for tag in thisClip["Tags"].split(',')]
    metadata['categoryID'] = "22"
    
    youtube_metadata = {}
    youtube_metadata['snippet'] = metadata
    youtube_metadata['status'] = {"privacyStatus": "public","selfDeclaredMadeForKids":False}
   
    try:
        # Upload the video to YouTube
        media_file = MediaFileUpload(file, chunksize=1048576, resumable=True)
        request = youtube.videos().insert(part='snippet,status', body=youtube_metadata, media_body=media_file)
        response = None
        start_time = time.time()
        while response is None:
            status, response = request.next_chunk()
            if status:
                elapsed_time = time.time() - start_time
                progress = status.progress()
                estimated_completion_time = (elapsed_time / (progress + 1e-9)) * (1 - progress)
                estimated_minutes, estimated_seconds = divmod(int(estimated_completion_time), 60)
                estimated_time_string = f"{estimated_minutes:02d}:{estimated_seconds:02d}"
                if redirector == None:
                    print(f"Uploaded {int(status.progress * 100)}%.")
                else:
                    redirector.progress_widget['maximum'] = 1
                    redirector.progress_var.set(progress)
                    redirector.action_label.config(text="Uploading "+os.path.basename(file)+" to YouTube")
                    redirector.progress_label.config(text=f"Uploaded {int(progress * 100)}%, {format_time(elapsed_time)}<{estimated_time_string}.")
        print("Video uploaded successfully! Video URL: "+"https://www.youtube.com/watch?v="+response["id"])
        print("UPLOAD COMPLETE AT " + datetime.datetime.now().strftime("%H:%M:%S"), end='\n\n')
        print("-----------------------------------------------------")
        return None
    except googleapiclient.errors.HttpError as e:
        error_details = e.resp
        error_message = remove_html_tags(e._get_reason())
        error_code = error_details['status']
        print(f"HTTP Error {error_code}: {error_message}")
        print(datetime.datetime.now().strftime("%H:%M:%S"),end='\n\n')
        print("-----------------------------------------------------")
        if redirector != None:
            redirector.progress_var.set(0)
            redirector.action_label.config(text="")
            redirector.progress_label.config(text="")
        return error_code, error_message