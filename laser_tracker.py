#! /usr/bin/env python
import sys
import argparse
import cv2
import numpy
import tkinter

from getperspective import four_point_transform

from pynput.mouse import Button, Controller

screenRoot = tkinter.Tk()

class Emulate(object):
    def __init__(self, count=0, seen=False, cursor_range=10, click_on=False):
        self.count = count
        self.seen = seen
        self.cursor_range = cursor_range
        self.click_on = click_on

    def reset(self):
        self.count = 0
        self.seen = False
        self.cursor_range = 10
        self.click_on = False

class LaserTracker(object):    

    def __init__(self, cam_width=640, cam_height=480, hue_min=20, hue_max=160,
                 sat_min=100, sat_max=255, val_min=200, val_max=256,
                 display_thresholds=False):
        """
        * ``cam_width`` x ``cam_height`` -- This should be the size of the
        image coming from the camera. Default is 640x480.

        HSV color space Threshold values for a RED laser pointer are determined
        by:

        * ``hue_min``, ``hue_max`` -- Min/Max allowed Hue values
        * ``sat_min``, ``sat_max`` -- Min/Max allowed Saturation values
        * ``val_min``, ``val_max`` -- Min/Max allowed pixel values

        If the dot from the laser pointer doesn't fall within these values, it
        will be ignored.

        * ``display_thresholds`` -- if True, additional windows will display
          values for threshold image channels.

        """

        self.cam_width = cam_width
        self.cam_height = cam_height
        self.hue_min = hue_min
        self.hue_max = hue_max
        self.sat_min = sat_min
        self.sat_max = sat_max
        self.val_min = val_min
        self.val_max = val_max
        self.display_thresholds = display_thresholds

        self.capture = None  # camera capture device
        self.channels = {
            'hue': None,
            'saturation': None,
            'value': None,
            'laser': None,
        }

        self.mouse = Controller()
        self.corners=[False,False,False,False] #TL, TR, BR, BL
        self.refPts=[]
        
        global screenRoot
        self.wRatio = 1/(self.cam_width/screenRoot.winfo_screenwidth())
        self.hRatio = 1/(self.cam_height/screenRoot.winfo_screenheight())
        print('Cam resolution : {} x {}'.format(self.cam_width, self.cam_height))
        print('Screen resolution : {} x {}'.format(screenRoot.winfo_screenwidth(), screenRoot.winfo_screenheight()))
        print('calculated ratio {} x {}'.format(self.wRatio, self.hRatio))
        self.emulate = Emulate()
        self.previous_pos = []


    def simulateMouseClick(self, pos):
        #Cursor position is integer (current pixel)
        intPos = (int(self.wRatio * pos[0]), int(self.hRatio * pos[1]))
        self.mouse.position = intPos
        # Click the left button 
        x = [p[0] for p in self.previous_pos]
        y = [p[1] for p in self.previous_pos]
        centroid = (numpy.median(x), numpy.median(y))
        #print('{} - {}'.format(centroid, self.previous_pos))
        flag = (abs(pos[0]-centroid[0])<5 or abs(pos[1]-centroid[1])<5 )
        if self.emulate.seen and self.emulate.count > 30 and flag:
            self.mouse.press(Button.left)
            self.emulate.click_on = True

    def on_mouse(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            if not self.corners[0]:
                self.corners[0]=True
                self.refPts=[(x, y)]
            elif not self.corners[1]:
                self.corners[1]=True
                self.refPts.append((x, y))
            elif not self.corners[2]:
                self.corners[2]=True
                self.refPts.append((x, y))
            elif not self.corners[3]:
                self.corners[3]=True
                self.refPts.append((x, y))

    def create_and_position_window(self, name, xpos, ypos):
        """Creates a named widow placing it on the screen at (xpos, ypos)."""
        # Create a window
        cv2.namedWindow(name)
        # Resize it to the size of the camera image
        cv2.resizeWindow(name, self.cam_width, self.cam_height)
        # Move to (xpos,ypos) on the screen
        cv2.moveWindow(name, xpos, ypos)

    def setup_camera_capture(self, device_num=0):
        """Perform camera setup for the device number (default device = 0).
        Returns a reference to the camera Capture object.

        """
        try:
            device = int(device_num)
            sys.stdout.write("Using Camera Device: {0}\n".format(device))
        except (IndexError, ValueError):
            # assume we want the 1st device
            device = 0
            sys.stderr.write("Invalid Device. Using default device 0\n")

        # Try to start capturing frames
        self.capture = cv2.VideoCapture(device)
        if not self.capture.isOpened():
            sys.stderr.write("Faled to Open Capture device. Quitting.\n")
            sys.exit(1)

        # set the wanted image size from the camera
        self.capture.set(
            cv2.cv.CV_CAP_PROP_FRAME_WIDTH if cv2.__version__.startswith('2') else cv2.CAP_PROP_FRAME_WIDTH,
            self.cam_width
        )
        self.capture.set(
            cv2.cv.CV_CAP_PROP_FRAME_HEIGHT if cv2.__version__.startswith('2') else cv2.CAP_PROP_FRAME_HEIGHT,
            self.cam_height
        )
        return self.capture

    def handle_quit(self, delay=10):
        """Quit the program if the user presses "Esc" or "q"."""
        key = cv2.waitKey(delay)
        c = chr(key & 255)
        if c in ['c', 'C']:
            self.corners=[False,False,False,False] #TL, TR, BR, BL
            self.refPts=[]
        
        if c in ['q', 'Q', chr(27)]:
            sys.exit(0)

    def threshold_image(self, channel):
        if channel == "hue":
            minimum = self.hue_min
            maximum = self.hue_max
        elif channel == "saturation":
            minimum = self.sat_min
            maximum = self.sat_max
        elif channel == "value":
            minimum = self.val_min
            maximum = self.val_max

        (t, tmp) = cv2.threshold(
            self.channels[channel],  # src
            maximum,  # threshold value
            0,  # we dont care because of the selected type
            cv2.THRESH_TOZERO_INV  # t type
        )

        (t, self.channels[channel]) = cv2.threshold(
            tmp,  # src
            minimum,  # threshold value
            255,  # maxvalue
            cv2.THRESH_BINARY # type
        )

        if channel == 'hue':
            # only works for filtering red color because the range for the hue
            # is split
            self.channels['hue'] = cv2.bitwise_not(self.channels['hue'])

    def track(self, frame, mask):
        """
        Track the position of the laser pointer.

        Code taken from
        http://www.pyimagesearch.com/2015/09/14/ball-tracking-with-opencv/
        """
        center = None
        # cv2.RETR_EXTERNAL
        countours = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                     cv2.CHAIN_APPROX_SIMPLE)[-2]

        # only proceed if at least one contour was found
        if len(countours) > 0:
            # find the largest contour in the mask, then use
            # it to compute the minimum enclosing circle and
            # centroid
            c = max(countours, key=cv2.contourArea)
            ((x, y), radius) = cv2.minEnclosingCircle(c)
            moments = cv2.moments(c)
            if moments["m00"] > 0:
                center = int(moments["m10"] / moments["m00"]), \
                         int(moments["m01"] / moments["m00"])
            else:
                center = int(x), int(y)

            # only proceed if the radius meets a minimum size
            if radius > 5 and radius < 20:
                # draw the circle and centroid on the frame,
                cv2.circle(frame, (int(x), int(y)), int(radius),
                           (0, 255, 255), 2)
                cv2.circle(frame, center, 5, (0, 0, 255), -1)
                self.emulate.seen = True
                self.emulate.count = self.emulate.count + 1
                self.previous_pos.append(center)
                self.simulateMouseClick(center)
        else:
            if self.emulate.click_on:
                self.mouse.release(Button.left)
            self.emulate.reset()
            self.previous_pos = []


    def detect(self, frame):
        hsv_img = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # split the video frame into color channels
        h, s, v = cv2.split(hsv_img)
        self.channels['hue'] = h
        self.channels['saturation'] = s
        self.channels['value'] = v

        # Threshold ranges of HSV components; storing the results in place
        self.threshold_image("hue")
        self.threshold_image("saturation")
        self.threshold_image("value")

        # Perform an AND on HSV components to identify the laser!
        self.channels['laser'] = cv2.bitwise_and(
            self.channels['hue'],
            self.channels['value']
        )
        '''
        self.channels['laser'] = cv2.bitwise_and(
            self.channels['saturation'],
            self.channels['laser']
        )
        '''

        # Merge the HSV components back together.
        hsv_image = cv2.merge([
            self.channels['hue'],
            self.channels['saturation'],
            self.channels['value'],
        ])

        self.track(frame, self.channels['laser'])

        return hsv_image

    def display(self, img, frame):
        """Display the combined image and (optionally) all other image channels
        NOTE: default color space in OpenCV is BGR.
        """
        cv2.imshow('RGB_VideoFrame', frame)
        cv2.imshow('LaserPointer', self.channels['laser'])
        if self.display_thresholds:
            cv2.imshow('Thresholded_HSV_Image', img)
            #cv2.imshow('Hue', self.channels['hue'])
            #cv2.imshow('Saturation', self.channels['saturation'])
            #cv2.imshow('Value', self.channels['value'])

    def setup_windows(self):
        sys.stdout.write("Using OpenCV version: {0}\n".format(cv2.__version__))

        # create output windows
        self.create_and_position_window('LaserPointer', 0, 0)
        self.create_and_position_window('RGB_VideoFrame',
                                        10 + self.cam_width, 0)
        if self.display_thresholds:
            self.create_and_position_window('Thresholded_HSV_Image', 10, 10 + self.cam_height)
            #self.create_and_position_window('Hue', 20, 20)
            #self.create_and_position_window('Saturation', 30, 30)
            #self.create_and_position_window('Value', 40, 40)

    def isCalibrate(self, frame):
        cv2.setMouseCallback('RGB_VideoFrame', self.on_mouse)
        
        for i in range(4):
            if self.corners[i]:
                cv2.circle(frame, self.refPts[i], 5, (0,255,0), 1)

        if self.corners[0] and self.corners[1] and self.corners[2] and self.corners[3]:
            warped = four_point_transform(frame, numpy.array(self.refPts, dtype = "float32"), (self.cam_width, self.cam_height))
            return warped

        return frame


    def run(self):
        # Set up window positions
        self.setup_windows()
        # Set up the camera capture
        self.setup_camera_capture()

        # 1. capture the current image
        success, frame = self.capture.read()
        if not success:  # no image captured... end the processing
            sys.stderr.write("Could not read camera frame. Quitting\n")
            sys.exit(1)

        while(self.capture.isOpened()):
            success, frame = self.capture.read()
            
            frame = self.isCalibrate(frame)

            hsv_image = self.detect(frame)
            self.display(hsv_image, frame)
            self.handle_quit()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run the Laser Tracker')
    parser.add_argument('-W', '--width',
                        default=640,
                        type=int,
                        help='Camera Width')
    parser.add_argument('-H', '--height',
                        default=480,
                        type=int,
                        help='Camera Height')
    parser.add_argument('-u', '--huemin',
                        default=20,
                        type=int,
                        help='Hue Minimum Threshold')
    parser.add_argument('-U', '--huemax',
                        default=160,
                        type=int,
                        help='Hue Maximum Threshold')
    parser.add_argument('-s', '--satmin',
                        default=100,
                        type=int,
                        help='Saturation Minimum Threshold')
    parser.add_argument('-S', '--satmax',
                        default=255,
                        type=int,
                        help='Saturation Maximum Threshold')
    parser.add_argument('-v', '--valmin',
                        default=200,
                        type=int,
                        help='Value Minimum Threshold')
    parser.add_argument('-V', '--valmax',
                        default=255,
                        type=int,
                        help='Value Maximum Threshold')
    parser.add_argument('-d', '--display',
                        action='store_true',
                        help='Display Threshold Windows')
    params = parser.parse_args()

    tracker = LaserTracker(
        cam_width=params.width,
        cam_height=params.height,
        hue_min=params.huemin,
        hue_max=params.huemax,
        sat_min=params.satmin,
        sat_max=params.satmax,
        val_min=params.valmin,
        val_max=params.valmax,
        display_thresholds=params.display
    )
    tracker.run()
