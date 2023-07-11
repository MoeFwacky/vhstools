import argparse
import configparser
import datetime
import io
import json
import os
import random
import ray
import re
import string
import sys
import threading
import tkinter as tk
import tqdm
import webbrowser
from alive_progress import alive_bar
from tkinter import filedialog
from tkinter import messagebox
from tkinter import scrolledtext
from tkinter import ttk

scriptPath = os.path.realpath(os.path.dirname(__file__))
config = configparser.ConfigParser()
config.read(os.path.join(scriptPath,'config.ini'))
json_file = config['analysis']['json file']

# Create a custom TextRedirector class to redirect console output to the text box
class TextRedirector(io.TextIOBase):
    def __init__(self, text_widget, max_lines=150, progress_widget=None, progress_label=None, action_label=None):
        self.text_widget = text_widget
        self.max_lines = max_lines
        self.progress_widget = progress_widget
        self.progress_label = progress_label
        self.action_label = action_label

    def write(self, s):
        # Remove excess lines if necessary
        lines = self.text_widget.get("1.0", tk.END).splitlines()
        if len(lines) >= self.max_lines:
            self.text_widget.delete("1.0", f"{len(lines)-self.max_lines+1}.0")

        # Handle custom end characters
        if s.endswith("\r\n"):
            # Remove carriage return and newline characters
            s = s.rstrip("\r\n")
        elif s.endswith("\r"):
            # Append a return character to the output
            s += "\r"
        else:
            s = s.rstrip("\n")

        # Update the progress bar if it exists and skip output starting with 'chunk:'
        if s.lstrip().startswith("chunk:") or s.lstrip().startswith("t:"):
            self.progress_widget['maximum'] = 100
            self.update_progress_mp(s)
            return
        elif s.lstrip().startswith("MoviePy") or s.lstrip().startswith("[ACTION]"):
            if "MoviePy" and "Done" in s.lstrip():
                self.progress_widget['value'] = self.progress_widget['maximum']
                self.progress_widget.update()
                return
            self.action_label.config(text=s.strip().replace("MoviePy - ","").replace("[ACTION] ",""))
            return
        # Write to the console
        #sys.__stdout__.write(s)
        if len(s.strip()) == 0 or s.strip() == "\n" or "Done." in s.strip():
            return
        # Remove the last newline character if it exists
        if self.text_widget.get("end-1c", "end") == "\n":
            self.text_widget.delete("end-1c")

        # Insert new output at the end, with a newline at the beginning of the next line
        self.text_widget.insert(tk.END, "\n" + s)

        # Update the progress widget immediately
        self.progress_widget.update()
        self.text_widget.see(tk.END)  # Scroll to the end of the text box


    def set_progress_widget(self, progress_widget):
        self.progress_widget = progress_widget

    def update_progress(self, output):
        # Parse the progress information from the output
        progress = output.split(": ")[-1].rstrip("\n")

        # Update the progress widget
        self.progress_widget['value'] = float(progress)
        self.progress_widget.update()

    def update_progress_mp(self, output):
        # Extract the progress information from the output
        if "chunk:" in output:
            parts = output.split("chunk:")
        elif "t:" in output:
            parts = output.split("t:")
        progress_info = parts[1].strip()
        progress = progress_info.split('%')[0]
        progress_data = progress + '% ' + parts[1].split('|')[2]
        progress_data = progress_data.replace(' [',', ').replace(', now=None]','')
        # Update the progress widget
        self.progress_label.config(text=str(progress_data))
        self.progress_widget['value'] = float(progress)
        self.progress_widget.update()

    def flush(self):
        pass  # No need to flush in this case
        
print(":::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::")
print(":::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::")
print("::o     o  o      8                 ooooo               8        ::")
print("::8     8         8                   8                 8        ::")
print("::8     8 o8 .oPYo8 .oPYo. .oPYo.     8   .oPYo. .oPYo. 8 .oPYo. ::")
print("::`b   d'  8 8    8 8oooo8 8    8     8   8    8 8    8 8 Yb..   ::")
print(":: `b d'   8 8    8 8.     8    8     8   8    8 8    8 8   'Yb. ::")
print("::  `8'    8 `YooP' `Yooo' `YooP'     8   `YooP' `YooP' 8 `YooP' ::")
print(":::::..::::..:.....::.....::.....:::::..:::.....::.....:..:.....:::")
print(":::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::")
#print(":::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::")

parser = argparse.ArgumentParser(description="Video Tools")
parser.add_argument('-b', '--bot', action='store_true', help="Bot that listens for submissions of video clip information")
parser.add_argument('-a', '--archive', action='store_true', help="Upload indicated file(s) to the internet archive")
parser.add_argument('-fb', '--facebook', action='store_true', help="Automatically post video clips to Facebook")
parser.add_argument('-tw', '--twitter', action='store_true', help="Automatically post video clips to Twitter")
parser.add_argument('-tb', '--tumblr', action='store_true', help="Automatically post video clips to Tumblr")
parser.add_argument('-m', '--mastodon', action='store_true', help="Automatically post video clips to Mastodon")
parser.add_argument('-ds', '--discord', action='store_true', help="Automatically post video clips to Discord")
parser.add_argument('-sc', '--scanner', action='store_true', help="Scan video file(s) and generate json data file(s)")
parser.add_argument('-sp', '--splitter', action='store_true', help="Detect dip-to-black in video file(s) and save clips to folder")
parser.add_argument('-au', '--audio', action='store_true', help="Normalize audio levels")
parser.add_argument('-id', '--identify', action='store_true', help="Use AI tools to analyze and identify video clips")
parser.add_argument('-e', '--editor', action='store_true', help="Process video edits as defined in a JSON file")
parser.add_argument('-t', '--tagger', action='store_true', help="Add metadata to videos by parsing JSON data")
parser.add_argument('-fn', '--filename', type=str, help="Name of the video file in the working directory (including extension)")
parser.add_argument('-fp', '--filepath', type=str, help="Full path of the video file (Windows paths use double backlash)")
parser.add_argument('-d', '--directory', type=str, help="Full path of directory to process all videos (Windows paths use double backslash)")
parser.add_argument('-p', '--persist', action='store_true', help="Allows some functions to save and load some status information between uses")
args = parser.parse_args()

if os.name == 'nt':
    delimeter = '\\'
else:
    delimeter = '/'

