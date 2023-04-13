import asyncio
import configparser
import cv2
import datetime
import discord
import ffmpeg
import getvid
import glob
import html
import json
import math
import mastodon
import os
import pytumblr
import pytz
import random
import re
import requests
import sys
import time
import tweepy
import videoscanner
from discord.ext import commands
from multiprocessing import Process

if os.name == 'nt':
    delimeter = '\\'
else:
    delimeter = '/'
    
scriptPath = os.path.realpath(os.path.dirname(__file__))

config = configparser.ConfigParser()
config.read(scriptPath + delimeter + 'config.ini')
temp_directory = config['social']['temp directory']
video_directory = config['social']['video directory']
vhs_json_file = config['social']['json file']

def runInParallel(*fns):
  proc = []
  for fn in fns:
    p = Process(target=fn)
    p.start()
    proc.append(p)
  for p in proc:
    p.join()

def list_videos(directory):
    all_videos = []

    for video_file in glob.glob(directory+delimeter+"*.mp4"):
        all_videos.append(video_file)
    return all_videos

def grab_video(filename,outfile,start,end,crf=11):
    #print("SAVING VIDEO FROM: "+filename)
    (
        ffmpeg
        .input(filename, ss=start, to=end)
        .output(outfile, vcodec='libx264', preset='veryfast', crf=crf, acodec='aac', loglevel="quiet")
        .run(overwrite_output=True)
    )

def video_resize(original_file,file,ts,te,max_mb=8):
    crfValue = 28
    grab_video(original_file,file,ts,te,crf=crfValue)
    new_file_size = os.path.getsize(file)
    video_data = videoscanner.getFrameRateDuration(file)
    while new_file_size > max_mb*1024*1024:
        size_over = new_file_size - max_mb*1024*1024
        size_over_kb = size_over/1024
        size_over_mb = size_over_kb/1024
        if size_over_mb < 1:
            if size_over_kb < 1:
                print("FILE SIZE EXCEEDS MAXIMUM OF",max_mb,"MEGABYTES BY",round(size_over,2),"BYTES")
            else:
                print("FILE SIZE EXCEEDS MAXIMUM OF",max_mb,"MEGABYTES BY",round(size_over/1024,2),"KILOBYTES")
        else:
            print("FILE SIZE EXCEEDS MAXIMUM OF",max_mb,"MEGABYTES BY",round(size_over_mb,2),"MEGABYTES")        
        clip_duration = getvid.get_duration(file,int(video_data[0]))
        bytes_per_second = round(new_file_size/clip_duration)
        crfValue=crfValue+math.ceil(size_over_mb*0.5)
        print("INCREASING CRF VALUE TO",crfValue)
        grab_video(original_file,file,ts,te,crf=crfValue)
        new_file_size = os.path.getsize(file)
        print("\nCLIP SIZE:", round(new_file_size/1024/1024,4), "megabytes")
    return video_data

def remove_html_markup(s):
    tag = False
    quote = False
    out = ""
    s=s.replace('<br />','\n')
    for c in s:
        if c == '<' and not quote:
            tag = True
        elif c == '>' and not quote:
            tag = False
        elif (c == '"' or c == "'") and tag:
            quote = not quote
        elif not tag:
            out = out + c

    return out

def get_last_tweet(file):
    f = open(file, 'r')
    lastId = int(f.read().strip())
    f.close()
    return lastId

def put_last_tweet(file, Id):
    f = open(file, 'w')
    f.write(str(Id))
    f.close()
    return

def get_duration(filename):
    video = cv2.VideoCapture(filename)
    frame_count = video.get(cv2.CAP_PROP_FRAME_COUNT)
    fps = video.get(cv2.CAP_PROP_FPS)
    duration = frame_count/fps
    return duration

