import configparser
import cv2
import datetime
import enchant
import io
import json
import moviepy.editor as mp
import noisereduce as nr
import numpy as np
import openai
import metatagger
import librosa
import nltk
import os
import PIL
import pytesseract
import re
#import speech_recognition as sr
import sys
import time
import tkinter as tk
import torch
#import torchvision
import torchvision.transforms as transforms
import traceback
import urllib.request
from alive_progress import alive_bar
from difflib import SequenceMatcher
from google.cloud import vision
from moviepy.editor import AudioFileClip
from nltk.corpus import words
from openai.error import RateLimitError
from skimage.metrics import structural_similarity as ssim
from spellchecker import SpellChecker
from tkinter import ttk
from torch import hub
#from torchvision.models import video as vid
#from torchvision.io.video import read_video
#from torchvision.models.video import r3d_18, R3D_18_Weights
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor #Wav2Vec2Tokenizer 

scriptPath = os.path.realpath(os.path.dirname(__file__))
config = configparser.ConfigParser()
config.read(os.path.join(scriptPath,'config.ini'))
json_file = config['analysis']['json file']
confidence_threshold = float(config['analysis']['yolo confidence'])
video_language = config['analysis']['video language']
openai.api_key = config['analysis']['openai api key']

nltk.download('words')

# Define the transformation to apply to video frames
transform = transforms.Compose([
    transforms.ToPILImage(),
    transforms.Resize((112, 112)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.43216, 0.394666, 0.37645], std=[0.22803, 0.22145, 0.216989])
])

# Set up Tesseract OCR
pytesseract.pytesseract.tesseract_cmd = config['analysis']['tesseract executable']
tesseract_config = f"--psm 3 -l eng"  # Set language to English
ocr_confidence = float(config['analysis']['tesseract confidence'])

spell = SpellChecker()

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