def redirect_console_output(text_widget,progress_widget=None,progress_label=None,action_label=None):
    #print("Create an instance of TextRedirector and Progress Bar Redirector")
    stdout_redirector = TextRedirector(text_widget,progress_widget=progress_widget,progress_label=progress_label,action_label=action_label)
    #print("Replace sys.stdout and sys.stderr with redirector") 
    try:
        sys.stdout = stdout_redirector
        sys.stderr = stdout_redirector
    except Exception as e:
        print("ERROR:",e)
    #tqdm_out = tqdm.tqdm(file=progress_bar_redirector, ncols=80)
    progress_bar_redirector = None
    return stdout_redirector,progress_bar_redirector

def update_progress_bar():
    progress_var.set(progress)
    progress_label.config(text=f"Progress: {progress}%")

def launch_scanner(file=None,directory=None,progress_label=None,progress_widget=None):
    import videoscanner
    
    print(": ___  __              ___     __   __                  ___  __  ::")
    print(":|__  |__)  /\   |\/| |__     /__` /  `  /\  |\ | |\ | |__  |__) ::")
    print(":|    |  \ /~~\  |  | |___    .__/ \__, /~~\ | \| | \| |___ |  \ ::")
    print(":::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::")
    starting_time = datetime.datetime.now()
    if file != None:
        #print("PROCESSING", file)
        try:
            videoscanner.scanVideo(file,progress_label=progress_label,progress_widget=progress_widget)
        except Exception as e:
            print(e)
            videoscanner.scanVideo(file,progress_label=progress_label,progress_widget=progress_widget)
    elif directory != None:
        dirContents = os.scandir(args.directory)
        dirList = []
        extensions = ['mp4','avi','m4v','mkv']
        total_files = 0
        for entry in dirContents:
            if entry.name[-3:] in extensions:
                print("Processing file {}/{}: {}".format(current_file, total_files, entry.name))
                total_files += 1
                videoscanner.scanVideo(os.path.join(directory,entry.name),directory,progress_label=progress_label,progress_widget=progress_widget)
    else:
        videoscanner.scanVideo(progress_label=progress_label,progress_widget=progress_widget)
    ending_time = datetime.datetime.now()
    elapsed_time = ending_time - starting_time
    time_minutes = elapsed_time.total_seconds() // 60
    time_seconds = elapsed_time.total_seconds() % 60
    if action_label != None:
        progress_widget['value'] = progress_widget['maximum']
        action_label.config(text="")
        progress_label.config(text=f"Complete in {int(time_minutes):d} minutes, {int(time_seconds):d} seconds")
    else: 
        print(f"Complete in {int(time_minutes):d} minutes, {int(time_seconds):d} seconds")
def launch_splitter(file=None,directory=None,progress_label=None,progress_widget=None):
    import scenesplitter
    print(":::::::::  __                   __                        :::::::::")
    print("::::::::: (_   _  _  ._   _    (_  ._  | o _|_ _|_  _  ._ :::::::::")
    print("::::::::: __) (_ (/_ | | (/_   __) |_) | |  |_  |_ (/_ |  :::::::::")
    print(":::::::::                          |                      :::::::::")
    print(":::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::")
    starting_time = datetime.datetime.now()
    if file != None:
        #print("PROCESSING", file)
        scenesplitter.processVideo(file,os.path.dirname(file),progress_label=progress_label,progress_widget=progress_widget)
    elif directory != None:
        dirContents = os.scandir(directory)
        dirList = []
        extensions = ['mp4','avi','m4v','mkv']
        for entry in dirContents:
            if entry.name[-3:] in extensions:
                print("PROCESSING", entry.name, "in", directory)
                scenesplitter.processVideo(entry.name, directory,progress_label=progress_label,progress_widget=progress_widget)
    else:
        scenesplitter.processVideo(progress_label=progress_label,progress_widget=progress_widget)
    ending_time = datetime.datetime.now()
    elapsed_time = ending_time - starting_time
    time_minutes = elapsed_time.total_seconds() // 60
    time_seconds = elapsed_time.total_seconds() % 60
    if action_label != None:
        progress_widget['value'] = progress_widget['maximum']
        action_label.config(text="")
        progress_label.config(text=f"Complete in {int(time_minutes):d} minutes, {int(time_seconds):d} seconds")
    else: 
        print(f"Complete in {int(time_minutes):d} minutes, {int(time_seconds):d} seconds")
def launch_audio_normalizer(file=None,directory=None,progress_label=None,progress_widget=None):
    print("::: ___  __ __ _____ __  _____                                  :::")
    print(":::||=|| || || ||  ) || ((   ))                                 :::")
    print(":::|| ||_\\_//_||_//_|| _\\_//_  ___  __    __ ____  _____ _____:::")
    print(":::||\\|| ((   )) ||_// || \/ | ||=|| ||    ||   //  ||==  ||_//:::")
    print(":::|| \||  \\_//  || \\ ||    | || || ||__| ||  //__ ||___ || \\:::")
    print(":::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::")
    starting_time = datetime.datetime.now()
    import normalizer
    if file != None:
        normalizer.normalize_audio(file)
    elif directory != None:
        dirContents = os.scandir(directory)
        dirList = []
        extensions = ['mp4','avi','m4v','mkv']
        for entry in dirContents:
            if entry.name[-3:] in extensions:
                print("NORMALIZING "+str(entry.name)+" in "+str(directory))
                normalizer.normalize_audio(os.path.join(directory, entry.name))
    else:
        print("Press Enter to use "+workingDir)
        path = input(">:")
        if path == "":
            path = workingDir
        dirContents = os.scandir(path)
        dirDict = {}
        extensions = ['mp4', 'm4v', 'avi', 'mkv']
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
        normalizer.normalize_audio(os.path.join(path,dirDict[fileSelection]))
    ending_time = datetime.datetime.now()
    elapsed_time = ending_time - starting_time
    time_minutes = elapsed_time.total_seconds() // 60
    time_seconds = elapsed_time.total_seconds() % 60
    if action_label != None:
        progress_widget['value'] = progress_widget['maximum']
        action_label.config(text="")
        progress_label.config(text=f"Complete in {int(time_minutes):d} minutes, {int(time_seconds):d} seconds")
    else: 
        print(f"Complete in {int(time_minutes):d} minutes, {int(time_seconds):d} seconds")
