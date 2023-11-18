import argparse
import configparser
import cv2
import datetime
import io
import json
import metatagger
import numpy as np
import os
import random
import re
import string
import sys
import threading
import time
import tkinter as tk
#import tqdm
import vlc
import webbrowser
from collections import defaultdict
from tkinter import filedialog
from tkinter import messagebox
from tkinter import scrolledtext
from tkinter import ttk

scriptPath = os.path.realpath(os.path.dirname(__file__))
tv_ico = os.path.join(scriptPath,'tv.ico')
config = configparser.ConfigParser()
config.read(os.path.join(scriptPath,'config.ini'))
json_file = config['directories']['json file']

class VideoPlayer(tk.Frame):
    def __init__(self, master=None, media_path=None):
        super().__init__(master)
        self.media_path = media_path

        self.instance = vlc.Instance("--no-xlib --quiet")
        self.player = self.instance.media_player_new()
        self.media = self.instance.media_new(media_path)
        self.player.set_media(self.media)

        self.video_canvas = tk.Canvas(self)
        self.video_canvas.pack()

        self.player.play()
        self.player.set_hwnd(self.video_canvas.winfo_id())

        # Create a progress bar and label
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self, variable=self.progress_var, maximum=100, length=375)
        self.progress_bar.pack(fill=tk.Y, padx=10)

        # Bind the click event to seek_to_position method
        self.progress_bar.bind("<Button-1>", self.seek_to_position)

        # Start checking the video state
        self.update_progress()

    def update_progress(self):
        state = self.player.get_state()
        if state == vlc.State.Playing or state == vlc.State.Paused:
            total_time = self.player.get_length() / 1000  # Total time in seconds
            if total_time > 0:
                current_time = self.player.get_time() / 1000  # Current time in seconds
                self.progress_var.set((current_time / total_time) * 100)

        if state == vlc.State.Ended:
            self.player.stop()
            self.player.set_time(0)
            self.player.play()

        self.after(100, self.update_progress)

    def load_media(self, new_media_path):
        # Load a new media source
        new_media = self.instance.media_new(new_media_path)
        self.player.set_media(new_media)
        self.player.play()  # Start playing the new video

    def seek_to_position(self, event):
        # Get the position where the click occurred
        click_position = event.x / self.progress_bar.winfo_width()

        # Set the player's position to the target time
        total_time = self.player.get_length() / 1000  # Total time in seconds
        target_time = total_time * click_position
        self.player.set_time(int(target_time * 1000))

    def play(self):
        self.player.play()

    def pause(self):
        self.player.pause()

    def stop(self):
        self.player.stop()

    def release(self):
        self.player.stop()
        self.player.release()

    def step_backward(self):
        fps = self.player.get_fps()  # Get the frames per second of the video
        current_time = self.player.get_time()  # Get the current playback time in milliseconds
        frame_duration_ms = int(1000 / fps)  # Duration of each frame in milliseconds
        target_time = max(current_time - frame_duration_ms, 0)  # Move back one frame (in milliseconds)
        self.player.set_time(target_time)  # Seek to the new time
        self.update_progress()

    def step_forward(self):
        fps = self.player.get_fps()  # Get the frames per second of the video
        current_time = self.player.get_time()  # Get the current playback time in milliseconds
        frame_duration_ms = int(1000 / fps)  # Duration of each frame in milliseconds
        target_time = min(current_time + frame_duration_ms, self.media.get_duration())  # Move forward one frame (in milliseconds)
        self.player.set_time(target_time)  # Seek to the new time
        self.update_progress()

    def seek_to_frame(self, frame_number):
        fps = self.media.get_fps()
        target_time = int((frame_number / fps) * 1000)
        self.player.set_time(target_time)
        self.update_progress()

    def go_to_first_frame(self):
        if self.player.is_playing():
            self.player.pause()
        self.player.set_position(0.0)
        self.update_progress()

    def go_to_last_frame(self):
        if self.player.is_playing():
            self.player.pause()
        duration_ms = self.player.get_length()
        frame_rate = self.player.get_fps()
        total_frames = int(duration_ms * frame_rate / 1000)
        last_frame_index = total_frames - 1
        self.player.set_time(int((last_frame_index / frame_rate) * 1000))
        self.update_progress()

    def go_forward_x_percent(self,x=1):
        duration_ms = self.player.get_length()
        step_ms = duration_ms // 100  # 1% of the video duration in milliseconds
        current_position_ms = self.player.get_time()
        new_position_ms = current_position_ms + round(step_ms*x)
        if new_position_ms <= duration_ms:
            self.player.set_time(new_position_ms)
        self.update_progress()

    def go_backward_x_percent(self,x=1):
        duration_ms = self.player.get_length()
        step_ms = duration_ms // 100  # 1% of the video duration in milliseconds
        current_position_ms = self.player.get_time()
        new_position_ms = current_position_ms - round(step_ms*x)
        if new_position_ms >= 0:
            self.player.set_time(new_position_ms)
        self.update_progress()

    def set_volume(self, volume):
        self.player.audio_set_volume(volume)

# Create a custom TextRedirector class to redirect console output to the text box
class TextRedirector(io.TextIOBase):
    def __init__(self, text_widget, max_lines=500):
        self.text_widget = text_widget
        self.max_lines = max_lines
        #self.progress_widget = progress_widget
        #self.progress_label = progress_label
        #self.action_label = action_label
        
        self.selected_script_label = tk.Label(window, text="Select an Operation to Start", font=("Helvetica", 14, "bold"))
        self.selected_script_label.grid(row=0, column=0, columnspan=9, sticky=tk.W)   

        self.description_label = tk.Label(window, text="To begin, select an operation from the Operations Menu", font=("Helvetica", 12, "italic"))
        self.description_label.grid(row=1, column=0, columnspan=15, sticky=tk.W)
        
        self.progress_label_var = tk.StringVar()
        self.progress_label_var.set('')
        self.progress_label = tk.Label(window, text='')
        self.progress_label.grid(row=12, column=11, columnspan=8, sticky=tk.W)
        
        self.progress_var = tk.IntVar()
        self.progress_widget = ttk.Progressbar(window, variable=self.progress_var, orient=tk.HORIZONTAL, length=500, mode='determinate')
        self.progress_widget.grid(row=12, column=0, columnspan=18, sticky=tk.SW)
        
        self.label_label = tk.Label(window, text="File or Directory:", font=("TkDefaultFont", 10, "bold"))
        self.label_label.grid(row=2, column=0, columnspan=2, sticky=tk.W)

        self.selected_file_label = tk.Label(window, text="Use the File menu to choose a file or directory to process")
        self.selected_file_label.grid(row=2, column=2, columnspan=15, sticky=tk.W)
        
        self.json_file_selection = tk.StringVar()
        self.json_file_selection.set('')
        
        self.json_file_label_var = tk.StringVar()
        self.json_file_label_var.set('')
        
        self.json_file_label = tk.Label(window, textvariable=self.json_file_label_var, font=("TkDefaultFont", 10, "bold"))
        self.json_file_label.grid(row=3, column=0, columnspan=2, sticky=tk.W)

        self.json_file_entry = tk.Label(window, textvariable=self.json_file_selection, state=tk.DISABLED)
        self.json_file_entry.grid(row=3, column=2, columnspan=5, sticky=tk.W)

        self.action_label = tk.Label(window, text="", font=("TkDefaultFont", 12, "bold"))
        self.action_label.grid(row=11, column=0, columnspan=20)

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
                self.progress_var.set(self.progress_widget['maximum'])
                self.progress_widget.update()
                return
            self.action_label.config(text=s.strip().replace("MoviePy - ","").replace("[ACTION] ",""))
            return
        elif s.lstrip().startswith("uploading "):
            self.progress_widget['maximum'] = 100
            self.update_progress_ia(s)
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
        self.progress_var.set(float(progress))
        self.progress_widget.update()

    def update_progress_ia(self, output):
        # Extract the progress information from the output
        try:
            parts = output.split(": ")
            progress_info = parts[1].strip()
            progress = progress_info.split('%')[0]
            progress_data = progress + '% ' + parts[1].split('|')[2]
            #progress_data = progress_data.replace(' [',', ').replace(']','')
            # Update the progress widget
            self.progress_label.config(text=str(progress_data))
            self.progress_widget['value'] = float(progress)
            self.progress_var.set(int(progress))
            self.progress_widget.update()
        except Exception as e:
            print("[ERROR] "+str(e))

    def update_progress_mp(self, output):
        # Extract the progress information from the output
        #print(output)
        if "chunk:" in output:
            parts = output.split("chunk:")
        elif "t:" in output:
            parts = output.split("t:")
        progress_info = parts[1].strip()
        progress = progress_info.split('%')[0]
        progress_data = progress + '% ' + parts[1].split('|')[2]
        progress_data = progress_data.replace(' [',', ').replace(', now=None]','')
        # Update the progress widget
        #self.progress_widget['value'] = float(progress)
        self.progress_var.set(int(progress))
        self.progress_widget.update()
        self.progress_label.config(text=str(progress_data))

    def flush(self):
        pass  # No need to flush in this case

def banner():
    print(":::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::")
    print(":::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::")
    print(":: dBP dP  dBP dBP.dBBBBP       dBBBBBBP dBBBBP dBBBBP dBP .dBBBB::")
    print("::                BP                    dBP.BP dBP.BP      BP    ::")
    print("::dB .BP dBBBBBP  `BBBBb         dBP   dBP.BP dBP.BP dBP   `BBBBb::")
    print("::BB.BP dBP dBP      dBP        dBP   dBP.BP dBP.BP dBP       dBP::")
    print("::BBBP dBP dBP  dBBBBP'        dBP   dBBBBP dBBBBP dBBBBPdBBBBP' ::")
    print(":::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::")

parser = argparse.ArgumentParser(description="VHS Tools")
parser.add_argument('-b', '--bot', action='store_true', help="Bot that listens for submissions of video clip information")
parser.add_argument('-a', '--archive', action='store_true', help="Upload indicated file(s) to the internet archive. Use of this argument also requires the use of either the --clip or --video argument")
parser.add_argument('-v', '--video', action='store_true', help="For use with --archive, indicates the file being uploaded is a full video")
parser.add_argument('-c', '--clip', action='store_true', help="For use with --archive, indicates the file being uploaded is a clip from a full video")
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

def redirect_console_output(text_widget):
    #print("Create an instance of TextRedirector and Progress Bar Redirector")
    stdout_redirector = TextRedirector(text_widget)
    #print("Replace sys.stdout and sys.stderr with redirector") 
    try:
        sys.stdout = stdout_redirector
        sys.stderr = stdout_redirector
    except Exception as e:
        print("ERROR:",e)
    #tqdm_out = tqdm.tqdm(file=progress_bar_redirector, ncols=80)
    progress_bar_redirector = None
    return stdout_redirector

def update_progress_bar():
    progress_var.set(progress)
    progress_label.config(text=f"Progress: {progress}%")

def launch_scanner(file=None,directory=None,redirector=None):
    import videoscanner
    
    print(": ___  __              ___     __   __                  ___  __  ::")
    print(":|__  |__)  /\   |\/| |__     /__` /  `  /\  |\ | |\ | |__  |__) ::")
    print(":|    |  \ /~~\  |  | |___    .__/ \__, /~~\ | \| | \| |___ |  \ ::")
    print(":::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::")
    starting_time = datetime.datetime.now()
    if file != None:
        #print("PROCESSING", file)
        try:
            videoscanner.scanVideo(file,redirector=redirector)
        except Exception as e:
            print(e)
            videoscanner.scanVideo(file,redirector=redirector)
    elif directory != None:
        dirContents = os.scandir(args.directory)
        dirList = []
        extensions = ['mp4','avi','m4v','mkv']
        total_files = 0
        for entry in dirContents:
            if entry.name[-3:] in extensions:
                print("Processing file {}/{}: {}".format(current_file, total_files, entry.name))
                total_files += 1
                videoscanner.scanVideo(os.path.join(directory,entry.name),directory,redirector=redirector)
    else:
        videoscanner.scanVideo(redirector=redirector)
    ending_time = datetime.datetime.now()
    elapsed_time = ending_time - starting_time
    time_minutes = elapsed_time.total_seconds() // 60
    time_seconds = elapsed_time.total_seconds() % 60
    if redirector != None:
        redirector.progress_widget['value'] = progress_widget['maximum']
        redirector.progress_var.set(progress_widget['maximum'])
        redirector.action_label.config(text="")
        redirector.progress_label.config(text=f"Complete in {int(time_minutes):d} minutes, {int(time_seconds):d} seconds")
        messagebox.showinfo("Video Scan Complete", f"Video Scan Complete in {int(time_minutes):d} minutes, {int(time_seconds):d} seconds",icon=messagebox.INFO)
    else: 
        print(f"Complete in {int(time_minutes):d} minutes, {int(time_seconds):d} seconds")
