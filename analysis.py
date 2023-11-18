import base64
import configparser
import cv2
import datetime
#import enchant
import io
import json
import moviepy.editor as mp
import noisereduce as nr
import numpy as np
import openai
import metatagger
import librosa
#import nltk
import os
import PIL
import pytesseract
import re
import shutil
import sys
import time
import tkinter as tk
import torch
import torchvision.transforms as transforms
import tqdm
import traceback
import urllib.request
import vlc
#from alive_progress import alive_bar
from difflib import SequenceMatcher
from google.cloud import vision
from moviepy.editor import AudioFileClip
#from nltk.corpus import words
from openai import RateLimitError
from skimage.metrics import structural_similarity as ssim
#from spellchecker import SpellChecker
from tkinter import ttk
from torch import hub
#from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor #Wav2Vec2Tokenizer 

scriptPath = os.path.realpath(os.path.dirname(__file__))
config = configparser.ConfigParser()
config.read(os.path.join(scriptPath,'config.ini'))
json_file = config['directories']['json file']

openai_client = openai.OpenAI(api_key=config['analysis']['openai api key'])
openai_client.api_key = config['analysis']['openai api key']
#nltk.download('words')

# Define the transformation to apply to video frames
transform = transforms.Compose([
    transforms.ToPILImage(),
    transforms.Resize((112, 112)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.43216, 0.394666, 0.37645], std=[0.22803, 0.22145, 0.216989])
])

# Set up Tesseract OCR
#pytesseract.pytesseract.tesseract_cmd = config['analysis']['tesseract executable']
#tesseract_config = f"--psm 3 -l eng"  # Set language to English
#ocr_confidence = float(config['analysis']['tesseract confidence'])

#spell = SpellChecker()

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
        new_position_ms = current_position_ms + step_ms*x
        if new_position_ms <= duration_ms:
            self.player.set_time(new_position_ms)
        self.update_progress()

    def go_backward_x_percent(self,x=1):
        duration_ms = self.player.get_length()
        step_ms = duration_ms // 100  # 1% of the video duration in milliseconds
        current_position_ms = self.player.get_time()
        new_position_ms = current_position_ms - step_ms*x
        if new_position_ms >= 0:
            self.player.set_time(new_position_ms)
        self.update_progress()

    def set_volume(self, volume):
        self.player.audio_set_volume(volume)

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
    #volume_scale.set(75)  # Set initial volume
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
    '''start_frame_var = tk.StringVar()
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
    create_new_clip_button.grid(row=1, column=6, padx=5, pady=5)'''

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

def enhance_edges(image):
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Apply Gaussian blur
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Perform histogram equalization
    equalized = cv2.equalizeHist(blurred)
    
    # Apply adaptive thresholding
    threshold = cv2.adaptiveThreshold(equalized, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 11, 2)
    
    # Perform morphological operations (optional)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    morphed = cv2.morphologyEx(threshold, cv2.MORPH_CLOSE, kernel)
    
    return morphed

def is_frame_similar(frame1, frame2, threshold):
    # Convert frames to grayscale
    frame1_gray = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    frame2_gray = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)

    # Calculate SSIM score between frames
    score = ssim(frame1_gray, frame2_gray)

    # If the SSIM score is above the threshold, frames are considered similar
    return score >= threshold

def perform_local_text_detection(frame):
    # Convert the frame to grayscale for better text recognition
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Apply image preprocessing techniques if necessary (e.g., thresholding, denoising)

    # Perform text detection using Tesseract OCR
    text = pytesseract.image_to_string(gray)

    # Return the detected text if any
    if text.strip():
        return text.strip()
    else:
        return None

