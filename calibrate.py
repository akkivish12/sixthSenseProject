# import the necessary packages
from getperspective import four_point_transform
import numpy as np
import cv2

corners=[False,False,False,False] #TL, TR, BR, BL
refPts=[]

def on_mouse(event, x, y, flags, param):
	global corners, refPts
	if event == cv2.EVENT_LBUTTONDOWN:
		if not corners[0]:
			corners[0]=True
			refPts=[(x, y)]
		elif not corners[1]:
			corners[1]=True
			refPts.append((x, y))
		elif not corners[2]:
			corners[2]=True
			refPts.append((x, y))
		elif not corners[3]:
			corners[3]=True
			refPts.append((x, y))
		
cap = cv2.VideoCapture(0)

# read the first frame
ret, frame = cap.read()

while(cap.isOpened()):
    # Capture frame-by-frame
    ret, frame = cap.read()
    
    cv2.setMouseCallback('frame', on_mouse)
    
    for i in range(4):
    	if corners[i]:
    		cv2.circle(frame, refPts[i], 5, (0,255,0), 1)

	# Display the resulting frame
    cv2.imshow('frame',frame)
    
    if corners[0] and corners[1] and corners[2] and corners[3]:
    	warped = four_point_transform(frame, np.array(refPts, dtype = "float32"))
    	cv2.imshow("warped", warped)

    if cv2.waitKey(20) & 0xFF == ord('q'):
        break

# When everything done, release the capture
cap.release()
cv2.destroyAllWindows()