def launch_splitter(file=None,directory=None,redirector=None):
    import scenesplitter
    print(":::::::::  __                   __                        :::::::::")
    print("::::::::: (_   _  _  ._   _    (_  ._  | o _|_ _|_  _  ._ :::::::::")
    print("::::::::: __) (_ (/_ | | (/_   __) |_) | |  |_  |_ (/_ |  :::::::::")
    print(":::::::::                          |                      :::::::::")
    print(":::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::")
    starting_time = datetime.datetime.now()
    if file != None:
        #print("PROCESSING", file)
        scenesplitter.processVideo(file,os.path.dirname(file),redirector)
    elif directory != None:
        dirContents = os.scandir(directory)
        dirList = []
        extensions = ['mp4','avi','m4v','mkv']
        for entry in dirContents:
            if entry.name[-3:] in extensions:
                print("PROCESSING", entry.name, "in", directory)
                scenesplitter.processVideo(entry.name, directory, redirector)
    else:
        scenesplitter.processVideo(redirector)
    ending_time = datetime.datetime.now()
    elapsed_time = ending_time - starting_time
    time_minutes = elapsed_time.total_seconds() // 60
    time_seconds = elapsed_time.total_seconds() % 60
    if redirector != None:
        redirector.progress_widget['value'] = progress_widget['maximum']
        redirector.progress_var.set(progress_widget['maximum'])
        redirector.action_label.config(text="")
        redirector.progress_label.config(text=f"Complete in {int(time_minutes):d} minutes, {int(time_seconds):d} seconds")
        messagebox.showinfo("Scene Split Complete", f"Scene Split Complete in {int(time_minutes):d} minutes, {int(time_seconds):d} seconds",icon=messagebox.INFO)
    else:
        print(f"Complete in {int(time_minutes):d} minutes, {int(time_seconds):d} seconds")
def launch_audio_normalizer(file=None,directory=None,redirector=None):
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
    if redirector != None:
        redirector.progress_widget['value'] = progress_widget['maximum']
        redirector.progress_var.set(progress_widget['maximum'])
        redirector.action_label.config(text="")
        redirector.progress_label.config(text=f"Complete in {int(time_minutes):d} minutes, {int(time_seconds):d} seconds")
        messagebox.showinfo("Audio Normalization Complete", f"Audio Normalized in {int(time_minutes):d} minutes, {int(time_seconds):d} seconds",icon=messagebox.INFO)
    else: 
        print(f"Complete in {int(time_minutes):d} minutes, {int(time_seconds):d} seconds")
def launch_identifier(file=None,directory=None,redirector=None,window=None):
    print("██ ██████  ███████ ███    ██ ████████ ██ ███████ ██ ███████ ██████ ")
    print("██ ██   ██ ██      ████   ██    ██    ██ ██      ██ ██      ██   ██")
    print("██ ██   ██ █████   ██ ██  ██    ██    ██ █████   ██ █████   ██████ ")
    print("██ ██   ██ ██      ██  ██ ██    ██    ██ ██      ██ ██      ██   ██")
    print("██ ██████  ███████ ██   ████    ██    ██ ██      ██ ███████ ██   ██")
    print(":::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::")
    starting_time = datetime.datetime.now()
    if redirector.action_label != None:
        redirector.action_label.config(text="")
    if redirector.progress_label != None:
        redirector.progress_label.config(text="")
    import analysis
    video_player = None
    if file != None:
        analysis.analyze_video(file,redirector,window)
    elif directory != None:
        dirContents = os.scandir(directory)
        dirList = []
        extensions = ['mp4','avi','m4v','mkv']

        for i, entry in enumerate(dirContents):
            if entry.name[-3:] in extensions:
                print(entry.name)
                file = os.path.join(directory, entry.name)
                analysis.analyze_video(os.path.join(directory, entry.name),redirector,window)
    else:
        dirContents = os.scandir(os.getcwd())
        dirList = []
        extensions = ['mp4','avi','m4v','mkv']
        for entry in dirContents:
            if entry.name[-3:] in extensions:
                print(entry.name)
                analysis.analyze_video(os.path.join(os.getcwd(), entry.name),redirector)
    ending_time = datetime.datetime.now()
    elapsed_time = ending_time - starting_time
    time_minutes = elapsed_time.total_seconds() // 60
    time_seconds = elapsed_time.total_seconds() % 60
    if redirector != None:
        #redirector.progress_widget['value'] = redirector.progress_widget['maximum']
        #redirector.progress_var.set(redirector.progress_widget['maximum'])
        redirector.action_label.config(text="")
        redirector.progress_label.config(text=f"Complete in {int(time_minutes):d} minutes, {int(time_seconds):d} seconds")
        messagebox.showinfo("Clip Identification Complete", f"Clip Identification Complete in {int(time_minutes):d} minutes, {int(time_seconds):d} seconds",icon=messagebox.INFO)
    else: 
        print(f"Complete in {int(time_minutes):d} minutes, {int(time_seconds):d} seconds")
def launch_archiver(file=None,directory=None,redirector=None,is_video=False,is_clip=False,clip_json_file=None):
    import iauploader
    print("::::::: █████╗ ██████╗  ██████╗██╗  ██╗██╗██╗   ██╗███████╗::::::::")
    print(":::::::██╔══██╗██╔══██╗██╔════╝██║  ██║██║██║   ██║██╔════╝::::::::")
    print(":::::::███████║██████╔╝██║     ███████║██║██║   ██║█████╗  ::::::::")
    print(":::::::██╔══██║██╔══██╗██║     ██╔══██║██║╚██╗ ██╔╝██╔══╝  ::::::::")
    print(":::::::██║  ██║██║  ██║╚██████╗██║  ██║██║ ╚████╔╝ ███████╗::::::::")
    print(":::::::╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═══╝  ╚══════╝::::::::")
    print(":::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::")
    starting_time = datetime.datetime.now()
    if clip_json_file == "Use the File menu to open the corresponding clip data file":
        clip_json_file = None
    if args.video != False or args.clip != False or is_video != False or is_clip != False:
        if file != None:
            print("[ACTION] UPLOADING "+file+" to the Internet Archive")
            if args.video == True or is_video == True:
                status = iauploader.uploadToArchive([file])
            elif args.clip == True or is_clip == True:
                status = iauploader.uploadClipToArchive(file,clip_json_file)
        elif directory != None:
            dirContents = os.scandir(directory)
            videos = []
            extensions = ['mp4','avi','m4v','mkv']
            for entry in dirContents:
                if entry.name[-3:] in extensions:
                    print("[ACTION] UPLOADING "+entry.name+" to the Internet Archive")
                    if args.video == True or is_video == True:
                        status = iauploader.uploadToArchive([entry.name])
                    elif args.clip == True or is_clip == True:
                        status = iauploader.uploadClipToArchive(os.path.join(directory,entry.name),clip_json_file)
        else:
            if args.video == True or is_video == True:
                status = iauploader.uploadToArchive(None)
            elif args.clip == True or is_clip == True:
                status = iauploader.uploadClipToArchive(None)
    else:
        print("[ERROR] Video Type not Specified")
    ending_time = datetime.datetime.now()
    elapsed_time = ending_time - starting_time
    total_seconds = elapsed_time.total_seconds()
    time_hours = total_seconds // 3600
    time_minutes = (total_seconds % 3600) // 60
    time_seconds = total_seconds % 60
    if redirector != None:
        if status == None:
            redirector.action_label.config(text="")
            global clip_editor
            global current_index
            with open(clip_json_file, "r") as clip_data:
                clip_data = json.load(clip_data) 
            show_clip_details(clip_data[current_index], clip_data, current_index, os.path.dirname(clip_json_file))
            if time_hours < 1:
                redirector.progress_label.config(text=f"Complete in {int(time_minutes):d} minutes, {int(time_seconds):d} seconds")
                messagebox.showerror("Archive Complete", f"Internet Archive Upload Complete in {int(time_minutes):d} minutes, {int(time_seconds):d} seconds",icon=messagebox.INFO)
            else:
                redirector.progress_label.config(text=f"Complete in {int(time_hours):d} hours, {int(time_minutes):d} minutes, {int(time_seconds):d} seconds")
                messagebox.showerror("Archive Complete", f"Internet Archive Upload Complete in {int(time_hours):d} hours, {int(time_minutes):d} minutes, {int(time_seconds):d} seconds",icon=messagebox.INFO)
        else:
            messagebox.showerror("ERROR: "+status[0],status[1])
    else: 
        if time_hours < 1:
            print(f"Complete in {int(time_minutes):d} minutes, {int(time_seconds):d} seconds")
        else:
            print(f"Complete in {int(time_hours):d} hours, {int(time_minutes):d} minutes, {int(time_seconds):d} seconds")
            
