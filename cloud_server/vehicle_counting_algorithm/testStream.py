'''
#######################
This is an extra file
#######################
'''


import os
folderPath = "/home/ubuntu/ave/adaptive-video-encoding/cloud_server/streamed_files/fog1/cam2"


from main_live_stream import *


def getFogAndCameraName(videoFilePath):
	'''
	Extracting the fog node name and the camera name from the file path
	:param videoFilePath: Path to the video file
	:return: Camera name, Fog Node name
	'''
	videoFilePath += "/"
	splittedPath = videoFilePath.split("/")
	if splittedPath[-1] == "":
		return splittedPath[-3], splittedPath[-4]
	else:
		return splittedPath[-2], splittedPath[-3]

numVideosReceived = 4
while numVideosReceived > 0:
    videoFiles = os.listdir(folderPath)
    videoFile = sorted(videoFiles)[4 - numVideosReceived]
    print("Analyzing file: ", videoFile)
    videoAbsPath = os.path.abspath(os.path.join(folderPath, videoFile))
    print("ABS:", videoAbsPath)
    cameraName, fogNodeName = getFogAndCameraName(videoAbsPath)
    # print("Cam:" , cameraName, "Fog:", fogNodeName)
    count_vehicles(videoAbsPath)
    # countVideo(videoAbsPath, fogNodeName, cameraName)
    # Removing file after analysis
    # os.remove(videoAbsPath)
    numVideosReceived -= 1