def score_frame(frames, model, original_frames, object_summary={}):
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model.to(device)
    prev_texts = []
    max_distance = 50
    objects = []
    dict_array = []  # Initialize dict_array outside the loop
    
    with alive_bar(len(frames), force_tty=False) as bar:
        for frame, original_frame in zip(frames, original_frames):
            x_shape, y_shape = frame.shape[1], frame.shape[0]
            results = model(frame)
            detections = format(results).split('\n')[0].split(':', 1)[1].split(' ', 2)[2]

            data = results.pandas().xyxy[0]

            entry_dict = []  # Initialize as a list
            for _, row in data.iterrows():
                if row['confidence'] >= confidence_threshold:
                    object_type = row['name']
                    confidence = row['confidence']
                    object_class = row['class']
                    xmin = row['xmin']
                    ymin = row['ymin']
                    xmax = row['xmax']
                    ymax = row['ymax']

                    x1 = int(xmin)
                    y1 = int(ymin)
                    x2 = int(xmax)
                    y2 = int(ymax)
                    bgr = (255, 0, 0)

                    label_font = cv2.FONT_HERSHEY_SIMPLEX
                    cv2.rectangle(original_frame, (x1, y1), (x2, y2), bgr, 2)
                    cv2.putText(original_frame, f"{object_type} ({confidence:.2f})", (x1, y1), label_font, 0.7, bgr, 2)

                    centroid_x = int((xmin + xmax) / 2)
                    centroid_y = int((ymin + ymax) / 2)

                    entry_dict.append({
                        'name': object_type,
                        'confidence': confidence,
                        'class': object_class,
                        'xmin': xmin,
                        'ymin': ymin,
                        'xmax': xmax,
                        'ymax': ymax,
                        'centroid_x': centroid_x,
                        'centroid_y': centroid_y
                    })

            # Perform centroid tracking
            objects = centroid_tracking(objects, entry_dict, max_distance)

            # Remove disappeared objects
            objects = [obj for obj in objects if obj.frames_since_seen <= max_distance]

            # Add objects to the summary dictionary and dict_array
            for obj in objects:
                object_id = obj.object_id
                object_type = obj.object_type
                frame_number = len(object_summary.get(object_id, {}).get('frames', [])) + 1

                if object_id not in object_summary:
                    object_summary[object_id] = {
                        'object_type': object_type,
                        'frames': [frame_number],
                        'centroid': obj.centroid,
                        'movement_trajectory': obj.movement_trajectory,
                        'movement_speed': obj.movement_speed,
                        'movement_distance': obj.movement_distance
                    }
                else:
                    object_summary[object_id]['frames'].append(frame_number)

                dict_array.append({
                    'object_id': object_id,
                    'object_type': object_type,
                    'frame_number': frame_number,
                    'centroid': obj.centroid,
                    'movement_trajectory': obj.movement_trajectory,
                    'movement_speed': obj.movement_speed,
                    'movement_distance': obj.movement_distance
                })

                # Draw tracked objects on the frame
                for obj in objects:
                    x, y = obj.centroid
                    object_id = obj.object_id
                    cv2.putText(original_frame, f"{obj.object_type} {object_id}", (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7,(0, 255, 0), 2)

            # Display the processed frame
            '''cv2.imshow("Processed Frame", original_frame)
            if cv2.waitKey(1) == ord("q"):
                break'''
            bar()

    # Release the video capture and destroy the window
    video.release()
    #cv2.destroyAllWindows()

    return dict_array, object_summary

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

def detect_text_in_video(video_path, frames, x, y, similarity_threshold,progress_label=None,progress_widget=None):
    print("[ACTION] Extracting text from the video")
    if progress_widget != None:
        progress_widget['value'] = 0
        progress_widget['maximum'] = len(frames)
        progress_label.config(text="")
    client = vision.ImageAnnotatorClient()
    frame_count = len(frames)
    text = []
    prev_texts = []
    prev_frame = None  # Store the previous frame
    prev_f = -50
    count = 0
    spell_checker = SpellChecker()
    batch_size = 1
    start_time = time.time()
    p = 0
    with alive_bar(frame_count, force_tty=False) as bar:
        for f, frame in enumerate(frames):
            if prev_frame is not None:
                if is_frame_similar(frame, prev_frame, similarity_threshold) or prev_f > f-25:
                    # Skip text detection if the frame is similar to the previous frame
                    '''cv2.imshow("Processed Frame", frame)
                    if cv2.waitKey(1) == ord("q"):
                        break'''
                    p+=1
                    progress_list = get_eta(start_time,p,frame_count)
                    progress(progress_widget,p,batch_size,progress_label,progress_list)
                    bar()
                    continue
            #print("Checking frame for text")
            detected_text = perform_local_text_detection(frame)

            if detected_text:
                #print("Text Detected!")
                prev_f = f
                count += 1
                # Convert frame to bytes
                _, frame_bytes = cv2.imencode('.jpg', frame)
                frame_image = vision.Image(content=frame_bytes.tobytes())

                response = client.text_detection(image=frame_image)
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
                                #cv2.putText(frame, frame_text.upper(), (int((x - text_width) / 2), int(0.7 * y)),cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

            '''cv2.imshow("Processed Frame", frame)
            if cv2.waitKey(1) == ord("q"):
                break'''
            bar()
            p+=1
            progress_list = get_eta(start_time,p,frame_count)
            progress(progress_widget,p,batch_size,progress_label,progress_list)
            prev_frame = frame  # Update the previous frame
        progress_list = get_eta(start_time,frame_count,frame_count)
        progress(progress_widget,frame_count,batch_size,progress_label,progress_list)
        #video.release()
        #cv2.destroyAllWindows()
    print("[INFO] Detection Usage Count: "+str(count))
    return text, count

def similarity_ratio(a, b):
    return SequenceMatcher(None, a, b).ratio()

def extract_audio_transcript(audio_file, language):
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

    return transcription

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

def generate_summary(audio_text,screen_text,metadata):
    screen_text_string = '\n'.join(screen_text)
    video_context = ''
    response = None
    if metadata:
        video_context += "This is the metadata for the program this video clip is from:\n Program: "+metadata[2]+'\nStation: '+metadata[1]+'\n Date Recorded: '+metadata[3]+'\n Tape ID: '+metadata[0]
    if screen_text:
        video_context += '\nThe following is text that was detected on screen during the clip, some of it may be repetitive in whole or part:\n'+screen_text_string    
    if audio_text:
        video_context += '\nThe following text is a transcript of the audio from the video clip\n'+audio_text
    while True:
        try:
            response=openai.ChatCompletion.create(
              model="gpt-3.5-turbo",
              messages=[
                    {"role": "system", "content": config['analysis']['chatgpt role']},
                    {"role": "assistant", "content": video_context},
                    {"role": "user", "content": config['analysis']['chatgpt prompt']}
                ]
            )
            break
        except RateLimitError as e:
            print(e)
            print("Retrying in 60 seconds...")
            time.sleep(60)
    #print(response)
    
    summary = response['choices'][0]['message']['content']
    tokens_used = response['usage']['total_tokens']

    return summary, tokens_used

def get_eta(start_time,f,total_frames):
    seconds_elapsed = time.time() - start_time
    elapsed_minutes, elapsed_seconds = divmod(seconds_elapsed, 60)
    elapsed_hours, elapsed_minutes = divmod(elapsed_minutes, 60)
    if elapsed_hours > 0:
        time_elapsed = "{:02d}:{:02d}:{:02d}".format(round(elapsed_hours), round(elapsed_minutes), round(elapsed_seconds))
    else:
        time_elapsed = "{:02d}:{:02d}".format(round(elapsed_minutes), round(elapsed_seconds))    
    
    frames_per_second = f / seconds_elapsed
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

def progress(progress_widget,frames_processed,batch_size,progress_label,progress_list):
    if progress_widget is not None and frames_processed % batch_size == 0:
        time_elapsed, frames_per_second, time_remaining = progress_list
        #print(frames_processed)
        #print(progress_widget['maximum'])
        percentage_complete = round((frames_processed/progress_widget['maximum'])*100)
        #print(percentage_complete)
        frames_per_second = "{:.2f}".format(frames_per_second)
        
        progress_label.config(text=str(percentage_complete)+'% '+str(frames_processed)+'/'+str(progress_widget['maximum'])+', '+str(time_elapsed)+'<'+time_remaining+', '+ str(frames_per_second+'f/s'))
        progress_widget['value'] = frames_processed
        progress_widget.update()

def analyze_video(video_path,progress_label=None,progress_widget=None):
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
        video_name = os.path.basename(video_path)
        video_name = os.path.splitext(video_name)[0]
        print("[INFO] Extracting audio from video using MoviePy")
        audio_file = os.path.join(scriptPath, f"{video_name}.wav")
        video_mp = mp.VideoFileClip(video_path)
        video_mp.audio.write_audiofile(audio_file, verbose=False, logger=None)
        video_duration = video_mp.duration
        
        wav_size = os.path.getsize(audio_file)
        target_size = 26214400
        
        if wav_size > target_size:
            audio = AudioFileClip(audio_file)
            mp3_file = os.path.join(scriptPath, f"{video_name}.mp3")
            audio.write_audiofile(mp3_file, codec='mp3', bitrate='192k', logger="bar")
            print(f"File compressed to MP3: {mp3_file}")
            print("[ACTION] Extracting audio transcript")
            audio_mp3 = open(os.path.join(scriptPath, f"{video_name}.mp3"), 'rb')
            audio_text = openai.Audio.transcribe("whisper-1", audio_mp3)
            audio_mp3.close()            
            os.remove(os.path.join(scriptPath, f"{video_name}.mp3"))
            if progress_widget != None:
                progress_widget['value'] = 100
                progress_label.config(text="")
        else:
            print("[ACTION] Extracting audio transcript")
            audio_wav = open(os.path.join(scriptPath, f"{video_name}.wav"), 'rb')
            audio_text = openai.Audio.transcribe("whisper-1", audio_wav)
            audio_wav.close()
        print("[TRANSCRIPTION] "+audio_text.text)
        os.remove(os.path.join(scriptPath, f"{video_name}.wav"))
        if os.path.exists(os.path.join(scriptPath, f"{video_name}.mp3")):
            os.remove(os.path.join(scriptPath, f"{video_name}.mp3"))
        print("[ACTION] Preprocessing Frames")
        cap = cv2.VideoCapture(video_path)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if progress_widget != None:
            try:
                progress_widget['value'] = 0
                progress_widget['maximum'] = frame_count
                progress_label.config(text="")
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
        
        with alive_bar(frame_count, force_tty=False) as bar:
            while True:
                progress_list = get_eta(start_time,f,frame_count)
                progress(progress_widget,f,batch_size,progress_label,progress_list)
                ret, frame = video.read()
                if not ret:
                    frame_diff = frame_count - len(frames)
                    while frame_diff > 0:
                        bar()
                        frame_diff -= 1
                    break

                # Convert to grayscale
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
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
                processed = transform(pil_frame)
                
                
                # Apply adaptive thresholding
                #threshold = cv2.adaptiveThreshold(equalized, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 11, 2)
                
                # Perform morphological operations (optional)
                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
                morphed = cv2.morphologyEx(equalized, cv2.MORPH_CLOSE, kernel)

                # Convert the frame to a numpy array
                #frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                #frame = frame.transpose(2, 0, 1)  # Change to channel-first format
                frames.append(frame)
                gray_frames.append(gray)
                blurred_frames.append(blurred)
                #threshold_frames.append(threshold)
                sharpened_frames.append(sharpened)
                morphed_frames.append(morphed)
                processed_frames.append(processed)
                '''cv2.imshow("Frame", frame)
                if cv2.waitKey(1) == ord("q"):
                    break'''
                bar()
                f += 1
            video.release()
            #cv2.destroyAllWindows()    
        progress_list = get_eta(start_time,frame_count,frame_count)
        progress(progress_widget,frame_count,batch_size,progress_label,progress_list)
        #text = extract_text_from_video(blurred_frames, x_shape, y_shape)
        text, count = detect_text_in_video(video_path, frames, x_shape, y_shape, 0.9,progress_label=progress_label,progress_widget=progress_widget)
        for i, t in enumerate(text):
            print(str(i)+': '+str(t))
        # Perform object detection on the frame
        # Load the YOLOv5 model
        #yolo_model = hub.load('ultralytics/yolov5', 'yolov5s', pretrained=True)
        #dict_array, object_summary = score_frame(morphed_frames, yolo_model, frames)
        #print(object_summary)
        #most_frequent_objects = identify_prominent_objects(object_summary)
        #Wprint(most_frequent_objects)
        #object_interactions = analyze_object_interactions(object_summary)
        #print(object_interactions)
        '''while True:
            ret, frame = video.read()
            if not ret:
                break

            # Preprocess the frame
            input_frame = transform(frame).unsqueeze(0)

            # Display the processed frame
            cv2.imshow("Processed Frame", frame)
            if cv2.waitKey(1) == ord("q"):
                break'''
        # Release the video capture and destroy the window
        video.release()
        #cv2.destroyAllWindows()
            
        print("Generating a summary using OpenAI")
        summary, tokens_used = generate_summary(audio_text.text, text, metadata)

        print("Tokens Used: "+str(tokens_used),end='\n\n')
        clip_dict = json.loads(summary)
        try:
            clip_dict['Filename'] = str(start_frame)+'_'+re.sub(r'[\\/*?:"<>|]', '',clip_dict['Filename']+os.path.splitext(video_file_name)[1])
            clip_dict['Tape ID'] = tape_id
            clip_dict['Length (seconds)'] = video_duration
            clip_dict['Location'] = location
            clip_dict['Frame Range'] = [start_frame,end_frame]

            print("\nAdding metadata to file and renaming")
            metatagger.createMetadata(video_path, directory,clip_dict,outputFile=clip_dict['Filename'])
            if os.path.exists(os.path.join(directory, clip_dict['Filename'])):
                print("Success!")
                # delete the original file
                #os.remove(video_path)
            else:
                print("An error has occurred creating the tagged file")
            
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
                
            print("Saving API Usage Data")
            api_usage_json = "api_usage.json"
            if os.path.exists(api_usage_json):
                with open(api_usage_json, "r") as jsonfile:
                    existing_api_usage = json.load(jsonfile)
            else:
                existing_api_usage = {}
            current_month_year = datetime.datetime.now().strftime("%Y-%m")
            chatgpt_usage = int(tokens_used)
            whisper_usage = round(video_duration)
            vision_usage = count
            
            if current_month_year in existing_api_usage:
                month_data = existing_api_usage[current_month_year]
            else:
                month_data = {
                    'chatgpt': {
                        'usage': 0,
                        'cost': 0
                    },
                    'whisper': {
                        'usage': 0,
                        'cost': 0
                    },
                    'vision': {
                        'usage': 0,
                        'cost': 0
                    }
                }
                existing_api_usage[current_month_year] = month_data

        except Exception as e:
            print("[ERROR]"+str(e))
            traceback.print_exc()
        
        month_data['chatgpt']['usage'] += chatgpt_usage
        month_data['whisper']['usage'] += whisper_usage
        month_data['vision']['usage'] += vision_usage
        
        chatgpt_cost = float(config['analysis']['chatgpt cost'])
        whisper_cost = float(config['analysis']['whisper cost'])
        vision_cost = {
            'tier1': float(config['analysis']['google vision tier 1']),
            'tier2': float(config['analysis']['google vision tier 2']),
            'tier3': float(config['analysis']['google vision tier 3'])
        }
        vision_tier1_limit = 1000
        vision_tier2_limit = 5000000
        
        month_data['chatgpt']['cost'] = month_data['chatgpt']['usage'] * chatgpt_cost
        month_data['whisper']['cost'] = month_data['whisper']['usage'] * whisper_cost
        if month_data['vision']['usage'] <= vision_tier1_limit:
            month_data['vision']['cost'] = month_data['vision']['usage'] * vision_cost['tier1']
        elif month_data['vision']['usage'] <= vision_tier2_limit:
            tier1_cost = vision_tier1_limit * vision_cost['tier1']
            remaining_uses = month_data['vision']['usage'] - vision_tier1_limit
            month_data['vision']['cost'] = tier1_cost + remaining_uses * vision_cost['tier2']
        else:
            tier1_cost = vision_tier1_limit * vision_cost['tier1']
            tier2_cost = (vision_tier2_limit - vision_tier1_limit) * vision_cost['tier2']
            remaining_uses = month_data['vision']['usage'] - vision_tier2_limit
            month_data['vision']['cost'] = tier1_cost + tier2_cost + remaining_uses * vision_cost['tier3']

        existing_api_usage[current_month_year] = month_data

        with open(api_usage_json, 'w') as file:
            json.dump(existing_api_usage, file, indent=4)

        #get time to complete
        end_time = datetime.datetime.now()
        elapsed_time = end_time - starting_time
        time_minutes = elapsed_time.total_seconds() // 60
        time_seconds = elapsed_time.total_seconds() % 60
        #print(f"\nElapsed time: {int(time_minutes):02d}:{int(time_seconds):02d}")
            
        print("\n------------------------------------------------")
        print("Total API Usage and Costs for this month\nChatGPT: "+str(month_data['chatgpt']['usage'])+" "+str(month_data['chatgpt']['cost'])+"\nWhisper: "+str(month_data['whisper']['usage'])+" "+str(month_data['whisper']['cost'])+"\nGoogle Vision: "+str(month_data['vision']['usage'])+" "+str(month_data['vision']['cost']))
        print("------------------------------------------------")
        print(f"[ACTION] File Analyisis Complete in {int(time_minutes):d} minutes, {int(time_seconds):d} seconds")
        try:
            for k, v in clip_dict.items():
                print(str(k)+': '+str(v))
            print("------------------------------------------------\n")
        except:
            pass
        time.sleep(5)
        
    except Exception as e:
        print("[ERROR] "+str(e))
        traceback.print_exc()