def launch_identifier(file=None,directory=None,progress_label=None,progress_widget=None,action_label=None):
    print("██ ██████  ███████ ███    ██ ████████ ██ ███████ ██ ███████ ██████ ")
    print("██ ██   ██ ██      ████   ██    ██    ██ ██      ██ ██      ██   ██")
    print("██ ██   ██ █████   ██ ██  ██    ██    ██ █████   ██ █████   ██████ ")
    print("██ ██   ██ ██      ██  ██ ██    ██    ██ ██      ██ ██      ██   ██")
    print("██ ██████  ███████ ██   ████    ██    ██ ██      ██ ███████ ██   ██")
    print(":::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::")
    starting_time = datetime.datetime.now()
    if action_label != None:
        action_label.config(text="")
    if progress_label != None:
        progress_label.config(text="")
    import analysis
    if file != None:
        analysis.analyze_video(file,progress_label=progress_label,progress_widget=progress_widget)
        progress_widget.destroy() if progress_widget is not None else None
    elif directory != None:
        dirContents = os.scandir(directory)
        dirList = []
        extensions = ['mp4','avi','m4v','mkv']

        for i, entry in enumerate(dirContents):
            if entry.name[-3:] in extensions:
                print(entry.name)
                analysis.analyze_video(os.path.join(directory, entry.name),progress_label=progress_label,progress_widget=progress_widget)
    else:
        dirContents = os.scandir(os.getcwd())
        dirList = []
        extensions = ['mp4','avi','m4v','mkv']
        for entry in dirContents:
            if entry.name[-3:] in extensions:
                print(entry.name)
                analysis.analyze_video(os.path.join(os.getcwd(), entry.name),progress_label=progress_label,progress_widget=progress_widget)
    ending_time = datetime.datetime.now()
    elapsed_time = ending_time - starting_time
    time_minutes = elapsed_time.total_seconds() // 60
    time_seconds = elapsed_time.total_seconds() % 60
    if action_label != None:
        progress_widget['value'] = progress_widget['maximum']
        action_label.config(text="")
        progress_label.config(text=f"Complete in {int(time_minutes):d} minutes, {int(time_seconds):d} seconds")
    else: 
        print(f"Complete in {int(time_minutes):d} minutes, {int(time_seconds):d} seconds")
def launch_archiver(file=None,directory=None):
    import iauploader
    print("::::::: █████╗ ██████╗  ██████╗██╗  ██╗██╗██╗   ██╗███████╗::::::::")
    print(":::::::██╔══██╗██╔══██╗██╔════╝██║  ██║██║██║   ██║██╔════╝::::::::")
    print(":::::::███████║██████╔╝██║     ███████║██║██║   ██║█████╗  ::::::::")
    print(":::::::██╔══██║██╔══██╗██║     ██╔══██║██║╚██╗ ██╔╝██╔══╝  ::::::::")
    print(":::::::██║  ██║██║  ██║╚██████╗██║  ██║██║ ╚████╔╝ ███████╗::::::::")
    print(":::::::╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═══╝  ╚══════╝::::::::")
    print(":::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::")
    if file != None:
        print("UPLOADING", file, "to the Internet Archive")
        iauploader.uploadToArchive([file])
    elif directory != None:
        dirContents = os.scandir(directory)
        videos = []
        extensions = ['mp4','avi','m4v','mkv']
        for entry in dirContents:
            if entry.name[-3:] in extensions:
                print(entry)
                videos.append(entry)
        if len(videos) > 0:
            iauploader.uploadToArchive(videos)
        else:
            extensions_string = ''
            for ext in extensions:
                extensions_string += ', '+ext
            print("ERROR:",directory,"CONTAINS NO VIDEOS OF THE FOLLOWING TYPES:",extensions_string)
    else:
        iauploader.uploadToArchive(None)

def launch_json_editor(file=None, tape_id=None, progress_label=None, progress_widget=None):
    print("JSON Edit")
    import jsongui
    try:
        jsongui.launch_gui(file)
    except Exception as e:
        print(e)

def launch_editor(file=None,directory=None):
    import editor
    print("::::::                $$\ $$\   $$\                         :::::::")
    print("::::::                $$ |\__|  $$ |                        :::::::")
    print(":::::: $$$$$$\   $$$$$$$ |$$\ $$$$$$\    $$$$$$\   $$$$$$\  :::::::")
    print("::::::$$  __$$\ $$  __$$ |$$ |\_$$  _|  $$  __$$\ $$  __$$\ :::::::")
    print("::::::$$$$$$$$ |$$ /  $$ |$$ |  $$ |    $$ /  $$ |$$ |  \__|:::::::")
    print("::::::$$   ____|$$ |  $$ |$$ |  $$ |$$\ $$ |  $$ |$$ |      :::::::")
    print("::::::\$$$$$$$\ \$$$$$$$ |$$ |  \$$$$  |\$$$$$$  |$$ |      :::::::")
    print(":::::: \_______| \_______|\__|   \____/  \______/ \__|      :::::::")
    print(":::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::")
    if file != None:
        print("PROCESSING", file)
        editor.processJSON(args.filename)
    elif args.filepath != None:
        pathArray = args.filepath.split(delimeter)
        videoFileName = args.filepath.split(delimeter)[-1]
        pathArray.pop()
        path = ""
        for p in pathArray:
            path = path + p + delimeter
        
        editor.processJSON(videoFileName, path)
    elif args.directory != None:
        dirContents = os.scandir(args.directory)
        dirList = []
        extensions = ['json']
        for entry in dirContents:
            if entry.name[-3:] in extensions:
                print(entry.name)
                print("PROCESSING", file,"IN DIRECTORY",directory)
                editor.processJSON(entry.name, args.directory)
    else:
        editor.processJSON()

def launch_tagger(file=None,directory=None):
    import metatagger
    print(":::::::::: __ __ ___ _____ __ _____ __   __  __ ___ ___ :::::::::::")
    print("::::::::::|  V  | __|_   _/  \_   _/  \ / _]/ _] __| _ \:::::::::::")
    print("::::::::::| \_/ | _|  | || /\ || || /\ | [/\ [/\ _|| v /:::::::::::") 
    print("::::::::::|_| |_|___| |_||_||_||_||_||_|\__/\__/___|_|_\:::::::::::") 
    print(":::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::")
    if file != None:
        print("PROCESSING", file)
        metatagger.tagFiles(file)
    elif directory != None:
        dirContents = os.scandir(directory)
        dirList = []
        extensions = ['json']
        for entry in dirContents:
            if entry.name[-3:] in extensions:
                print(entry.name)
                metatagger.tagFiles(entry.name, directory)
    else:
        metatagger.tagFiles()

