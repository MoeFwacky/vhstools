import configparser
import csv
import cv2
import datetime
import ffmpeg
import glob
import json
import math
import mastodon
import os
import pytumblr
import pytz
import random
import sys
import time
import tweepy
import videoscanner
from datetime import datetime
from datetime import timedelta
from random import randrange

if os.name == 'nt':
    delimeter = '\\'
else:
    delimeter = '/'

scriptPath = os.path.realpath(os.path.dirname(__file__))

config = configparser.ConfigParser()
config.read(scriptPath + delimeter + 'config.ini')

vhs_json_file = config['social']['json file']
directory = config['social']['video directory']
temp_directory = config['social']['temp directory']
scene_rgb = int(config['social']['rgb threshold'])
loop_time = int(config['social']['time between'])
clip_length = int(config['social']['clip minimum'])
clip_max = int(config['social']['clip maximum'])
file_max = int(config['social']['file size maximum'])
buffer_frames = [int(config['social']['front buffer']),int(config['social']['end buffer'])]

def list_videos(directory):
    all_videos = []

    for video_file in glob.glob(directory+delimeter+"*.mp4"):
        all_videos.append(video_file)
    return all_videos

def select_video(directory):
    dir_files = os.listdir(directory)
    files = glob.glob(directory+delimeter+"*.mp4")
    number_of_files = len(files)
    random_file = files[randrange(number_of_files)-1]
    print("SELECTED FILE: "+random_file)
    return random_file
    
def scale_number(unscaled, to_min, to_max, from_min, from_max):
    return (to_max-to_min)*(unscaled-from_min)/(from_max-from_min)+to_min

def get_frame(json_filename, frameRate=30, scene_rgb=scene_rgb,clip_length=int(clip_length)):
    minimum_clip_frames = clip_length*frameRate
    with open(json_filename) as json_file:
        json_data = json.load(json_file)
        number_of_frames = int(json_data['analysis']['total frames'])
        print(str(number_of_frames)+ " TOTAL FRAMES")
        random_frame = int(randrange(number_of_frames))
        print("RGB Threshold value:",json_data['analysis']['median_rgb']/3)
        scene_rgb = scale_number(json_data['analysis']['median_rgb'],0,255,json_data['analysis']['min_rgb'],json_data['analysis']['max_rgb'])/3
        print("RGB Threshold changed to",scene_rgb)
        rgb = 256
        while float(rgb) > scene_rgb:
            random_frame = random_frame + 1
            while random_frame < buffer_frames[0] or random_frame > (number_of_frames-buffer_frames[1]):
                random_frame = random_frame + 1
            selected_frame_data = json_data['frames'][random_frame]
            rgb = scale_number(selected_frame_data['rgb'],0,255,json_data['analysis']['min_rgb'],json_data['analysis']['max_rgb'])
            print("FRAME NUMBER "+str(random_frame)+" SELECTED, RGB = "+str(rgb),end='\r')
            #start_frame = random_frame
            try:
                while not (json_data['frames'][random_frame-2]['rgb'] > json_data['frames'][random_frame-1]['rgb'] > json_data['frames'][random_frame]['rgb'] < json_data['frames'][random_frame+1]['rgb'] < json_data['frames'][random_frame+2]['rgb']):
                    random_frame = random_frame + 1
                    print("FRAME NUMBER "+str(random_frame)+" SELECTED, RGB = "+str(rgb),end='\r')
                    try:
                        selected_frame_data = json_data['frames'][random_frame]
                        rgb = scale_number(selected_frame_data['rgb'],0,255,json_data['analysis']['min_rgb'],json_data['analysis']['max_rgb'])
                    except IndexError as e:
                        selected_frame_data = json_data['frames'][random_frame-1]
                        rgb = scale_number(selected_frame_data['rgb'],0,255,json_data['analysis']['min_rgb'],json_data['analysis']['max_rgb'])
                        break
            except IndexError as e:
                selected_frame_data = json_data['frames'][random_frame-1]
                rgb = scale_number(selected_frame_data['rgb'],0,255,json_data['analysis']['min_rgb'],json_data['analysis']['max_rgb'])
                break
        print("FRAME NUMBER "+str(random_frame)+" SELECTED, RGB = "+str(rgb),end='\n')
        start_frame = random_frame
        while random_frame <= (start_frame + minimum_clip_frames):
            random_frame = random_frame + 1
            last_frame_data = json_data['frames'][random_frame]
            rgb = scale_number(float(last_frame_data['rgb']),0,255,json_data['analysis']['min_rgb'],json_data['analysis']['max_rgb'])
            print("FRAME NUMBER "+str(random_frame)+" SELECTED, RGB = "+str(rgb),end='\r')
        while float(rgb) > scene_rgb and (random_frame-start_frame)/frameRate <= clip_max:
            random_frame = random_frame + 1
            last_frame_data = json_data['frames'][random_frame]
            rgb = scale_number(float(last_frame_data['rgb']),0,255,json_data['analysis']['min_rgb'],json_data['analysis']['max_rgb'])
            print("FRAME NUMBER "+str(random_frame)+" SELECTED, RGB = "+str(rgb),end='\r')
            while not (json_data['frames'][random_frame-2]['rgb'] > json_data['frames'][random_frame-1]['rgb'] > json_data['frames'][random_frame]['rgb'] < json_data['frames'][random_frame+1]['rgb'] < json_data['frames'][random_frame+2]['rgb']):
                random_frame = random_frame + 1
                print("FRAME NUMBER "+str(random_frame)+" SELECTED, RGB = "+str(rgb),end='\r')
                last_frame_data = json_data['frames'][random_frame]
                rgb = scale_number(float(last_frame_data['rgb']),0,255,json_data['analysis']['min_rgb'],json_data['analysis']['max_rgb'])
        print("FRAME NUMBER "+str(random_frame)+" SELECTED, RGB = "+str(rgb),end='\n')
    return selected_frame_data, last_frame_data