def checkTwitter():
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
        print("[TWITTER] Starting Twitter Mention Monitoring")
        while True:
            data = {}
            #tweets = api.user_timeline(twitter_username, count=1) #get last tweet
            try:
                last_id = get_last_tweet(temp_directory+delimeter+'tweet_ID.txt')
            except FileNotFoundError:
                last_id = 0
                with open(temp_directory+delimeter+'tweet_ID.txt', 'w') as newFile:
                    newFile.write('0')
            mentions = api.mentions_timeline(count=20, tweet_mode='extended') #get last 20 mentions
            if len(mentions) == 0:
                print("[TWITTER] No mentions found, checking again at",datetime.datetime.now()+datetime.timedelta(minutes=1))
                time.sleep(60)
            else:
                for mention in reversed(mentions):
                    new_id = mention.id
                    if mention.in_reply_to_status_id_str != None and new_id > last_id and '#submit' in mention._json['full_text']:
                        in_reply_to = mention.in_reply_to_status_id_str
                        replied_tweet = api.get_status(in_reply_to, tweet_mode='extended')
                        replied_lines = replied_tweet._json['full_text'].replace(';','\n').split('\n')
                        print("[TWITTER]",mention.id, mention.author.screen_name, mention._json['full_text'])
                        #try:
                        if len(replied_lines) <= 3:
                            for replied_line in replied_lines:
                                if "Tape ID:" in replied_line:
                                    data['tape_id'] = replied_line.replace('Tape ID: ','')
                                if "Timestamp:" in replied_line:
                                    timestamp = replied_line.replace('Timestamp: ','')
                        elif len(replied_lines) == 6:
                            data['tape_id'] = replied_lines[0]
                            timestamp = replied_lines[1]
                            data['program'] = replied_lines[2]
                            data['network'] = replied_lines[3]
                            data['airdate'] = datetime.datetime.strptime(replied_lines[4],'%b %d, %Y').strftime('%Y-%m-%d')
                        try:
                            timestamp = datetime.datetime.strptime(timestamp, '%H:%M:%S.%f')
                        except:
                            timestamp = datetime.datetime.strptime(timestamp, '%H:%M:%S')
                        duration = get_duration(replied_tweet._json['extended_entities']['media'][0]['video_info']['variants'][0]['url'])
                        #print("DURATION:",duration)
                        duration = datetime.timedelta(seconds=duration)
                        istimestart = False
                        istimeend = False
                        mention_text = mention._json['full_text'].replace('@'+twitter_username, '').replace('#','\n#')
                        for line in mention_text.split('\n'):
                            try: data['program']
                            except KeyError:
                                if '#program' in line:
                                    data['program'] = line.replace('#program ','')
                            try: data['clip']
                            except KeyError:
                                if '#clip' in line:
                                    data['clip'] = line.replace('#clip ','')
                            try: data['network']
                            except KeyError:
                                if '#network' in line:
                                    data['network'] = line.replace('#network ','')
                            try: data['location']
                            except KeyError:
                                if '#location' in line:
                                    data['location'] = line.replace('#location ','')
                            try: data['airdate']
                            except KeyError:
                                if '#airdate' in line:
                                    data['airdate'] = line.replace('#airdate ','')
                            if '#year' in line:
                                data['year'] = line.replace('#year ','')
                            if '#timestart' in line:
                                timestart = line.replace('#timestart ','')
                                time_seconds = int(timestart.split(':')[-1])+int(timestart.split(':')[-2])*60
                                timedelta = datetime.timedelta(seconds=time_seconds)
                                timestart_ = timestamp + timedelta
                                data['timestart'] = timestart_.strftime('%H:%M:%S')
                                istimestart = True
                            else:
                                if istimestart == False:
                                    data['timestart'] = timestamp.strftime('%H:%M:%S')
                            if '#timeend' in line:
                                timeend = line.replace('#timeend ','')
                                timeend_seconds = int(timeend.split(':')[-1])+int(timeend.split(':')[-2])*60
                                timendelta = datetime.timedelta(seconds=timeend_seconds)
                                timeend = timestamp + timendelta
                                istimeend = True
                            else:
                                if istimeend == False:
                                    timeend = timestamp + duration
                            data['timeend'] = timeend.strftime('%H:%M:%S')
                            if '#tags' in line:
                                data['tags'] = line.replace('#tags ','').split(',')
                                data['tags'] = [t.strip() for t in data['tags']]
                        data['submitted_by'] = mention.author.screen_name
                        try:
                            with open(temp_directory+delimeter+'_twitter.json') as json_file:
                                json_data = json.load(json_file)
                        except:
                                json_data = []
                        json_data.append(data)
                        json_data = sorted(json_data, key=lambda d: (d['tape_id'].upper(), d['timestart']))
                        with open(temp_directory+delimeter+'_twitter.json', 'w') as json_file:
                            json_file.write(json.dumps(json_data, indent=4))
                        try:
                            api.create_favorite(mention.id)
                        except:
                            pass
                        '''except Exception as e:
                            print(e)
                            print("[TWITTER] Mention is not data submission")'''
                        
                    elif new_id > last_id and '#video' in mention._json['full_text']:
                        try:
                            api.create_favorite(mention.id)
                        except:
                            pass
                        print("[TWITTER] #video Command initiated by",mention.author.screen_name)
                        print("[TWITTER]",mention.id, mention.author.screen_name, mention._json['full_text'])
                        mention_text = mention._json['full_text'].replace('@'+twitter_username, '').replace('#','\n#')
                        for line in mention_text.split('\n'):
                            all_videos = list_videos(video_directory)
                            if '#tape' in mention_text and '#tape' in line:
                                match_videos = []
                                for video in all_videos:
                                    videofilename = video.split(delimeter)[-1]
                                    if videofilename.startswith(line.replace('#tape ','').strip()):
                                        match_videos.append(video)
                                if len(match_videos) > 0:
                                    chosen_video = random.choice(match_videos)
                                else:
                                    chosen_video = random.choice(all_videos)
                            elif '#tape' not in mention_text:
                                chosen_video = random.choice(all_videos)
                            if '#timestart' in mention_text and '#timestart' in line:
                                if line.count(':') == 2:
                                    timestart = datetime.datetime.strptime(line.replace('#timestart','').strip(), "%H:%M:%S") - datetime.datetime(1900,1,1)
                                elif line.count(':') == 1:
                                    timestart = datetime.datetime.strptime(line.replace('#timestart','').strip(), "%M:%S") - datetime.datetime(1900,1,1)
                                else:
                                    timestart = datetime.datetime.strptime(line.replace('#timestart','').strip(), "%S") - datetime.datetime(1900,1,1)
                                startseconds = float(timestart.total_seconds())
                            if '#timeend' in mention_text and '#timeend' in line:
                                if line.count(':') == 2:
                                    timeend = datetime.datetime.strptime(line.replace('#timeend','').strip(), "%H:%M:%S") - datetime.datetime(1900,1,1)
                                elif line.count(':') == 1:
                                    timeend = datetime.datetime.strptime(line.replace('#timeend','').strip(), "%M:%S") - datetime.datetime(1900,1,1)
                                else:
                                    timeend = datetime.datetime.strptime(line.replace('#timeend','').strip(), "%S") - datetime.datetime(1900,1,1)
                                #te = flags.timeend
                                endseconds = float(timeend.total_seconds())

                        video_json = chosen_video.replace('.mp4','.json')
                        tape_name = chosen_video.split(delimeter)[-1].split('.')[0][0:7]
                        skipdurationcheck = False
                        if os.path.exists(video_json) == False:
                            api.update_status(status="The data file for "+tape_name+" is missing. Creating a new one, but it will take a while.", in_reply_to_status_id = mention.id, auto_populate_reply_metadata=True)
                            filePathArray = chosen_video.split(delimeter)
                            filePathArray.pop()
                            filePath = ""
                            for p in filePathArray:
                                filePath = filePath + p + delimeter
                            videoscanner.scanVideo(tape_name,filePath)

                        if '#timestart' not in mention_text and '#timeend' not in mention_text:
                            skipdurationcheck = True
                            firstframe,lastframe = getvid.get_frame(video_json, clip_length=15, clip_max=140)
                            try:
                                timestart = datetime.datetime.strptime(firstframe['ts'], "%H:%M:%S.%f") - datetime.datetime(1900,1,1)
                            except:
                                timestart = datetime.datetime.strptime(firstframe['ts'], "%H:%M:%S") - datetime.datetime(1900,1,1)
                            try:
                                timeend = datetime.datetime.strptime(lastframe['ts'], "%H:%M:%S.%f") - datetime.datetime(1900,1,1)
                            except:
                                timeend = datetime.datetime.strptime(lastframe['ts'], "%H:%M:%S") - datetime.datetime(1900,1,1)
                            startseconds = float(timestart.total_seconds())
                            endseconds = float(timeend.total_seconds())
                        elif '#timestart' in mention_text and '#timeend' not in mention_text:
                            endseconds = float(startseconds) + 140
                        elif '#timestart' not in mention_text and '#timeend' in mention_text:
                            startseconds = float(endseconds) - 140
                        if float(endseconds) - float(startseconds) > 140 and skipdurationcheck != True:
                            endseconds = float(startseconds) + 140
                        else:
                            outfilename = temp_directory+delimeter+chosen_video.split(delimeter)[-1].split('.')[0][0:7]+"_"+mention.author.screen_name+'.mp4'
                            ts = str(datetime.timedelta(seconds=startseconds))
                            te = str(datetime.timedelta(seconds=endseconds))
                            try:
                                print("[TWITTER]",end=" ")
                                print("Redering Video Selection")
                                video_data = video_resize(chosen_video,outfilename,ts,te,max_mb=512)
                            except TypeError:
                                #await ctx.reply('Timestamp exceeds video length.')
                                api.update_status(status="The timestamp requested for "+tape_name+" exceeds the video length. Please try again.", in_reply_to_status_id = mention.id, auto_populate_reply_metadata=True)
                                return
                            get_duration(outfilename)

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
                                if entryTimeSeconds > float(endseconds):
                                    thisEntry = entry
                                    tapeID = thisEntry['Tape_ID']
                                    #print("\nTAPE ID: "+tapeID)
                                    program = thisEntry['Programs']
                                    #print("PROGRAM: "+program)
                                    station = thisEntry['Network/Station']
                                    #print("NETWORK/STATION: "+station)
                                    location = thisEntry['Location']
                                    #print("LOCATION: "+location)
                                    try:
                                        airDate = datetime.datetime.strptime(thisEntry['Recording Date'], '%Y-%m-%d')
                                        airDateLong = datetime.datetime.strftime(airDate,'%A %B %d, %Y')
                                        airDateShort = datetime.datetime.strftime(airDate,'%b %d, %Y')
                                        #print("AIR DATE: "+airDateLong)
                                    except Exception as e:
                                        print(e)
                                        #print("ERROR: AIR DATE NOT FOUND")
                                        pass
                                    #break

                            try:
                                #caption = "Tape ID: "+tapeID+"\nTimestamp: "+ts+"\nDuration: "+str(video_data[1])+" Seconds"+"\nProgram: "+program+"\nNetwork/Station: "+station+"\nBroadcast Location: "+location+"\nAir Date: "+airDateLong
                                tweet = tapeID+"\n"+ts.split('.')[0]+"\n"+program+"\n"+station+"\n"+airDateShort
                            except:
                                #caption = "Tape ID: "+tape_name[0:7]+"\nTimestamp: "+ts+"\nDuration: "+str(video_data[1])+" Seconds"
                                try:
                                    tweet = tapeID+"\n"+ts.split('.')[0]+"\n"+program+"\n"+station
                                except:
                                    tweet = "Tape ID: "+tape_name[0:7]+"\nTimestamp: "+ts.split('.')[0]
                                    
                            print("[TWITTER]",end=" ")
                            try:
                                print("Uploading video to Twitter:\n"+tweet)
                                media = api.chunked_upload(outfilename,media_category="tweet_video")
                                time.sleep(10)
                            except Exception as e:
                                print("[TWITTER] Error uploading video to twitter")
                                print(e)
                                time.sleep(10)
                                try:
                                    print("[TWITTER] Uploading video to Twitter again")
                                    media = api.chunked_upload(outfilename,media_category="tweet_video")
                                    time.sleep(10)
                                except Exception as e:
                                    print("[TWITTER] Error uploading video to twitter")
                                    print(e)
                                    media = None
                            blocking_statuses = ['pending', 'in_progress']
                            if (hasattr(media, 'processing_info') and media.processing_info['state'] in blocking_statuses):
                                check_after = media.processing_info['check_after_secs']+1
                                print("[TWITTER] Waiting for upload to complete at",datetime.datetime.now()+datetime.timedelta(seconds=check_after))
                                time.sleep(check_after)
                            print("[TWITTER]",end=" ")
                            print("Upload complete, sending reply")
                            #try:
                            if hasattr(media, 'media_id'):
                                post_result = api.update_status(status=tweet, media_ids=[media.media_id], in_reply_to_status_id=mention.id, auto_populate_reply_metadata=True)
                            else:
                                print("[TWITTER] Media missing media_id attribute")
                                print(media)
                            '''except Exception as e:
                                api.update_status(status="Sorry, there was an error :(", in_reply_to_status_id = mention.id, auto_populate_reply_metadata=True)
                                print("An error prevented the video from being tweeted.")'''
                            os.remove(outfilename)
                            time.sleep(2.5)

                    put_last_tweet(temp_directory+delimeter+'tweet_ID.txt',new_id)
                #print("[TWITTER] Done processing mentions, checking again at",datetime.datetime.now()+datetime.timedelta(minutes=1))
                time.sleep(60)

