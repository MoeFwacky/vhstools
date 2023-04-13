import argparse
import os
import ray

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

parser = argparse.ArgumentParser()
parser.add_argument('-b', '--bot', action='store_true', help="Bot that listens for submissions of video clip information")
parser.add_argument('-a', '--archive', action='store_true', help="Upload indicated file(s) to the internet archive")
parser.add_argument('-fb', '--facebook', action='store_true', help="Automatically post video clips to Facebook")
parser.add_argument('-tw', '--twitter', action='store_true', help="Automatically post video clips to Twitter")
parser.add_argument('-tb', '--tumblr', action='store_true', help="Automatically post video clips to Tumblr")
parser.add_argument('-m', '--mastodon', action='store_true', help="Automatically post video clips to Mastodon")
parser.add_argument('-ds', '--discord', action='store_true', help="Automatically post video clips to Discord")
parser.add_argument('-sc', '--scanner', action='store_true', help="Scan video file(s) and generate json data file(s)")
parser.add_argument('-sp', '--splitter', action='store_true', help="Detect dip-to-black in video file(s) and save clips to folder")
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

if args.scanner != False:
    import videoscanner
    print(": ___  __              ___     __   __                  ___  __  ::")
    print(":|__  |__)  /\   |\/| |__     /__` /  `  /\  |\ | |\ | |__  |__) ::")
    print(":|    |  \ /~~\  |  | |___    .__/ \__, /~~\ | \| | \| |___ |  \ ::")
    print(":::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::")
    if args.filename != None:
        videoscanner.scanVideo(args.filename)
    elif args.filepath != None:
        pathArray = args.filepath.split(delimeter)
        videoFileName = args.filepath.split(delimeter)[-1]
        pathArray.pop()
        path = ""
        for p in pathArray:
            path = path + p + delimeter
        videoscanner.scanVideo(videoFileName, path)
    elif args.directory != None:
        dirContents = os.scandir(args.directory)
        dirList = []
        extensions = ['mp4','avi','m4v','mkv']
        for entry in dirContents:
            if entry.name[-3:] in extensions:
                print(entry.name)
                videoscanner.scanVideo(entry.name, args.directory)
    else:
        videoscanner.scanVideo()
elif args.archive != False:
    import iauploader
    print("::::::: █████╗ ██████╗  ██████╗██╗  ██╗██╗██╗   ██╗███████╗::::::::")
    print(":::::::██╔══██╗██╔══██╗██╔════╝██║  ██║██║██║   ██║██╔════╝::::::::")
    print(":::::::███████║██████╔╝██║     ███████║██║██║   ██║█████╗  ::::::::")
    print(":::::::██╔══██║██╔══██╗██║     ██╔══██║██║╚██╗ ██╔╝██╔══╝  ::::::::")
    print(":::::::██║  ██║██║  ██║╚██████╗██║  ██║██║ ╚████╔╝ ███████╗::::::::")
    print(":::::::╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═══╝  ╚══════╝::::::::")
    print(":::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::")
    if args.filename != None:
        print("UPLOADING", args.filename, "to the Internet Archive")
        iauploader.uploadToArchive([args.filename])
    elif args.filepath != None:
        pathArray = args.filepath.split(delimeter)
        videoFileName = args.filepath.split(delimeter)[-1]
        pathArray.pop()
        path = ""
        for p in pathArray:
            path = path + p + delimeter
        print("UPLOADING", videoFileName,"IN DIRECTORY",path,"to the Internet Archive")
        iauploader.uploadToArchive([args.filepath])
    elif args.directory != None:
        dirContents = os.scandir(args.directory)
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
            print("ERROR:",args.directory,"CONTAINS NO VIDEOS OF THE FOLLOWING TYPES:",extensions_string)
    else:
        iauploader.uploadToArchive(None)