def label_detection(client, image_content, is_vision_image=False):
    if is_vision_image == False:
        _, frame_bytes = cv2.imencode('.jpg', image_content)
        image = vision.Image(content=frame_bytes.tobytes())
    else:
        image = image_content
    response = client.label_detection(image=image)
    if response.error.message:
        raise Exception(
            '{}\nFor more info on error messages, check: '
            'https://cloud.google.com/apis/design/errors'.format(
                response.error.message))
        return None
    else:
        labels = response.label_annotations
        label_descriptions = [label.description for label in labels if label.score >= 0.9]
        return label_descriptions

def logo_detection(client, image_content, is_vision_image=False):
    if is_vision_image == False:
        _, frame_bytes = cv2.imencode('.jpg', image_content)
        image = vision.Image(content=frame_bytes.tobytes())
    else:
        image = image_content
    response = client.logo_detection(image=image)
    if response.error.message:
        raise Exception(
            '{}\nFor more info on error messages, check: '
            'https://cloud.google.com/apis/design/errors'.format(
                response.error.message))
        return None
    else:
        logos = response.logo_annotations
        logo_descriptions = [logo.description for logo in logos if logo.score >= 0.9]
        return logo_descriptions

def detect_text_in_video(video_path, frames, x, y, similarity_threshold,client,redirector=None):
    print("[ACTION] Extracting text from the video")
    if redirector != None:
        redirector.progress_var.set(0)
        redirector.progress_widget['maximum'] = len(frames)
        redirector.progress_label.config(text="")
    frame_count = len(frames)
    text = []
    prev_texts = []
    logo_descriptions = []
    prev_frame = None  # Store the previous frame
    prev_f = -50
    count = 0
    #spell_checker = SpellChecker()
    batch_size = 1
    start_time = time.time()
    p = 0
    #with alive_bar(frame_count, force_tty=False) as bar:
    for f, frame in enumerate(frames):
        if f <= 5:
            if redirector != None:
                p+=1
                progress_list = get_eta(start_time,p,frame_count)
                progress(redirector.progress_widget,p,batch_size,redirector.progress_label,progress_list,redirector.progress_var)
            #bar()
            continue
        if prev_frame is not None:
            if is_frame_similar(frame, prev_frame, similarity_threshold) or prev_f > f-25:
                # Skip text detection if the frame is similar to the previous frame
                if redirector != None:
                    p+=1
                    progress_list = get_eta(start_time,p,frame_count)
                    progress(redirector.progress_widget,p,batch_size,redirector.progress_label,progress_list,redirector.progress_var)
                #bar()
                continue
        detected_text = perform_local_text_detection(frame)
        if detected_text:
            #print("Text Detected!")
            prev_f = f
            
            # Convert frame to bytes
            _, frame_bytes = cv2.imencode('.jpg', frame)
            frame_image = vision.Image(content=frame_bytes.tobytes())

            logo_set = set(logo_descriptions)
            logo_data = set(logo_detection(client, frame_image, is_vision_image=True))
            count += 1
            logo_descriptions = list(logo_set.union(logo_data))

            response = client.text_detection(image=frame_image)
            count += 1
            frame_text_data = response.text_annotations
            if response.error.message:
                raise Exception(
                    '{}\nFor more info on error messages, check: '
                    'https://cloud.google.com/apis/design/errors'.format(
                        response.error.message))
            elif frame_text_data != []:
                frame_text = frame_text_data[0].description.replace('\n',' ').strip()
                frame_text = re.sub(r'[^\w\s\d!"#$%&\'()*+,\-./:;<=>?@[\\]^_`{|}~]', '', frame_text)
                text_width, text_height = cv2.getTextSize(frame_text, cv2.FONT_HERSHEY_SIMPLEX, 1, 2)[0]

                if frame_text != '':
                    frame_words = frame_text.split()
                    real_frame_words = [word for word in frame_words if word.lower() in set(words.words()) or word.isdigit()]
                    if real_frame_words and len(real_frame_words) > 3:
                        filtered_text = ' '.join(real_frame_words)
                        # Check similarity with previous texts
                        similarity_found = any(similarity_ratio(filtered_text, prev_text) >= 0.90 for prev_text in prev_texts)
                        if not similarity_found and len(frames) > 1 and len(filtered_text) > 3:
                            text.append(filtered_text.strip())
                            prev_texts.append(filtered_text.strip())
                            print("[TEXT]: " + filtered_text)
        #bar()
        if redirector != None:
            p+=1
            progress_list = get_eta(start_time,p,frame_count)
            progress(redirector.progress_widget,p,batch_size,redirector.progress_label,progress_list,redirector.progress_var)
        prev_frame = frame  # Update the previous frame
        #video.release()
        #cv2.destroyAllWindows()
    print("[INFO] Detection Usage Count: "+str(count))
    return text, count, logo_descriptions