def launch_youtuber(file=None,directory=None,redirector=None,is_video=False,is_clip=False,clip_json_file=None):
    print(":::::::::::::░░░░░░░░░░░░░░░░░░░▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄░░::::::::::::::")
    print(":::::::::::::██░░██░░░░░░░░░░░▄█░░░░░░████░░████████▄::::::::::::::")
    print(":::::::::::::██▄▄██░░░░░░░░░░░████░░██████░░█████████::::::::::::::")
    print(":::::::::::::▀████▀░████░█░░█░████░░█░██░█░▄▄░█░░▄▄██::::::::::::::")
    print(":::::::::::::░░██░░░█░░█░█▄▄█░████░░█░░░░█░▀▀░█░░▄▄██::::::::::::::")
    print(":::::::::::::░░██░░░████░████░▀███▄▄█▄▄▄▄█▄▄▄▄█▄▄▄▄█▀::::::::::::::")
    print(":::::::::::::░░░░░░░░░░░░░░░░░░░▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀░░::::::::::::::")
    print(":::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::")
    starting_time = datetime.datetime.now()
    if clip_json_file == "Use the File menu to open the corresponding clip data file":
        clip_json_file = None
    if args.video != False or args.clip != False or is_video != False or is_clip != False:
        if file != None:
            print("[ACTION] UPLOADING "+os.path.basename(file)+" to YouTube")
            if args.video == True or is_video == True:
                status = ytuploader.uploadToYouTube(file)
            elif args.clip == True or is_clip == True:
                status = ytuploader.uploadClipToYouTube(file,clip_json_file,redirector)
        elif directory != None:
            dirContents = os.scandir(directory)
            videos = []
            extensions = ['mp4','avi','m4v','mkv']
            for entry in dirContents:
                if entry.name[-3:] in extensions:
                    print("[ACTION] UPLOADING "+entry.name+" to YouTube")
                    if args.video == True or is_video == True:
                        status = ytuploader.uploadToYouTube(entry.name)
                    elif args.clip == True or is_clip == True:
                        status = ytuploader.uploadClipToYouTube(os.path.join(directory,entry.name,redirector),clip_json_file)
        else:
            if args.video == True or is_video == True:
                status = ytuploader.uploadToYouTube(None)
            elif args.clip == True or is_clip == True:
                status = ytuploader.uploadClipToYouTube(None)
    else:
        print("[ERROR] Video Type not Specified")
    ending_time = datetime.datetime.now()
    elapsed_time = ending_time - starting_time
    total_seconds = elapsed_time.total_seconds()
    time_hours = total_seconds // 3600
    time_minutes = (total_seconds % 3600) // 60
    time_seconds = total_seconds % 60
    if redirector != None:
        if status == None:
            redirector.action_label.config(text="")
            global clip_editor
            global current_index
            with open(clip_json_file, "r") as clip_data:
                clip_data = json.load(clip_data) 
            show_clip_details(clip_data[current_index], clip_data, current_index, os.path.dirname(clip_json_file))
            if time_hours < 1:
                redirector.progress_label.config(text=f"Complete in {int(time_minutes):d} minutes, {int(time_seconds):d} seconds")
                messagebox.showinfo("Upload Complete", f"YouTube Upload Complete in {int(time_minutes):d} minutes, {int(time_seconds):d} seconds",icon=messagebox.INFO)
            else:
                redirector.progress_label.config(text=f"Complete in {int(time_hours):d} hours, {int(time_minutes):d} minutes, {int(time_seconds):d} seconds")
                messagebox.showinfo("Upload Complete", f"YouTube Upload Complete in {int(time_hours):d} hours, {int(time_minutes):d} minutes, {int(time_seconds):d} seconds",icon=messagebox.INFO)
        else:
            messagebox.showerror("ERROR: "+status[0],status[1])
    else: 
        if time_hours < 1:
            print(f"Complete in {int(time_minutes):d} minutes, {int(time_seconds):d} seconds")
        else:
            print(f"Complete in {int(time_hours):d} hours, {int(time_minutes):d} minutes, {int(time_seconds):d} seconds")
            
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
    #ray.init()
    if file != None:
        '''@ray.remote
        def Social():
            getvid.social([args.filename],socials['facebook'], socials['twitter'], socials['tumblr'], socials['mastodon'], socials['discord'], persist)'''
        social = threading.Thread(target=getvid.social,args=([args.filename],), kwargs={
        'facebook': socials['facebook'],
        'twitter': socials['twitter'],
        'tumblr': socials['tumblr'],
        'useMastodon': socials['mastodon'],
        'useDiscord': socials['discord'],
        'persist': persist
    })
    elif directory != None:
        '''@ray.remote
        def Social():
            vidList = getvid.list_videos(directory)
            getvid.social(vidList,socials['facebook'], socials['twitter'], socials['tumblr'], socials['mastodon'], socials['discord'], persist)'''
        vidList = getvid.list_videos(directory)
        social = threading.Thread(target=getvid.social,args=(vidList,),kwargs={
        'facebook': socials['facebook'],
        'twitter': socials['twitter'],
        'tumblr': socials['tumblr'],
        'useMastodon': socials['mastodon'],
        'useDiscord': socials['discord'],
        'persist': persist
    })
    else:
        '''@ray.remote
        def Social():
            vidList = getvid.list_videos(getvid.directory)
            getvid.social(vidList,socials['facebook'], socials['twitter'], socials['tumblr'], socials['mastodon'], socials['discord'], persist)'''
        social = threading.Thread(target=getvid.social,args=(vidList,),kwargs={
        'facebook': socials['facebook'],
        'twitter': socials['twitter'],
        'tumblr': socials['tumblr'],
        'useMastodon': socials['mastodon'],
        'useDiscord': socials['discord'],
        'persist': persist
    })
    social.start()
    threads = []
    threads.append(social)
    #rayList = []
    #rayList.append(Social.remote())
    if socials['discord'] != False:
        '''@ray.remote
        def DiscordBot():
            listentosocial.checkDiscord()
        rayList.append(DiscordBot.remote())'''
        discord_listen = threading.Thread(target=listentosocial.checkDiscord)
        discord_listen.start()
        threads.append(discord_listen)
    #for i in range(0,250):
    if socials['twitter'] != False:
        #@ray.remote
        '''def TwitterBot():
            listentosocial.checkTwitter()
        rayList.append(TwitterBot.remote())'''
        twitter_listen = threading.Thread(target=listentosocial.checkTwitter)
        threads.append(twitter_listen)
    if socials['mastodon'] != False:
        #@ray.remote
        '''def MastodonBot():
            listentosocial.checkMastodon()
        rayList.append(MastodonBot.remote())'''
        mastodon_listen = threading.Thread(garget=listentosocial.checkMastodon)
        threads.append(mastodon_listen)
    '''try:
        ray.get(rayList)
    except Exception as e:
        print(e)'''
    for t in threads:
        t.join()

def on_archiver_select(option,script="Archiver"):
    global is_clip
    global is_video
    
    if option == "Full Video":
        file_menu.entryconfig("Open Clip Data File...", state=tk.DISABLED)
        selected_script_label.config(text=script+" - Full Video Upload")
        json_file_entry.config(state=tk.DISABLED)
        json_file_label_var.set('Data File:')
        json_file_selection.set(json_data.name)
        is_video = True
        is_clip = False
    else:
        file_menu.entryconfig("Open Clip Data File...", state=tk.NORMAL)
        json_file_entry.config(state=tk.NORMAL)
        selected_script_label.config(text=script+" - Video Clip Upload")
        json_file_selection.set('Use the File menu to open the corresponding clip data file')
        json_file_label_var.set('Data File:')
        is_clip = True
        is_video = False

def on_youtuber_select(option,script="YouTube Uploader"):
    global is_clip
    global is_video
    
    ytuploader.youtube = ytuploader.get_authenticated_youtube_service(config['youtube']['credentials path'])
    
    if option == "Full Video":
        file_menu.entryconfig("Open Clip Data File...", state=tk.DISABLED)
        selected_script_label.config(text=script+" - Full Video Upload")
        json_file_entry.config(state=tk.DISABLED)
        json_file_label_var.set('Data File:')
        json_file_selection.set(json_data.name)
        is_video = True
        is_clip = False
    else:
        file_menu.entryconfig("Open Clip Data File...", state=tk.NORMAL)
        json_file_entry.config(state=tk.NORMAL)
        selected_script_label.config(text=script+" - Video Clip Upload")
        json_file_selection.set('Use the File menu to open the corresponding clip data file')
        json_file_label_var.set('Data File:')
        is_clip = True
        is_video = False
 
def browse_file(json_file_selection):
    file_path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
    if file_path:
        json_file_selection.set(file_path)
        json_file_label_var.set('Data File:')

def update_arguments(*args, selected_script, descriptions):
    global selected_argument
    global json_file_selection

    # Clear any existing checkboxes
    for checkbox in checkboxes:
        checkbox.destroy()
    checkboxes.clear()

    # Get the selected option from the menu
    selected_script = selected_script.get()

    if selected_script == "Archiver":

        selected_argument = tk.StringVar(window)

        selected_argument.trace("w", on_archiver_select)

        description_label.config(text=descriptions[selected_script])

        json_file_selection.set(json_data.name)
        
        json_file_label.config(text="Data File:")
        
        json_file_entry.config(textvariable=json_file_selection)
    elif selected_script == "YouTube Uploader":

        selected_argument = tk.StringVar(window)

        selected_argument.trace("w", on_youtuber_select)

        description_label.config(text=descriptions[selected_script])

        json_file_selection.set(json_data.name)
        
        json_file_label.config(text="Data File:")
        
        json_file_entry.config(textvariable=json_file_selection)

    else:
        selected_script_label.config(text=selected_script)
        json_file_label_var.set('')
        json_file_selection.set('')
        description_label.config(text=descriptions[selected_script])
        file_menu.entryconfig("Open Clip Data File...", state=tk.DISABLED)


def update_text():
    output_text.delete(1.0, tk.END)
    output_text.insert(tk.END, output_variable.get())

def update_button_state(*args):
    global filename_button
    global directory_button
    selected_option = selected_script.get()
    selected_script_label.config(text=selected_option)
    if selected_option != "SELECT OPERATION":
        #filename_button.config(state=tk.NORMAL)
        file_menu.entryconfig("Open File...", state=tk.NORMAL)
        #directory_button.config(state=tk.NORMAL)
        file_menu.entryconfig("Open Directory...", state=tk.NORMAL)
        launch_button.config(state=tk.NORMAL)

def choose_directory():
    directory = filedialog.askdirectory()
    selected_option = selected_script.get()
    label_label.config(text="Directory to Process:")
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
    
    if selected_option in ["Scanner", "Splitter", "Audio Normalizer", "Identifier", "Metatagger", "Archiver", "YouTube Uploader", "SocialBot"]:
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
    label_label.config(text="File to Process:")
    selected_file_label.config(text=os.path.basename(filepath))
    filename_var.set(filepath)

def stop_execution():
    window.destroy()
    os._exit(0)