def launch_vid2social(file=None,directory=None,socials={},persist=False):
    import getvid
    print(":::::::: _   _ _     _  _____  _____            _       _ :::::::::")
    print("::::::::| | | (_)   | |/ __  \/  ___|          (_)     | |:::::::::")
    print("::::::::| | | |_  __| |`' / /'\ `--.  ___   ___ _  __ _| |:::::::::")
    print("::::::::| | | | |/ _` |  / /   `--. \/ _ \ / __| |/ _` | |:::::::::")
    print("::::::::\ \_/ / | (_| |./ /___/\__/ / (_) | (__| | (_| | |:::::::::")
    print(":::::::: \___/|_|\__,_|\_____/\____/ \___/ \___|_|\__,_|_|:::::::::")
    print(":::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::")
    if file != None:
        getvid.social([file],socials['facebook'], socials['twitter'], socials['tumblr'], socials['mastodon'], socials['discord'], persist)
    elif directory != None:
        getvid.social(getvid.list_videos(directory),socials['facebook'], socials['twitter'], socials['tumblr'], socials['mastodon'], socials['discord'], persist)
    else:
        getvid.social(getvid.list_videos(getvid.directory),socials['facebook'], socials['twitter'], socials['tumblr'], socials['mastodon'], socials['discord'], persist)

def launch_socialbot(file=None,directory=None,socials={},persist=False):
    import listentosocial
    import getvid
    print("::::: _______              __         __ ______         __   ::::::")
    print(":::::|     __|.-----.----.|__|.---.-.|  |   __ \.-----.|  |_ ::::::")
    print(":::::|__     ||  _  |  __||  ||  _  ||  |   __ <|  _  ||   _|::::::")
    print(":::::|_______||_____|____||__||___._||__|______/|_____||____|::::::")
    print(":::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::")
    ray.init()
    if file != None:
        @ray.remote
        def Social():
            getvid.social([args.filename],socials['facebook'], socials['twitter'], socials['tumblr'], socials['mastodon'], socials['discord'], persist)
    elif directory != None:
        @ray.remote
        def Social():
            vidList = getvid.list_videos(directory)
            getvid.social(vidList,socials['facebook'], socials['twitter'], socials['tumblr'], socials['mastodon'], socials['discord'], persist)
    else:
        @ray.remote
        def Social():
            vidList = getvid.list_videos(getvid.directory)
            getvid.social(vidList,socials['facebook'], socials['twitter'], socials['tumblr'], socials['mastodon'], socials['discord'], persist)
    rayList = []
    rayList.append(Social.remote())
    if socials['discord'] != False:
        @ray.remote
        def DiscordBot():
            listentosocial.checkDiscord()
        rayList.append(DiscordBot.remote())
    #for i in range(0,250):
    if socials['twitter'] != False:
        @ray.remote
        def TwitterBot():
            listentosocial.checkTwitter()
        rayList.append(TwitterBot.remote())
    if socials['mastodon'] != False:
        @ray.remote
        def MastodonBot():
            listentosocial.checkMastodon()
        rayList.append(MastodonBot.remote())
    try:
        ray.get(rayList)
    except Exception as e:
        print(e)

def update_arguments(*args, selected_script):
    # Clear any existing checkboxes
    for checkbox in checkboxes:
        checkbox.destroy()
    checkboxes.clear()

    # Get the selected option from the dropdown menu
    selected_script = selected_script.get()

    # Create checkboxes for the selected option
    position=6
    for argument in script_to_run[selected_script]:
        var = tk.BooleanVar()
        checkbox = tk.Checkbutton(window, text=argument, variable=var)
        checkbox.grid(row=1, column=position, columnspan=2, sticky=tk.W)
        checkboxes.append(checkbox)
        position+=2

def update_text():
    output_text.delete(1.0, tk.END)
    output_text.insert(tk.END, output_variable.get())

def update_button_state(*args):
    global filename_button
    global directory_button
    selected_option = selected_script.get()
    if selected_option != "SELECT OPERATION":
        filename_button.config(state=tk.NORMAL)
        directory_button.config(state=tk.NORMAL)
        launch_button.config(state=tk.NORMAL)

def choose_directory():
    directory = filedialog.askdirectory()
    selected_option = selected_script.get()
    
    selected_file_label.config(text=directory)
    directory_var.set(directory)

'''def on_json_file_selected(selected_file):
    with open(selected_file) as file:
        data = json.load(file)
        tape_ids = list(set(entry["Tape_ID"] for entry in data))
        tape_id_dropdown['menu'].delete(0, 'end')
        for tape_id in tape_ids:
            tape_id_dropdown['menu'].add_command(label=tape_id, command=tk._setit(selected_tape_id, tape_id))
        tape_id_dropdown.config(state=tk.NORMAL)'''

def select_file():
    selected_option = selected_script.get()
    filetypes = []
    
    if selected_option in ["Scanner", "Splitter", "Audio Normalizer", "Identifier", "Metatagger", "Archiver", "Vid2Social", "SocialBot"]:
        filetypes = (
            ('Video Files', '*.mp4;*.avi;*.mkv;*.m4v'),
            ('All Files', '*.*')
        )
    elif selected_option in ["Video Editor", "Data Editor"]:
        filetypes = (
            ('JSON Files', '*.json'),
            ('All Files', '*.*')
        )
    else:
        filename_button.config(state=tk.DISABLED)
        launch_button.config(state=tk.DISABLED)
    filepath = filedialog.askopenfilename(filetypes=filetypes)
    selected_file_label.config(text=os.path.basename(filepath))
    filename_var.set(filepath)

def stop_execution():
    window.destroy()
    os._exit(0)

def show_about_dialog():
    # Create a top-level window for the about dialog
    about_window = tk.Toplevel()
    about_window.title("About VideoTools")
    
    # About dialog text
    about_text = """
    VideoTools - Version: 20230628
    Developer: Moe Fwacky
    Repository: https://github.com/MoeFwacky/videotools
    VideoTools is released under the GNU General Public License (GPL).
    
    VideoTools is a multifunctional script designed for video analysis, editing, and social sharing. 
    It provides various tools for processing video files, extracting metadata, and performing automated video editing functions."""

    function_text= """
    Scanner - The Scanner tool analyzes video files to gather audio levels and frame brightness data for further analysis and processing.
    Splitter - The Splitter tool analyzes the Scanner's saved JSON data to determine split points, primarily for extracting commercial files from recordings of broadcast TV.
    Identifier - The Identifier tool utilizes AI algorithms to analyze video clips, extracting audio transcripts, on-screen text, and other available data to generate comprehensive metadata.
    Archiver - The Archiver tool facilitates the uploading of video files to the Internet Archive, utilizing available metadata for the upload process.
    Video Editor - The Video Editor tool enables automated video editing functions based on a JSON file, providing a convenient way to perform advanced editing operations.
    Metatagger - The Metatagger tool allows users to add and modify metadata for video files, enhancing their organization and accessibility.
    Vid2Social - The Vid2Social tool automates social sharing by randomly uploading video clips to various social media platforms at regular intervals.
    SocialBot - The SocialBot tool enables users to issue commands to obtain specific video clips on demand, streamlining the retrieval process."""

    footer_text="""
    For more information, support, or to contribute, please visit the project repository at the provided link or by clicking the button below.

    Thank you for using VideoTools!
    """
    
    # Create a label to display the about text
    header_label = tk.Label(about_window, text=about_text)
    header_label.pack(padx=10, pady=5)    
    description_label = tk.Label(about_window, text=function_text, anchor='w', justify='left')
    description_label.pack(padx=10, pady=5)    
    footer_label = tk.Label(about_window, text=footer_text)
    footer_label.pack(padx=10, pady=15)

    # Create a button to close the dialog
    close_button = tk.Button(about_window, text="Close", command=about_window.destroy)
    close_button.pack(side="right",pady=10)
    
    # Create a button to open the repository link
    button = tk.Button(about_window, text="Visit Repository", command=lambda: webbrowser.open('https://github.com/MoeFwacky/videotools'))
    button.pack(side="right",pady=5)

