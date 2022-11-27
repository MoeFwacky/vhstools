import configparser
import csv
import cv2
import datetime
import ffmpeg
import glob
import json
import math
import os
import pytumblr
import pytz
import random
import sys
import time
import tweepy
from datetime import datetime
from datetime import timedelta
from random import randrange

config = configparser.ConfigParser()
config.read('config.ini')

vhs_json_file = config['files']['json file']
directory = config['files']['video directory']
scene_rgb = int(config['values']['rgb threshold'])
loop_time = int(config['values']['time between'])
clip_length = int(config['values']['clip minimum'])
buffer_frames = [int(config['values']['front buffer']),int(config['values']['end buffer'])]

twitter_username = config['twitter']['username']
twitter_auth_keys = {
    "consumer_key":config['twitter']['consumer key'],
    "consumer_secret":config['twitter']['consumer secret'],
    "access_token":config['twitter']['access token'],
    "access_token_secret":config['twitter']['access secret']
}

tumblr_client = pytumblr.TumblrRestClient(
    config['tumblr']['consumer key'],
    config['tumblr']['consumer secret'],
    config['tumblr']['access token'],
    config['tumblr']['access secret']
)

all_videos = []

for video_file in glob.glob(directory+"\\*.mp4"):
    all_videos.append(video_file)

def select_video(directory):
    dir_files = os.listdir(directory)
    files = glob.glob(directory+"\\*.mp4")
    number_of_files = len(files)
    random_file = files[randrange(number_of_files)-1]
    print("SELECTED FILE: "+random_file)
    return random_file

def get_frame(csv_filename, scene_rgb=scene_rgb,clip_length=int(clip_length)):
    minimum_clip_frames = clip_length*30
    with open(csv_filename) as csv_file:
        number_of_frames = sum(1 for line in csv_file)
        print(str(number_of_frames)+ " TOTAL FRAMES")
        random_frame = randrange(number_of_frames)
        rgb = 999
        while float(rgb) > scene_rgb:
            random_frame = random_frame + 30
            while random_frame < buffer_frames[0] or random_frame > (number_of_frames-buffer_frames[1]):
                random_frame = random_frame + 1
            csv_file.seek(0)
            readCSV = csv.reader(csv_file)
            for i in range(random_frame):
                next(readCSV)
            selected_frame_data = next(readCSV)
            rgb = float(selected_frame_data[2])
            print("FRAME NUMBER "+str(random_frame)+" SELECTED, RGB = "+str(rgb),end='\r')
            start_frame = random_frame
        print("")
        while random_frame < (start_frame + minimum_clip_frames):
            random_frame = random_frame + 1
            last_frame_data = next(readCSV)
            rgb = float(last_frame_data[2])
            print("FRAME NUMBER "+str(random_frame)+" SELECTED, RGB = "+str(rgb),end='\r')
        print("")
        while float(rgb) > scene_rgb:
            random_frame = random_frame + 1
            last_frame_data = next(readCSV)
            rgb = float(last_frame_data[2])
            print("FRAME NUMBER "+str(random_frame)+" SELECTED, RGB = "+str(rgb),end='\r')
    print("")
    return selected_frame_data, last_frame_data

def get_video(filename,start,end,crf=11):
    print("SAVING VIDEO FROM: "+filename)
    (
        ffmpeg
        .input(filename, ss=start, to=end)
        .output('clip.mp4', vcodec='libx264', preset='veryfast', crf=crf, acodec='aac', loglevel="quiet")
        .run(overwrite_output=True)
    )

def render_video(filename,start,end,crf=22):
    print("RENDERING VIDEO AGAIN")
    (
        ffmpeg
        .input(filename, ss=start, to=end)
        .output('newclip.mp4', vcodec='libx264', preset='veryfast', crf=crf, acodec='aac', loglevel="quiet")
        .run()
    )

def get_audio(filename,start,end):
    print("EXTRACTING AUDIO FROM: "+filename)
    (
        ffmpeg
        .input(filename, ss=start, t=clip_length)
        .output('clip.wav', map='a', loglevel="quiet")
        .run()
    )