def checkDiscord():
    class DataFlags(commands.FlagConverter):
        tape: str = None
        tags: str = None
        program: str = None
        clip: str = None
        network: str = None
        location: str = None
        airdate: str = None
        year: int = None
        timestart: str = None
        timeend: str = None
    
    discord_token=config['discord']['access token']
    if ',' in config['discord']['channels']:
        discord_channels=config['discord']['channels'].split(',')
    else:
        discord_channels = []
        discord_channels.append(config['discord']['channels'])
    discord_intents=discord.Intents.default()
    discord_intents.message_content=True
    discord_bot=commands.Bot(intents=discord_intents, command_prefix='!')
    @discord_bot.event
    async def on_ready():
        print("[DISCORD]",end=" ")
        print(f'{discord_bot.user.name} has connected to Discord.')
    @discord_bot.command(help="Detailed explanation of the !submit command")
    async def explain(ctx):
        helpMessage = "Submit clip information by replying to a video clip with `!submit` and any of the following flags followed by a colon:\n\
        `timestart:` timestamp of start of defined clip (default 0:00)\n\
        `timeend:` timestamp of end of defined clip (default is end of clip)\n\
        `program:` name of the TV program or broadcast in the clip\n\
        `clip:` name of the commercial, bump or other content featured in the clip\n\
        `network:` name of the TV network or station identification\n\
        `location:` broadcast location where the content was recorded from\n\
        `airdate:` exact date of broadcast in YYYY-MM-DD or MM-DD-YYYY format\n\
        `year:` year of broadcast in YYYY format\n\
        `tags:` comma separated tags indicating what is in the clip\n\
        use `!example` for an example command"
        await ctx.reply(helpMessage)

    @discord_bot.command(help="Show an example of the !submit command")
    async def example(ctx):
        helpExample = "`!submit timestart: 0:15 timeend: 0:30 clip: Serpentini Chevrolet Commercial network: ABC/WEWS 5 location: Cleveland, OH airdate: 1999-05-20`\n\
        The above command indicates that the Serpentini Chevorlet commercial exists between 15 and 30 seconds on the clip and was aired on WEWS 5, and ABC affiliate in Cleveland, Ohio on May 20, 1999"
        await ctx.reply(helpExample)
    
    @discord_bot.command(help="Get list of video IDs sent to your inbox")
    async def videolist(ctx):
        all_videos = list_videos(video_directory)
        message = "Here are all of the currently available video IDs\n"
        i = 1
        for video in all_videos:
            if i%3 != 0:
                message += video.split(delimeter)[-1][0:7]+"   |   "
            else:
                message += video.split(delimeter)[-1][0:7]+"\n"
            i += 1
        user = discord_bot.get_user(int(ctx.author.id))
        await ctx.reply("DMing video list now.")
        print("[DISCORD]",end=" ")
        print("Sending video list in DM to",ctx.author.name)
        await ctx.author.send(message)

    @discord_bot.command(help="Get a video clip")
    async def video(ctx, *, flags: DataFlags):
        print("[DISCORD]",end=" ")
        print("!video Command initated by", ctx.author.name)
        all_videos = list_videos(video_directory)
        match_videos = []
        if flags.tape != None:
            for video in all_videos:
                videofilename = video.split(delimeter)[-1]
                if videofilename.startswith(flags.tape):
                    match_videos.append(video)
            if len(match_videos) > 0:
                chosen_video = random.choice(match_videos)
            else:
                chosen_video = random.choice(all_videos)
        else:
            chosen_video = random.choice(all_videos)
        video_json = chosen_video.replace('.mp4','.json')
        tape_name = chosen_video.split(delimeter)[-1].split('.')[0][0:7]
        skipdurationcheck = False
        if os.path.exists(video_json) == False:
            ctx.reply("json data not found, scanning video file (this could take a while)")
            filePathArray = chosen_video.split(delimeter)
            filePathArray.pop()
            filePath = ""
            for p in filePathArray:
                filePath = filePath + p + delimeter
            videoscanner.scanVideo(tape_name,filePath)
        
        if flags.timestart != None:
            if flags.timestart.count(':') == 2:
                timestart = datetime.datetime.strptime(flags.timestart, "%H:%M:%S") - datetime.datetime(1900,1,1)
            elif flags.timestart.count(':') == 1:
                timestart = datetime.datetime.strptime(flags.timestart, "%M:%S") - datetime.datetime(1900,1,1)
            else:
                timestart = datetime.datetime.strptime(flags.timestart, "%S") - datetime.datetime(1900,1,1)
            #ts = flags.timestart
            startseconds = float(timestart.total_seconds())
        if flags.timeend != None:
            if flags.timeend.count(':') == 2:
                timeend = datetime.datetime.strptime(flags.timeend, "%H:%M:%S") - datetime.datetime(1900,1,1)
            elif flags.timeend.count(':') == 1:
                timeend = datetime.datetime.strptime(flags.timeend, "%M:%S") - datetime.datetime(1900,1,1)
            else:
                timeend = datetime.datetime.strptime(flags.timeend, "%S") - datetime.datetime(1900,1,1)
            #te = flags.timeend
            endseconds = float(timeend.total_seconds())
        if flags.timestart == None and flags.timeend == None:
            skipdurationcheck = True
            firstframe,lastframe = getvid.get_frame(video_json, clip_length=15, clip_max=35)
            #ts = firstframe['ts']
            try:
                timestart = datetime.datetime.strptime(firstframe['ts'], "%H:%M:%S.%f") - datetime.datetime(1900,1,1)
            except:
                timestart = datetime.datetime.strptime(firstframe['ts'], "%H:%M:%S") - datetime.datetime(1900,1,1)
            #te = lastframe['ts']
            try:
                timeend = datetime.datetime.strptime(lastframe['ts'], "%H:%M:%S.%f") - datetime.datetime(1900,1,1)
            except:
                timeend = datetime.datetime.strptime(lastframe['ts'], "%H:%M:%S") - datetime.datetime(1900,1,1)
            startseconds = float(timestart.total_seconds())
            endseconds = float(timeend.total_seconds())
        elif flags.timestart != None and flags.timeend == None:
            endseconds = float(startseconds) + 35
        elif flags.timestart == None and flags.timeend != None:
            startseconds = float(endseconds) - 35
        if float(endseconds) - float(startseconds) > 35 and skipdurationcheck != True:
            await ctx.reply('Please enter a timestamp range of 35 seconds or less')
        else:
            outfilename = temp_directory+delimeter+chosen_video.split(delimeter)[-1].split('.')[0][0:7]+"_"+ctx.author.name+'.mp4'
            ts = str(datetime.timedelta(seconds=startseconds))
            te = str(datetime.timedelta(seconds=endseconds))
            try:
                print("[DISCORD]",end=" ")
                print("Redering Video Selection")
                video_data = video_resize(chosen_video,outfilename,ts,te)
            except TypeError:
                await ctx.reply('Timestamp exceeds video length.')
                return
            getvid.get_duration(outfilename)
            
            j = open(vhs_json_file,)
            tapeData = json.load(j)
            thisTape = []
            
            for entry in tapeData:
                if entry['Tape_ID'] in tape_name:
                    thisTape.append(entry)
            tapeSorted = sorted(thisTape, key=lambda d: d['Order on Tape'])
            
            for entry in tapeSorted:
                timeSplit = entry['Segment End'].split(':')
                entryTimeSeconds = int(timeSplit[0])*3600+int(timeSplit[1])*60+int(timeSplit[2])
                #print("entryTimeSeconds",entryTimeSeconds,"| endseconds:",endseconds)
                if entryTimeSeconds > float(endseconds):
                    thisEntry = entry
                    tapeID = thisEntry['Tape_ID']
                    #print("\nTAPE ID: "+tapeID)
                    program = thisEntry['Programs']
                    #print("PROGRAM: "+program)
                    station = thisEntry['Network/Station']
                    #print("NETWORK/STATION: "+station)
                    location = thisEntry['Location']
                    #print("LOCATION: "+location)
                    try:
                        airDate = datetime.datetime.strptime(thisEntry['Recording Date'], '%Y-%m-%d')
                        airDateLong = datetime.datetime.strftime(airDate,'%A %B %d, %Y')
                        airDateShort = datetime.datetime.strftime(airDate,'%b %d, %Y')
                        #print("AIR DATE: "+airDateLong)
                    except Exception as e:
                        print(e)
                        #print("ERROR: AIR DATE NOT FOUND")
                        pass
                    break
                    
            try:
                caption = "Tape ID: "+tapeID+"\nTimestamp: "+ts.split('.')[0]+"\nDuration: "+str(video_data[1])+" Seconds"+"\nProgram: "+program+"\nNetwork/Station: "+station+"\nBroadcast Location: "+location+"\nAir Date: "+airDateLong
            except Exception as e:
                print(e)
                try:
                    caption = "Tape ID: "+tapeID+"\nTimestamp: "+ts.split('.')[0]+"\nDuration: "+str(video_data[1])+" Seconds"+"\nProgram: "+program+"\nNetwork/Station: "+station+"\nBroadcast Location: "+location
                except:
                    caption = "Tape ID: "+tape_name[0:7]+"\nTimestamp: "+ts.split('.')[0]+"\nDuration: "+str(video_data[1])+" Seconds"
            print("[DISCORD]",end=" ")
            print("Uploading video and attaching to message:\n"+caption)
            await ctx.reply(caption,file=discord.File(outfilename))
            print("[DISCORD]",end=" ")
            print("Upload complete, message sent!")
            os.remove(outfilename)
        
    @discord_bot.command(help="Submit clip information by replying to a video clip with")
    async def submit(ctx, *, flags: DataFlags):
        data = {}
        if ctx.message.reference.resolved == None:
            data['tape_id'] = flags.tape
            data['timestart'] = flags.timestart
            data['timeend'] = flags.timeend
            data['program'] = flags.program
            data['clip'] = flags.clip
            data['network'] = flags.network
            data['location'] = flags.location
            data['airdate'] = flags.airdate
            data['year'] = flags.year
        else:
            data['tape_id'] = None
            try:
                data['timestart'] = flags.timestart
            except:
                data['timestart'] = None
            try:
                data['timeend'] = flags.timeend
            except:
                data['timeend'] = None
            try:
                data['program'] = flags.program
            except:
                data['program'] = None
            try:
                data['clip'] = flags.clip
            except:
                data['clip'] = None
            try:
                data['network'] = flags.network
            except:
                data['network'] = None
            try:
                data['location'] = flags.location
            except:
                data['location'] = None
            try:
                data['airdate'] = flags.airdate
            except:
                data['airdate'] = None
            try:
                data['year'] = flags.year
            except:
                data['year'] = None
            message_id = ctx.message.reference.resolved.id
            message_channel = ctx.message.reference.resolved.channel
            messageData = ctx.message.reference.resolved.content
            messageData = str(messageData).split('\n')
            for m in messageData:
                if 'Tape ID:' in m:
                    data['tape_id'] = m.replace('Tape ID: ','')
                    continue
                if 'Duration:' in m:
                    duration = float(m.replace('Duration: ','').replace(' Seconds',''))
                    duration = datetime.timedelta(seconds=duration)
                    continue
                if 'Timestamp:' in m:
                    timestart = datetime.datetime.strptime(m.replace('Timestamp: ',''), '%H:%M:%S')
                    if flags.timestart == None:
                        data['timestart'] = timestart.strftime('%H:%M:%S')
                    else:
                        time_seconds = int(flags.timestart.split(':')[-1])+int(flags.timestart.split(':')[-2])*60
                        timedelta = datetime.timedelta(seconds=time_seconds)
                        timestart_ = timestart + timedelta
                        data['timestart'] = timestart_.strftime('%H:%M:%S')
                    continue
                if 'Program:' in m:
                    data['program'] = m.replace('Program: ','')
                    continue
                elif data['program'] == None:
                    data['program'] = flags.program
                if 'Network/Station:' in m:
                    data['network'] = m.replace('Network/Station: ','')
                    continue
                elif data['network'] == None:
                    data['network'] = flags.network
                    continue
                if 'Broadcast Location:' in m:
                    data['location'] = m.replace('Broadcast Location: ','')
                    continue
                elif data['location'] == None:
                    data['location'] = flags.location
                if 'Air Date:' in m:
                    airDate = datetime.datetime.strptime(m.replace('Air Date: ',''),'%A %B %d, %Y')
                    data['airdate'] = airDate.strftime('%Y-%m-%d')
                    continue
                elif flags.airdate != None and data['airdate'] == None:
                    data['airdate'] = flags.airdate
                elif flags.year != None and data['year'] == None:
                    data['year'] = flags.year
            if flags.timeend == None:
                timeend = timestart + duration
            else:
                timeend_seconds = int(flags.timeend.split(':')[-1])+int(flags.timeend.split(':')[-2])*60
                timendelta = datetime.timedelta(seconds=timeend_seconds)
                timeend = timestart + timendelta
            data['timeend'] = timeend.strftime('%H:%M:%S')
        data['clip'] = flags.clip
        try:
            data['tags'] = flags.tags.split(',')
            data['tags'] = [t.strip() for t in data['tags']]
        except:
            pass
        data['submitted_by'] = ctx.author.name
        dataString = ''
        all_videos = list_videos(video_directory)
        all_tape_ids = []
        for video in all_videos:
            all_tape_ids.append(video.split(delimeter)[-1].split('.')[0][0:7])
        if data['tape_id'] in all_tape_ids:
            for k, v in data.items():
                if v == None or v == "None":
                    pass
                else:
                    dataString = dataString + '**' + k + '**: ' + str(v) + '\n'
            try:
                with open(temp_directory+delimeter+'_discord.json') as json_file:
                    json_data = json.load(json_file)
            except:
                    json_data = []
            json_data.append(data)
            json_data = sorted(json_data, key=lambda d: (d['tape_id'].upper(), d['timestart']))
            with open(temp_directory+delimeter+'_discord.json', 'w') as json_file:
                json_file.write(json.dumps(json_data, indent=4))
            await ctx.reply(dataString)
        else:
            await ctx.reply(f'ERROR: Tape {data["tape_id"]} not found')
    discord_bot.run(discord_token, log_handler=None)

