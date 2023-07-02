import configparser
import os
import sys
import ffmpeg
import datetime
import time
import json

if os.name == 'nt':
    delimeter = '\\'
else:
    delimeter = '/'

scriptPath = os.path.realpath(os.path.dirname(__file__))
config = configparser.ConfigParser()
config.read(scriptPath + delimeter + 'config.ini')

directory = config['metatagger']['output subdirectory']

cwd = os.getcwd()

def selectFile(k):
    fileSelection = input(">:")
    try:
        fileSelection = int(fileSelection)
    except ValueError:
        print("Enter a Number Between 1 and "+str(k-1)+":")
        fileSelection = input(">:")
    while fileSelection >= int(k):
        print("Enter a Number Between 1 and "+str(k-1)+":")
        fileSelection = input(">:")
        try:
            fileSelection = int(fileSelection)
        except ValueError:
            fileSelection = k
    return fileSelection
    
def selectJSON(path):
    dirContents = os.scandir(path)
    dirDict = {}
    k = 1
    for entry in dirContents:
        if entry.name[-4:].lower() in 'json':
            dirDict[k] = entry.name
            print(str(k)+": "+entry.name)
            k = k + 1
    fileSelection = selectFile(k)
    print("\nJSON FILE SELECTED")
    print(path+dirDict[fileSelection])
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
        cont = input("\nContinue with this file? (Y/N) >:")
    print("CONFIRMED!")
    return dirDict[fileSelection]

def selectDirectory(delimeter=delimeter):
    print("Enter the directory path to scan")
    workingDir = os.getcwd()
    print("Press Enter to use "+workingDir)
    path = input(">:")
    if path == "":
        path = workingDir
    if path[-1] != delimeter:
        path = path + delimeter
    print("Selected Directory: "+path)
    return path

def editMetadata(filename,outputPath,metadata,outputFile=None):
    if outputFile == None:
        outputFile = outputPath + delimeter + filename.split(delimeter)[-1]
    
    try:
        (
            ffmpeg
            .input(filename)
            .output(
                outputFile, 
                c='copy', 
                loglevel="verbose",
                **{
                    'metadata:g:0':"title="+metadata['description'],
                    'metadata:g:1':"date="+metadata['date'],
                    'metadata:g:2':"genre="+metadata['tags'],
                    'metadata:g:3':"network="+metadata['network'],
                    'metadata:g:4':"synopsis="+metadata['tapeID'],
                    'metadata:g:5':"episode_id="+metadata['clip'],
                    'metadata:g:6':"comment="+metadata['location'],
                }
            )
            .run(capture_stdout=True, capture_stderr=True)
    )
    except ffmpeg.Error as e:
        print(e.stderr)

def createMetadata(filename,outputPath,metadata,outputFile):
    outputFile = os.path.join(outputPath,outputFile)
    print(filename)
    print(outputFile)
    print('')

    try:
        print("Processing metadata with ffmpeg")
        (
            ffmpeg
            .input(filename)
            .output(
                outputFile, 
                c='copy', 
                loglevel="verbose",
                **{
                    'metadata:g:0':"title="+metadata['Title'],
                    'metadata:g:1':"date="+metadata['Air Date'],
                    'metadata:g:2':"genre="+metadata['Tags'],
                    'metadata:g:3':"network="+metadata['Network/Station'],
                    'metadata:g:4':"synopsis="+metadata['Tape ID'],
                    'metadata:g:5':"episode_id="+str(metadata['Frame Range'][0]),
                    'metadata:g:6':"comment="+metadata['Location']+'\n'+metadata['Description'],
                }
            )
            .run(capture_stdout=True, capture_stderr=True)
        )
    except ffmpeg.Error as e:
        print(e.stderr)
    
def tagFiles(JSONFile=None, workingDirectory=None, directory=directory):
    if workingDirectory == None:
        workingDirectory = selectDirectory()
    if JSONFile == None:
        JSONFile = selectJSON(workingDirectory)
    j = open(JSONFile,)
    jsonData = json.load(j)

    destinationDirectory = workingDirectory + directory
    print(destinationDirectory)
    if os.path.exists(destinationDirectory) != True:
        print("_metadata directory does not exist, creating directory...")
        try:
            os.makedirs(destinationDirectory)
        except Exception as e:
            print("ERROR: Could not create directory\n"+str(e))

    for d in jsonData:
        if d['Folder'] == workingDirectory.split(delimeter)[-2]:
            print(d['Filename'])
            editMetadata(d['Filename'],destinationDirectory,{'description':d['Description'],'date':d['Air Date'],'tags':d['Tags'],'network':d['Network/Station'],'tapeID':d['Tape ID'],'clip':str(d['Clip Number']),'location':d['Location']})
        else:
            print(d['Folder'])
            print(workingDirectory.split(delimeter)[-2])
            print("Directories do not match, skipping...")
            
            