def show_about_dialog():
    # Create a top-level window for the about dialog
    about_window = tk.Toplevel()
    about_window.title("About VHS Tools")
    
    # About dialog text
    about_text = """
    VHS Tools
    Developer: Moe Fwacky
    Repository: github.com/MoeFwacky/vhstools
    VHS Tools is released under the GNU General Public License (GPL).
    
    VHS Tools is a powerful and user-friendly application designed to 
    simplify the process of extracting, analyzing, and identifying clips 
    from large video files of old broadcast TV content, often taken 
    from digitized VHS tapes. Whether you're an experienced video 
    archivist or new to the world of preservation, VHS Tools offers a 
    comprehensive solution for navigating through extensive footage and 
    transforming it into organized, shareable content."""

    function_text= """"""

    footer_text="""
    For more information, support, to report bugs/issues, or to contribute, please visit the project repository at the provided link or by clicking the button below.

    Thank you for using VHS Tools!
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

def update_timecode(video_player,timecode,gui_window,frame_offset=0):
    current_ms = video_player.player.get_time()
    total_ms = video_player.player.get_length()
    frame_rate = video_player.player.get_fps()

    current_hours, remaining_minutes = divmod(current_ms // 1000, 3600)
    current_minutes, current_seconds = divmod(remaining_minutes, 60)

    total_hours, total_remaining_minutes = divmod(total_ms // 1000, 3600)
    total_minutes, total_seconds = divmod(total_remaining_minutes, 60)

    current_frame = str(int(current_ms / 1000 * frame_rate)+frame_offset)
    total_frames = str(int(total_ms / 1000 * frame_rate)+frame_offset)

    if int(total_hours) > 0:
        timecode_string = (
            f"{current_frame}/{total_frames} | "
            f"{current_hours:02d}:{current_minutes:02d}:{current_seconds:02d}/"
            f"{total_hours:02d}:{total_minutes:02d}:{total_seconds:02d}"
        )
    else:
        timecode_string = (
            f"{current_frame}/{total_frames} | "
            f"{current_minutes:02d}:{current_seconds:02d}/"
            f"{total_minutes:02d}:{total_seconds:02d}"
        )
    timecode.set(timecode_string)
    gui_window.after(33, lambda: update_timecode(video_player,timecode,gui_window,frame_offset))
    return current_ms,current_frame

def show_video_player(window_object,file_path,item,frame_offset=0):
    global start_frame_var
    global end_frame_var
    video_player = VideoPlayer(window_object, media_path=file_path)
    # Update the entry widgets with current item values and populate the clip_widget_mapping list
    volume_frame = tk.Frame(window_object)
    
    # Add a volume bar
    volume_scale = ttk.Scale(volume_frame, from_=100, to=0, orient=tk.VERTICAL, length=250, command=lambda v: video_player.player.audio_set_volume(round((float(v)))))
    #volume_scale.set(75)  # Set initial volume to 50
    volume_scale.grid(row=0, column=0)

    # Add a mute button
    mute_button = ttk.Button(volume_frame, text="Mute", command=lambda: video_player.player.audio_set_mute(not video_player.player.audio_get_mute()))
    mute_button.grid(row=1, column=0, padx=5, sticky="nsew")

    control_frame = ttk.Frame(window_object)
    

    # Buttons to step back x%
    extra_jump_back_button = ttk.Button(control_frame, text="<<<", command=lambda: video_player.go_backward_x_percent(x=5))
    extra_jump_back_button.grid(row=0, column=0, sticky="nsew")
    
    jump_back_button = ttk.Button(control_frame, text="<<", command=lambda: video_player.go_backward_x_percent(x=0.5))
    jump_back_button.grid(row=0, column=1, sticky="nsew")
    
    # Add buttons for step backward and step forward
    step_backward_button = ttk.Button(control_frame, text="<", command=video_player.step_backward)
    step_backward_button.grid(row=0, column=2, sticky="nsew")

    pause_button = ttk.Button(control_frame, text="►/‖", command=video_player.pause)
    pause_button.grid(row=0, column=3, sticky="nsew")

    step_forward_button = ttk.Button(control_frame, text=">", command=video_player.step_forward)
    step_forward_button.grid(row=0, column=4, sticky="nsew")

    # Buttons to step forward x%
    jump_forward_button = ttk.Button(control_frame, text=">>", command=lambda: video_player.go_forward_x_percent(x=0.5))
    jump_forward_button.grid(row=0, column=5, sticky="nsew")

    extra_jump_forward_button = ttk.Button(control_frame, text=">>>", command=lambda: video_player.go_forward_x_percent(x=5))
    extra_jump_forward_button.grid(row=0, column=6, sticky="nsew")
    
    timecode = tk.StringVar()
    timecode.set('TIMECODE')
    time_label = tk.Label(window_object,textvariable=timecode,font=("Lucida Console", 12, "normal"))
    current_frame,current_ms = update_timecode(video_player,timecode,window_object,frame_offset)

    # Entry widgets to show the start and end frames
    start_frame_var = tk.StringVar()
    start_ms_var = tk.StringVar()
    start_frame_entry = ttk.Entry(control_frame, textvariable=start_frame_var, width=8)
    start_frame_entry.grid(row=1, column=2, padx=5, pady=5)

    end_frame_var = tk.StringVar()
    end_ms_var = tk.StringVar()
    end_frame_entry = ttk.Entry(control_frame, textvariable=end_frame_var, width=8)
    end_frame_entry.grid(row=1, column=3, padx=5, pady=5)

    def set_current_frame(frame_offset,video_player,start=True):
        current_ms = video_player.player.get_time()
        frame_rate = video_player.player.get_fps()
        current_frame = str(int(current_ms / 1000 * frame_rate)+frame_offset)
        if start is True:
            start_frame_var.set(current_frame)
            start_ms_var.set(current_ms)
            start_frame_entry.update()
        else:
            end_frame_var.set(current_frame)
            end_ms_var.set(current_ms)
            end_frame_entry.update

    def set_start_end(frame_offset,video_player,start=True):
        total_ms = video_player.player.get_length()
        frame_rate = video_player.player.get_fps()
        total_frames = str(int(total_ms / 1000 * frame_rate)+frame_offset)
        if start is True:
            start_frame_var.set(frame_offset)
            start_frame_entry.update()
        else:
            end_frame_var.set(total_frames)
            end_frame_entry.update

    # Buttons to get the current frame and update start and end frame entry widgets

    set_first_frame_button = ttk.Button(control_frame, text="First In",command=lambda: set_start_end(frame_offset,video_player,start=True))
    set_first_frame_button.grid(row=1, column=0, padx=5, pady=5)

    set_start_frame_button = ttk.Button(control_frame, text="Current In",command=lambda: set_current_frame(frame_offset,video_player,start=True))
    set_start_frame_button.grid(row=1, column=1, padx=5, pady=5)
    
    set_end_frame_button = ttk.Button(control_frame, text="Current Out",command=lambda: set_current_frame(frame_offset,video_player,start=False))
    set_end_frame_button.grid(row=1, column=4, padx=5, pady=5)    

    set_last_frame_button = ttk.Button(control_frame, text="Last Out",command=lambda: set_start_end(frame_offset,video_player,start=False))
    set_last_frame_button.grid(row=1, column=5, padx=5, pady=5)

    # Button to initiate the new_video_clip function
    def create_new_clip():
        new_clip_data={}
        new_clip_data['source_file'] = file_path
        new_clip_data['tape_id'] = item.get("Tape ID", "")
        if new_clip_data['tape_id'] == "":
            new_clip_data['tape_id'] = item.get("Tape_ID", "")
        new_clip_data['start_frame'] = int(start_frame_var.get())
        new_clip_data['end_frame'] = int(end_frame_var.get())

        # Calculate start_ms and end_ms based on frame numbers and frame rate
        frame_rate = video_player.player.get_fps()
        new_clip_data['start_ms'] = int(new_clip_data['start_frame'] / frame_rate * 1000)
        new_clip_data['end_ms'] = int(new_clip_data['end_frame'] / frame_rate * 1000)

        # Validate start_ms and end_ms
        if new_clip_data['start_ms'] < new_clip_data['end_ms']:
            new_video_clip(new_clip_data)
        else:
            error_message="Start Frame ["+str(new_clip_data['start_frame'])+"] is higher than End Frame ["+str(new_clip_data['end_frame'])+"]"
            messagebox.showinfo("ERROR!", error_message,icon=messagebox.ERROR)

    create_new_clip_button = ttk.Button(control_frame, text="New Clip",
                                        command=create_new_clip)
    create_new_clip_button.grid(row=1, column=6, padx=5, pady=5)

    return video_player,volume_frame,control_frame,time_label

def new_video_clip(new_clip_data):
    file_extension = os.path.basename(new_clip_data['source_file']).split('.')[1]
    base_file = os.path.join(os.path.dirname(json_file),new_clip_data['tape_id']+'.'+file_extension)
    output_name = new_clip_data['tape_id']+'_'+str(new_clip_data['start_frame'])+'-'+str(new_clip_data['end_frame'])+'.'+file_extension
    output_path = os.path.join(os.path.dirname(json_file),new_clip_data['tape_id'])
    import editor
    try:
        editor.splitVideo(base_file,new_clip_data['start_ms']/1000,new_clip_data['end_ms']/1000,output_name,output_path)
    except Exception as e:
        print(e)
        return
    completion_message = f"{output_name} created in {output_path}"
    messagebox.showinfo("Clip Creation Complete", completion_message,icon=messagebox.INFO)

def launch_script(selected_script,output_text,redirector,window=None):
    print("Launching "+selected_script)
    # Get the selected filename or directory
    global thread
    global stop_event 
    global is_video
    global is_clip
    stop_event = threading.Event()
    selected_filename = filename_var.get() if filename_var.get() else None
    selected_directory = directory_var.get() if directory_var.get() else None

    # Get the arguments from the checkboxes
    #print("Getting arguments")
    selected_arguments = []
    for checkbox in checkboxes:
        if checkbox.get() == 1:
            selected_arguments.append(checkbox.cget('text'))
    action_label.config(text="Starting "+selected_script)
    #print("Redirecting console output to the GUI text box...")

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
            thread = threading.Thread(target=launch_scanner,args=(selected_filename,selected_directory,redirector))
            thread.start()
        except Exception as e:
            print(e)
    elif selected_script == "Splitter":
        try:
            thread = threading.Thread(target=launch_splitter,args=(selected_filename,selected_directory,redirector))
            thread.start()
        except Exception as e:
            print(e)
    elif selected_script == "Audio Normalizer":
        try:
            thread = threading.Thread(target=launch_audio_normalizer,args=(selected_filename,selected_directory,redirector))
            thread.start()
        except Exception as e:
            print(e)
    elif selected_script == "Identifier":
        try:
            thread = threading.Thread(target=launch_identifier,args=(selected_filename,selected_directory,redirector,window))
            thread.start()
        except Exception as e:
            print(e)
    elif selected_script == "Archiver":
        try:
            thread = threading.Thread(target=launch_archiver, args=(selected_filename, selected_directory, redirector, is_video, is_clip, json_file_selection.get()))  # Pass the variables here
            thread.start()
        except Exception as e:
            print(e)
    elif selected_script == "YouTube Uploader":
        disclaimer_text = "By continuing you certify that the content you are uploading complies with the YouTube Terms of Service (including the YouTube Community Guidelines) at https://www.youtube.com/t/terms. Please be sure not to violate others' copyright or privacy rights."
        response = messagebox.askokcancel("Disclaimer", disclaimer_text)
        if response:
            try:
                thread = threading.Thread(target=launch_youtuber, args=(selected_filename, selected_directory, redirector, is_video, is_clip, json_file_selection.get()))  # Pass the variables here
                thread.start()
            except Exception as e:
                print(e)
        else:
            return
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
    banner()
    if args.filename != None:
        launch_scanner(file=args.filename)
    elif args.filepath != None:
        launch_scanner(file=args.filepath)
    elif args.directory != None:
        launch_scanner(directory=args.directory)
    else:
        launch_scanner()

elif args.audio != False:
    banner()
    if args.filename != None:
        launch_audio_normalizer(file=args.filename)
    elif args.filepath != None:
        launch_audio_normalizer(file=args.filepath)
    elif args.directory != None:
        launch_audio_normalizer(directory=args.directory)
    else:
        launch_audio_normalizer()

elif args.archive != False:
    banner()
    if args.filename != None:
        launch_archiver(file=args.filename)
    elif args.filepath != None:
        launch_archiver(file=args.filepath)
    elif args.directory != None:
        launch_archiver(directory=args.directory)
    else:
        launch_archiver()
        
elif args.twitter != False or args.tumblr != False or args.mastodon != False or args.discord != False or args.facebook != False or args.bot != False:
    banner()
    
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
    banner()
    if args.filename != None:
        launch_splitter(file=os.path.join(os.getcwd(),args.filename))
    elif args.filepath != None:
        launch_splitter(file=args.filepath)
    elif args.directory != None:
        launch_splitter(directory=args.directory)
    else:
        launch_splitter()
elif args.editor != False:
    banner()
    if args.filename != None:
        launch_editor(file=os.path.join(os.getcwd(),args.filename))
    elif args.filepath != None:
        launch_editor(file=args.filepath)
    elif args.directory != None:
        launch_editor(directory=args.directory)
    else:
        launch_editor()

elif args.tagger != False:
    banner()
    if args.filename != None:
        launch_tagger(file=os.path.join(os.getcwd(),args.filename))
    elif args.filepath != None:
        launch_tagger(file=args.filepath)
    elif args.directory != None:
        launch_tagger(directory=args.directory)
    else:
        launch_tagger()
elif args.identify != False:
    banner()
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
    clip_editor = None
    clip_navigator = None
    video_player = None
    def create_new_entry(video_player=None):
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
        if video_player:
            video_player.stop()
        show_item_details(tape_data[current_index], tape_data, current_index)

    def create_clip_entry(clip_data, index, data_dir, video_player):

        # Get the information from the previous entry
        previous_entry = clip_data[index]
        tape_id = previous_entry["Tape ID"]
        #segment_end = datetime.datetime.strptime(previous_entry["Segment End"], "%H:%M:%S").time()
        recording_date = previous_entry["Air Date"]
        network = previous_entry["Network/Station"]
        location = previous_entry["Location"]

        file_path = filedialog.askopenfilename(initialdir=data_dir, title="Select a Video File", filetypes=[("Video Files", "*.mp4;*.avi;*.mkv;*.m4v")])
        file_name = os.path.basename(file_path)
        if not file_path:
            # User canceled the file selection, do nothing
            return                
        if any(item["Filename"] == file_name for item in clip_data):
            messagebox.showinfo("ERROR!", "Clip Data Already Exists",icon=messagebox.ERROR)
            return
        if file_name.strip().startswith(tape_id):
            new_segment_start,new_segment_end = os.path.splitext(file_name)[0].split('_')[1].split('-')
        else:
            # Determine the highest order on tape value
            max_order_on_tape = max(entry["Frame Range"][1] for entry in clip_data)
            new_segment_start = max_order_on_tape + 1
            new_segment_end = new_segment_start + 1
        
        # Create the new entry
        new_entry = {
            "Air Date": recording_date,
            "Network/Station": network,
            "Description": "",
            "Tags": "",
            "Title": "",
            "Filename": file_name,
            "Tape ID": tape_id,
            "Length (seconds)": "",
            "Location": location,
            "Frame Range": [int(new_segment_start),int(new_segment_end)]
        }

        # Append the new entry to the data list
        clip_data.append(new_entry)

        # Sort the data list based on the starting frame
        clip_data.sort(key=lambda entry: (entry["Frame Range"][0]))

        # Update the data list
        #clip_data = get_ordered_data(tape_id)
        #print(clip_data)
        # Find the index of the new entry in the tape_data list
        index = clip_data.index(new_entry)

        # Update the current index and show the new entry details
        video_player.stop()
        show_clip_details(clip_data[index], clip_data, index, data_dir)

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

    def edit_clip_data():
        clip_data_path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if clip_data_path == '':
            return
        with open(clip_data_path, "r") as clip_data:
            clip_data = json.load(clip_data)        
        show_clip_details(clip_data[0], clip_data, 0, os.path.dirname(clip_data_path))

    def get_number_after_underscore(filename):
        parts = filename.rsplit("_", 1)  # Split the filename into two parts at the first underscore
        if len(parts) == 2:
            number_part = parts[1].split("-", 1)[0]  # Get the part after the underscore and before the first hyphen
            try:
                return int(number_part)  # Convert the extracted part to an integer
            except ValueError:
                return 0  # Return 0 if the extracted part is not a valid number
        return 0  # Return 0 if the filename doesn't contain an underscore

    def view_clip_data():
        current_index = 0
        # Ask the user to select a directory
        data_dir = filedialog.askdirectory()
        if not data_dir:
            return

        # Get a list of video files in the selected directory
        video_extensions = (".mp4", ".avi", ".mkv", ".m4v")
        video_files = [os.path.join(data_dir, file) for file in os.listdir(data_dir) if file.lower().endswith(video_extensions)]
        video_files = sorted(video_files, key=get_number_after_underscore)

        if not video_files:
            messagebox.showinfo("No Video Files", "No video files found in the selected directory.",icon=messagebox.ERROR)
            return

        # Now you have the list of video files, call show_unidentified_clips
        with open(json_file, "r") as json_data:
            json_data = json.load(json_data)
        show_unidentified_clips(video_files, json_data, os.path.dirname(json_file),current_index)

    def to_previous_clip(index, data, data_dir, video_player):
        global current_index
        video_player.stop()
        if current_index > 0:
            current_index -= 1  # Decrement the index to move to the previous item
            show_clip_details(data[current_index], data, current_index, data_dir)

    def to_next_clip(index, data, data_dir, video_player):
        global current_index
        video_player.stop()
        if current_index < len(data) - 1:
            current_index += 1  # Increment the index to move to the next item
            show_clip_details(data[current_index], data, current_index, data_dir)

    def on_youtube_upload_button_press(option,filename,data_dir,redirector,clip_data_path,data,upload_to_youtube_button,video_player):
        #if "ytuploader" not in sys.modules:
        video_player.stop()
        redirector.progress_label_var.set("Uploading Video to YouTube")
        upload_to_youtube_button.config(textvariable=redirector.progress_label_var,state="disabled")
        #import ytuploader
        if 'youtube' not in ytuploader.__dict__:
            ytuploader.youtube = ytuploader.get_authenticated_youtube_service(config['youtube']['credentials path'])
        global clip_editor
        global current_index
        '''try:
            if ytuploader.youtube:
                pass
        except NameError:
            ytuploader.youtube = ytuploader.get_authenticated_youtube_service(config['youtube']['credentials path'])'''
        
        #upload_to_youtube_label = tk.Label(clip_editor, textvariable=redirector.progress_label_var)
        #upload_to_youtube_label.grid(row=i-1, column=1, columnspan=3, padx=10, pady=1, sticky="w")
        if option == "Full Video":
            pass
        else:
            disclaimer_text = "By continuing you certify that the content you are uploading complies with the YouTube Terms of Service (including the YouTube Community Guidelines) at https://www.youtube.com/t/terms. Please be sure not to violate others' copyright or privacy rights."
            response = messagebox.askokcancel("Disclaimer", disclaimer_text)
            if response:
                try:
                    thread = threading.Thread(target=launch_youtuber, args=(os.path.join(data_dir,filename), data_dir, redirector, False, True, clip_data_path))  # Pass the variables here

                    thread.start()
                except Exception as e:
                    print(e)
            else:
                return

    def on_archive_upload_button_press(option,filename,data_dir,redirector,clip_data_path,data,upload_to_archive_button,video_player):
        video_player.stop()
        redirector.progress_label_var.set("Uploading Video to the Internet Archive")
        upload_to_archive_button.config(textvariable=redirector.progress_label_var,state="disabled")
        
        if option == "Full Video":
            pass
        else:
            try:
                thread = threading.Thread(target=launch_archiver, args=(os.path.join(data_dir,filename), data_dir, redirector, False, True, clip_data_path))
                
                thread.start()
            except Exception as e:
                print(e)
            else:
                return
        
    def show_clip_details(item, data, index, data_dir):
        # Update the current index

        current_index = index
        global clip_editor
        clip_data_path = os.path.join(data_dir, item["Tape ID"]+"_Clips.json")
        launchloop = False
        # Destroy the existing window if it exists
        if clip_editor is None:
            clip_editor = tk.Toplevel()
            clip_editor.title("Clip Data Editor")
            clip_editor.iconbitmap(tv_ico)
            clip_editor.geometry("966x1080")
            launchloop = True

            # Bind the window close event to set `clip_editor` to None
            #clip_editor.protocol("WM_DELETE_WINDOW", lambda: on_window_close(clip_editor))

        if not clip_editor:
            return

        if clip_editor.winfo_exists():
            for widget in clip_editor.grid_slaves():
                widget.destroy()
        
        # Clear existing widgets
        for widget in clip_editor.grid_slaves():
            widget.grid_forget()

        video_player,volume_frame,control_frame,time_label = show_video_player(clip_editor, os.path.join(data_dir,item["Filename"]),item,item["Frame Range"][0])
        original_filename = item["Filename"]
        # Create labels and editable widgets for each key-value pair
        entry_widgets = []
        text_widgets = []
        clip_widget_mapping = []
        keys = ["Tape ID", "Frame Range", "Title", "Description", "Air Date", "Network/Station", "Location", "Tags", "Filename", "Length (seconds)", "Uploaded"]

        try:
            for i, key in enumerate(keys):
                
                if key != "Uploaded":
                    label = tk.Label(clip_editor, text=key)
                    label.grid(row=i, column=0, padx=10, sticky="e")

                value = tk.StringVar(value=item[key])
                if (key == "Length (seconds)" or key == "Tape ID"):
                    entry = tk.Entry(clip_editor, textvariable=value, state="disabled")
                    entry.grid(row=i, column=1, columnspan=2, padx=10, pady=1, sticky="w")
                    if (key == "Length (seconds)" and item[key] == ""):
                        time.sleep(0.15)
                        value.set(round(video_player.player.get_length()/1000, 1))
                    entry_widgets.append(entry)  # Add the Entry widget to the common list
                    clip_widget_mapping.append((entry, key)) 
                elif key == "Description":
                    entry = tk.Text(clip_editor, height=10, width=50, wrap="word")
                    entry.insert(tk.END, value.get())
                    entry.grid(row=i, column=1, columnspan=2, padx=10, pady=1, sticky="nsew")
                    text_widgets.append(entry)  # Add the Text widget to the separate list
                    clip_widget_mapping.append((entry, key)) 
                elif key == "Frame Range":
                    frame_range = value.get().strip('()').split(',')
                    start_frame_var = tk.StringVar(value=frame_range[0])
                    end_frame_var = tk.StringVar(value=frame_range[1])
                    frame = tk.Frame(clip_editor)
                    frame.grid(row=i, column=1, sticky="w")
                    entry_a = tk.Entry(frame, textvariable=start_frame_var, width=10, state="disabled")
                    entry_a.grid(row=0, column=0, padx=10, sticky="w")
                    hyphen = tk.Label(frame, text=" - ")
                    hyphen.grid(row=0, column=1, padx=10, sticky="nsew")
                    entry_b = tk.Entry(frame, textvariable=end_frame_var, width=10, state="disabled")
                    entry_b.grid(row=0, column=2, padx=10, pady=1, sticky="w")

                    entry_widgets.append(entry_a)  # Add the Entry widgets to the common list
                    entry_widgets.append(entry_b)

                    # Add both entry widgets with the "Frame Range" key to clip_widget_mapping
                    clip_widget_mapping.append((entry_a, key))
                    clip_widget_mapping.append((entry_b, key))
                elif key == "Uploaded":
                    label = tk.Label(clip_editor, text="YouTube")
                    label.grid(row=i, column=0, padx=10, sticky="e")
                    if "youtube" not in item[key]:
                        upload_to_youtube_button = tk.Button(clip_editor, text="Upload Clip to YouTube", command=lambda: on_youtube_upload_button_press("Clip",item["Filename"],data_dir,redirector,clip_data_path,data,upload_to_youtube_button, video_player))
                        upload_to_youtube_button.grid(row=i, column=1, columnspan=2, padx=10, pady=1, sticky="w")
                    else:
                        destination = "youtube"
                        destination_value = tk.StringVar(value=item[key][destination]["url"])
                        entry = tk.Entry(clip_editor, textvariable=destination_value, fg="blue", cursor="hand2", state="readonly")
                        entry.grid(row=i, column=1, columnspan=2, padx=10, sticky="nsew")
                        entry_widgets.append(entry)
                        clip_widget_mapping.append((entry, destination))
                    i +=1
                    label = tk.Label(clip_editor, text="Internet Archive")
                    label.grid(row=i, column=0, padx=10, sticky="e")
                    if "internet archive" not in item[key]:
                        upload_to_archive_button = tk.Button(clip_editor, text="Upload Clip to the Internet Archive", command=lambda: on_archive_upload_button_press("Clip",item["Filename"],data_dir,redirector,clip_data_path,data,upload_to_archive_button,video_player))
                        upload_to_archive_button.grid(row=i, column=1, columnspan=2, padx=10, pady=1, sticky="w")                      
                    else:
                        destination = "internet archive"
                        destination_value = tk.StringVar(value=item[key][destination]["url"])
                        entry = tk.Entry(clip_editor, textvariable=destination_value, fg="blue", cursor="hand2", state="readonly")
                        entry.grid(row=i, column=1, columnspan=2, padx=10, sticky="nsew")
                        entry_widgets.append(entry)
                        clip_widget_mapping.append((entry, destination))
                    i +=1                        
                else:
                    entry = tk.Entry(clip_editor, textvariable=value, width=60, state="normal")
                    entry.grid(row=i, column=1, columnspan=2, padx=10, sticky="nsew")
                    entry_widgets.append(entry)  # Add the Entry widget to the common list
                
                    clip_widget_mapping.append((entry, key))  # Store the mapping between widget object and key

        except KeyError as e:
            if str(e) != "'Uploaded'":
                print("KeyError: " + str(e))
            else:
                i+=2
                upload_to_youtube_button = tk.Button(clip_editor, text="Upload Clip to YouTube", command=lambda: on_youtube_upload_button_press("Clip",item["Filename"],data_dir,redirector,clip_data_path,data,upload_to_youtube_button, video_player))
                upload_to_youtube_button.grid(row=i-1, column=1, columnspan=2, padx=10, pady=1, sticky="w")

                upload_to_archive_button = tk.Button(clip_editor, text="Upload Clip to the Internet Archive", command=lambda: on_archive_upload_button_press("Clip",item["Filename"],data_dir,redirector,clip_data_path,data,upload_to_archive_button,video_player))
                upload_to_archive_button.grid(row=i, column=1, columnspan=2, padx=10, pady=1, sticky="w")

        # Adjust column widths to accommodate the widgets
        clip_editor.grid_columnconfigure(0, weight=1)
        clip_editor.grid_columnconfigure(1, weight=3)

        save_button = tk.Button(clip_editor, text="Save Changes to File", command=lambda: save_clip_data(item, data, clip_widget_mapping, clip_data_path, video_player, index))
        save_button.grid(row=i+1, column=0, columnspan=3, padx=30, pady=10, sticky="nsew")

        # Create buttons to navigate back and forth
        prev_button = tk.Button(clip_editor, text="Previous Clip", command=lambda: to_previous_clip(current_index, data, data_dir, video_player))
        prev_button.grid(row=i+2, column=0, padx=10, pady=10, sticky="nsew")

        next_button = tk.Button(clip_editor, text="Next Clip", command=lambda: to_next_clip(current_index,data,data_dir,video_player))
        next_button.grid(row=i+2, column=2, padx=10, pady=10, sticky="e")

        # Check if the current item is the first or last one
        is_first_item = index == 0
        is_last_item = index == len(data) - 1

        # Disable the previous button if it's the first item
        prev_button.config(state=tk.DISABLED if is_first_item else tk.NORMAL)

        # Disable the next button if it's the last item
        next_button.config(state=tk.DISABLED if is_last_item else tk.NORMAL)

        # Function to delete the current entry from the dictionary array
        def delete_entry():
            nonlocal current_index
            confirmation = messagebox.askyesno("Confirmation", "Are you sure you want to delete this entry?",icon=messagebox.QUESTION)
            if confirmation:
                # Delete the current entry from the dictionary array
                del data[current_index]
                # Save the updated data to the JSON file
                with open(clip_data_path, 'w') as file:
                    json.dump(data, file, indent=2)

                # Stop the video player and audio
                video_player.stop()

                # Move to the next entry if available, otherwise close the window
                if current_index < len(data):
                    current_index += 1
                    show_clip_details(data[current_index], data, current_index, data_dir)
                else:
                    clip_editor_close(video_player)
            else:
                return
                
        def clip_editor_close(video_player):
            global clip_editor
            if video_player:
                video_player.stop()
                video_player.player.set_position(0.0)  # Reset video position to the beginning
            clip_editor.destroy()
            clip_editor = None

        # Create a frame to hold the "New Clip Data" and "Delete Entry" buttons
        button_frame = tk.Frame(clip_editor)
        button_frame.grid(row=i+2, column=1, padx=10, pady=10)

        # Create the "New Clip Data" button
        new_entry_button = tk.Button(button_frame, text="New Clip Entry", command=lambda: create_clip_entry(data, current_index, data_dir, video_player))
        new_entry_button.grid(row=0, column=0, padx=5, pady=5)

        # Create the "Delete Entry" button
        delete_button = tk.Button(button_frame, text="Delete Entry", command=delete_entry)
        delete_button.grid(row=0, column=1, padx=5, pady=5)

        video_player.grid(row=i+4, column=1, columnspan=1, rowspan=3, padx=1, pady=1, sticky="nsew")
        volume_frame.grid(row=i+4, column=2)
        time_label.grid(row=len(keys)+7,column=1)
        control_frame.grid(row=i+9, column=0, columnspan=3, sticky=tk.S)
        
        # Bind the window close event to set `clip_editor` to None
        #clip_editor.protocol("WM_DELETE_WINDOW", lambda: on_window_close(clip_editor,video_player))
        clip_editor.protocol("WM_DELETE_WINDOW", lambda: clip_editor_close(video_player))
        
        # Run the Tkinter event loop for the window
        if launchloop:
            clip_editor.mainloop()

    def to_previous_segment(current_index, tape_data, video_player):
        video_player.stop()
        current_index = max(0, current_index - 1)
        show_item_details(tape_data[current_index], tape_data, current_index)

    def to_next_segment(current_index, tape_data, video_player):
        video_player.stop()
        current_index = min(current_index + 1, len(tape_data) - 1)
        show_item_details(tape_data[current_index], tape_data, current_index)

    def get_ordered_data(tape_id=None):
        ordered_data = sorted(data, key=lambda item: (item.get("Tape_ID"), item.get("Segment Start")))
        if tape_id is not None:
            ordered_data = [item for item in ordered_data if item.get("Tape_ID") == tape_id]
        return ordered_data
            
    def delete_entry(data, index, video_player=None):
        global current_index

        # Remove the entry at the given index
        if 0 <= index < len(data):
            data.pop(index)

        # If the index is at the end of the list after removal, set it to the new last index
        current_index = min(index, len(data) - 1)

        # Close the current window and open the next entry if available
        #gui_close(video_player)
        video_player.stop()
        if current_index >= 0:
            show_item_details(data[current_index], data, current_index)

    def show_item_details(item, data, index):
        global gui, entry_widget_mapping
        launchloop = False
        # Destroy the existing window if it exists
        if gui is None:
            gui = tk.Toplevel()
            gui.title("Tape Data Editor")
            gui.iconbitmap(tv_ico)
            gui.geometry("900x933")
            launchloop = True

            # Bind the window close event to set `gui` to None
            #gui.protocol("WM_DELETE_WINDOW", lambda: on_window_close(gui))

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
            if key == "ID" or key == "Tape_ID":
                entry = tk.Entry(gui, textvariable=value, state="disabled")
            else:
                entry = tk.Entry(gui, textvariable=value, width=60, state="normal")
            entry.grid(row=i, column=1, columnspan=2, padx=10, pady=5, sticky="w")
            entry_widgets.append(entry)
            entry_widget_mapping.append((entry, key))  # Store the mapping between entry widget and key

        entries_frame =  tk.Frame(gui)
        entries_frame.grid(row=len(keys)+1,column=1)

        save_button = tk.Button(gui, text="Save Changes to File", command=lambda: save_to_json(video_player))
        save_button.grid(row=len(keys) + 2, column=0, columnspan=3, padx=30, pady=10, sticky="nsew")

        for file in os.listdir(os.path.dirname(json_file)):
            if file.lower().endswith(('.mp4','.avi','.mkv','.m4v')):
                if os.path.splitext(file)[0].lower() == item['Tape_ID'].lower():
                    video_file_path = os.path.join(os.path.dirname(json_file),file)

        video_player,volume_frame,control_frame,time_label = show_video_player(gui, video_file_path,item)
        time.sleep(.2)
        video_fps = video_player.player.get_fps()
        video_duration_ms = video_player.player.get_length()

        delete_entry_button = tk.Button(entries_frame, text="Delete Entry", command=lambda: delete_entry(data, current_index, video_player))
        delete_entry_button.grid(row=0, column=0, padx=10, pady=10)

        new_entry_button = tk.Button(entries_frame, text="New Entry", command=lambda: create_new_entry(video_player))
        new_entry_button.grid(row=0, column=1, padx=10, pady=10)

        new_tape_button = tk.Button(entries_frame, text="New Tape", command=lambda: create_new_tape(video_player=video_player))
        new_tape_button.grid(row=0, column=2, padx=10, pady=10, sticky="w")
        
        segment_start = item.get("Segment Start", 0)  # Get the "Segment Start" value in seconds (default is 0)
        
        start_hours, start_minutes, start_seconds = segment_start.split(":")
        total_seconds = int(start_hours) * 3600 + int(start_minutes) * 60 + int(start_seconds)
        segment_start_ms = total_seconds * 1000
        
        try:
            position = segment_start_ms / video_duration_ms  # Calculate the position as a fraction of the video duration
        except: 
            position = 0
        video_player.player.set_position(position)  # Start the video player at the specified position

        # Create buttons to navigate back and forth
        prev_button = tk.Button(gui, text="Previous Segment", command=lambda: to_previous_segment(current_index, tape_data, video_player))
        prev_button.grid(row=len(keys), column=0, padx=10, pady=10, sticky="w")

        next_button = tk.Button(gui, text="Next Segment", command=lambda: to_next_segment(current_index, tape_data, video_player))
        next_button.grid(row=len(keys), column=2, padx=10, pady=10, sticky="e")

        # Check if the current item is the first or last one
        is_first_item = index == 0
        is_last_item = index == len(data) - 1

        # Disable the previous button if it's the first item
        prev_button.config(state=tk.DISABLED if is_first_item else tk.NORMAL)

        # Disable the next button if it's the last item
        next_button.config(state=tk.DISABLED if is_last_item else tk.NORMAL)

        video_player.grid(row=len(keys)+4,column=1,sticky="nsew")
        volume_frame.grid(row=len(keys)+4,column=2,rowspan=3)
        time_label.grid(row=len(keys)+8,column=1)
        control_frame.grid(row=len(keys)+9, column=0, columnspan=3, sticky=tk.S)
        # Update the entry widgets with current item values
        for i, key in enumerate(reversed(keys)):
            entry = entry_widgets[i]
            entry.delete(0, tk.END)
            entry.insert(tk.END, item[key])

        # Update the current index
        global current_index
        current_index = index

        # Bind the window close event to set `clip_editor` to None
        #gui.protocol("WM_DELETE_WINDOW", lambda: on_window_close(gui,video_player))
        gui.protocol("WM_DELETE_WINDOW",lambda: gui_close(video_player))

        # Run the Tkinter event loop for the window
        if launchloop:
            gui.mainloop()

    def gui_close(video_player=None):
        global gui
        if video_player:
            video_player.stop()
        gui.destroy()
        gui = None

    def create_new_tape(tape_id=None,video_player=None):
        global current_index, tape_data
        if tape_id == None:
            file_path = filedialog.askopenfilename(initialdir=os.path.dirname(json_file), title="Select a Video File", filetypes=[("Video Files", "*.mp4;*.avi;*.mkv;*.m4v")])
            if not file_path:
                # User canceled the file selection, do nothing
                return                
            tape_id = os.path.splitext(os.path.basename(file_path))[0]
            tape_ids = [entry["Tape_ID"] for entry in data]
            if tape_id in tape_ids:
                messagebox.showinfo("ERROR!", "Tape Data Already Exists",icon=messagebox.ERROR)
                return
        '''else:
            random_string = "".join(random.choice(string.ascii_letters) for _ in range(3))
            if tape_id == None or tape_id == "":
                tape_id = random_string.upper() + "-001"  # Blank Tape ID
            # Check if the tape ID already exists
            tape_ids = [entry["Tape_ID"] for entry in data]
            while tape_id in tape_ids:
                # Extract the prefix and highest number from existing tape IDs
                prefix = tape_id[:-4]  # Remove the last four characters ("-001")
                existing_numbers = [int(tid[-3:]) for tid in tape_ids if tid.startswith(prefix)]
                highest_number = max(existing_numbers) if existing_numbers else 0

                # Generate the new tape ID with the next number
                next_number = highest_number + 1
                tape_id = f"{prefix}-{next_number:03d}"'''


        segment_start = "0:00:00"  # Initial segment start value
        order_on_tape = 1  # Initial order on tape value

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
        if video_player:
            video_player.stop()
        show_item_details(tape_data[current_index], tape_data, current_index)

    def save_clip_data(item, data, widget_mapping, data_file_path, video_player, current_index):
        '''print("Clip Widget Mapping:")
        for entry, key in widget_mapping:
            print(f"{key} - Widget Type: {type(entry)}")
            print(f"{key} - Entry: {entry}")'''
        
        data_directory = os.path.dirname(data_file_path)
        # Get the modified data from the entry widgets
        updated_data = {}
        for entry, key in widget_mapping:
            # Handle tk.Text widgets differently
            if isinstance(entry, tk.Text):
                #print("Text:",end=' ')
                #print(entry.get("1.0", tk.END).strip())
                updated_data[key] = entry.get("1.0", tk.END).strip()
            else:
                #print("Entry:",end=' ')
                #print(entry.get())
                updated_data[key] = entry.get()

        frame_range_entry_widgets = [
            entry for entry, key in widget_mapping if key == "Frame Range"
        ]
        start_frame_str, end_frame_str = [
            widget.get().strip() for widget in frame_range_entry_widgets
        ]
        updated_data["Frame Range"] = [int(start_frame_str), int(end_frame_str)]

        # Perform data validation
        validation_errors = validate_clip_data(updated_data, data, data_file_path)

        if validation_errors:
            # Display validation errors in the GUI
            display_validation_errors(validation_errors)
        else:
            video_player.stop()
            os.rename(os.path.join(data_directory,data[current_index]["Filename"]),os.path.join(data_directory,"temp_for_rename"+os.path.splitext(data[current_index]["Filename"])[1]))
            # Write data into file metadata
            metatagger.createMetadata(os.path.join(data_directory,"temp_for_rename"+os.path.splitext(data[current_index]["Filename"])[1]), data_directory, updated_data, outputFile=updated_data['Filename'])
            if os.path.exists(os.path.join(data_directory, updated_data['Filename'])):
                os.remove(os.path.join(data_directory,"temp_for_rename"+os.path.splitext(data[current_index]["Filename"])[1]))
            else:
                os.rename(os.path.join(data_directory,"temp_for_rename"+os.path.splitext(data[current_index]["Filename"])[1]),os.path.join(data_directory,updated_data["Filename"]))
            show_clip_details(updated_data,data,current_index,data_directory)

            # Save the modified data to the data list
            data[current_index] = updated_data

            # Save the data list to the JSON file
            with open(data_file_path, "w") as file:
                json.dump(data, file, indent=4)

            # Clear any existing validation error messages
            display_validation_errors([])
            messagebox.showinfo("Sava Data Complete", "Changes saved to "+data_file_path,icon=messagebox.INFO,parent=clip_editor)

    def validate_clip_data(clip_data, all_data, data_file_path):
        global current_index
        validation_errors = []

        # Check if any field is empty
        for key, value in clip_data.items():
            if not value:
                validation_errors.append(f"Field '{key}' cannot be empty.")
        # Check frame range validation
        frame_range_str = clip_data["Frame Range"]
        
        #frame_range_str = frame_range_str.strip('()')  
        start_frame_str, end_frame_str = frame_range_str
        new_start_frame = int(start_frame_str)
        new_end_frame = int(end_frame_str)
        clip_data["Frame Range"] = [new_start_frame,new_end_frame]
        try:
            clip_data["Length (seconds)"] = float(clip_data["Length (seconds)"])
        except:
            pass
        #print(dict(sorted(clip_data.items())))
        #print(dict(sorted(all_data[0].items())))
        for i, data in enumerate(all_data):
            if data['Frame Range'] == clip_data['Frame Range']:
                continue
            start_frame = int(data["Frame Range"][0])
            end_frame = int(data["Frame Range"][1])

            if data != clip_data and start_frame < new_end_frame and end_frame > new_start_frame:
                validation_errors.append("Frame range overlaps with another entry.")
        if os.path.exists(os.path.join(data_file_path,clip_data['Filename'])) and clip_data['Filename'] != updated_data['Filename']:
            if os.path.exists(os.path.join(data_file_path,updated_data['Filename'])):
                validation_errors.append("Cannot change filename, file already exists")
        # Check air date format (YYYY-MM-DD)
        air_date = clip_data.get("Air Date")
        try:
            datetime.datetime.strptime(air_date, "%Y-%m-%d")
        except ValueError:
            validation_errors.append("Air Date should be in the format 'YYYY-MM-DD'.")

        return validation_errors
        
    def save_to_json(video_player):
        global tape_data, current_index, data

        # Update the data list with the modified values from the entry fields
        new_entry = {}
        for widget, key in reversed(entry_widget_mapping):
            entry_value = widget.get().strip()
            if key in ["ID", "Order on Tape"]:
                try:
                    entry_value = int(entry_value)  # Convert to integer if it's ID or Order on Tape
                except ValueError:
                    messagebox.showerror("Validation Error", f"Order on Tape value must be an integer: {entry_value}",icon=messagebox.ERROR)
                    return
            new_entry[key] = entry_value

        validation_errors = validate_data(new_entry, tape_data)

        if validation_errors:
            # Display validation errors and prevent saving
            messagebox.showerror("Validation Error", "\n".join(validation_errors),icon=messagebox.ERROR)
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

        # Find the index of the current entry in the tape_data list
        current_index = tape_data.index(new_entry)

        # Update the current index and show the new entry details
        video_player.stop()
        show_item_details(tape_data[current_index], tape_data, current_index)

        messagebox.showinfo("Save Successful", "Data saved successfully.",icon=messagebox.INFO,parent=gui)

    def validate_data(entry_data, data):
        global current_index
        validation_errors = []
        tape_id = entry_data["Tape_ID"]
        segment_start = entry_data["Segment Start"]
        segment_end = entry_data["Segment End"]
        order_on_tape = str(entry_data["Order on Tape"])

        for entry in data:
            if entry["Tape_ID"] == tape_id and entry["ID"] != entry_data["ID"]:
                if str(entry["Order on Tape"]) == order_on_tape:
                    validation_errors.append("Duplicate Order on Tape value with Tape ID: {}".format(tape_id))
                    break
                else:
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
        if not re.match(date_pattern, entry_data["Recording Date"]) and entry_data["Recording Date"] != "Unknown":
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
        if gui:
            interface = gui
        elif clip_editor:
            interface = clip_editor
        for widget in interface.grid_slaves():
            if isinstance(widget, tk.Label) and widget.cget("foreground") == "red":
                widget.destroy()
            
        # Display validation errors in the GUI
        error_row = len(data) + 5
        for error in validation_errors:
            error_label = tk.Label(interface, text=error, foreground="red")
            error_label.grid(row=error_row, column=0, columnspan=3, padx=10, pady=5, sticky="w")
            error_row += 1


    def on_selection_changed():
        selection = selection_var.get()
        if selection == "file":
            filename_button.grid(row=0, column=4, columnspan=4, sticky=tk.SW, pady=1)
            directory_button.grid_forget()
        elif selection == "directory":
            directory_button.grid(row=0, column=4, columnspan=4, sticky=tk.SW, pady=1)
            filename_button.grid_forget()

    def close_video_player():
        global video_player
        if video_player:
            video_player.stop()
            video_player = None

    def show_unidentified_clips(unidentified_videos, data, data_dir, current_index):
        global clip_navigator
        global start_frame_var
        global end_frame_var
        launchloop = False

        # Destroy the existing window if it exists
        if clip_navigator is None:
            clip_navigator = tk.Toplevel()
            clip_navigator.title("Unidentified Clip Navigator")
            clip_navigator.iconbitmap(tv_ico)
            clip_navigator.geometry("966x850")
            launchloop = True

        if not clip_navigator:
            return

        if clip_navigator.winfo_exists():
            for widget in clip_navigator.grid_slaves():
                widget.destroy()

        # Clear existing widgets
        for widget in clip_navigator.grid_slaves():
            widget.grid_forget()
        
        tape_id_from_file = os.path.basename(unidentified_videos[current_index]).rsplit('_',1)[0]
        frame_offset_from_file = int(os.path.basename(unidentified_videos[current_index]).rsplit('_',1)[1].split('-')[0])

        video_player, volume_frame, control_frame, time_label = show_video_player(
            clip_navigator, unidentified_videos[current_index], {"Tape ID": tape_id_from_file}, frame_offset_from_file
        )

        # Function to update the entry widgets
        def update_entry_widgets():
            time.sleep(0.2)
            frame_rate = video_player.player.get_fps()
            try:
                start_ms = int(start_frame_var.get())/frame_rate*1000
                # Update the start and end frame entry widgets
                video_player.start_frame_var.set(start_frame_var.get())
                video_player.start_ms_var.set(start_ms)
                video_player.start_frame_entry.update()
            except:
                pass
            try:
                end_ms = int(end_frame_var.get())/frame_rate*1000
                video_player.end_frame_var.set(end_frame_var.get())
                video_player.end_ms_var.set(end_ms)
                video_player.end_frame_entry.update()
            except:
                pass

        # Extract Tape ID and Frame Range from the filename
        filename = os.path.basename(unidentified_videos[current_index])
        tape_id, frame_range = filename.split("_")[0], filename.split("_")[1].split(".")[0]
        start_frame, end_frame = map(int, frame_range.split("-"))
        time.sleep(0.2)
        # Calculate length in seconds using the video frame rate (if available)
        video_frame_rate = video_player.player.get_fps()
        if video_frame_rate is not None:
            try:
                length_in_seconds = (end_frame - start_frame + 1) / video_frame_rate
            except ZeroDivisionError:
                time.sleep(0.5)
                length_in_seconds = (end_frame - start_frame + 1) / video_frame_rate
        else:
            length_in_seconds = None

        # Create labels and entry widgets for the required key-value pairs
        keys = ["Tape ID", "Frame Range", "Programs", "Recording Date", "Network/Station", "Location"]
        entry_widgets = []
        clip_widget_mapping = []
        for i, key in enumerate(keys):
            label = tk.Label(clip_navigator, text=key)
            label.grid(row=i, column=0, padx=10, sticky="e")

            value = tk.StringVar()

            if key == "Tape ID":
                value.set(tape_id)
            elif key == "Frame Range":
                value.set(f"{start_frame} - {end_frame}")
            elif key == "Length (seconds)":
                value.set(length_in_seconds) if length_in_seconds is not None else value.set("")
            else:
                # For other keys, search for matching value based on frame range
                matching_value = ""
                for item in data:
                    if item["Tape_ID"] == tape_id:
                        segment_start_str = item.get("Segment Start", "")
                        segment_end_str = item.get("Segment End", "")
                        try:
                            segment_start = datetime.datetime.strptime(segment_start_str, "%H:%M:%S")
                            segment_end = datetime.datetime.strptime(segment_end_str, "%H:%M:%S")
                            frame_rate = video_player.player.get_fps()
                            start_time = datetime.timedelta(seconds=start_frame / frame_rate)
                            end_time = datetime.timedelta(seconds=end_frame / frame_rate)

                            # Convert segment_start and segment_end to timedelta objects
                            segment_start = datetime.timedelta(hours=segment_start.hour, minutes=segment_start.minute, seconds=segment_start.second)
                            segment_end = datetime.timedelta(hours=segment_end.hour, minutes=segment_end.minute, seconds=segment_end.second)

                            if start_time >= segment_start and end_time <= segment_end:
                                matching_value = item.get(key, "")
                                break
                        except ValueError:
                            pass
                value.set(matching_value)

            entry = tk.Entry(clip_navigator, textvariable=value, state="disabled", width=60)
            entry.grid(row=i, column=1, columnspan=2, padx=10, sticky="nsew")
            entry_widgets.append(entry)
            clip_widget_mapping.append((value, key))  # Store the mapping between StringVar object and key

        # Adjust column widths to accommodate the widgets
        clip_navigator.grid_columnconfigure(0, weight=1)
        clip_navigator.grid_columnconfigure(1, weight=3)

        # Create a list of video filenames for the dropdown menu
        video_filenames = [os.path.basename(file) for file in unidentified_videos]

        # Create the dropdown menu
        video_selection_var = tk.StringVar()
        video_selection_var.set(video_filenames[current_index])  # Set the default selection
        video_dropdown = ttk.Combobox(clip_navigator, textvariable=video_selection_var, values=video_filenames, state="readonly")
        video_dropdown.grid(row=len(keys), column=1, columnspan=2, padx=10, pady=5, sticky="nsew")
        video_dropdown.set(video_filenames[current_index])

        # Function to handle the video selection from the dropdown
        def on_video_selected(event):
            nonlocal current_index  # Use nonlocal to update the current_index in the outer function scope
            nonlocal video_player
            
            video_player.stop()
            video_player = None
            selected_video = video_dropdown.get()
            current_index = video_filenames.index(selected_video)
            show_unidentified_clips(unidentified_videos, data, data_dir, current_index)
            video_selection_var.set(selected_video)

        # Bind the event handler to the dropdown selection
        video_dropdown.bind("<<ComboboxSelected>>", on_video_selected)

        # Create a dictionary to map the option names to the corresponding subdirectories
        options_mapping = {
            "Ready to Identify": "",
            "Recut Needed": "_recut",
            "Do Not Identify": "_hold"
        }

        # Function to handle the option selection
        def update_option(selected_option):
            nonlocal current_index
            nonlocal video_player
            subdirectory = options_mapping[selected_option]
            if subdirectory:
                # Ask for confirmation before moving the file
                confirmation = messagebox.askyesno(
                    "Confirmation",
                    f"Are you sure you want to move the file to the '{selected_option}' subdirectory?",
                    icon=messagebox.QUESTION,
                    parent=clip_navigator
                )

                if confirmation:
                    # Move the file to the corresponding subdirectory if selected
                    video_player.stop()
                    video_player = None
                    file_to_move = unidentified_videos[current_index]
                    new_path = os.path.join(os.path.dirname(file_to_move), subdirectory, os.path.basename(file_to_move))
                    os.makedirs(os.path.dirname(new_path), exist_ok=True)
                    os.rename(file_to_move, new_path)
                    # Remove the moved file from the video list
                    del unidentified_videos[current_index]
                    # Update the navigation buttons and labels
                    if current_index >= len(unidentified_videos):
                        # If current_index is out of range, set it to the last index
                        current_index = len(unidentified_videos) - 1

                    # Show the next clip or close the window if there are no more clips
                    if current_index >= 0:
                        show_unidentified_clips(unidentified_videos, data, data_dir, current_index)
                    else:
                        # No more clips left, close the window
                        clip_navigator_close(video_player)

        # Create a frame to hold the buttons
        button_frame = tk.Frame(clip_navigator)
        button_frame.grid(row=len(keys)+1, column=1, columnspan=1, padx=30, pady=10, sticky="e")

        # Create the buttons with the options (excluding "Ready to Identify")
        for i, option in enumerate(options_mapping.keys()):
            if option != "Ready to Identify":
                button = tk.Button(button_frame, text=option, command=lambda option=option: update_option(option))
                button.grid(row=0, column=i, padx=5)

        # Buttons to navigate back and forth
        def to_previous_clip():
            nonlocal current_index
            nonlocal video_player
            video_player.stop()
            video_player = None
            start_frame = start_frame_var.get()
            end_frame = end_frame_var.get()
            if current_index > 0:
                current_index -= 1
                video_player = show_unidentified_clips(unidentified_videos, data, data_dir, current_index)
                update_entry_widgets()
                start_frame_var.set(start_frame)
                end_frame_var.set(end_frame)

        def to_next_clip():
            nonlocal current_index
            nonlocal video_player
            video_player.stop()
            video_player = None
            start_frame = start_frame_var.get()
            end_frame = end_frame_var.get()
            if current_index < len(unidentified_videos) - 1:
                current_index += 1
                video_player = show_unidentified_clips(unidentified_videos, data, data_dir, current_index)
                update_entry_widgets()
                start_frame_var.set(start_frame)
                end_frame_var.set(end_frame)
            
        def update_current_clip():
            show_unidentified_clips(unidentified_videos, data, data_dir)

            # Extract Tape ID and Frame Range from the filename
            filename = os.path.basename(unidentified_videos[current_index])
            tape_id, frame_range = filename.split("_")[0], filename.split("_")[1].split(".")[0]
            start_frame, end_frame = map(int, frame_range.split("-"))

            # Calculate length in seconds using the video frame rate (if available)
            video_frame_rate = video_player.player.get_fps()
            if video_frame_rate is not None:
                length_in_seconds = (end_frame - start_frame + 1) / video_frame_rate
            else:
                length_in_seconds = None

            for i, key in enumerate(keys):
                value = tk.StringVar()
                if key == "Tape ID":
                    value.set(tape_id)
                elif key == "Frame Range":
                    value.set(f"({start_frame}) - ({end_frame})")
                elif key == "Length (seconds)":
                    value.set(length_in_seconds) if length_in_seconds is not None else value.set("")
                else:
                    value.set("")  # For other keys, set an empty value for now

                entry_widgets[i].config(textvariable=value)

        prev_button = tk.Button(clip_navigator, text="Previous Clip", command=to_previous_clip)
        prev_button.grid(row=len(keys) + 1, column=0, padx=10, pady=10, sticky="nsew")

        next_button = tk.Button(clip_navigator, text="Next Clip", command=to_next_clip)
        next_button.grid(row=len(keys) + 1, column=2, padx=10, pady=10, sticky="e")

        # Check if the current item is the first or last one
        is_first_item = current_index == 0
        is_last_item = current_index == len(unidentified_videos) - 1

        # Disable the previous button if it's the first item
        prev_button.config(state=tk.DISABLED if is_first_item else tk.NORMAL)

        # Disable the next button if it's the last item
        next_button.config(state=tk.DISABLED if is_last_item else tk.NORMAL)

        video_player.grid(row=len(keys) + 3, column=1, columnspan=1, rowspan=3, padx=1, pady=1, sticky="nsew")
        volume_frame.grid(row=len(keys) + 3, column=2)
        time_label.grid(row=len(keys) + 7, column=1)
        control_frame.grid(row=len(keys) + 8, column=0, columnspan=3, sticky=tk.S)

        def clip_navigator_close(video_player):
            global clip_navigator
            if video_player:
                video_player.stop()
            clip_navigator.destroy()
            clip_navigator = None

        # Bind the window close event to set `clip_navigator` to None
        clip_navigator.protocol("WM_DELETE_WINDOW", lambda: clip_navigator_close(video_player))

        # Run the Tkinter event loop for the window
        if launchloop:
            clip_navigator.mainloop()
        return video_player

    print("Launching GUI")
    if "ytuploader" not in sys.modules:
        import ytuploader
    window = tk.Tk()
    window.title("VHS Tools")
    window.geometry("1000x1000")
    
    menu_bar = tk.Menu(window)
    help_menu = tk.Menu(menu_bar, tearoff=0)
    edit_menu = tk.Menu(menu_bar, tearoff=0)
    file_menu = tk.Menu(menu_bar, tearoff=0)
    tapeid_menu = tk.Menu(menu_bar, tearoff=0)
    
    menu_bar.configure(background="lightgrey")
    help_menu.add_command(label="About", command=show_about_dialog)
    
    window.config(menu=menu_bar)
    window.iconbitmap(tv_ico)
    
    for i in range(20):
        window.grid_rowconfigure(i,weight=1,uniform="equal")
        window.grid_columnconfigure(i,weight=1,uniform="equal")

    # Creating a dictionary of options for the dropdown menu
    script_to_run = {
        "Scanner": [],
        "Splitter": [],
        "Audio Normalizer": [],
        "Identifier": [],
        "Archiver": ["Video","Clip"],
        "YouTube Uploader": ["Video","Clip"],
    }

    # Create a text box to display the output
    output_text = scrolledtext.ScrolledText(window, background="black", foreground="lime", height=25, wrap ="word")
    output_text.grid(row=13, column=0, columnspan=20, rowspan=7, sticky=tk.NSEW)
    window.grid_propagate(0)
    redirector = redirect_console_output(output_text)
    banner()
    # Creating a variable to store the selected option
    selected_script = tk.StringVar()
    selected_script.trace('w', update_button_state)  # Call update_button_state when the selected_script changes
    labeltext = selected_script.get()
    if labeltext not in script_to_run.keys():
        labeltext = "Select an Operation to Start"
    elif selected_script.get() != "Archiver":
        labeltext = selected_script.get()
    else:
        if is_clip == True:
            labeltext = selected_script + " - Clip(s) Upload!"
        elif is_video == True:
            labeltext = selected_script + " - Full Video(s) Upload!"
    selected_script_label = redirector.selected_script_label
    
    script_selection = tk.Menu(menu_bar, tearoff=0)
    description_label = redirector.description_label
    
    for script in script_to_run.keys():
        if script == "YouTube Uploader":
            archiver_submenu = tk.Menu(script_selection, tearoff=0)
            
            archiver_submenu.add_radiobutton(label="Full Video Upload", variable=selected_script, value="YouTube Uploader", command=lambda: on_youtuber_select("Full Video"))
            archiver_submenu.add_radiobutton(label="Clip Upload", variable=selected_script, value="YouTube Uploader", command=lambda: on_youtuber_select("Clip"))
            script_selection.add_cascade(label="YouTube Uploader", menu=archiver_submenu)
        elif script == "Archiver":
            archiver_submenu = tk.Menu(script_selection, tearoff=0)
            
            archiver_submenu.add_radiobutton(label="Full Video Upload", variable=selected_script, value="Archiver", command=lambda: on_archiver_select("Full Video"))
            archiver_submenu.add_radiobutton(label="Clip Upload", variable=selected_script, value="Archiver", command=lambda: on_archiver_select("Clip"))
            script_selection.add_cascade(label="Archiver", menu=archiver_submenu)
        else:
            script_selection.add_radiobutton(label=script, variable=selected_script, value=script, command=update_button_state)

    # Create a progress variable to store the progress value
    progress_var = redirector.progress_var
    progress_label = redirector.progress_label
    progress_widget = redirector.progress_widget

    # Disable Menu Options for operations that have not been configured yet
    #script_selection.entryconfig("Metatagger", state=tk.DISABLED)
    #script_selection.entryconfig("Video Editor", state=tk.DISABLED)
    
    menu_bar.add_cascade(label="File", menu=file_menu)
    menu_bar.add_cascade(label="Edit", menu=edit_menu)
    menu_bar.add_cascade(label="Operations", menu=script_selection)
    menu_bar.add_cascade(label="Help", menu=help_menu)
    
    checkboxes = []
    selection_var = tk.StringVar(value="file")
    file_menu.add_command(label="Open File...", command=select_file, state=tk.DISABLED)
    filename_var = tk.StringVar()
    
    descriptions = {}
    descriptions["Scanner"] = "Scan digitized VHS content for brightness and audio levels"
    descriptions["Splitter"] = "Split video into clips based on brightness and audio levels"
    descriptions["Audio Normalizer"] = "Normalizes audio levels, setting the peak level to 0dB"
    descriptions["Identifier"] = "Identifies video clip content using AI tools and context from the Tape Data"
    descriptions["Archiver"] = "Upload a full digitized file or clip to the Internet Archive"
    descriptions["YouTube Uploader"] = "Upload a full digitized file or clip to YouTube."
    
    directory_var = tk.StringVar()
    file_menu.add_command(label="Open Directory...", command=choose_directory, state=tk.DISABLED)

    file_menu.add_command(label="Open Clip Data File...", command=lambda: browse_file(json_file_selection), state=tk.DISABLED)
    
    selected_script.trace("w", lambda *args: update_arguments(*args, selected_script=selected_script, descriptions=descriptions))

    label_label = redirector.label_label
    selected_file_label = redirector.selected_file_label

    json_file_selection = redirector.json_file_selection
    json_file_selection.set('')
    json_file_label_var = redirector.json_file_label_var
    json_file_label_var.set('')
    json_file_label = redirector.json_file_label
    json_file_entry = redirector.json_file_entry
    action_label = redirector.action_label

    '''stop_button = tk.Button(window, text="ABORT!", command=stop_execution)
    stop_button.grid(row=2, column=18, columnspan=2, padx=10, sticky=tk.N) ''' 

    launch_button = tk.Button(window, text="Start", command=lambda: launch_script(selected_script.get(),output_text,redirector,window))
    launch_button.grid(row=0, column=18, columnspan=2, padx=10, sticky=tk.NSEW)
    launch_button.config(state=tk.DISABLED)

    # Load the JSON data from the file
    with open(json_file, "r") as json_data:
        data = json.load(json_data)

    tape_ids = list(set(entry["Tape_ID"] for entry in data))
    tape_ids = sorted(tape_ids, key=lambda x: int(''.join(filter(str.isdigit, x))))
    
    current_index = 0

    letters = defaultdict(list)
    for tid in tape_ids:
        abc = tid[:3].upper()
        letters[abc].append(tid)

    edit_menu.add_command(label="Add New Tape...", command=lambda: on_tape_id_selected(None))

    submenus = {}

    for key, value in letters.items():
        submenu = tk.Menu(edit_menu, tearoff=0)
        for tid in value:
            submenu.add_command(label=tid, command=lambda tid=tid: on_tape_id_selected(tid))
        submenus[key] = submenu

    # Create the main submenu 'Edit Tape Data' to contain the letter submenus
    tapeid_menu = tk.Menu(edit_menu, tearoff=0)

    # Add each letter submenu to the 'Edit Tape Data' submenu
    for key, submenu in submenus.items():
        tapeid_menu.add_cascade(label=key, menu=submenu)

    # Add the 'Edit Tape Data' submenu to the main 'edit_menu'
    edit_menu.add_cascade(label="Edit Tape Data", menu=tapeid_menu)

    #for tid in tape_ids:
    #    tapeid_menu.add_command(label=tid, command=lambda tid=tid: on_tape_id_selected(tid))
    #edit_menu.add_cascade(label="Edit Tape Data", menu=tapeid_menu)
 
    edit_menu.add_command(label="Edit Clip Data...", command=edit_clip_data)
    edit_menu.add_command(label="View Unidentified Clips...", command=view_clip_data)
    
    # Function to handle window close event
    def on_window_close(kill=False):
        global window
        if kill == True:
            stop_execution()
        window.destroy()
        window = None
        return None
    window.protocol("WM_DELETE_WINDOW", lambda: on_window_close(kill=True))
    
    # Run the GUI event loop
    window.mainloop()
    sys.stdout = sys.__stdout__