def launch_script(selected_script,output_text,progress_widget=None,action_label=None):
    print("Launching",selected_script)
    # Get the selected filename or directory
    global thread
    global stop_event 
    stop_event = threading.Event()
    selected_filename = filename_var.get() if filename_var.get() else None
    selected_directory = directory_var.get() if directory_var.get() else None

    # Get the arguments from the checkboxes
    #print("Getting arguments")
    selected_arguments = []
    for checkbox in checkboxes:
        if checkbox.get() == 1:
            selected_arguments.append(checkbox.cget('text'))
    if selected_script != "Data Editor":
        # Create a progress variable to store the progress value
        progress_var = tk.IntVar()
        # Create a label to display the progress status text
        progress_label = tk.Label(window, text=" ")
        progress_label.grid(row=4, column=9, columnspan=12, sticky=tk.W)
        progress_widget = ttk.Progressbar(window, variable=progress_var, orient=tk.HORIZONTAL, length=500, mode='determinate')
        progress_widget.grid(row=4, column=0, columnspan=18, sticky=tk.SW)
    else:
        progress_label = None
    action_label.config(text="Starting "+selected_script)
    #print("Redirecting console output to the GUI text box...")
    redirector = redirect_console_output(output_text,progress_widget=progress_widget,
    progress_label=progress_label,action_label=action_label)

    # Redirect the standard output to the text box
    #sys.stdout = TextRedirector(output_text)
    #sys.stderr = TextRedirector(output_text)  # Redirect stderr as well

    '''if selected_filename != None:
        print(selected_filename)
    elif selected_directory != None:
        print(selected_directory)'''
    # Get the selected checkboxes
    selected_checkboxes = {argument: var.get() for argument, var in checkboxes}
    #print(selected_checkboxes)
    # Get the selected script
    if selected_script == "Scanner":
        try:
            thread = threading.Thread(target=launch_scanner,args=(selected_filename,selected_directory,progress_label,progress_widget))
            thread.start()
        except Exception as e:
            print(e)
    elif selected_script == "Splitter":
        try:
            thread = threading.Thread(target=launch_splitter,args=(selected_filename,selected_directory,progress_label,progress_widget))
            thread.start()
        except Exception as e:
            print(e)
    elif selected_script == "Audio Normalizer":
        try:
            thread = threading.Thread(target=launch_audio_normalizer,args=(selected_filename,selected_directory,progress_label,progress_widget))
            thread.start()
        except Exception as e:
            print(e)
    elif selected_script == "Video Editor":
        try:
            thread = threading.Thread(target=launch_editor,args=(selected_filename,selected_directory))
            thread.start()
        except Exception as e:
            print(e)
    elif selected_script == "Identifier":
        try:
            thread = threading.Thread(target=launch_identifier,args=(selected_filename,selected_directory,progress_label,progress_widget,action_label))
            thread.start()
        except Exception as e:
            print(e)
    elif selected_script == "Metatagger":
        try:
            thread = threading.Thread(target=launch_tagger,args=(selected_filename,selected_directory))
            thread.start()
        except Exception as e:
            print(e)
    elif selected_script == "Archiver":
        try:
            thread = threading.Thread(target=launch_archiver,args=(selected_filename,selected_directory))
            thread.start()
        except Exception as e:
            print(e)
    elif selected_script == "Vid2Social":
        try:
            thread = threading.Thread(target=launch_vid2social,args=(selected_filename,selected_directory))
            thread.start()
        except Exception as e:
            print(e)
    elif selected_script == "SocialBot":
        try:
            thread = threading.Thread(target=launch_socialbot,args=(selected_filename,selected_directory))
            thread.start()
        except Exception as e:
            print(e)
    # Restore the original stdout
    #sys.stdout = sys.__stdout__
    

if args.scanner != False:
    if args.filename != None:
        launch_scanner(file=args.filename)
    elif args.filepath != None:
        launch_scanner(file=args.filepath)
    elif args.directory != None:
        launch_scanner(directory=args.directory)
    else:
        launch_scanner()

if args.audio != False:
    if args.filename != None:
        launch_audio_normalizer(file=args.filename)
    elif args.filepath != None:
        launch_audio_normalizer(file=args.filepath)
    elif args.directory != None:
        launch_audio_normalizer(directory=args.directory)
    else:
        launch_audio_normalizer()

elif args.archive != False:
    if args.filename != None:
        launch_archiver(file=args.filename)
    elif args.filepath != None:
        launch_archiver(file=args.filepath)
    elif args.directory != None:
        launch_archiver(directory=args.directory)
    else:
        launch_archiver()
        
elif args.twitter != False or args.tumblr != False or args.mastodon != False or args.discord != False or args.facebook != False or args.bot != False:
    
    socials = {}
    socials["twitter"] = args.twitter
    socials["tumblr"] = args.tumblr
    socials["mastodon"] = args.mastodon
    socials["discord"] = args.discord
    socials["facebook"] = args.facebook
    persist = args.persist
    
    if args.bot == False:
        if args.filename != None:
            launch_vid2social(file=args.filename,socials=socials,persist=persist)
        elif args.filepath != None:
            launch_vid2social(file=args.filepath,socials=socials,persist=persist)
        elif args.directory != None:
            launch_vid2social(directory=args.directory,socials=socials,persist=persist)
        else:
            launch_vid2social(socials=socials,persist=persist)
    else:
        if args.filename != None:
            launch_socialbot(file=args.filename,socials=socials,persist=persist)
        elif args.filepath != None:
            launch_socialbot(file=args.filepath,socials=socials,persist=persist)
        elif args.directory != None:
            launch_socialbot(directory=args.directory,socials=socials,persist=persist)
        else:
            launch_socialbot(socials=socials,persist=persist)       