def similarity_ratio(a, b):
    return SequenceMatcher(None, a, b).ratio()

'''def extract_audio_transcript(audio_file, language):
    model_name = "facebook/wav2vec2-base-960h"
    processor = Wav2Vec2Processor.from_pretrained(model_name, language=language)
    model = Wav2Vec2ForCTC.from_pretrained(model_name)

    desired_sampling_rate = 16000
    waveform, sample_rate = librosa.load(audio_file, sr=desired_sampling_rate)

    # Convert to mono if necessary
    if len(waveform.shape) > 1 and waveform.shape[0] > 1:
        waveform = waveform.mean(axis=0, keepdims=True)

    # Perform noise reduction
    waveform = nr.reduce_noise(y=waveform, sr=sample_rate)
    
    # Preprocess the audio waveform
    input_values = processor(waveform, sampling_rate=sample_rate, return_tensors="pt").input_values

    # Perform speech-to-text inference
    with torch.no_grad():
        logits = model(input_values).logits

    # Decode the predicted tokens
    predicted_ids = torch.argmax(logits, dim=-1)
    transcription = processor.batch_decode(predicted_ids, skip_special_tokens=True)[0]

    return transcription'''

def get_video_metadata(json_file, clip_filename, frame_rate=30):
    # Load the JSON data from the file
    with open(json_file) as file:
        data = json.load(file)

    # Extract the tape ID, start frame, and end frame from the clip filename
    #print(os.path.basename(clip_filename))
    clip_parts = os.path.basename(clip_filename).split('_')
    #print(clip_parts)
    tape_id = clip_parts[0]
    #print(tape_id)
    frame_range = clip_parts[1].split('-')
    #print(frame_range)
    start_frame = int(frame_range[0])
    end_frame = int(frame_range[1].split('.')[0])

    # Find the matching entry in the JSON data
    for entry in data:
        if entry['Tape_ID'] == tape_id:
            segment_start = entry['Segment Start']
            segment_end = entry['Segment End']
            start_time = sum(int(x) * 60 ** i for i, x in enumerate(reversed(segment_start.split(':'))))
            end_time = sum(int(x) * 60 ** i for i, x in enumerate(reversed(segment_end.split(':'))))

            # Convert start and end times to frames
            start_frame_json = int(start_time * frame_rate)
            end_frame_json = int(end_time * frame_rate)

            if start_frame_json <= start_frame and end_frame_json >= end_frame:
                return tape_id, entry['Network/Station'], entry['Programs'], entry['Recording Date'], entry['Location'], start_frame, end_frame

    # Return None if no matching entry is found
    return None

