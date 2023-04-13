import asyncio
import configparser
import csv
import cv2
import datetime
import discord
import facebook
import ffmpeg
import glob
import json
import math
import mastodon
import os
import pytumblr
import pytz
import random
import ray
import requests
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
clip_maximum = int(config['social']['clip maximum'])
file_max = int(config['social']['file size maximum'])
buffer_frames = [int(config['social']['front buffer']),int(config['social']['end buffer'])]

def next_thirty():
    current_time = time.time()
    next_half_hour = (current_time // 1800 + 1) * 1800
    if next_half_hour < 0:
        next_half_hour = 0
    wait_time = next_half_hour - current_time
    return next_half_hour, wait_time

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

def get_frame(json_filename, frameRate=30, scene_rgb=scene_rgb,clip_length=int(clip_length),clip_max=clip_maximum,persist=False):
    minimum_clip_frames = clip_length*frameRate
    tape_name = json_filename.replace('.json','.csv')
    with open(json_filename) as json_file:
        json_data = json.load(json_file)
        number_of_frames = int(json_data['analysis']['total frames'])
        if persist != False:
            try:
                #print("LOADING "+tape_name+".csv")
                with open(tape_name+'.csv', newline="") as framefile:
                    framesData = framefile.readlines()
                    framesData = framesData[0].split(',')
                random_frame = random.choice(list(set([x for x in range(buffer_frames[0],number_of_frames-buffer_frames[1])]) - set(framesData)))
            except:
                random_frame = random.sample(range(buffer_frames[0],number_of_frames-buffer_frames[1]),1)
        else:
            random_frame = random.sample(range(buffer_frames[0],number_of_frames-buffer_frames[1]),1)
        scene_rgb = scale_number(json_data['analysis']['median_rgb'],0,255,json_data['analysis']['min_rgb'],json_data['analysis']['max_rgb'])/3
        random_frame = random_frame[0]
        selected_frame_data = json_data['frames'][random_frame]
        rgb = scale_number(selected_frame_data['rgb'],0,255,json_data['analysis']['min_rgb'],json_data['analysis']['max_rgb'])
        try:
            while float(rgb) > scene_rgb:
                random_frame = random_frame + 1
                selected_frame_data = json_data['frames'][random_frame]
                rgb = scale_number(selected_frame_data['rgb'],0,255,json_data['analysis']['min_rgb'],json_data['analysis']['max_rgb'])
                #print("FRAME NUMBER "+str(random_frame)+" SELECTED, RGB = "+str(rgb),end='\r')
                #start_frame = random_frame
                while not (json_data['frames'][random_frame-2]['rgb'] > json_data['frames'][random_frame-1]['rgb'] > json_data['frames'][random_frame]['rgb'] < json_data['frames'][random_frame+1]['rgb'] < json_data['frames'][random_frame+2]['rgb']):
                    random_frame = random_frame + 1
                    #print("FRAME NUMBER "+str(random_frame)+" SELECTED, RGB = "+str(rgb),end='\r')
                    selected_frame_data = json_data['frames'][random_frame]
                    rgb = scale_number(selected_frame_data['rgb'],0,255,json_data['analysis']['min_rgb'],json_data['analysis']['max_rgb'])
        except IndexError as e:
            selected_frame_data = json_data['frames'][random_frame-1]
            rgb = scale_number(selected_frame_data['rgb'],0,255,json_data['analysis']['min_rgb'],json_data['analysis']['max_rgb'])
        start_frame = random_frame
        random_frame = start_frame + minimum_clip_frames
        try:
            last_frame_data = json_data['frames'][random_frame]
            rgb = scale_number(float(last_frame_data['rgb']),0,255,json_data['analysis']['min_rgb'],json_data['analysis']['max_rgb'])
        except IndexError as e:
            last_frame_data = json_data['frames'][random_frame-1]
            rgb = scale_number(last_frame_data['rgb'],0,255,json_data['analysis']['min_rgb'],json_data['analysis']['max_rgb'])
            #print("FRAME NUMBER "+str(random_frame)+" SELECTED, RGB = "+str(rgb),end='\r')
        while float(rgb) > scene_rgb and (random_frame-start_frame)/frameRate <= clip_max:
            random_frame = random_frame + 1
            try:
                last_frame_data = json_data['frames'][random_frame]
                rgb = scale_number(float(last_frame_data['rgb']),0,255,json_data['analysis']['min_rgb'],json_data['analysis']['max_rgb'])
            except IndexError as e:
                last_frame_data = json_data['frames'][random_frame-1]
                rgb = scale_number(last_frame_data['rgb'],0,255,json_data['analysis']['min_rgb'],json_data['analysis']['max_rgb'])
                break                
            #print("FRAME NUMBER "+str(random_frame)+" SELECTED, RGB = "+str(rgb),end='\r')
            try:
                while not (json_data['frames'][random_frame-2]['rgb'] > json_data['frames'][random_frame-1]['rgb'] > json_data['frames'][random_frame]['rgb'] < json_data['frames'][random_frame+1]['rgb'] < json_data['frames'][random_frame+2]['rgb']):
                    random_frame = random_frame + 1
                    last_frame_data = json_data['frames'][random_frame]
                    rgb = scale_number(float(last_frame_data['rgb']),0,255,json_data['analysis']['min_rgb'],json_data['analysis']['max_rgb'])
            except IndexError as e:
                last_frame_data = json_data['frames'][random_frame-1]
                rgb = scale_number(last_frame_data['rgb'],0,255,json_data['analysis']['min_rgb'],json_data['analysis']['max_rgb'])
                break
                #print("FRAME NUMBER "+str(random_frame)+" SELECTED, RGB = "+str(rgb),end='\r')
        #print("FRAME NUMBER "+str(random_frame)+" SELECTED, RGB = "+str(rgb),end='\n')
    return selected_frame_data, last_frame_data

def get_video(filename,start,end,crf=11):
    print("SAVING VIDEO FROM: "+filename)
    (
        ffmpeg
        .input(filename, ss=start, to=end)
        .output(temp_directory+delimeter+'clip.mp4', vcodec='libx264', preset='veryfast', crf=crf, acodec='aac', loglevel="quiet")
        .run(overwrite_output=True)
    )

def render_video(filename,outname,start,end,crf=22):
    print("RENDERING VIDEO AGAIN")
    (
        ffmpeg
        .input(filename, ss=start, to=end)
        .output(temp_directory+delimeter+outname, vcodec='libx264', preset='veryfast', crf=crf, acodec='aac', loglevel="quiet")
        .run(overwrite_output=True)
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

def social(videos,facebook=False,twitter=False,tumblr=False,useMastodon=False,useDiscord=False,persist=False):
    if facebook != False:
        fb_page_access_token = config['facebook']['access token']
        fb_page_id = config['facebook']['page id']
        
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
    
    if useDiscord != False:
        discord_token=config['discord']['access token']
        if ',' in config['discord']['channels']:
            discord_channels=config['discord']['channels'].split(',')
        else:
            discord_channels = []
            discord_channels.append(config['discord']['channels'])
    
    if persist == False:    
        all_videos = videos
    else:
        all_videos = []
        try:
            #print("LOADING persist.csv")
            with open(temp_directory+delimeter+'persist.csv', newline="") as csvfile:
                csvData = csvfile.readlines()
                csvData = csvData[0].split(',')
            for d in csvData:
                if d in videos:
                    all_videos.append(d)
                else:
                    print("NO MATCH FOUND FOR",d)
            if len(all_videos) <= 1:
                all_videos = videos
            print(len(all_videos),"VIDEOS FOUND")
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
        breakloop = False
        if int(len(all_videos)) <= 1:
            all_videos = list_videos(directory)
            print("SELECTING VIDEO FROM", len(all_videos), "VIDEO FILES")
            video_filename = random.choice(all_videos)
        else:
            try:
                print("SELECTING VIDEO FROM", len(all_videos), "VIDEO FILES")
                video_filename = random.choice(all_videos)
            except IndexError as e:
                all_videos = videos
                video_filename = random.choice(videos)
        
        if "http" not in video_filename:
            tape_name = video_filename.split(delimeter)[-1]
            tape_name = tape_name.split('.')[0]
        else:
            tape_name = video_filename.split('/')[-1]
            tape_name = tape_name.split('.')[0]            
        print(tape_name,"SELECTED!")
        json_filename = directory+delimeter+tape_name+'.json'
        #print(json_filename)
        if os.path.exists(json_filename) == False:
            print("JSON DATA FILE NOT FOUND, SCANNING",tape_name)
            filePathArray = video_filename.split(delimeter)
            filePathArray.pop()
            filePath = ""
            for p in filePathArray:
                filePath = filePath + p + delimeter
            videoscanner.scanVideo(tape_name+'.mp4',filePath)

        #print("SELECTING STARTING FRAME")
        video_data = videoscanner.getFrameRateDuration(video_filename)
        try:
            frame, last_frame = get_frame(json_filename,int(video_data[0]),persist)
        except Exception as e:
            print(e)
            continue
        framesList = list(range(frame['f'], last_frame['f']-1))
        
        if persist != False:
            try:
                #print("LOADING "+tape_name+".csv")
                with open(temp_directory+delimeter+tape_name+'.csv', newline="") as framefile:
                    framesData = framefile.readlines()
                    framesData = framesData[0].split(',')
                    framesDataInt = [eval(i) for i in framesData]
                    frameExists = bool(set(framesList).intersection(framesDataInt))
                    whileLoop = 0
                    while frameExists != False:
                        whileLoop += 1
                        if whileLoop < 200:
                            print("FRAME FOUND IN",tape_name+".csv. GETTING NEW FRAMES "+str(whileLoop)+"x",end='\r')
                            frame, last_frame = get_frame(json_filename,int(video_data[0]),persist)
                            framesList = list(range(frame['f'], last_frame['f']-1))
                            frameExists = bool(set(framesList).intersection(framesDataInt))
                            breakloop = False
                        else:
                            breakloop = True
                            break
                    if breakloop == True:
                        breakloop = False
                        continue
                all_frames = framesList
                all_frames.extend(framesData)
            except Exception as e:
                print("ERROR: COULD NOT LOAD "+tape_name+".csv")
                print(e)
                all_frames = framesList
            print('')

        video = cv2.VideoCapture(video_filename)
        frameTimeSeconds = frame['f']/int(video_data[0])
        endTimeSeconds = last_frame['f']/int(video_data[0])
        
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
            if entryTimeSeconds > endTimeSeconds:
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
                
                
        print("\nFIRST FRAME:",frame['f'],frame['ts'])
        print("LAST FRAME:",last_frame['f'],last_frame['ts'])
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
            render_video(temp_directory+delimeter+'clip.mp4','newclip.mp4',0,clip_duration-time_over,crf=22)

            os.remove(temp_directory+delimeter+'clip.mp4')
            os.rename(temp_directory+delimeter+'newclip.mp4',temp_directory+delimeter+'clip.mp4')
            file_size = os.path.getsize(temp_directory+delimeter+"clip.mp4")
            clip_duration = get_duration(temp_directory+delimeter+'clip.mp4')
            print("\nCLIP SIZE:", round(file_size/1024/1024,4), "megabytes")
            print("CLIP LENGTH:", round(clip_duration,1), "SECONDS")

        #print("\nGETTING THUMBNAIL")
        video.set(cv2.CAP_PROP_POS_FRAMES,int(frame['f'])+round(clip_duration/2)*int(video_data[0]))
        success, image = video.read()
        if success:
            resized_image = cv2.resize(image, (640,480))
            cv2.imwrite(temp_directory+delimeter+"thumbnail.png", resized_image)

        times = next_thirty()
        print("SLEEPING UNTIL",time.ctime(times[0]))
        try:
            time.sleep(times[1])
        except ValueError as e:
            print(e)

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
            #print(e)
            hashtags = hashtags
            
        rays = []
        returns = 0
        if twitter != False:
            @ray.remote
            def tw():
                blocking_statuses = ['pending', 'in_progress']
                try:
                    tweet = tapeID+"\n"+frame['ts'].split('.')[0]+"\n"+program+"\n"+station+"\n"+airDateShort+"\n"+hashtagString
                except:
                    tweet = "Tape ID: "+tape_name[0:7]+"\nTimestamp: "+frame['ts'].split('.')[0]+"\n"+hashtagString
                if len(tweet) > 280:
                    tweet = +tapeID+"\n"+frame['ts'].split('.')[0]+"\n"+program+"\n"+station+"\n"+airDateShort+"\n"+hashtagString

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
                if media != None:
                    #checking if file is still processing
                    blocking_statuses = ['pending', 'in_progress']
                    if (hasattr(media, 'processing_info') and media.processing_info['state'] in blocking_statuses):
                        check_after = media.processing_info['check_after_secs']
                        print("WAITING FOR TWITTER UPLOAD TO COMPLETE AT",datetime.datetime.now()+datetime.timedelta(seconds=check_after))
                        #print("SLEEPING UNTIL "+str(datetime.now()+timedelta(seconds=check_after))+"\n")
                        time.sleep(check_after)
                    '''if datetime.now(pytz.utc) < last_tweet_timestamp+timedelta(minutes=loop_time):
                        time_to_sleep = (last_tweet_timestamp+timedelta(minutes=loop_time))-datetime.now(pytz.utc)
                        print("\nSLEEPING UNTIL "+str(time_to_sleep+datetime.now())+"\n")
                        time.sleep(time_to_sleep.total_seconds())'''
                    try:
                        print("SENDING TWEET")
                        post_result = api.update_status(status=tweet, media_ids=[media.media_id])
                        #print(tape_name[0:7]+": "+frame['ts']+"\n")
                    except Exception as e:
                        print("ERROR: COULD NOT TWEET VIDEO")
                        print(e)
                else:
                    print("VIDEO NOT UPLOADED, SKIPPING TWEET")
            returns += 1
            rays.append(tw.remote())
            #return True

        if tumblr != False:
            @ray.remote
            def tb():
                try:
                    tumblrCaption = "Tape ID: "+tapeID+"<br>Timestamp: "+frame['ts'].split('.')[0]+"<br>Program: "+program+"<br>Network/Station: "+station+"<br>Broadcast Location: "+location+"<br>Air Date: "+airDateLong
                except:
                    tumblrCaption = "Tape ID: "+tape_name[0:7]+"<br>Timestamp: "+frame['ts'].split('.')[0]

                #print("\nTUMBLR:\n"+tumblrCaption)
                try:
                    print("SENDING TO TUMBLR")
                    caption = tumblrCaption
                    tags = hashtags
                    tumblr_post = tumblr_client.create_video('foundonvhs',caption=caption,tags=tags,data=temp_directory+delimeter+"clip.mp4")
                except Exception as e:
                    print("ERROR: COULD NOT POST VIDEO TO TUMBLR")
                    print(e)
            returns += 1
            rays.append(tb.remote())
            #return True

        if facebook != False:
            @ray.remote
            def fb():
                try:
                    facebookCaption = "Tape ID: "+tapeID+"\nTimestamp: "+frame['ts'].split('.')[0]+"\nAir Date: "+airDateLong+"\nProgram: "+program+"\nNetwork/Station: "+station+"\nBroadcast Location: "+location+"\n"+hashtagString
                except:
                    facebookCaption = facebookCaption = "Tape ID: "+tape_name[0:7]+"\nTimestamp: "+frame['ts'].split('.')[0]+"\n"+hashtagString
                #print("\nFACEBOOK:\n"+facebookCaption)
                try:
                    print("UPLOADING VIDEO TO FACEBOOK")
                    fb_url = 'https://graph.facebook.com/'+fb_page_id+'/videos'
                    video_file ={'source':open(temp_directory+delimeter+"clip.mp4",'rb')}
                    fb_payload = {'description':facebookCaption,'access_token':fb_page_access_token}
                    fb_flag = requests.post(fb_url, files=video_file, data=fb_payload)
                    video_file['source'].close()
                    #print(fb_flag.text)
                except Exception as e:
                    print("ERROR UPLOADING TO FACEBOOK")
                    print(e)
            returns += 1
            rays.append(fb.remote())
            #return True
        
        if useMastodon != False:
            @ray.remote
            def mast():
                try:
                    mastodonCaption = "Tape ID: "+tapeID+"\nTimestamp: "+frame['ts'].split('.')[0]+"\nProgram: "+program+"\nNetwork/Station: "+station+"\nBroadcast Location: "+location+"\nAir Date: "+airDateLong+"\n"+"#bot "+hashtagString
                except:
                    mastodonCaption = "Tape ID: "+tape_name[0:7]+"\nTimestamp: "+frame['ts'].split('.')[0]+"\n"+"#bot "+hashtagString
                #print("\nMASTODON:\n"+mastodonCaption)
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
                if mastodon_media != None:
                    while mastodon_media['url'] == None:
                        mastodon_media = mastodon_client.media(mastodon_media.id)
                        #print(mastodon_media)
                        if mastodon_media.url == None:
                            print("MASTODON MEDIA URL NOT READY, CHECKING AGAIN IN 10 SECONDS")
                            time.sleep(10)
                        else:
                            print("MASTODON URL READY! POSTING VIDEO TO MASTODON")
                    try:
                        mastodon_client.status_post(mastodonCaption,media_ids=[mastodon_media])
                    except Exception as e:
                        print("ERROR: COULD NOT POST VIDEO TO MASTODON")
                        print(e)
                else:
                    print("VIDEO NOT UPLOADED, SKIPPING TOOT")
            returns += 1
            rays.append(mast.remote())
            #return True

        if useDiscord != False:
            @ray.remote
            def disc(clip_duration=clip_duration):
                crfValue = 28
                render_video(temp_directory+delimeter+'clip.mp4','foundonvhs.mp4',0,clip_duration,crf=crfValue)
                new_file_size = os.path.getsize(temp_directory+delimeter+"foundonvhs.mp4")
                while new_file_size > 8*1024*1024:
                    size_over = new_file_size - 8*1024*1024
                    size_over_kb = size_over/1024
                    size_over_mb = size_over_kb/1024
                    if size_over_mb < 1:
                        if size_over_kb < 1:
                            print("FILE SIZE EXCEEDS DISCORD MAXIMUM OF",8,"MEGABYTES BY",round(size_over,2),"BYTES")
                        else:
                            print("FILE SIZE EXCEEDS DISCORD MAXIMUM OF",8,"MEGABYTES BY",round(size_over/1024,2),"KILOBYTES")
                    else:
                        print("FILE SIZE EXCEEDS DISCORD MAXIMUM OF",8,"MEGABYTES BY",round(size_over_mb,2),"MEGABYTES")
                    clip_duration = get_duration(temp_directory+delimeter+'foundonvhs.mp4',int(video_data[0]))
                    bytes_per_second = round(file_size/clip_duration)
                    crfValue=crfValue+math.ceil(size_over_mb*.75)
                    print("INCREASING CRF VALUE TO",crfValue)
                    render_video(temp_directory+delimeter+'clip.mp4','foundonvhs.mp4',0,clip_duration,crf=crfValue)
                    new_file_size = os.path.getsize(temp_directory+delimeter+"foundonvhs.mp4")
                    print("\nCLIP SIZE:", round(new_file_size/1024/1024,4), "megabytes")

                try:
                    discordCaption = "Tape ID: "+tapeID+"\nTimestamp: "+frame['ts'].split('.')[0]+"\nDuration: "+str(round(clip_duration,1))+" Seconds"+"\nProgram: "+program+"\nNetwork/Station: "+station+"\nBroadcast Location: "+location+"\nAir Date: "+airDateLong
                except:
                    discordCaption = "Tape ID: "+tape_name[0:7]+"\nTimestamp: "+frame['ts'].split('.')[0]+"\nDuration: "+str(round(clip_duration,1))+" Seconds"
                print("SENDING VIDEO TO DISCORD")
                discord_intents=discord.Intents.default()
                discord_intents.message_content=True
                discord_client=discord.Client(intents=discord_intents)
                
                @discord_client.event
                async def on_ready():
                    for discord_channel in discord_channels:
                        channel = discord_client.get_channel(int(discord_channel))
                        await channel.send(discordCaption,file=discord.File(temp_directory+delimeter+'foundonvhs.mp4'))
                    await discord_client.close()
                try:
                    discord_client.run(discord_token, log_handler=None)
                except Exception as e:
                    print("ERROR: COULD NOT SEND VIDEO TO DISCORD")
                    print(e)
                os.remove(temp_directory+delimeter+'foundonvhs.mp4')
            returns += 1
            rays.append(disc.remote())
            #return True

        try:
            ray.get(rays)
            while len(rays) > 0:
                done, rays = ray.wait(rays)
            print("ALL SOCIAL POSTING PROCESSES COMPLETE AT", datetime.now())
            if int(len(all_videos)) <= 1:
                print("RESETTING VIDEO LIST")
                all_videos = videos
            else:
                all_videos.remove(video_filename)
                print(len(all_videos),"VIDEO FILES REMAIN")

            print("CLEANING UP FILES")
            if persist != False:
                with open(temp_directory+delimeter+'persist.csv', 'w') as persistFile:
                    persistFile.write(','.join(all_videos))
                with open(temp_directory+delimeter+tape_name+'.csv', 'w') as framesFile:
                    all_frames = list(map(int, all_frames))
                    all_frames = list(set(all_frames))
                    all_frames.sort()
                    framesFile.write(','.join(str(a) for a in all_frames))

            try:
                os.remove(temp_directory+delimeter+'clip.mp4')
                fileInUse = False
            except PermissionError as e:
                fileInUse = True
            while fileInUse == True:
                print("VIDEO FILE STILL IN USE, CHECKING AGAIN IN 60 SECONDS")
                time.sleep(60)
                try:
                    os.remove(temp_directory+delimeter+'clip.mp4')
                    fileInUse = False
                except PermissionError as e:
                    fileInUse = True

            os.remove(temp_directory+delimeter+'thumbnail.png')
        except Exception as e:
            print(e)

        print("\n:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::\n")
        print("RESTARTING LOOP\n")
        time.sleep(5)