elif args.twitter != False or args.tumblr != False or args.mastodon != False or args.discord != False or args.facebook != False or args.bot != False:
    import getvid
    if args.bot == False:
        print(":::::::: _   _ _     _  _____  _____            _       _ :::::::::")
        print("::::::::| | | (_)   | |/ __  \/  ___|          (_)     | |:::::::::")
        print("::::::::| | | |_  __| |`' / /'\ `--.  ___   ___ _  __ _| |:::::::::")
        print("::::::::| | | | |/ _` |  / /   `--. \/ _ \ / __| |/ _` | |:::::::::")
        print("::::::::\ \_/ / | (_| |./ /___/\__/ / (_) | (__| | (_| | |:::::::::")
        print(":::::::: \___/|_|\__,_|\_____/\____/ \___/ \___|_|\__,_|_|:::::::::")
        print(":::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::")
        if args.filename != None:
            getvid.social([args.filename],args.facebook, args.twitter, args.tumblr, args.mastodon, args.discord, args.persist)
        elif args.filepath != None:
            getvid.social([args.filepath],args.facebook, args.twitter, args.tumblr, args.mastodon, args.discord, args.persist)
        elif args.directory != None:
            getvid.social(getvid.list_videos(args.directory),args.facebook, args.twitter, args.tumblr, args.mastodon, args.discord, args.persist)
        else:
            getvid.social(getvid.list_videos(getvid.directory),args.facebook, args.twitter, args.tumblr, args.mastodon, args.discord, args.persist)
    else:
        import listentosocial
        if args.twitter != False or args.tumblr != False or args.mastodon != False or args.discord != False or args.facebook != False:
            print("::::: _______              __         __ ______         __   ::::::")
            print(":::::|     __|.-----.----.|__|.---.-.|  |   __ \.-----.|  |_ ::::::")
            print(":::::|__     ||  _  |  __||  ||  _  ||  |   __ <|  _  ||   _|::::::")
            print(":::::|_______||_____|____||__||___._||__|______/|_____||____|::::::")
            print(":::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::")
            ray.init()
            if args.filename != None:
                @ray.remote
                def Social():
                    getvid.social([args.filename],args.facebook, args.twitter, args.tumblr, args.mastodon, args.discord, args.persist)
            elif args.filepath != None:
                @ray.remote
                def Social():
                    getvid.social([args.filepath],args.facebook, args.twitter, args.tumblr, args.mastodon, args.discord, args.persist)
            elif args.directory != None:
                @ray.remote
                def Social():
                    vidList = getvid.list_videos(args.directory)
                    getvid.social(vidList,args.facebook, args.twitter, args.tumblr, args.mastodon, args.discord, args.persist)
            else:
                @ray.remote
                def Social():
                    vidList = getvid.list_videos(getvid.directory)
                    getvid.social(vidList,args.facebook, args.twitter, args.tumblr, args.mastodon, args.discord, args.persist)
            rayList = []
            rayList.append(Social.remote())
            if args.discord != False:
                @ray.remote
                def DiscordBot():
                    listentosocial.checkDiscord()
                rayList.append(DiscordBot.remote())
            #for i in range(0,250):
            if args.twitter != False:
                @ray.remote
                def TwitterBot():
                    listentosocial.checkTwitter()
                rayList.append(TwitterBot.remote())
            if args.mastodon != False:
                @ray.remote
                def MastodonBot():
                    listentosocial.checkMastodon()
                rayList.append(MastodonBot.remote())
            try:
                ray.get(rayList)
            except Exception as e:
                print(e)
                #continue
            #    break
        else:
            print("::::::::██    ██ ██   ██ ███████ ██████   ██████  ████████:::::::::")
            print("::::::::██    ██ ██   ██ ██      ██   ██ ██    ██    ██   :::::::::")
            print("::::::::██    ██ ███████ ███████ ██████  ██    ██    ██   :::::::::")
            print(":::::::: ██  ██  ██   ██      ██ ██   ██ ██    ██    ██   :::::::::")
            print("::::::::  ████   ██   ██ ███████ ██████   ██████     ██   :::::::::")
            print(":::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::")
            listentosocial.checkMastodon()
elif args.splitter != False:
    import scenesplitter
    print(":::::::::  __                   __                        :::::::::")
    print("::::::::: (_   _  _  ._   _    (_  ._  | o _|_ _|_  _  ._ :::::::::")
    print("::::::::: __) (_ (/_ | | (/_   __) |_) | |  |_  |_ (/_ |  :::::::::")
    print(":::::::::                          |                      :::::::::")
    print(":::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::")
    if args.filename != None:
        scenesplitter.processVideo(args.filename)
    elif args.filepath != None:
        pathArray = args.filepath.split(delimeter)
        videoFileName = args.filepath.split(delimeter)[-1]
        pathArray.pop()
        path = ""
        for p in pathArray:
            path = path + p + delimeter
        print("PROCESSING", videoFileName,"IN DIRECTORY",path)
        scenesplitter.processVideo(videoFileName, path)
    elif args.directory != None:
        dirContents = os.scandir(args.directory)
        dirList = []
        extensions = ['mp4','avi','m4v','mkv']
        for entry in dirContents:
            if entry.name[-3:] in extensions:
                print(entry.name)
                scenesplitter.processVideo(entry.name, args.directory)
    else:
        scenesplitter.processVideo()
elif args.editor != False:
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
    if args.filename != None:
        editor.processJSON(args.filename)
    elif args.filepath != None:
        pathArray = args.filepath.split(delimeter)
        videoFileName = args.filepath.split(delimeter)[-1]
        pathArray.pop()
        path = ""
        for p in pathArray:
            path = path + p + delimeter
        print("PROCESSING", videoFileName,"IN DIRECTORY",path)
        editor.processJSON(videoFileName, path)
    elif args.directory != None:
        dirContents = os.scandir(args.directory)
        dirList = []
        extensions = ['json']
        for entry in dirContents:
            if entry.name[-3:] in extensions:
                print(entry.name)
                editor.processJSON(entry.name, args.directory)
    else:
        editor.processJSON()
elif args.tagger != False:
    import metatagger
    print(":::::::::: __ __ ___ _____ __ _____ __   __  __ ___ ___ :::::::::::")
    print("::::::::::|  V  | __|_   _/  \_   _/  \ / _]/ _] __| _ \:::::::::::")
    print("::::::::::| \_/ | _|  | || /\ || || /\ | [/\ [/\ _|| v /:::::::::::") 
    print("::::::::::|_| |_|___| |_||_||_||_||_||_|\__/\__/___|_|_\:::::::::::") 
    print(":::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::")
    if args.filename != None:
        metatagger.tagFiles(args.filename)
    elif args.filepath != None:
        pathArray = args.filepath.split(delimeter)
        videoFileName = args.filepath.split(delimeter)[-1]
        pathArray.pop()
        path = ""
        for p in pathArray:
            path = path + p + delimeter
        print("PROCESSING", videoFileName,"IN DIRECTORY",path)
        metatagger.tagFiles(videoFileName, path)
    elif args.directory != None:
        dirContents = os.scandir(args.directory)
        dirList = []
        extensions = ['json']
        for entry in dirContents:
            if entry.name[-3:] in extensions:
                print(entry.name)
                metatagger.tagFiles(entry.name, args.directory)
    else:
        metatagger.tagFiles()
else:
    parser.print_help()