def generate_summary(audio_text,metadata,frames):
    #screen_text_string = '\n'.join(screen_text)
    # Join elements of nested lists, convert all elements to strings
    '''logos = ['\n'.join(item) if isinstance(item, list) else item for item in logos]

    # Flatten the list and convert elements to strings
    logos = [item for sublist in logos for item in sublist]

    logos_string = '\n'.join(logos)'''
    
    video_context = ''
    response = None
    if metadata:
        video_context += "This is the metadata for the program this video clip is from:\n Program: "+metadata[2]+'\nStation: '+metadata[1]+'\n Date Recorded: '+metadata[3]+'\n Tape ID: '+metadata[0]
    '''if screen_text:
        video_context += '\nThe following is text that was detected on screen during the clip, some of it may be repetitive in whole or part:\n'+screen_text_string'''
    if audio_text:
        video_context += '\nThe following text is a transcript of the audio from the video clip\n'+audio_text
    '''if len(logos) > 0:
        video_context += '\nThe following text is a list of logos detected in the video, ignore anything that did not exist before the air date.\n'+logos_string
    if len(labels) > 0:
        video_context += '\nThe following text is a list of labels of objects detected in three frames of the video, at the 10%, 50% and 90% duration points.\n'+logos_string'''
    content = [{"type": "text","text": video_context}]
    for frame in frames:
        content.append({"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{frame}","detail":config['analysis']['vision detail level']}})
    while True:
        try:
            response=openai_client.chat.completions.create(
              model=config['analysis']['gpt model'],
              messages=[
                    {"role": "system", "content": [config['analysis']['chatgpt role']]},
                    {"role": "assistant", "content": content},
                    {"role": "user", "content": [config['analysis']['chatgpt prompt']]}
                ],
                max_tokens=4096,
            )
            break
        except RateLimitError as e:
            print(e)
            retry_at = datetime.datetime.now()+datetime.timedelta(minutes=15)
            retry_at_str = retry_at.strftime('%H:%M:%S')
            print("Retrying at "+retry_at_str)
            time.sleep(900)
    #print(response)
    finish_details = response.choices[0].finish_details['type']
    summary = response.choices[0].message.content
    tokens_used = response.usage.total_tokens
    input_tokens = response.usage.prompt_tokens
    output_tokens = response.usage.completion_tokens
    #print(response)
    return summary, tokens_used, input_tokens, output_tokens, finish_details

def get_eta(start_time,f,total_frames):
    seconds_elapsed = time.time() - start_time
    elapsed_minutes, elapsed_seconds = divmod(seconds_elapsed, 60)
    elapsed_hours, elapsed_minutes = divmod(elapsed_minutes, 60)
    if elapsed_hours > 0:
        time_elapsed = "{:02d}:{:02d}:{:02d}".format(round(elapsed_hours), round(elapsed_minutes), round(elapsed_seconds))
    else:
        time_elapsed = "{:02d}:{:02d}".format(round(elapsed_minutes), round(elapsed_seconds))    
    
    try:
        frames_per_second = f / seconds_elapsed
    except ZeroDivisionError:
        frames_per_second = 0.001
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

def progress(progress_widget,frames_processed,batch_size,progress_label,progress_list,progress_var):
    if progress_widget is not None and frames_processed % batch_size == 0:
        time_elapsed, frames_per_second, time_remaining = progress_list
        #print(frames_processed)
        #print(progress_widget['maximum'])
        percentage_complete = round((frames_processed/progress_widget['maximum'])*100)
        #print(percentage_complete)
        frames_per_second = "{:.2f}".format(frames_per_second)
        
        progress_label.config(text=str(percentage_complete)+'% '+str(frames_processed)+'/'+str(progress_widget['maximum'])+', '+str(time_elapsed)+'<'+time_remaining+', '+ str(frames_per_second+'f/s'))
        progress_widget['value'] = frames_processed
        progress_var.set(frames_processed)
        progress_widget.update()