def checkMastodon():
    mastodon_client = mastodon.Mastodon(access_token=config['mastodon']['access token'], api_base_url=config['mastodon']['instance url'])
    print('[MASTODON] Starting Mastodon Mention Monitoring')
    outfiles = []
    while True:
        data = {}
        try:
            last_id = get_last_tweet(temp_directory+delimeter+'toot_ID.txt')
        except FileNotFoundError:
            last_id = 0
            with open(temp_directory+delimeter+'toot_ID.txt', 'w') as newFile:
                newFile.write('0')           
        mentions = mastodon_client.notifications(since_id=last_id,types='mention')
        if mentions == False:
            print("[MASTODON] No mentions found, checking again at",datetime.datetime.now()+datetime.timedelta(minutes=1))
            time.sleep(60)
        else:
            for mention in reversed(mentions):
                new_id = mention.id

                if mention.type == 'mention':
                    if new_id > last_id and '#submit' in remove_html_markup(mention.status.content) and mention.status.in_reply_to_id != None:
                        replied_toot = remove_html_markup(mastodon_client.status(mention.status.in_reply_to_id).content)
                        replied_lines = replied_toot.replace(';','\n').split('\n')
                        print("[MASTODON]",mention.id, mention.account.username, remove_html_markup(mention.status.content))
                        if len(replied_lines) <= 3:
                            for replied_line in replied_lines:
                                if "Tape ID:" in replied_line:
                                    data['tape_id'] = replied_line.replace('Tape ID: ','')
                                if "Timestamp:" in replied_line:
                                    timestamp = replied_line.replace('Timestamp: ','')
                        elif len(replied_lines) == 6:
                                data['tape_id'] = replied_lines[0].replace('Tape ID: ','')
                                timestamp = replied_lines[1].replace('Timestamp: ','')
                                data['program'] = replied_lines[2].replace('Program: ','')
                                data['network'] = replied_lines[3].replace('Network/Station: ','')
                                data['airdate'] = datetime.datetime.strptime(replied_lines[4].replace('Air Date: ',''),'%A %B %d, %Y').strftime('%Y-%m-%d')                        
                        try:
                            timestamp = datetime.datetime.strptime(timestamp, '%H:%M:%S.%f')
                        except:
                            timestamp = datetime.datetime.strptime(timestamp, '%H:%M:%S')
                        duration = mastodon_client.status(mention.status.in_reply_to_id).media_attachments[0].meta.original.duration
                        duration = datetime.timedelta(seconds=duration)
                        istimestart = False
                        istimeend = False
                        mention_text = remove_html_markup(mention.status.content).replace('#','\n#')
                        for line in mention_text.split('\n'):
                            try: data['program']
                            except KeyError:
                                if '#program' in line:
                                    data['program'] = line.replace('#program ','')
                            try: data['clip']
                            except KeyError:
                                if '#clip' in line:
                                    data['clip'] = line.replace('#clip ','')
                            try: data['network']
                            except KeyError:
                                if '#network' in line:
                                    data['network'] = line.replace('#network ','')
                            try: data['location']
                            except KeyError:
                                if '#location' in line:
                                    data['location'] = line.replace('#location ','')
                            try: data['airdate']
                            except KeyError:
                                if '#airdate' in line:
                                    data['airdate'] = line.replace('#airdate ','')
                            if '#year' in line:
                                data['year'] = line.replace('#year ','')
                            if '#timestart' in line:
                                timestart = line.replace('#timestart ','')
                                time_seconds = int(timestart.split(':')[-1])+int(timestart.split(':')[-2])*60
                                timedelta = datetime.timedelta(seconds=time_seconds)
                                timestart_ = timestamp + timedelta
                                data['timestart'] = timestart_.strftime('%H:%M:%S')
                                istimestart = True
                            else:
                                if istimestart == False:
                                    data['timestart'] = timestamp.strftime('%H:%M:%S')
                            if '#timeend' in line:
                                timeend = line.replace('#timeend ','')
                                timeend_seconds = int(timeend.split(':')[-1])+int(timeend.split(':')[-2])*60
                                timendelta = datetime.timedelta(seconds=timeend_seconds)
                                timeend = timestamp + timendelta
                                istimeend = True
                            else:
                                if istimeend == False:
                                    timeend = timestamp + duration
                            data['timeend'] = timeend.strftime('%H:%M:%S')
                            if '#tags' in line:
                                data['tags'] = line.replace('#tags ','').split(',')
                                data['tags'] = [t.strip() for t in data['tags']]
                            data['submitted_by'] = mention.account.username

                        try:
                            with open(temp_directory+delimeter+'_mastodon.json') as json_file:
                                json_data = json.load(json_file)
                        except:
                                json_data = []
                        json_data.append(data)
                        json_data = sorted(json_data, key=lambda d: (d['tape_id'].upper(), d['timestart']))
                        #print(json_data)
                        with open(temp_directory+delimeter+'_mastodon.json', 'w') as json_file:
                            json_file.write(json.dumps(json_data, indent=4))
                        try:
                            mastodon_client.status_favourite(mention.id)
                        except:
                            pass

                    elif new_id > last_id and '#video' in remove_html_markup(mention.status.content):
                        print("[MASTODON] #video Command initiated by",mention.account.username)
                        print("[MASTODON]",mention.id, mention.account.username, remove_html_markup(mention.status.content))
                        try:
                            mastodon_client.status_favourite(mention.id)
                        except:
                            pass
                        mention_text = mention_text = remove_html_markup(mention.status.content).replace('#','\n#')
                        for line in mention_text.split('\n'):
                            all_videos = list_videos(video_directory)
                            if '#tape' in mention_text and '#tape' in line:
                                match_videos = []
                                for video in all_videos:
                                    videofilename = video.split(delimeter)[-1]
                                    if videofilename.startswith(line.replace('#tape ','').strip()):
                                        match_videos.append(video)
                                if len(match_videos) > 0:
                                    chosen_video = random.choice(match_videos)
                                else:
                                    chosen_video = random.choice(all_videos)
                            elif '#tape' not in mention_text:
                                chosen_video = random.choice(all_videos)
                            if '#timestart' in mention_text and '#timestart' in line:
                                if line.count(':') == 2:
                                    timestart = datetime.datetime.strptime(line.replace('#timestart','').strip(), "%H:%M:%S") - datetime.datetime(1900,1,1)
                                elif line.count(':') == 1:
                                    timestart = datetime.datetime.strptime(line.replace('#timestart','').strip(), "%M:%S") - datetime.datetime(1900,1,1)
                                else:
                                    timestart = datetime.datetime.strptime(line.replace('#timestart','').strip(), "%S") - datetime.datetime(1900,1,1)
                                startseconds = float(timestart.total_seconds())
                            if '#timeend' in mention_text and '#timeend' in line:
                                if line.count(':') == 2:
                                    timeend = datetime.datetime.strptime(line.replace('#timeend','').strip(), "%H:%M:%S") - datetime.datetime(1900,1,1)
                                elif line.count(':') == 1:
                                    timeend = datetime.datetime.strptime(line.replace('#timeend','').strip(), "%M:%S") - datetime.datetime(1900,1,1)
                                else:
                                    timeend = datetime.datetime.strptime(line.replace('#timeend','').strip(), "%S") - datetime.datetime(1900,1,1)
                                #te = flags.timeend
                                endseconds = float(timeend.total_seconds())

                        video_json = chosen_video.replace('.mp4','.json')
                        tape_name = chosen_video.split(delimeter)[-1].split('.')[0][0:7]
                        skipdurationcheck = False
                        if os.path.exists(video_json) == False:
                            mastodon_client.status_reply(to_status=mention.status,status="The data file for "+tape_name+" is missing. Creating a new one, but it will take a while.", in_reply_to_id = mention.id)
                            filePathArray = chosen_video.split(delimeter)
                            filePathArray.pop()
                            filePath = ""
                            for p in filePathArray:
                                filePath = filePath + p + delimeter
                            videoscanner.scanVideo(tape_name,filePath)                        

                        if '#timestart' not in mention_text and '#timeend' not in mention_text:
                            skipdurationcheck = True
                            firstframe,lastframe = getvid.get_frame(video_json, clip_length=15, clip_max=60)
                            try:
                                timestart = datetime.datetime.strptime(firstframe['ts'], "%H:%M:%S.%f") - datetime.datetime(1900,1,1)
                            except:
                                timestart = datetime.datetime.strptime(firstframe['ts'], "%H:%M:%S") - datetime.datetime(1900,1,1)
                            try:
                                timeend = datetime.datetime.strptime(lastframe['ts'], "%H:%M:%S.%f") - datetime.datetime(1900,1,1)
                            except:
                                timeend = datetime.datetime.strptime(lastframe['ts'], "%H:%M:%S") - datetime.datetime(1900,1,1)
                            startseconds = float(timestart.total_seconds())
                            endseconds = float(timeend.total_seconds())
                        elif '#timestart' in mention_text and '#timeend' not in mention_text:
                            endseconds = float(startseconds) + 60
                        elif '#timestart' not in mention_text and '#timeend' in mention_text:
                            startseconds = float(endseconds) - 60
                        if float(endseconds) - float(startseconds) > 60 and skipdurationcheck != True:
                            endseconds = float(startseconds) + 60
                        else:
                            outfilename = temp_directory+delimeter+chosen_video.split(delimeter)[-1].split('.')[0][0:7]+"_mastodon_"+mention.account.username+'.mp4'
                            ts = str(datetime.timedelta(seconds=startseconds))
                            te = str(datetime.timedelta(seconds=endseconds))
                            try:
                                print("[MASTODON]",end=" ")
                                print("Redering Video Selection")
                                video_data = video_resize(chosen_video,outfilename,ts,te,max_mb=40)
                            except TypeError:
                                #await ctx.reply('Timestamp exceeds video length.')
                                #api.update_status(status="The timestamp requested for "+tape_name+" exceeds the video length. Please try again.", in_reply_to_status_id = mention.id, auto_populate_reply_metadata=True)
                                mastodon_client.status_reply(to_status=mention.status,status="The timestamp requested for "+tape_name+" exceeds the video length. Please try again.")
                                return
                            get_duration(outfilename)

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
                                if entryTimeSeconds > float(endseconds):
                                    thisEntry = entry
                                    tapeID = thisEntry['Tape_ID']
                                    #print("\nTAPE ID: "+tapeID)
                                    program = thisEntry['Programs']
                                    #print("PROGRAM: "+program)
                                    station = thisEntry['Network/Station']
                                    #print("NETWORK/STATION: "+station)
                                    location = thisEntry['Location']
                                    #print("LOCATION: "+location)
                                    try:
                                        airDate = datetime.datetime.strptime(thisEntry['Recording Date'], '%Y-%m-%d')
                                        airDateLong = datetime.datetime.strftime(airDate,'%A %B %d, %Y')
                                        airDateShort = datetime.datetime.strftime(airDate,'%b %d, %Y')
                                        #print("AIR DATE: "+airDateLong)
                                    except Exception as e:
                                        print(e)
                                        #print("ERROR: AIR DATE NOT FOUND")
                                        pass
                                    break
                            toot = "Here is the clip you requested.\n"
                            try:
                                toot = toot+"Tape ID: "+tapeID+"\nTimestamp: "+frame['ts'].split('.')[0]+"\nProgram: "+program+"\nNetwork/Station: "+station+"\nBroadcast Location: "+location+"\nAir Date: "+airDateLong+"#bot"
                            except:
                                try:
                                    toot = toot+"Tape ID: "+tapeID+"\nTimestamp: "+frame['ts'].split('.')[0]+"\nProgram: "+program+"\nNetwork/Station: "+station+"\nBroadcast Location: "+location+"#bot"
                                except:
                                    toot = toot+"Tape ID: "+tape_name[0:7]+"\nTimestamp: "+ts.split('.')[0]+" #bot"
                                    
                            video = cv2.VideoCapture(outfilename)
                            video.set(cv2.CAP_PROP_POS_FRAMES,60)
                            success, image = video.read()
                            if success:
                                resized_image = cv2.resize(image, (640,480))
                                thumbfilename=outfilename.replace('.mp4','.png')
                                cv2.imwrite(thumbfilename, resized_image)

                            print("[MASTODON]",end=" ")
                            try:
                                print("Uploading video to Mastodon:\n"+toot)
                                media = mastodon_client.media_post(
                                    outfilename,
                                    mime_type='video/mp4',
                                    description="Video clip from a digitized VHS tape",
                                    focus=(0,-0.333),
                                    thumbnail=thumbfilename,
                                    thumbnail_mime_type='image/png'
                                )
                            except Exception as e:
                                print("[MASTODON] Error uploading video to mastodon")
                                print(e)
                                media = None
                            #time.sleep(60)
                            if media != None:
                                res = False
                                while res == False:
                                    try:
                                        post_result = mastodon_client.status_reply(to_status=mention.status,status=toot,media_ids=[media])
                                        res = True
                                    except Exception as e:
                                        time.sleep(10)
                                        continue
                                print("[MASTODON]",end=" ")
                                print("Upload complete, reply sent!")
                            else:
                                print("[MASTODON] Error posting video")
                                mastodon_client.status_reply(to_status=mention.status,status="Sorry, there was an error posting the requested video. Please try again later.")
                            while post_result == None:
                                time.sleep(10)
                                print("[MASTODON] Post not uploaded yet, waiting...")
                            #print(post_result)
                            outfiles.append(outfilename)
                            '''res = False
                            while res == False:
                                try:
                                    os.remove(outfilename)
                                    res = True
                                except PermissionError as e:
                                    print(e)
                                    time.sleep(10)
                                    continue'''
                            os.remove(thumbfilename)
                            time.sleep(2.5)
                for outfile in outfiles:
                    try:
                        os.remove(outfile)
                        outfiles.remove(outfile)
                    except:
                        continue
                put_last_tweet(temp_directory+delimeter+'toot_ID.txt',new_id)
                '''if mention.type == 'mention':
                    print(json.loads(mention))'''
            time.sleep(60)
                
        
def get_response(facebook=False,twitter=False,tumblr=False,useMastodon=False,useDiscord=False):

    if twitter != False:
        checkTwitter()
    
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
        checkDiscord()