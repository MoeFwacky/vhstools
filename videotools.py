import argparse
import datetime
import io
import os
import ray
import re
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
        if s.lstrip().startswith("chunk:"):
            self.progress_widget['maximum'] = 100
            self.update_progress_mp(s)
            return
        elif s.lstrip().startswith("MoviePy") or s.lstrip().startswith("[ACTION]"):
            self.action_label.config(text=s.strip().replace("MoviePy - ","").replace("[ACTION] ",""))
            if "MoviePy" and "Done" in s.lstrip():
                self.progress_widget['value'] = self.progress_widget['maximum']
                self.progress_widget.update()
            return
        # Write to the console
        #sys.__stdout__.write(s)
        if len(s.strip()) == 0 or s.strip() == "\n":
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
        parts = output.split("chunk:")
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
        action_label.config(text=f"Complete in {int(time_minutes):d} minutes, {int(time_seconds):d} seconds")
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
        action_label.config(text=f"Complete in {int(time_minutes):d} minutes, {int(time_seconds):d} seconds")
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
        action_label.config(text=f"Complete in {int(time_minutes):d} minutes, {int(time_seconds):d} seconds")
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

def select_file():
    selected_option = selected_script.get()
    filetypes = []
    
    if selected_option in ["Scanner", "Splitter", "Identifier", "Metatagger", "Archiver", "Vid2Social", "SocialBot"]:
        filetypes = (
            ('Video Files', '*.mp4;*.avi;*.mkv;*.m4v'),
            ('All Files', '*.*')
        )
    elif selected_option in ["Video Editor"]:
        filetypes = (
            ('JSON Files', '*.json'),
            ('All Files', '*.*')
        )
    else:
        filename_button.config(state=tk.DISABLED)
        launch_button.config(state=tk.DISABLED)
    filepath = filedialog.askopenfilename(filetypes=filetypes)
    selected_file_label.config(text=filepath)
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

    # Create a progress variable to store the progress value
    progress_var = tk.IntVar()
    # Create a label to display the progress status text
    progress_label = tk.Label(window, text=" ")
    progress_label.grid(row=4, column=9, columnspan=12, sticky=tk.W)
    progress_widget = ttk.Progressbar(window, variable=progress_var, orient=tk.HORIZONTAL, length=500, mode='determinate')
    progress_widget.grid(row=4, column=0, columnspan=18, sticky=tk.SW)
    
    action_label.config(text="Starting "+selected_script)
    #print("Redirecting console output to the GUI text box...")
    redirector = redirect_console_output(output_text,progress_widget=progress_widget,progress_label=progress_label,action_label=action_label)

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
    print("Launching GUI")
    window = tk.Tk()
    window.title("Video Tools")
    window.geometry("1200x450")
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
    
    def on_selection_changed():
        selection = selection_var.get()
        if selection == "file":
            filename_button.grid(row=0, column=4, columnspan=4, sticky=tk.SW, pady=1)
            directory_button.grid_forget()
        elif selection == "directory":
            directory_button.grid(row=0, column=4, columnspan=4, sticky=tk.SW, pady=1)
            filename_button.grid_forget()
    
    radio_file = tk.Radiobutton(window, text="File", variable=selection_var, value="file", command=on_selection_changed)
    radio_file.grid(row=0, column=2, columnspan=2, sticky=tk.S, padx=5, pady=5)

    radio_directory = tk.Radiobutton(window, text="Directory", variable=selection_var, value="directory", command=on_selection_changed)
    radio_directory.grid(row=1, column=2, columnspan=2, sticky=tk.N, padx=5)

    directory_var = tk.StringVar()
    directory_button = tk.Button(window, text="Browse", command=choose_directory)
    directory_button.config(state=tk.DISABLED)

    selected_script.trace("w", lambda *args: update_arguments(*args, selected_script=selected_script))

    selected_file_label = tk.Label(window)
    selected_file_label.grid(row=0, column=8, columnspan=6, sticky=tk.W)

    action_label = tk.Label(window, text="")
    action_label.grid(row=3, column=0, columnspan=8)

    stop_button = tk.Button(window, text="ABORT!", command=stop_execution)
    stop_button.grid(row=2, column=18, columnspan=2, padx=10, sticky=tk.N)  

    launch_button = tk.Button(window, text="Execute Operation", command=lambda: launch_script(selected_script.get(),output_text, action_label=action_label))
    launch_button.grid(row=0, column=18, columnspan=2, padx=10, sticky=tk.NSEW)
    launch_button.config(state=tk.DISABLED)

    # Create a text box to display the output
    output_text = scrolledtext.ScrolledText(window, background="black", foreground="lime", height=15)
    output_text.grid(row=5, column=0, columnspan=20, rowspan=10, sticky=tk.NSEW)
    window.grid_propagate(0)
    
    def on_window_close():
        stop_execution()
        window.destroy()
    window.protocol("WM_DELETE_WINDOW", on_window_close)
    # Run the GUI event loop
    window.mainloop()
    sys.stdout = sys.__stdout__