def analyze_video(video_path,redirector,window=None):
    if window:
        video_player,volume_frame,control_frame,time_label = show_video_player(window,video_path,{"Tape ID": os.path.basename(video_path).split('_')[0]},int(os.path.basename(video_path).split('_')[1].split('-')[0]))
        video_player.grid(row=3, column=5, columnspan=10, rowspan=5, padx=1, pady=1, sticky="nsew")
        volume_frame.grid(row=3, column=17, rowspan=5, columnspan=3)
        time_label.grid(row=8,column=5,columnspan=10)
        control_frame.grid(row=9, column=0, columnspan=20, rowspan=2, sticky=tk.N)
    starting_time = datetime.datetime.now()
    try:
        # Open the video file
        directory, video_file_name = os.path.split(video_path)
        # Get Metadata
        metadata = get_video_metadata(json_file, video_file_name)
        
        if metadata:
            tape_id, station, program, recording_date, location, start_frame, end_frame = metadata
            print(f"Tape ID: {tape_id}")
            print(f"Program: {program}")
            print(f"Station: {station}")
            print(f"Date Recorded: {recording_date}")
            print(f"Location Recorded: {location}")
        else:
            print("[INFO] Metadata not found, applying default values")
            tape_id = "AAA-000"
            station = "UNK"
            recording_date = "1970-01-01"
            program = "Unknown"
            location = "USA"
            start_frame = video_file_name.split('_')[0]
            end_frame = video_file_name.split('_')[1].split('.')[0]
        video = cv2.VideoCapture(video_path)
        assert video.isOpened()

        # Obtain video properties
        x_shape = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
        y_shape = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = video.get(cv2.CAP_PROP_FPS)

        # Create a JSON object to store the results
        output = {"frames": []}
        frames = []
        gray_frames = []
        blurred_frames = []
        threshold_frames = []
        morphed_frames = []
        sharpened_frames = []
        processed_frames = []
        base64_frames = []
        video_name = os.path.basename(video_path)
        video_name = os.path.splitext(video_name)[0]
        print("[INFO] Extracting audio from video using MoviePy")
        audio_file = os.path.join(scriptPath, f"{video_name}.wav")
        video_mp = mp.VideoFileClip(video_path)
        video_mp.audio.write_audiofile(audio_file, verbose=False, logger=None)
        video_duration = video_mp.duration
        video_mp.close()
        wav_size = os.path.getsize(audio_file)
        target_size = 26214400
        
        if wav_size > target_size:
            audio = AudioFileClip(audio_file)
            mp3_file = os.path.join(scriptPath, f"{video_name}.mp3")
            audio.write_audiofile(mp3_file, codec='mp3', bitrate='192k', logger="bar")
            print(f"File compressed to MP3: {mp3_file}")
            print("[ACTION] Extracting audio transcript")
            audio_mp3 = open(os.path.join(scriptPath, f"{video_name}.mp3"), 'rb')
            audio_text = openai_client.audio.transcriptions.create(model="whisper-1", file=audio_mp3)
            audio_mp3.close()            
            os.remove(os.path.join(scriptPath, f"{video_name}.mp3"))
            if redirector != None:
                redirector.progress_widget['value'] = 100
                redirector.progress_label.config(text="")
        else:
            print("[ACTION] Extracting audio transcript")
            if redirector != None:
                redirector.progress_widget['value'] = 0
                redirector.progress_label.config(text="")
            audio_wav = open(os.path.join(scriptPath, f"{video_name}.wav"), 'rb')
            audio_text = openai_client.audio.transcriptions.create(model="whisper-1", file=audio_wav)
            audio_wav.close()
        print("[TRANSCRIPTION] "+audio_text.text)
        os.remove(os.path.join(scriptPath, f"{video_name}.wav"))
        if os.path.exists(os.path.join(scriptPath, f"{video_name}.mp3")):
            os.remove(os.path.join(scriptPath, f"{video_name}.mp3"))
        print("[ACTION] Processing Frames")
        cap = cv2.VideoCapture(video_path)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if redirector != None:
            try:
                redirector.progress_widget['value'] = 0
                redirector.progress_widget['maximum'] = frame_count
                redirector.progress_label.config(text="")
            except Exception as e:
                print("[ERROR] "+str(e))
                pass
        # Preprocess video frames
        transform = transforms.Compose([
            transforms.Resize((112, 112)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])

        batch_size = 1  # Adjust the batch size as needed
        start_time = time.time()
        f = 0
        
        #with alive_bar(frame_count, force_tty=False) as bar:
        while True:
            if redirector != None:
                progress_list = get_eta(start_time,f,frame_count)
                progress(redirector.progress_widget,f,batch_size,redirector.progress_label,progress_list,redirector.progress_var)
            ret, frame = video.read()
            if not ret:
                frame_diff = frame_count - len(frames)
                while frame_diff > 0:
                    #bar()
                    frame_diff -= 1
                break

            # Convert to grayscale
            '''gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Apply Gaussian blur
            blurred = cv2.GaussianBlur(gray, (0, 0), 1)
            equalized = cv2.equalizeHist(blurred)
            # Calculate the sharpening mask
            mask = cv2.addWeighted(gray, 1 + 1.5, equalized, -1.5, 0)
            # Convert mask to color image
            mask = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
            sharpened = cv2.add(frame, mask)
            # Perform histogram equalization
            pil_frame = PIL.Image.fromarray(np.uint8(frame))
            processed = transform(pil_frame)'''
            _, frame_buffer = cv2.imencode('.jpg', frame)
            frame_base64 = base64.b64encode(frame_buffer).decode('utf-8')
            
            # Perform morphological operations (optional)
            #kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            #morphed = cv2.morphologyEx(equalized, cv2.MORPH_CLOSE, kernel)

            '''frames.append(frame)
            gray_frames.append(gray)
            blurred_frames.append(blurred)
            #threshold_frames.append(threshold)
            sharpened_frames.append(sharpened)
            morphed_frames.append(morphed)
            processed_frames.append(processed)'''
            base64_frames.append(frame_base64)
            #bar()
            f += 1
        video.release()
        cap.release()
        progress_list = get_eta(start_time,frame_count,frame_count)
        progress(redirector.progress_widget,frame_count,batch_size,redirector.progress_label,progress_list,redirector.progress_var)
        count = 0
        #text = extract_text_from_video(blurred_frames, x_shape, y_shape)
        '''client = vision.ImageAnnotatorClient()
        text, count, logos = detect_text_in_video(video_path, frames, x_shape, y_shape, 0.9, client,redirector)
        for i, t in enumerate(text):
            print(str(i)+': '+str(t))
        print()'''

        chosen_frames = []
        labels = []
        frame_interval = int(fps*float(config['analysis']['seconds per image']))
        
        for i in range(int(fps), len(base64_frames), frame_interval):
            chosen_frames.append(base64_frames[i])
        
        '''# Calculate frame indices for the desired points
        interval_size = len(frames) // 3
        middle_frame_index = len(frames) // 2
        quarter_frame_index = len(frames) // 10
        three_quarters_frame_index = 9 * len(frames) // 10

        # Choose frames from the calculated indices
        chosen_frames.append(base64_frames[middle_frame_index])
        chosen_frames.append(base64_frames[quarter_frame_index])
        chosen_frames.append(base64_frames[three_quarters_frame_index])'''
    
        '''for choice in chosen_frames:
            logos.append(logo_detection(client, choice))
            detected_labels = label_detection(client, choice)
            for label in detected_labels:
                labels.append(label)
            count += 2
        
        for i, t in enumerate(logos):
            print(str(i)+': '+str(t))        

        for i, t in enumerate(labels):
            print(str(i)+': '+str(t))'''

        video.release()
        #cv2.destroyAllWindows()
        attempt = 0
        while True:
            try:
                attempt += 1
                print("[ACTION] Generating a summary using OpenAI")
                summary, tokens_used, input_tokens, output_tokens, finish_details = generate_summary(audio_text.text, metadata, chosen_frames)
                print("Summary generated with complete code: "+finish_details)
                '''if finish_details == "stop":
                    print(summary)'''
                print("Input Tokens Used: "+str(input_tokens),end='\n\n')
                print("Output Tokens Used: "+str(output_tokens),end='\n\n')
                try:
                    print("Saving API Usage Data")
                    api_usage_json = "api_usage.json"
                    if os.path.exists(api_usage_json):
                        with open(api_usage_json, "r") as jsonfile:
                            existing_api_usage = json.load(jsonfile)
                    else:
                        existing_api_usage = {}
                    current_month_year = datetime.datetime.now().strftime("%Y-%m")
                    chatgpt_usage = int(tokens_used)
                    chatgpt_input = int(input_tokens)
                    chatgpt_output = int(output_tokens)
                    if attempt == 1:
                        whisper_usage = round(video_duration)
                        #vision_usage = count
                    else:
                        whisper_usage = 0
                        #vision_usage = 0
                    
                    if current_month_year in existing_api_usage:
                        month_data = existing_api_usage[current_month_year]
                    else:
                        month_data = {
                            'chatgpt': {
                                'usage': 0,
                                'input': 0,
                                'output': 0,
                                'cost': 0
                            },
                            'whisper': {
                                'usage': 0,
                                'cost': 0
                            }
                        }
                        existing_api_usage[current_month_year] = month_data
                        
                except Exception as e:
                    print("[ERROR]"+str(e))
                    traceback.print_exc()
                
                month_data['chatgpt']['usage'] += chatgpt_usage
                
                try:
                    month_data['chatgpt']['input'] += chatgpt_input
                except:
                    month_data['chatgpt']['input'] = chatgpt_input
                try:
                    month_data['chatgpt']['output'] += chatgpt_output
                except:
                    month_data['chatgpt']['output'] = chatgpt_output
                    
                month_data['whisper']['usage'] += whisper_usage
                #month_data['vision']['usage'] += vision_usage
                
                chatgpt_input_cost = float(config['analysis']['chatgpt input cost'])
                chatgpt_output_cost = float(config['analysis']['chatgpt output cost'])
                
                whisper_cost = float(config['analysis']['whisper cost'])
                '''vision_cost = {
                    'tier1': float(config['analysis']['google vision tier 1']),
                    'tier2': float(config['analysis']['google vision tier 2']),
                    'tier3': float(config['analysis']['google vision tier 3'])
                }
                vision_tier1_limit = 1000
                vision_tier2_limit = 5000000'''
                
                clip_processing_cost = (chatgpt_input_cost * chatgpt_input) + (chatgpt_output_cost * chatgpt_output) + (whisper_cost * whisper_usage)
                
                print("API Usage Cost $"+str(clip_processing_cost))                
                try:
                    month_data['chatgpt']['cost'] = (month_data['chatgpt']['input'] * chatgpt_input_cost) + (month_data['chatgpt']['output'] * chatgpt_output_cost)
                except:
                    month_data['chatgpt']['cost'] = month_data['chatgpt']['usage'] * (chatgpt_input_cost + chatgpt_output_cost)/2
                
                month_data['whisper']['cost'] = month_data['whisper']['usage'] * whisper_cost
                '''if month_data['vision']['usage'] <= vision_tier1_limit:
                    month_data['vision']['cost'] = month_data['vision']['usage'] * vision_cost['tier1']
                elif month_data['vision']['usage'] <= vision_tier2_limit:
                    tier1_cost = vision_tier1_limit * vision_cost['tier1']
                    remaining_uses = month_data['vision']['usage'] - vision_tier1_limit
                    month_data['vision']['cost'] = tier1_cost + remaining_uses * vision_cost['tier2']
                else:
                    tier1_cost = vision_tier1_limit * vision_cost['tier1']
                    tier2_cost = (vision_tier2_limit - vision_tier1_limit) * vision_cost['tier2']
                    remaining_uses = month_data['vision']['usage'] - vision_tier2_limit
                    month_data['vision']['cost'] = tier1_cost + tier2_cost + remaining_uses * vision_cost['tier3']'''

                existing_api_usage[current_month_year] = month_data

                with open(api_usage_json, 'w') as file:
                    json.dump(existing_api_usage, file, indent=4)
                start_pos = summary.find("{")
                end_pos = summary.rfind("}")
                
                if start_pos != -1 and end_pos != -1:
                    json_str = summary[start_pos:end_pos + 1]
                    clip_dict = json.loads(json_str)
                else:
                    clip_dict = json.loads(summary)
                break
            except json.decoder.JSONDecodeError as e:
                print("[ERROR] "+str(e))
                print(summary)
                traceback.print_exc()
                if finish_details != "stop":
                    break
                print("[INFO] Retrying...")
        try:
            clip_dict['Filename'] = str(start_frame)+'_'+re.sub(r'[\\/*?:"<>|]', '',clip_dict['Filename']+os.path.splitext(video_file_name)[1])
            clip_dict['Tape ID'] = tape_id
            clip_dict['Length (seconds)'] = video_duration
            clip_dict['Location'] = location
            clip_dict['Frame Range'] = [start_frame,end_frame]

            print("\nAdding metadata to file and renaming")
            metatagger.createMetadata(video_path, directory,clip_dict,outputFile=clip_dict['Filename'])
            
            # Path to the JSON file
            json_file_path = os.path.join(directory, tape_id + "_Clips.json")

            # Load existing list of dictionaries or initialize an empty list
            if os.path.exists(json_file_path):
                with open(json_file_path, "r") as infile:
                    existing_data = json.load(infile)
            else:
                existing_data = []

            # Add the new dictionary to the list
            existing_data.append(clip_dict)

            # Sort the list of dictionaries by the first value of "Frame Range" key
            sorted_data = sorted(existing_data, key=lambda x: x["Frame Range"][0])

            # Write the updated list of dictionaries back to the JSON file
            with open(json_file_path, "w") as outfile:
                json.dump(sorted_data, outfile, indent=4)

        except Exception as e:
            print("[ERROR]"+str(e))
            traceback.print_exc()
        
        #get time to complete
        end_time = datetime.datetime.now()
        elapsed_time = end_time - starting_time
        time_minutes = elapsed_time.total_seconds() // 60
        time_seconds = elapsed_time.total_seconds() % 60
        #print(f"\nElapsed time: {int(time_minutes):02d}:{int(time_seconds):02d}")
            
        print("\n------------------------------------------------")
        print("Total API Usage and Costs for this month\nChatGPT: "+str(month_data['chatgpt']['usage'])+" "+str(month_data['chatgpt']['cost'])+"\nWhisper: "+str(month_data['whisper']['usage'])+" "+str(month_data['whisper']['cost']))
        print("------------------------------------------------")
        print(f"[ACTION] File Analyisis Complete in {int(time_minutes):d} minutes, {int(time_seconds):d} seconds")
        try:
            for k, v in clip_dict.items():
                print(str(k)+': '+str(v))
            
        except:
            pass
        if video_player.winfo_exists():
            video_player.stop()
            video_player.destroy()
            volume_frame.destroy()
            control_frame.destroy()
            time_label.destroy()
        time.sleep(0.5)
        try:
            if os.path.exists(os.path.join(directory, clip_dict['Filename'])):
                print("Success!")
                unidentified_files_dir = os.path.join(directory,'_unidentified')
                os.makedirs(unidentified_files_dir, exist_ok=True)
                time.sleep(5)
                os.rename(video_path, os.path.join(directory,'_unidentified',os.path.basename(video_path)))
            else:
                print("An error has occurred creating the tagged file")
        except Exception as e:
            print(e)
            traceback.print_exc()
        
    except Exception as e:
        print("[ERROR] "+str(e))
        traceback.print_exc()
        if video_player.winfo_exists():
            video_player.stop()
            video_player.destroy()
            volume_frame.destroy()
            control_frame.destroy()
            time_label.destroy()
    print("------------------------------------------------\n")