def get_duration(filename):
    video = cv2.VideoCapture(filename)
    frame_count = video.get(cv2.CAP_PROP_FRAME_COUNT)
    duration = frame_count/30
    return duration

auth = tweepy.OAuthHandler(
        twitter_auth_keys['consumer_key'],
        twitter_auth_keys['consumer_secret']
        )
auth.set_access_token(
        twitter_auth_keys['access_token'],
        twitter_auth_keys['access_token_secret']
        )
api = tweepy.API(auth)

while True:
    tapeID = None
    thisEntry = None
    station = None
    location = None
    airDate = None
    airDateLong = None
    airDateShort = None
    if len(all_videos) == 0:
        for video_file in glob.glob(directory+"\\*.mp4"):
            all_videos.append(video_file)
    print("SELECTING VIDEO FROM", len(all_videos), "VIDEO FILES")
    video_filename = random.choice(all_videos)
    tape_name = video_filename.split('\\')[-1]
    tape_name = tape_name.replace('.mp4','')
    print(tape_name,"SELECTED!")
    csv_filename = video_filename.replace('.mp4','.csv')

    print("SELECTING STARTING FRAME")
    frame, last_frame = get_frame(csv_filename)
    video = cv2.VideoCapture(video_filename)
    frameTimeSeconds = int(frame[0])/30
    
    j = open(vhs_json_file,)
    tapeData = json.load(j)
    thisTape = []
    
    for entry in tapeData:
        if entry['Tape_ID'] == tape_name[0:7]:
            thisTape.append(entry)
    tapeSorted = sorted(thisTape, key=lambda d: d['Order on Tape'])
    
    for entry in tapeSorted:
        timeSplit = entry['Segment End'].split(':')
        entryTimeSeconds = int(timeSplit[0])*3600+int(timeSplit[1])*60+int(timeSplit[2])
        if entryTimeSeconds > frameTimeSeconds:
            thisEntry = entry
            tapeID = thisEntry['Tape_ID']
            print("\nTAPE ID: "+tapeID)
            program = thisEntry['Programs']
            print("PROGRAM: "+program)
            station = thisEntry['Network/Station']
            print("NETWORK/STATION: "+station)
            location = thisEntry['Location']
            print("LOCATION: "+location)
            try:
                airDate = datetime.strptime(thisEntry['Recording Date'], '%Y-%m-%d')
                airDateLong = datetime.strftime(airDate,'%A %B %d, %Y')
                airDateShort = datetime.strftime(airDate,'%b %d, %Y')
                print("AIR DATE: "+airDateLong)
            except Exception as e:
                print("ERROR: AIR DATE NOT FOUND")
            break
        else:
            #print("FRAME TIME: "+str(frameTimeSeconds)+" | ENTRY TIME: "+str(entryTimeSeconds),end='\n')
            print(' ',end='\r')
            
            
    print("FIRST FRAME: "+frame[1])
    print("LAST FRAME: "+last_frame[1])
    get_video(video_filename,frame[1],last_frame[1],crf=22)
    file_size = os.path.getsize("clip.mp4")
    print("VIDEO SIZE:", file_size, "bytes")
    clip_duration = get_duration('clip.mp4')
    loops = 0
    while file_size > 41943040:
        loops = loops + 1
        size_over = file_size - 41943040
        print("FILE SIZE EXCEEDS MAXIMUM OF 41943040 BYTES BY",size_over)
        clip_duration = get_duration('clip.mp4')
        render_video('clip.mp4',0,clip_duration-loops,crf=22)
        os.remove('clip.mp4')
        os.rename('newclip.mp4','clip.mp4')
        file_size = os.path.getsize("clip.mp4")
        print("VIDEO SIZE:", file_size, "bytes")

    print("\nGETTING THUMBNAIL")
    video.set(cv2.CAP_PROP_POS_FRAMES,int(frame[0])+15*30)
    success, image = video.read()
    if success:
        resized_image = cv2.resize(image, (640,480))
        cv2.imwrite("thumbnail.png", resized_image)

    tweets = api.user_timeline(screen_name=twitter_username, count=1) #get last tweet
    last_tweet = tweets[0]
    last_tweet_timestamp = last_tweet.created_at
    if datetime.now(pytz.utc) < last_tweet_timestamp+timedelta(minutes=loop_time):
        print("\nLAST TWEET WAS: " + str(last_tweet_timestamp.astimezone(pytz.timezone('US/Pacific'))))
        time_to_sleep = (last_tweet_timestamp+timedelta(minutes=loop_time))-datetime.now(pytz.utc)-timedelta(minutes=5)
        if time_to_sleep.total_seconds() > 0:
            print("SLEEPING UNTIL "+str(time_to_sleep+datetime.now())+"\n")
            time.sleep(time_to_sleep.total_seconds())

    hashtags = ['#VHS','#retromedia']
    try:
        stationList = station.split('/')
        for n in stationList:
            n2 = n.split(' ')
            if len(n2) != 2:
                hashtags.append('#'+n)
            else:
                hashtags.append('#'+n2[0])
    except:
        hashtags = hashtags
    
    hashtagString = hashtags[0]
    for tag in hashtags:
        if tag in hashtagString.split(' '):
            continue
        else:
            hashtagString = hashtagString+" "+tag

    try:
        locationList = location.split('\, ')        
        for l in locationList:
            hashtags.append('#'+l)
    except Exception as e:
        print(e)
        hashtags = hashtags
        
    try:
        tweet = tapeID+"\n"+frame[1]+"\n"+program+"\n"+station+"\n"+airDateShort+"\n"+hashtagString
    except:
        tweet = "Tape ID: "+tape_name[0:7]+"\nTimestamp: "+frame[1]+"\n"+hashtagString
    if len(tweet) > 280:
        tweet = +tapeID+"\n"+frame[1]+"\n"+program+"\n"+station+"\n"+airDateShort+"\n"+hashtagString
    try:
        tumblrCaption = "Tape ID: "+tapeID+"<br>Timestamp: "+frame[1]+"<br>Program: "+program+"<br>Network/Station: "+station+"<br>Broadcast Location: "+location+"<br>Air Date: "+airDateLong
    except:
        tumblrCaption = "Tape ID: "+tape_name[0:7]+"<br>Timestamp: "+frame[1]

    print("\nTWEET: "+tweet)
    print("\nTUMBLR: "+tumblrCaption)

    try:
        print("UPLOADING VIDEO TO TWITTER")
        media = api.chunked_upload("clip.mp4",media_category="tweet_video")
    except Exception as e:
        print("ERROR: COULD NOT UPLOAD VIDEO")
        print(e)
        time.sleep(10)
        try:
            print("UPLOADING VIDEO TO TWITTER AGAIN")
            media = api.chunked_upload("clip.mp4",media_category="tweet_video")        
        except:
            print("ERROR: COULD NOT UPLOAD VIDEO")
            print(e)
            media = None
    try:
        print("SENDING TO TUMBLR")
        caption = tumblrCaption
        tags = hashtags
        tumblr_post = tumblr_client.create_video('foundonvhs',caption=caption,tags=tags,data="clip.mp4")
    except Exception as e:
        print("ERROR: COULD NOT POST VIDEO TO TUMBLR")
        print(e)

    if datetime.now(pytz.utc) < last_tweet_timestamp+timedelta(minutes=loop_time):
        time_to_sleep = (last_tweet_timestamp+timedelta(minutes=loop_time))-datetime.now(pytz.utc)
        print("\nSLEEPING UNTIL "+str(time_to_sleep+datetime.now())+"\n")
        time.sleep(time_to_sleep.total_seconds())

    if media != None:
        try:
            print("SENDING TWEET")
            post_result = api.update_status(status=tweet, media_ids=[media.media_id])
            print(tape_name[0:7]+": "+frame[1]+"\n")
        except Exception as e:
            print("ERROR: COULD NOT TWEET VIDEO")
            print(e)
        all_videos.remove(video_filename)
        os.remove('clip.mp4')
    else:
        print("VIDEO NOT UPLOADED, SKIPPING TWEET")

    print("CLEANING UP FILES")
    os.remove('thumbnail.png')
    print("\n---------------------------------\n")
    print("RESTARTING LOOP\n")
    time.sleep(5)