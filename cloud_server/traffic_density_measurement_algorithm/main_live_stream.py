from __future__ import division, print_function, absolute_import

import os
import warnings
import cv2
import numpy as np
from PIL import Image
from yolo import YOLO
import time

from deep_sort import preprocessing
from deep_sort import nn_matching
from deep_sort.detection import Detection
from deep_sort.tracker import Tracker
from tools import generate_detections as gdet
from deep_sort.detection import Detection as ddet
from collections import deque
from keras import backend
import tensorflow as tf
from tensorflow.compat.v1 import InteractiveSession

config = tf.ConfigProto()
config.gpu_options.allow_growth = True
session = InteractiveSession(config=config)

from tqdm import tqdm

# Line counter method
from counter import *

pts = [deque(maxlen=30) for _ in range(9999)]
warnings.filterwarnings('ignore')

# initialize a list of colors to represent each possible class label
np.random.seed(100)
COLORS = np.random.randint(0, 255, size=(200, 3),
                           dtype="uint8")

# Path to the vehicle counting algorithm folder
PATH_TO_FOLDER = "traffic_density_measurement_algorithm"

max_cosine_distance = 0.3
nn_budget = None
nms_max_overlap = 1.0

# deep_sort
model_filename = os.path.join(PATH_TO_FOLDER, 'model_data/market1501.pb')
encoder = gdet.create_box_encoder(model_filename, batch_size=1)

metric = None
tracker = None
vehicle_count = 0
line_counter = None
counter = []

yolo = YOLO(PATH_TO_FOLDER)

# Used when the framework is used for different videos
saved_vehicle_count = None
saved_metric = None
saved_tracker = None
saved_line_counter = None
saved_counter = None

def save_tracking_components():
    global saved_counter, saved_tracker, saved_vehicle_count, saved_line_counter, saved_metric
    saved_vehicle_count = vehicle_count
    saved_tracker = tracker
    saved_line_counter = line_counter
    saved_counter = counter

def reload_from_saved():
    global counter, tracker, vehicle_count, line_counter, metric
    vehicle_count = saved_vehicle_count
    tracker = saved_tracker
    line_counter = saved_line_counter
    counter = saved_counter
    metric = saved_metric

def initialize_vars(coordinates, current_resolution):
    '''
    Initialize variables at the beginning of an encoding calculation request
    '''
    global line_counter, vehicle_count, counter, tracker, metric
    vehicle_count = 0
    line_counter = Counter(coordinates, current_resolution)
    counter = []
    metric = nn_matching.NearestNeighborDistanceMetric("cosine", max_cosine_distance, nn_budget)
    tracker = Tracker(metric)

def write_count(count_file_path):
    '''
    Writing the count value to the log file
    '''
    global vehicle_count
    # Writing to a log file
    with open(count_file_path, 'a') as file:
        file.write(str(vehicle_count)+"\n")

def get_vehicle_count():
    '''
    Returns the vehicle count
    '''
    return vehicle_count

def count_vehicles(video_file_path):
    '''
    Counting the vehicles on the video with the given path.
    :param video_file_path: Path of the video to be analyzed
    '''
    video_capture = cv2.VideoCapture(video_file_path)

    fps = 0.0

    global vehicle_count, num_frames

    num_frames = 0

    total_frames = video_capture.get(cv2.CAP_PROP_FRAME_COUNT)
    # Initializing the progress bar
    pbar = tqdm(total=total_frames)

    # main loop
    while num_frames < total_frames:
        num_frames += 1
        ret, frame = video_capture.read()  # frame shape 640*480*3

        if ret != True:
            break
        t1 = time.time()

        image = Image.fromarray(frame[..., ::-1])  # bgr to rgb
        boxs, confidence, class_names = yolo.detect_image(image)
        features = encoder(frame, boxs)
        # score to 1.0 here).
        detections = [Detection(bbox, 1.0, feature) for bbox, feature in zip(boxs, features)]
        # Run non-maxima suppression.
        boxes = np.array([d.tlwh for d in detections])
        scores = np.array([d.confidence for d in detections])
        indices = preprocessing.non_max_suppression(boxes, nms_max_overlap, scores)
        detections = [detections[i] for i in indices]

        # Call the tracker
        tracker.predict()
        tracker.update(detections)

        i = int(0)
        indexIDs = []

        for det in detections:
            bbox = det.to_tlbr()
            cv2.rectangle(frame, (int(bbox[0]), int(bbox[1])), (int(bbox[2]), int(bbox[3])), (255, 255, 255), 2)

        for track in tracker.tracks:
            if not track.is_confirmed() or track.time_since_update > 1:
                continue

            indexIDs.append(int(track.track_id))
            counter.append(int(track.track_id))
            bbox = track.to_tlbr()
            color = [int(c) for c in COLORS[indexIDs[i] % len(COLORS)]]

            cv2.rectangle(frame, (int(bbox[0]), int(bbox[1])), (int(bbox[2]), int(bbox[3])), (color), 3)

            cv2.putText(frame, str(track.track_id), (int(bbox[0]), int(bbox[1] - 50)), 0, 5e-3 * 150, (color), 2)
            if len(class_names) > 0:
                cv2.putText(frame, str(class_names[0]), (int(bbox[0]), int(bbox[1] - 20)), 0, 5e-3 * 150, (color), 2)

            i += 1
            center = (int(((bbox[0]) + (bbox[2])) / 2), int(((bbox[1]) + (bbox[3])) / 2))

            pts[track.track_id].append(center)

            thickness = 5
            # center point
            cv2.circle(frame, (center), 1, color, thickness)

            # If the box intersects with the line
            if line_counter.intersects_with_bbox(bbox) and track.track_id not in line_counter.tracked_id:
                line_counter.add_to_tracked_list(track.track_id)
                vehicle_count += 1

            # draw motion path
            for j in range(1, len(pts[track.track_id])):
                if pts[track.track_id][j - 1] is None or pts[track.track_id][j] is None:
                    continue
                thickness = int(np.sqrt(64 / float(j + 1)) * 2)
                cv2.line(frame, (pts[track.track_id][j - 1]), (pts[track.track_id][j]), (color), thickness)

        cv2.putText(frame, "Total Line Counter: " + str(vehicle_count), (int(20), int(120)), 0, 5e-3 * 200, (0, 255, 0),
                    2)
        cv2.putText(frame, "FPS: %f" % (fps), (int(20), int(40)), 0, 5e-3 * 200, (0, 255, 0), 3)

        for line_to_draw in line_counter.get_lines():
            cv2.line(frame, line_to_draw[0], line_to_draw[1], (255, 0, 0), 2)

        fps = (fps + (1. / (time.time() - t1))) / 2

        pbar.update(1) #Updating the progress bar on the terminal window

        # Press Q to stop!
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    pbar.close()
    print("[Finish]")

    if len(pts[track.track_id]) != None:
        print(str(vehicle_count) + ' vehicles found')
    else:
        print("[No Found]")

    video_capture.release()
    cv2.destroyAllWindows()
    return vehicle_count