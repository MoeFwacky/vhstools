import argparse
import os

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
parser.add_argument('-tw', '--twitter', action='store_true', help="Automatically post video clips to Twitter")
parser.add_argument('-tb', '--tumblr', action='store_true', help="Automatically post video clips to Tumblr")
parser.add_argument('-m', '--mastodon', action='store_true', help="Automatically post video clips to Mastodon")
parser.add_argument('-sc', '--scanner', action='store_true', help="Scan video file(s) and generate json data file(s)")
parser.add_argument('-sp', '--splitter', action='store_true', help="Detect dip-to-black in video file(s) and save clips to folder")
parser.add_argument('-e', '--editor', action='store_true', help="Process video edits as defind in a JSON file")
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
elif args.twitter != False or args.tumblr != False or args.mastodon != False:
    import getvid
    print(":::::::: _   _ _     _  _____  _____            _       _ :::::::::")
    print("::::::::| | | (_)   | |/ __  \/  ___|          (_)     | |:::::::::")
    print("::::::::| | | |_  __| |`' / /'\ `--.  ___   ___ _  __ _| |:::::::::")
    print("::::::::| | | | |/ _` |  / /   `--. \/ _ \ / __| |/ _` | |:::::::::")
    print("::::::::\ \_/ / | (_| |./ /___/\__/ / (_) | (__| | (_| | |:::::::::")
    print(":::::::: \___/|_|\__,_|\_____/\____/ \___/ \___|_|\__,_|_|:::::::::")
    print(":::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::")
    if args.filename != None:
        getvid.social([args.filename],args.twitter, args.tumblr, args.mastodon, args.persist)
    elif args.filepath != None:
        getvid.social([args.filepath],args.twitter, args.tumblr, args.mastodon, args.persist)
    elif args.directory != None:
        getvid.social(getvid.list_videos(args.directory),args.twitter, args.tumblr, args.mastodon, args.persist)
    else:
        getvid.social(getvid.list_videos(getvid.directory),args.twitter, args.tumblr, args.mastodon, args.persist)
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