def get_video(filename,start,end,crf=11):
    print("SAVING VIDEO FROM: "+filename)
    (
        ffmpeg
        .input(filename, ss=start, to=end)
        .output(temp_directory+delimeter+'clip.mp4', vcodec='libx264', preset='veryfast', crf=crf, acodec='aac', loglevel="quiet")
        .run(overwrite_output=True)
    )

def render_video(filename,start,end,crf=22):
    print("RENDERING VIDEO AGAIN")
    (
        ffmpeg
        .input(filename, ss=start, to=end)
        .output(temp_directory+delimeter+'newclip.mp4', vcodec='libx264', preset='veryfast', crf=crf, acodec='aac', loglevel="quiet")
        .run()
    )

def get_audio(filename,start,end):
    print("EXTRACTING AUDIO FROM: "+filename)
    (
        ffmpeg
        .input(filename, ss=start, t=clip_length)
        .output(temp_directory+delimeter+'clip.wav', map='a', loglevel="quiet")
        .run()
    )

def get_duration(filename,frameRate=30):
    video = cv2.VideoCapture(filename)
    frame_count = video.get(cv2.CAP_PROP_FRAME_COUNT)
    duration = frame_count/frameRate
    return duration

def social(videos, twitter=False,tumblr=False,useMastodon=False,persist=False):
    if twitter != False:
        twitter_username = config['twitter']['username']
        twitter_auth_keys = {
            "consumer_key":config['twitter']['consumer key'],
            "consumer_secret":config['twitter']['consumer secret'],
            "access_token":config['twitter']['access token'],
            "access_token_secret":config['twitter']['access secret']
        }
        auth = tweepy.OAuthHandler(
                twitter_auth_keys['consumer_key'],
                twitter_auth_keys['consumer_secret']
                )
        auth.set_access_token(
                twitter_auth_keys['access_token'],
                twitter_auth_keys['access_token_secret']
                )
        api = tweepy.API(auth)
    
    if tumblr != False:
        tumblr_client = pytumblr.TumblrRestClient(
            config['tumblr']['consumer key'],
            config['tumblr']['consumer secret'],
            config['tumblr']['access token'],
            config['tumblr']['access secret']
        )
    if useMastodon != False:
        mastodon_client = mastodon.Mastodon(access_token=config['mastodon']['access token'], api_base_url=config['mastodon']['instance url'])
    
    if persist == False:    
        all_videos = videos
    else:
        all_videos = []
        try:
            print("LOADING persist.csv")
            with open(temp_directory+delimeter+'persist.csv', newline="") as csvfile:
                csvData = csvfile.readlines()
                csvData = csvData[0].split(',')
            for d in csvData:
                if d in videos:
                    all_videos.append(d)
                else:
                    print("NO MATCH FOUND FOR",d)
            print(len(all_videos),"VIDEOS FOUND")
            if len(all_videos) == 0:
                all_videos = videos
        except Exception as e:
            print("ERROR: COULD NOT LOAD persist.csv")
            print(e)
            all_videos = videos

    while True:
        tapeID = None
        thisEntry = None
        station = None
        location = None
        airDate = None
        airDateLong = None
        airDateShort = None
        print("SELECTING VIDEO FROM", len(all_videos), "VIDEO FILES")
        video_filename = random.choice(all_videos)
        tape_name = video_filename.split(delimeter)[-1]
        tape_name = tape_name.split('.')[0]
        print(tape_name,"SELECTED!")
        json_filename = video_filename.replace('.mp4','.json')

        if os.path.exists(json_filename) == False:
            print("JSON DATA FILE NOT FOUND, SCANNING",tape_name)
            filePathArray = video_filename.split(delimeter)
            filePathArray.pop()
            filePath = ""
            for p in filePathArray:
                filePath = filePath + p + delimeter
            videoscanner.scanVideo(tape_name+'.mp4',filePath)

        print("SELECTING STARTING FRAME")
        video_data = videoscanner.getFrameRateDuration(video_filename)
        frame, last_frame = get_frame(json_filename,int(video_data[0]))
        video = cv2.VideoCapture(video_filename)
        frameTimeSeconds = frame['f']/int(video_data[0])
        
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
                
                
        print("\nFIRST FRAME: "+frame['ts'])
        print("LAST FRAME: "+last_frame['ts'])
        total_frames = int(last_frame['f'])-int(frame['f'])
        print("DURATION: ",round(total_frames/int(video_data[0]),2),"SECONDS\n")
        get_video(video_filename,frame['ts'],last_frame['ts'],crf=22)
        file_size = os.path.getsize(temp_directory+delimeter+"clip.mp4")
        print("\nCLIP SIZE:", round(file_size/1024/1024,2), "megabytes")
        clip_duration = get_duration(temp_directory+delimeter+'clip.mp4',int(video_data[0]))
        print("CLIP LENGTH:", round(clip_duration,2), "SECONDS")
        loops = 0
        while file_size > file_max*1024*1024:
            loops = loops + 1
            size_over = file_size - file_max*1024*1024
            size_over_kb = size_over/1024
            size_over_mb = size_over_kb/1024
            if size_over_mb < 1:
                if size_over_kb < 1:
                    print("FILE SIZE EXCEEDS MAXIMUM OF",file_max,"MEGABYTES BY",round(size_over,2),"BYTES")
                else:
                    print("FILE SIZE EXCEEDS MAXIMUM OF",file_max,"MEGABYTES BY",round(size_over/1024,2),"KILOBYTES")
            else:
                print("FILE SIZE EXCEEDS MAXIMUM OF",file_max,"MEGABYTES BY",round(size_over_mb,2),"MEGABYTES")
            clip_duration = get_duration(temp_directory+delimeter+'clip.mp4',int(video_data[0]))
            bytes_per_second = round(file_size/clip_duration)
            time_over = round(size_over/bytes_per_second)
            print("REDUCING CLIP BY",time_over,"SECONDS")
            render_video(temp_directory+delimeter+'clip.mp4',0,clip_duration-time_over,crf=22)
            os.remove(temp_directory+delimeter+'clip.mp4')
            os.rename(temp_directory+delimeter+'newclip.mp4',temp_directory+delimeter+'clip.mp4')
            file_size = os.path.getsize(temp_directory+delimeter+"clip.mp4")
            clip_duration = get_duration(temp_directory+delimeter+'clip.mp4')
            print("\nCLIP SIZE:", round(file_size/1024/1024,4), "megabytes")
            print("CLIP LENGTH:", round(clip_duration,1), "SECONDS")

        print("\nGETTING THUMBNAIL")
        video.set(cv2.CAP_PROP_POS_FRAMES,int(frame['f'])+round(clip_duration/2)*int(video_data[0]))
        success, image = video.read()
        if success:
            resized_image = cv2.resize(image, (640,480))
            cv2.imwrite(temp_directory+delimeter+"thumbnail.png", resized_image)

        if twitter != False:
            tweets = api.user_timeline(screen_name=twitter_username, count=1) #get last tweet
            last_tweet = tweets[0]
            last_tweet_timestamp = last_tweet.created_at
            if datetime.now(pytz.utc) < last_tweet_timestamp+timedelta(minutes=loop_time):
                print("\nLAST TWEET WAS: " + str(last_tweet_timestamp.astimezone(pytz.timezone('US/Pacific'))))
                time_to_sleep = (last_tweet_timestamp+timedelta(minutes=loop_time))-datetime.now(pytz.utc)-timedelta(minutes=5)
                if time_to_sleep.total_seconds() > 0:
                    print("SLEEPING UNTIL "+str(time_to_sleep+datetime.now())+"\n")
                    time.sleep(time_to_sleep.total_seconds())
        else:
            #note: add other social platforms to check for last post
            time_to_sleep = ((loop_time-5)*60)
            if time_to_sleep.total_seconds() > 0:
                print("SLEEPING UNTIL "+str(time_to_sleep+datetime.now())+"\n")
                time.sleep(time_to_sleep)            
        
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
            

        if twitter != False:
            try:
                tweet = tapeID+"\n"+frame['ts'].split('.')[0]+"\n"+program+"\n"+station+"\n"+airDateShort+"\n"+hashtagString
            except:
                tweet = "Tape ID: "+tape_name[0:7]+"\nTimestamp: "+frame['ts'].split('.')[0]+"\n"+hashtagString
            if len(tweet) > 280:
                tweet = +tapeID+"\n"+frame['ts'].split('.')[0]+"\n"+program+"\n"+station+"\n"+airDateShort+"\n"+hashtagString
            print("TWEET:\n"+tweet,end='\n')
            try:
                print("UPLOADING VIDEO TO TWITTER")
                media = api.chunked_upload(temp_directory+delimeter+"clip.mp4",media_category="tweet_video")
            except Exception as e:
                print("ERROR: COULD NOT UPLOAD VIDEO TO TWITTER")
                print(e)
                time.sleep(10)
                try:
                    print("UPLOADING VIDEO TO TWITTER AGAIN")
                    media = api.chunked_upload(temp_directory+delimeter+"clip.mp4",media_category="tweet_video")        
                except Exception as e:
                    print("ERROR: COULD NOT UPLOAD VIDEO TO TWITTER")
                    print(e)
                    media = None

        if tumblr != False:
            try:
                tumblrCaption = "Tape ID: "+tapeID+"<br>Timestamp: "+frame['ts'].split('.')[0]+"<br>Program: "+program+"<br>Network/Station: "+station+"<br>Broadcast Location: "+location+"<br>Air Date: "+airDateLong
            except:
                tumblrCaption = "Tape ID: "+tape_name[0:7]+"<br>Timestamp: "+frame['ts'].split('.')[0]

            print("\nTUMBLR:\n"+tumblrCaption)
            try:
                print("SENDING TO TUMBLR")
                caption = tumblrCaption
                tags = hashtags
                tumblr_post = tumblr_client.create_video('foundonvhs',caption=caption,tags=tags,data=temp_directory+delimeter+"clip.mp4")
            except Exception as e:
                print("ERROR: COULD NOT POST VIDEO TO TUMBLR")
                print(e)
        
        if useMastodon != False:
            try:
                mastodonCaption = "Tape ID: "+tapeID+"\nTimestamp: "+frame['ts'].split('.')[0]+"\nProgram: "+program+"\nNetwork/Station: "+station+"\nBroadcast Location: "+location+"\nAir Date: "+airDateLong+"\n"+hashtagString
            except:
                mastodonCaption = "Tape ID: "+tape_name[0:7]+"\nTimestamp: "+frame['ts'].split('.')[0]+"\n"+hashtagString
            print("\nMASTODON:\n"+mastodonCaption)
            try:
                print("UPLOADING VIDEO TO MASTODON")
                mastodon_media = mastodon_client.media_post(
                    temp_directory+delimeter+"clip.mp4",
                    mime_type='video/mp4',
                    description="Random video clip from a digitized VHS tape",
                    focus=(0,-0.333),
                    thumbnail=temp_directory+delimeter+"thumbnail.png",
                    thumbnail_mime_type='image/png'
                )
            except Exception as e:
                print("ERROR: COULD NOT UPLOAD VIDEO TO MASTODON")
                print(e)
                mastodon_media = None

        if twitter != False:
            if datetime.now(pytz.utc) < last_tweet_timestamp+timedelta(minutes=loop_time):
                time_to_sleep = (last_tweet_timestamp+timedelta(minutes=loop_time))-datetime.now(pytz.utc)
                print("\nSLEEPING UNTIL "+str(time_to_sleep+datetime.now())+"\n")
                time.sleep(time_to_sleep.total_seconds())
            if media != None:
                try:
                    print("SENDING TWEET")
                    post_result = api.update_status(status=tweet, media_ids=[media.media_id])
                    #print(tape_name[0:7]+": "+frame['ts']+"\n")
                except Exception as e:
                    print("ERROR: COULD NOT TWEET VIDEO")
                    print(e)
            else:
                print("VIDEO NOT UPLOADED, SKIPPING TWEET")
        else:
            time_to_sleep = (5*60)
            print("\nSLEEPING UNTIL "+str(time_to_sleep+datetime.now())+"\n")
            time.sleep(time_to_sleep)
            
        if mastodon_media != None and mastodon != False:
            try:
                print("SENDING TO MASTODON")
                mastodon_client.status_post(mastodonCaption,media_ids=[mastodon_media])
            except Exception as e:
                print("ERROR: COULD NOT POST VIDEO TO MASTODON")
                print(e)
            
            if len(all_videos) > 1:
                all_videos.remove(video_filename)
            else:
                all_videos = videos
        else:
            print("VIDEO NOT UPLOADED, SKIPPING TOOT")

        print("CLEANING UP FILES")
        with open(temp_directory+delimeter+'persist.csv', 'w') as persistFile:
            persistFile.write(','.join(all_videos))
        os.remove(temp_directory+delimeter+'clip.mp4')
        os.remove(temp_directory+delimeter+'thumbnail.png')
        print(":::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::")
        print("RESTARTING LOOP\n")
        time.sleep(5)