elif args.splitter != False:
    if args.filename != None:
        launch_splitter(file=os.path.join(os.getcwd(),args.filename))
    elif args.filepath != None:
        launch_splitter(file=args.filepath)
    elif args.directory != None:
        launch_splitter(directory=args.directory)
    else:
        launch_scanner()
elif args.editor != False:
    if args.filename != None:
        launch_editor(file=os.path.join(os.getcwd(),args.filename))
    elif args.filepath != None:
        launch_editor(file=args.filepath)
    elif args.directory != None:
        launch_editor(directory=args.directory)
    else:
        launch_editor()

elif args.tagger != False:
    if args.filename != None:
        launch_tagger(file=os.path.join(os.getcwd(),args.filename))
    elif args.filepath != None:
        launch_tagger(file=args.filepath)
    elif args.directory != None:
        launch_tagger(directory=args.directory)
    else:
        launch_tagger()
elif args.identify != False:
    if args.filename != None:
        launch_identifier(file=os.path.join(os.getcwd(),args.filename))
    elif args.filepath != None:
        launch_identifier(file=args.filepath)
    elif args.directory != None:
        launch_identifier(directory=args.directory)
    else:
        launch_tagger()
else:
    #run the gui
    gui = None 
    def create_new_entry():
        global current_index, tape_data

        # Get the information from the previous entry
        previous_entry = tape_data[current_index]
        tape_id = previous_entry["Tape_ID"]
        #segment_end = datetime.datetime.strptime(previous_entry["Segment End"], "%H:%M:%S").time()
        recording_date = previous_entry["Recording Date"]
        order_on_tape = previous_entry["Order on Tape"]
        location = previous_entry["Location"]

        # Filter the data list to include entries with the same tape ID
        tape_entries = [entry for entry in data if entry["Tape_ID"] == tape_id]

        # Determine the highest order on tape value
        max_order_on_tape = max(entry["Order on Tape"] for entry in tape_entries)

        # Find the highest ID number in the entire file
        max_id = max(entry.get("ID", 0) for entry in data)

        # Find the last entry for the tape ID
        last_entry = max(tape_entries, key=lambda entry: entry["Order on Tape"])

        # Extract the end time from the last entry
        segment_end = datetime.datetime.strptime(last_entry["Segment End"], "%H:%M:%S").time()

        # Calculate the new segment start time
        new_segment_string = (datetime.datetime.combine(datetime.date.today(), segment_end) + datetime.timedelta(seconds=1)).time().strftime("%H:%M:%S")
        new_segment_split = new_segment_string.split(':')
        new_segment_hours = new_segment_split[0][1:] if new_segment_split[0].startswith("0") else new_segment_split[0]
        
        new_segment_start = new_segment_hours+':'+new_segment_split[1]+':'+new_segment_split[2]
        
        # Create the new entry
        new_entry = {
            "ID": max_id + 1,
            "Location": location,
            "Network/Station": "",
            "Order on Tape": max_order_on_tape + 1,
            "Programs": "",
            "Recording Date": recording_date,
            "Segment End": new_segment_start,
            "Segment Start": new_segment_start,
            "Tape_ID": tape_id,
        }

        # Append the new entry to the data list
        data.append(new_entry)

        # Sort the data list based on tape ID and segment start time
        data.sort(key=lambda entry: (entry["Tape_ID"], entry["Segment Start"]))

        # Update the tape_data list
        tape_data = get_ordered_data(tape_id)

        # Find the index of the new entry in the tape_data list
        current_index = tape_data.index(new_entry)

        # Update the current index and show the new entry details
        show_item_details(tape_data[current_index], tape_data, current_index)

    def on_tape_id_selected(selected_tape_id):
        global current_index, tape_data

        if selected_tape_id:
            tape_data = get_ordered_data(selected_tape_id)
            if tape_data:
                current_index = 0  # Reset the index to start from the first item
                show_item_details(tape_data[current_index], tape_data, current_index)
            else:
                create_new_tape(selected_tape_id)  # Pass the custom value as the tape_id argument
        else:
            create_new_tape(selected_tape_id)  # Pass the custom value as the tape_id argument

    def to_previous_segment():
        global current_index, tape_data
        if current_index > 0:
            current_index -= 1  # Decrement the index to move to the previous item
            show_item_details(tape_data[current_index], tape_data, current_index)

    def to_next_segment():
        global current_index, tape_data
        if current_index < len(tape_data) - 1:
            current_index += 1  # Increment the index to move to the next item
            show_item_details(tape_data[current_index], tape_data, current_index)

    def get_ordered_data(tape_id=None):
        ordered_data = sorted(data, key=lambda item: (item.get("Tape_ID"), item.get("Segment Start")))
        if tape_id is not None:
            ordered_data = [item for item in ordered_data if item.get("Tape_ID") == tape_id]
        return ordered_data
            
    def show_item_details(item, data, index):
        global gui, entry_widget_mapping
        launchloop = False
        # Destroy the existing window if it exists
        if gui is None:
            gui = tk.Toplevel()
            gui.title("Video JSON Keeper")
            gui.iconbitmap("tv.ico")
            launchloop = True

            # Bind the window close event to set `gui` to None
            gui.protocol("WM_DELETE_WINDOW", lambda: on_window_close())

        # Function to handle window close event
        def on_window_close():
            global gui
            gui.destroy()
            gui = None

        if not gui:
            return

        if gui.winfo_exists():
            for widget in gui.grid_slaves():
                widget.destroy()
        
        # Clear existing widgets
        for widget in gui.grid_slaves():
            widget.grid_forget()

        # Create labels and editable widgets for each key-value pair
        keys = list(item.keys())
        entry_widgets = []

        # Create labels and editable widgets for each key-value pair
        keys = list(item.keys())
        entry_widgets = []
        entry_widget_mapping = []

        for i, key in enumerate(reversed(keys)):
            label = tk.Label(gui, text=key)
            label.grid(row=i, column=0, sticky="e")

            value = tk.StringVar(value=item[key])
            if key == "ID":
                entry = tk.Entry(gui, textvariable=value, state="disabled")
            else:
                entry = tk.Entry(gui, textvariable=value, state="normal")
            entry.grid(row=i, column=1, padx=10, pady=5, sticky="w")
            entry_widgets.append(entry)
            entry_widget_mapping.append((entry, key))  # Store the mapping between entry widget and key

        # Create buttons to navigate back and forth
        prev_button = tk.Button(gui, text="Previous Segment", command=to_previous_segment)
        prev_button.grid(row=len(keys), column=0, padx=10, pady=10, sticky="nsew")

        next_button = tk.Button(gui, text="Next Segment", command=to_next_segment)
        next_button.grid(row=len(keys), column=1, padx=10, pady=10, sticky="nsew")

        new_entry_button = tk.Button(gui, text="New Entry", command=create_new_entry)
        new_entry_button.grid(row=len(keys) + 1, column=0, padx=10, pady=10, sticky="nsew")

        new_tape_button = tk.Button(gui, text="New Tape", command=create_new_tape)
        new_tape_button.grid(row=len(keys) + 1, column=1, padx=10, pady=10, sticky="nsew")

        # Create a video playback widget and frame tracking widget
        '''video_widget = tk.Label(gui, text="Video Playback Widget")
        video_widget.grid(row=len(keys) + 2, columnspan=2, padx=10, pady=10)

        frame_widget = tk.Label(gui, text="Frame Tracking Widget")
        frame_widget.grid(row=len(keys) + 3, columnspan=2, padx=10, pady=10)'''

        save_button = tk.Button(gui, text="Save Changes to File", command=save_to_json)
        save_button.grid(row=len(keys) + 4, column=0, columnspan=2, padx=30, pady=10, sticky="nsew")

        # Update the entry widgets with current item values
        for i, key in enumerate(reversed(keys)):
            entry = entry_widgets[i]
            entry.delete(0, tk.END)
            entry.insert(tk.END, item[key])

        # Update the current index
        global current_index
        current_index = index

        # Run the Tkinter event loop for the window
        if launchloop:
            gui.mainloop()

    def create_new_tape(tape_id=None):
        global current_index, tape_data
        random_string = "".join(random.choice(string.ascii_letters) for _ in range(3))
        if tape_id == None or tape_id == "":
            tape_id = random_string.upper() + "-001"  # Blank Tape ID
        segment_start = "0:00:00"  # Initial segment start value
        order_on_tape = 1  # Initial order on tape value

        # Check if the tape ID already exists
        tape_ids = [entry["Tape_ID"] for entry in data]
        while tape_id in tape_ids:
            # Extract the prefix and highest number from existing tape IDs
            prefix = tape_id[:-4]  # Remove the last four characters ("-001")
            existing_numbers = [int(tid[-3:]) for tid in tape_ids if tid.startswith(prefix)]
            highest_number = max(existing_numbers) if existing_numbers else 0

            # Generate the new tape ID with the next number
            next_number = highest_number + 1
            tape_id = f"{prefix}-{next_number:03d}"

        # Find the highest ID number in the entire file
        max_id = max(entry.get("ID", 0) for entry in data)

        # Create the new tape entry
        new_entry = {
            "ID": max_id + 1,
            "Location": "",
            "Network/Station": "",
            "Order on Tape": order_on_tape,
            "Programs": "",
            "Recording Date": "",
            "Segment End": segment_start,
            "Segment Start": segment_start,
            "Tape_ID": tape_id
        }

        # Append the new entry to the data list
        data.append(new_entry)

        # Sort the data list based on tape ID and segment start time
        data.sort(key=lambda entry: (entry["Tape_ID"], entry["Segment Start"]))

        # Update the tape_data list
        tape_data = get_ordered_data(tape_id)

        # Find the index of the new entry in the tape_data list
        current_index = tape_data.index(new_entry)

        # Update the current index and show the new entry details
        show_item_details(tape_data[current_index], tape_data, current_index)
        
    def save_to_json():
        global tape_data, current_index, data

        # Update the data list with the modified values from the entry fields
        new_entry = {}
        for widget, key in reversed(entry_widget_mapping):
            entry_value = widget.get().strip()
            if key in ["ID", "Order on Tape"]:
                try:
                    entry_value = int(entry_value)  # Convert to integer if it's ID or Order on Tape
                except ValueError:
                    messagebox.showerror("Validation Error", f"Order on Tape value must be an integer: {entry_value}")
                    return
            new_entry[key] = entry_value

        validation_errors = validate_data(new_entry)

        if validation_errors:
            # Display validation errors and prevent saving
            messagebox.showerror("Validation Error", "\n".join(validation_errors))
            return

        # Check if a matching ID number already exists
        matching_entry = next((entry for entry in data if entry["ID"] == new_entry["ID"]), None)
        if matching_entry:
            # Update the existing entry
            matching_entry.update(new_entry)
        else:
            # Append the new entry to the data list
            data.append(new_entry)

        # Save the modified data to the JSON file
        with open(json_file, "w") as json_data:
            json.dump(data, json_data, indent=4)

        # Reload the tape_data from the file
        tape_data = [new_entry]

        # Find the index of the current entry in the tape_data list
        current_index = tape_data.index(new_entry)

        # Update the current index and show the new entry details
        show_item_details(tape_data[current_index], tape_data, current_index)

        messagebox.showinfo("Save Successful", "Data saved successfully.")

    def validate_data(entry_data):
        validation_errors = []
        tape_id = entry_data["Tape_ID"]
        segment_start = entry_data["Segment Start"]
        segment_end = entry_data["Segment End"]
        order_on_tape = str(entry_data["Order on Tape"])

        # Check for overlaps in segment start and end times
        for entry in data:
            if entry["Tape_ID"] == tape_id and entry != entry_data:
                if entry["Segment End"] > segment_start and entry["Segment Start"] < segment_end:
                    validation_errors.append("Overlap in segment times with Tape ID: {}".format(tape_id))
                    break

        # Validate time format (H:MM:SS)
        time_pattern = r"^(?:[0-9]|0[0-9]|1[0-9]|2[0-3]):(?:[0-9]|[0-5][0-9]):(?:[0-9]|[0-5][0-9])$"
        if not re.match(time_pattern, segment_start):
            validation_errors.append("Invalid time format for Segment Start: {}".format(segment_start))
        if not re.match(time_pattern, segment_end):
            validation_errors.append("Invalid time format for Segment End: {}".format(segment_end))

        # Validate date format (YYYY-MM-DD)
        date_pattern = r"^\d{4}-\d{2}-\d{2}$"
        if not re.match(date_pattern, entry_data["Recording Date"]):
            validation_errors.append("Invalid date format for Recording Date: {}".format(entry_data["Recording Date"]))

        # Validate Order on Tape as integer
        try:
            int(order_on_tape)
        except:
            validation_errors.append("Order on Tape must be an integer: {}".format(order_on_tape))
 
        # Check for duplicates in order on tape
        for entry in data:
            if entry["Tape_ID"] == tape_id and entry["ID"] != entry_data["ID"]:
                if str(entry["Order on Tape"]) == order_on_tape:
                    print(entry)
                    print(entry_data)
                    validation_errors.append("Duplicate Order on Tape value with Tape ID: {}".format(tape_id))
                    break
                

        return validation_errors


    def display_validation_errors(validation_errors):
        # Clear existing error labels
        for widget in gui.grid_slaves():
            if isinstance(widget, tk.Label) and widget.cget("foreground") == "red":
                widget.destroy()

        # Display validation errors in the GUI
        error_row = len(data) + 5
        for error in validation_errors:
            error_label = tk.Label(gui, text=error, foreground="red")
            error_label.grid(row=error_row, column=0, columnspan=2, padx=10, pady=5, sticky="w")
            error_row += 1


    def on_selection_changed():
        selection = selection_var.get()
        if selection == "file":
            filename_button.grid(row=0, column=4, columnspan=4, sticky=tk.SW, pady=1)
            directory_button.grid_forget()
        elif selection == "directory":
            directory_button.grid(row=0, column=4, columnspan=4, sticky=tk.SW, pady=1)
            filename_button.grid_forget()

    print("Launching GUI")
    
    window = tk.Tk()
    window.title("Video Tools")
    window.geometry("1300x450")
    menu_bar = tk.Menu(window)
    help_menu = tk.Menu(menu_bar, tearoff=0)
    menu_bar.add_cascade(label="Help", menu=help_menu)
    menu_bar.configure(background="lightgrey")
    help_menu.add_command(label="About", command=show_about_dialog)
    window.config(menu=menu_bar)
    window.iconbitmap("tv.ico")
    
    for i in range(20):
        window.grid_rowconfigure(i,weight=1,uniform="equal")
        window.grid_columnconfigure(i,weight=1,uniform="equal")

    # Create the text box for console output
    #text_box = tk.Text(window,bg="black",fg="lime")
    #text_box.pack()

    # Creating a dictionary of options for the dropdown menu
    script_to_run = {
        "SELECT OPERATION": [],
        "Scanner": [],
        "Splitter": [],
        "Audio Normalizer": [],
        "Identifier": [],
        "Archiver": [],
        "Video Editor": [],
        "Metatagger": [],
        "Vid2Social": ["Facebook","Twitter","Tumblr","Mastodon","Discord","Persist"],
        "SocialBot": ["Facebook","Twitter","Tumblr","Mastodon","Discord","Persist"]
    }

    # Creating a variable to store the selected option
    selected_script = tk.StringVar()
    selected_script.trace('w', update_button_state)  # Call update_button_state when the selected_script changes
    
    # Create a label widget
    #label = tk.Label(window, text="Select Operation:")
    #label.grid(row=0, column=0, columnspan=2 sticky=tk.E)
    dropdown = ttk.OptionMenu(window, selected_script, *script_to_run.keys())
    dropdown.config(width=20)
    dropdown.grid(row=0, column=0, columnspan=2, sticky=tk.E)
    
    checkboxes = []
    selection_var = tk.StringVar(value="file")

    filename_var = tk.StringVar()
    filename_button = tk.Button(window, text="Browse", command=select_file)
    filename_button.grid(row=0, column=5, columnspan=4, sticky=tk.SW, pady=1)
    filename_button.config(state=tk.DISABLED)

    
    #selected_script.trace('w', on_selection_changed)
    radio_file = tk.Radiobutton(window, text="File", variable=selection_var, value="file", command=on_selection_changed)
    radio_file.grid(row=0, column=2, columnspan=2, sticky=tk.S, padx=5, pady=5)

    radio_directory = tk.Radiobutton(window, text="Directory", variable=selection_var, value="directory", command=on_selection_changed)
    radio_directory.grid(row=1, column=2, columnspan=2, sticky=tk.N, padx=5)

    directory_var = tk.StringVar()
    directory_button = tk.Button(window, text="Browse", command=choose_directory)
    directory_button.config(state=tk.DISABLED)

    #selected_script.trace("w", lambda *args: update_arguments(*args, selected_script=selected_script))

    selected_file_label = tk.Label(window)
    selected_file_label.grid(row=0, column=8, columnspan=8, sticky=tk.W)

    action_label = tk.Label(window, text="")
    action_label.grid(row=3, column=0, columnspan=20)

    stop_button = tk.Button(window, text="ABORT!", command=stop_execution)
    stop_button.grid(row=2, column=18, columnspan=2, padx=10, sticky=tk.N)  

    launch_button = tk.Button(window, text="Start", command=lambda: launch_script(selected_script.get(),output_text, action_label=action_label))
    launch_button.grid(row=0, column=18, columnspan=2, padx=10, sticky=tk.NSEW)
    launch_button.config(state=tk.DISABLED)

    json_file_label = tk.Label(window, text=json_file)
    json_file_label.grid(row=1, column=10, columnspan=3)
    
    # Create a label for the Tape ID dropdown
    tape_id_label = tk.Label(window, text="Tape ID:")
    tape_id_label.grid(row=1, column=13, sticky="e")
    #tape_id_label.config(state=tk.DISABLED)

    # Load the JSON data from the file
    with open(json_file, "r") as json_data:
        data = json.load(json_data)

    tape_ids = list(set(entry["Tape_ID"] for entry in data))
    tape_ids = sorted(tape_ids, key=lambda x: int(''.join(filter(str.isdigit, x))))
    
    current_index = 0

    # Create an editable dropdown for Tape ID selection
    selected_tape_id = tk.StringVar()
    tape_id_dropdown = ttk.Combobox(window, textvariable=selected_tape_id, state="normal")
    tape_id_dropdown["values"] = tape_ids
    tape_id_dropdown.grid(row=1, column=14, columnspan=3, sticky="w")
    #tape_id_dropdown.config(state=tk.DISABLED)

    # Create a button to launch the JSON editor
    launch_editor_button = tk.Button(window, text="Tape Data Editor", command=lambda: on_tape_id_selected(selected_tape_id.get()))
    launch_editor_button.grid(row=1, column=18, columnspan=2, sticky=tk.NSEW)
    #launch_editor_button.config(state=tk.DISABLED)
    
    # Create a text box to display the output
    output_text = scrolledtext.ScrolledText(window, background="black", foreground="lime", height=15)
    output_text.grid(row=6, column=0, columnspan=20, rowspan=10, sticky=tk.NSEW)
    window.grid_propagate(0)

    def on_window_close():
        stop_execution()
        window.destroy()
    window.protocol("WM_DELETE_WINDOW", on_window_close)
    # Run the GUI event loop
    window.mainloop()
    sys.stdout = sys.__stdout__