# -*- coding: utf-8 -*-
"""
Created on Sun Apr  4 16:46:44 2021
Autofocus algorithm.
Initial boilerplate from :
https://stackoverflow.com/questions/59339013/skimage-watershed-and-particles-size-detection
Credit: fmw42   
@author: Olle
"""


from dataclasses import dataclass
import numpy as np
import cv2
import skimage
import time
import IRHM
import PacMan
import scipy
import tifffile
from scipy.fftpack import fft2
from scipy.ndimage.measurements import sum as nd_sum


global dZMIN, Strength,MINSIZE,MAXSIZE
#Minimum z-movement
#FOR 10x: 0.2
#For 20x: 0.1
dZMIN = 1
#Focus score to dZ conversion factor
#FOR 10x: 60-100
Strength = 100
#Use blurring pre-processing?
BLURRING = True
#Use bilateral filter
BILATERAL = False
#Threshold for Binary thresholding
THRESHOLD = 7
#Colour parameter for bilateral filter
fC = 5
#Spatial parameter for bilateral filter
fS = 5
#Size filter in pixels, might need to change based on species and objective
MINSIZE = 5   #Olle value:20
MAXSIZE = 40
#Particle distance filter. Things that are closer together get merged
MINCELLDISTANCE = 5
#Circularity filter. 1 demands perfect circularity, 0 means no circularity
MINCIRC = 0.4   #Olle value:0.3
#Intertia filter. 1 
MININERTIA = 0.4

#Image borders to avoid gaussian?
#10x, 20x, 40x?
#or just remove 100px
BORDER = 75

@dataclass
class Particle:
    def __init__(self):
        pass
    x: float
    y: float
    area: float
    center_conf: float
    circularity: float
    intertia: float
    n_variance: float
    theta: float
    

# Python: cv2.KeyPoint([x, y, _size[, _angle[, _response[, _octave[, _class_id]]]]]) → <KeyPoint object>

IWE_fp = 'C:\ImagingPamGigE\Data_RGB'

class AFMan:
    
# Z-positions corresponding to every pos every time
# dZ correction applied to every pos evert time
# Previous focus informations

    def __init__(self, iterations, positions, AFFlag = True, PLLS = True, LPL = False, parameters = None, Strength = 100):
        self.FSComponents = np.zeros(shape = (iterations,positions,3))
        self.FS = np.zeros(shape = (iterations,positions))
        self.brects = []
        self.Init_Masks = []
        self.corrections = np.zeros(shape = (iterations,positions))
        self.AFOn = AFFlag
        self.Use_PLLS = PLLS
        self.Use_LPL = LPL
        if parameters is None:
            parameters = [None] * 9
            #Min/Max 
            parameters[0] = 0
            parameters[1] = 255
            #Area
            parameters[2] = MINSIZE
            parameters[3] = MAXSIZE
            #Circularity
            parameters[4] = MINCIRC
            parameters[5] = 1
            #Intertia Ratio
            parameters[6] = MININERTIA
            parameters[7] = 1
            #Min dist between cells before they are merged
            parameters[8] = MINCELLDISTANCE
        self.set_parameters(parameters)
        #return (f"Size range: {parameters[2]}-{parameters[3]}. Min circ: {parameters[4]}. Min inertia: {parameters[6]}")
    
    
    
    def do_autofocus(self, IPAM, iteration, position, Debug = False):
        """
        Calculates the difference in Z for current position/iteration. 

        Parameters
        ----------
        IPAM : IRHM.py
            IRHM handle. Needed for producing F0 images. 
        iteration : int
            What iteration.
        position : int
            Which position. Used to look up initial image to compare against.
        Debug : bool, optional
            DESCRIPTION. The default is False.

        Returns
        -------
        dZ : float
            distance in micrometers to move to correct.

        """
        dZ = 0
        if(self.AFOn):
            #Prepare image
            img = self.prepare_image(IPAM, Debug)
            cur_FS = 0
            #Compute focus score
            try:
                FComps = self.compute_focus_score_components(img*self.Init_Masks[position], self.brects[position],Debug)
            except ZeroDivisionError:
                cur_FS = 0
                FComps = self.FSComponents[0,0]
                print(f"No theta score possible. Stopped at iteration: {iteration}, position {position}. Shutting off autofocus \n\n", True)
                self.AFOn = False
            self.FSComponents[iteration,position] = FComps[0:3]
            #Normalize
            if(self.Use_PLLS):
                cur_FS += (FComps[1] / self.FSComponents[0,position,1])
            if(self.Use_LPL):
                norm_LPL = (FComps[2] / self.FSComponents[0,position,2])
                if(norm_LPL < 1):
                    cur_FS += norm_LPL
                else:
                    cur_FS += 1
            self.FS[iteration,position] = cur_FS
            #Calculate movement needed
            dZ = 0
            if(iteration != 0):             
                dZ = self.compute_correction(cur_FS, FComps[0], iteration, position, Debug)
                self.corrections[iteration][position] = dZ
            #Store and return that value   
        return dZ
        

    def compute_initial_setup(self, Imgs, Debug = False):
        """
        Calculates focus score of a set of initial images. Should be Fm and F0 images. 

        Parameters
        ----------
        Imgs : List of 640x480 uint8 arrays
            DESCRIPTION.
        Debug : bool, optional
            Debug mode. Additional outputs in the form of images and readouts. The default is False.

        Returns
        -------
        None.

        """
        cv2.destroyAllWindows()
        #Incoming images should be following: 
        #Set of Fm images for mask creation
        #Set of F0 images to calculate on
        for idx, init_img in enumerate(Imgs):
            prep_img = self.prepare_image(init_img, Debug)
            mask_img,b_rects = self.make_initial_mask(idx,prep_img, Debug)
            init_FS = 0
            try:
                FComps = self.compute_focus_score_components(prep_img * self.Init_Masks[idx], b_rects, True)
                #Assume laplcian first is always best
                self.FSComponents[0,idx] = FComps[0:3]
                if(self.Use_PLLS):
                    init_FS += 1
                if(self.Use_LPL):
                    init_FS += 1
            except ZeroDivisionError:
                print(f"Unable to establish baseline focus on position {idx}")
                self.AFOn = False
                init_FS = 0
                FComps = [0,0,0]
            self.FSComponents[0,idx] = FComps
            self.FS[0,idx] = init_FS
        
    def compute_focus_score_components(self, IMG, rects = [], Debug = False):
        """
        Computes the major focus score components.

        Parameters
        ----------
        IMG : uint8 array
            F0 image to calculate focus score on.
        rects : [rects], optional
            List of bounding rectangles. The default is [].
        Debug : bool, optional
            DESCRIPTION. The default is False.

        Returns
        -------
        None.

        """
    #Compute and return the focus score
    #However first we filter our particles
    #We choose our particles by filtering them based one
    #1. Size > MINSZIE
    #2. Circularity >  Min Circ   
    #Whole image focus metrics
        if(Debug):
            disp_img = cv2.cvtColor(IMG,cv2.COLOR_GRAY2BGR)
            cv2.imshow("Image used for focus score calc comp", disp_img)
        PLLS = calculate_power_spectrum(IMG)
        LPL = 0.0
        for rect in rects:
            rect_img = IMG[rect[0]:rect[1],rect[2]:rect[3]]
            try:
                LPL += cv2.Laplacian(rect_img, cv2.CV_64F).var()
            except:
                LPL += 0
        LPL /= len(rects)
        
    #Partial image focus metrics
        conts, hierarchy = cv2.findContours(IMG, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)  
        particles = self.fill_particles(IMG, conts)
        n_p = len(particles)
        avg_circ = avg_inertia = avg_scaled_direction = avg_theta = PARatio =  0.0
        if( n_p == 0):      
            contimg = cv2.cvtColor(IMG, cv2.COLOR_GRAY2BGR)
            drawn = cv2.drawContours(contimg,conts,-1,(0,0,255),3)
            disp_img = np.hstack((contimg,cv2.cvtColor(IMG,cv2.COLOR_GRAY2BGR)))
            cv2.imshow(f"No parts. Conts: {len(conts)}", disp_img)
            print("No particles. Showing image")
            particles = []
        else:
            for idx,part in enumerate(particles):
                avg_theta +=  part.theta 
                avg_inertia +=  part.inertia
                if(part.inertia<0.85):
                    avg_theta +=  part.theta      
                avg_circ +=  part.circularity
            avg_theta = avg_theta / n_p  
            avg_inertia = avg_inertia/n_p     
            avg_circ = avg_circ / n_p
            LPL = LPL / n_p
        factors = [1,1,1]
        FSComps = []
        FSComps.append( factors[0] * avg_theta )
        if(isinstance(PLLS,int) or isinstance(PLLS,float)):
            FSComps.append( factors[1] * float(PLLS))
        else:
            FSComps.append( factors[1] * PLLS[0])
        FSComps.append( factors[2] * avg_inertia)
        msg = f"Parts: {n_p}. Avg_circ: {avg_circ}. Theta: {FSComps[0]:.3f}, PLLS: {FSComps[1]:.3f}, Avg_inertia: {FSComps[2]:.3f}"
        if(Debug):
            print(msg)
        else:
            PacMan.logmsg(msg,True)
        print("Focus components calculated")
        return FSComps
    
    
        
    def compute_correction(self,FMS, avg_theta, iteration,position, Debug = False):
        """
        

        Parameters
        ----------
        FMS : float
            Focus metric score.
        avg_theta : Average direction/rotation of cells
            DESCRIPTION.
        iteration : TYPE
            DESCRIPTION.
        position : TYPE
            DESCRIPTION.
        Debug : TYPE, optional
            DESCRIPTION. The default is False.

        Returns
        -------
        TYPE
            DESCRIPTION.

        """
        #Compare to the first image, which is assumed to be completely in focus
        global dZMIN, Strength
        diff = abs(FMS - self.FS[0][position])
        orientation = 1
        if(avg_theta < 90):
            orientation = -1
        elif(avg_theta > 90):
            orientation = 1
        else:
            orientation = 0
        dz = 0
        if(FMS == 0):
            return 0
        dz = diff * orientation * Strength 
        if(abs(dz) > dZMIN): #Only perform correction if there is a large enough difference   
            msg = f"Computed Focus score diff: {diff:.3f} at pos{position}. Computed Z-Correction to apply: {dz:.2f}\n"
            self.corrections[iteration,position] = dz
        else:
            msg = f"Difference in focus score to small to merit correction. FS diff: {diff:.3f}. {dz:.2f} < {dZMIN} um at {position}\n"
            dz = 0
        if(Debug):
            print(msg)
        else:
            PacMan.logmsg(msg,True)
        return round(dz,2)

    def fill_particles(self,img, conts):
        Parts = []
        import ipdb
        for contourIdx, cnt in enumerate(conts):
            center = Particle()
            moms = cv2.moments(conts[contourIdx]);
            area = moms['m00'];
            if(area<4):
                continue
            center.area = area
            perimeter = cv2.arcLength(conts[contourIdx], True)
            if(perimeter > 0):
                center.circularity  = 4 * np.pi * area / (perimeter**2)
            else:
                center.circularity = 0
                
            if (moms['mu11'] == 0.0):
                #Perfectly circular
                center.inertia = 1
                center.theta = 0
                
            (x,y),(mA,MA),angle = cv2.fitEllipseDirect(cnt)
            center.inertia = MA/mA
            center.theta = angle
                
            
            if(len(Parts) >= 30):
                del(Parts[self.worst_part(Parts)])
            Parts.append(center)   
        return Parts

    
    def worst_part(self,parts):
        targetidx = 0
        #Remove particles that are 2 metrics lower
        for idx, part in enumerate(parts):
            if(part.circularity < parts[targetidx].circularity and part.inertia < parts[targetidx].inertia):
                targetidx = idx
        return targetidx
        

    def prepare_image(self, src, Debug = False):
        if(isinstance(src, IRHM.AIPam)):
            src.send_command("Select Image = ", "Ft")
            time.sleep(8)
            src.send_command("Ft only","")
            src.send_command("Save Tiff Image = ", "FocusImg")
            time.sleep(0.5)
            img = cv2.imread(IWE_fp + "\FocusImg.Tif",cv2.IMREAD_GRAYSCALE)
        else:
            img = src #Just debug thangs 
            #type(src)
        #Remove outer pixels to avoid beam shape interference. Original img is 480x640
        #Reduce to (480-border)x(640-border*2)
        img = img[BORDER:img.shape[0]-BORDER,BORDER*2:img.shape[1]-BORDER*2]        
        if(BLURRING):
            img = cv2.medianBlur(img,3)        
        if(BILATERAL):
            th = cv2.bilateralFilter(img,10,fC,fS)
        else:
            #Remove single peaks with values below Threshold(=7).
            ret, th = cv2.threshold(img,THRESHOLD,255,cv2.THRESH_TOZERO)
        #self.bin = thresh_binary
        #th = cv2.multiply(img, thresh_binary)
        img = th
        if Debug:
            img_disp = np.hstack((cv2.cvtColor(img,cv2.COLOR_GRAY2BGR),cv2.cvtColor(th*255,cv2.COLOR_GRAY2BGR), cv2.cvtColor(th,cv2.COLOR_GRAY2BGR)))
            cv2.imshow("Imgs",img_disp)
        self.img = img
        return img
    
    def make_initial_mask(self, idx, img = None, Debug = False):
        """
        

        Parameters
        ----------
        idx : TYPE
            DESCRIPTION.
        img : TYPE, optional
            DESCRIPTION. The default is None.
        Debug : TYPE, optional
            DESCRIPTION. The default is False.

        Returns
        -------
        bRectsMask : TYPE
            DESCRIPTION.
        bounding_rects : TYPE
            DESCRIPTION.

        """
        if(img is None):
            img = self.img #Debugging
        detector = cv2.SimpleBlobDetector_create(self.params)
        keypoints = detector.detect(img)  
        bRectsMask = np.zeros(shape = img.shape, dtype = np.uint8)
        border = 1
        bounding_rects = []
        for kp in keypoints:
            x = round(kp.pt[0])
            y = round(kp.pt[1])
            sz = round(kp.size)
            if(sz < 3):
                continue
            bxLeft = x-sz-border 
            bxRight = x+sz+border
            byTop =  y-sz-border 
            byBot = y+sz+border
            # if(np.any(img[byTop:byTop+1,bxLeft:bxRight] > 15) or np.any(img[byBot-1:byBot,bxLeft:bxRight] > 15) or np.any(img[byTop:byBot,bxLeft:bxLeft+1] > 15) or np.any(img[byTop:byBot,bxRight-1:bxRight] > 15)):
            #     continue
            if(bxLeft < 0 or byTop < 0):
                continue
            bRectsMask[byTop:byBot, bxLeft:bxRight ] = 1
            bounding_rects.append([byTop,byBot,bxLeft,bxRight])
        maskedimg = bRectsMask * img
        if Debug:
            img_disp = np.hstack((cv2.cvtColor(img,cv2.COLOR_GRAY2BGR),cv2.cvtColor(bRectsMask * 255,cv2.COLOR_GRAY2BGR), cv2.cvtColor(maskedimg,cv2.COLOR_GRAY2BGR)))
            cv2.imshow("Maskedimg", img_disp)
            #cv2.imwrite(f"Maskedimg_{idx}.tif",img_disp)
            #cv2.imwrite("..\Mask_Image.tif",img_disp)
        self.Init_Masks.append(bRectsMask)
        self.brects.append(bounding_rects)
        return bRectsMask, bounding_rects

    def set_parameters(self, parameters):
        self.params = cv2.SimpleBlobDetector_Params()
        # Change thresholds
        self.params.minThreshold = parameters[0]
        self.params.maxThreshold = parameters[1]
        #self.params.thresholdStep = 8
        
        # Filter by Area.
        self.params.filterByArea = True
        self.params.minArea = parameters[2]
        self.params.maxArea = parameters[3]
        
        # Filter by Circularity
        self.params.filterByCircularity = True
        self.params.minCircularity = parameters[4]
        self.params.maxCircularity = parameters[5]
        
        # Filter by InertiaRatio
        self.params.filterByInertia = True
        self.params.minInertiaRatio = parameters[6]
        self.params.maxInertiaRatio = parameters[7]
        
        # Distance Between Particles
        self.params.minDistBetweenBlobs = parameters[8]
        
        self.params.filterByColor = False
        
    def GUI_set_parameters(self,params):
        global dZMIN, Strength, MINSIZE, MAXSIZE, MININERTIA, MINCIRC
        dZMIN = params[0]
        Strength = params[1]
        
        self.params.minCircularity = params[2]
        MINCIRC = params[2]
        self.params.minInertiaRatio = params[3]
        MININERTIA = params[3]
        self.params.minArea = params[4]
        MINSIZE = params[4]
        self.params.maxArea = params[5]
        MAXSIZE = params[5]
    
    def GUI_get_parameters(self):
        return [dZMIN,Strength,MINCIRC,MININERTIA,MINSIZE,MAXSIZE]
        
    def GUI_load_parameters(self,fp = "PAC_settings.txt"):
        """
        Loads in AFM parameters from a settings file.

        Parameters
        ----------
        fp : TYPE, optional
            DESCRIPTION. The default is "PAC_settings.txt".

        Returns
        -------
        None.

        """
        import re
        with open(fp) as fh:
            lines = fh.readlines()
            AFM_settings = []
            for line in lines:
                if("focusThreshold" in line):
                    self.params.minThreshold=re.findall("(\d+)", line)[0]
                    self.params.maxThreshold=re.findall("(\d+)", line)[1]
                elif("focusArea" in line):
                    self.params.minArea=re.findall("(\d+)", line)[0]
                    self.params.maxArea=re.findall("(\d+)", line)[1]
                elif("focusCircularity" in line):
                    self.params.minCircularity=re.findall("(\d+)", line)[0]
                    self.params.maxCircularity=re.findall("(\d+)", line)[1]
                elif("focusInertia" in line):
                    self.params.minInertiaRatio=re.findall("(\d+)", line)[0]
                    self.params.maxInertiaRatio=re.findall("(\d+)", line)[1]
                elif("UseLPL" in line):
                   self.UseLPL = bool(line[5:])
                elif("UsePLLS" in line):
                   self.UsePLLS = bool(line[5:])
                   
                
    def calibrate(self,IPAM, SCMH, useLPL,usePLLS,startStrength, calibrationDistance):
        import matplotlib.pyplot as plt
        strength = startStrength
        LPLWeight = 8
        PLLSWeight  = 1
        
        temp_AFMan = AFMan(11,1,True,useLPL,usePLLS,None,startStrength)
        PFImg = self.prepare_image(IPAM)
        temp_AFMan.compute_initial_setup(PFImg)
        
        cRange,aRange,FSI = self.make_Z_image_stack(IPAM,SCMH,calibrationDistance)
        
        fig,ax = plt.figure()
        fig.set_title("Autofocus Scoring")
        ax.scatter(aRange,cRange)
        ax.set_xlabel('Actual Movements')
        ax.set_ylabel('Calculated Movements')

        tolerance = 0.5
        error = 1
        
        while(error>tolerance):
            for idx, img in enumerate(FSI):
                temp_AFMan.do_autofocus(img, idx+1, 0, True)
                
            dZFig,dzAX = plt.figure()
            dZFig.set_title("Autofocus Scoring")
            dzAX.scatter(aRange,temp_AFMan.corrections[:])
            errors = np.subtract(aRange,temp_AFMan.corrections[:])
            error = sum(errors)
            abserror = abs(error)
            dzAX.plot(errors,aRange,label = f"Errors. Cum. Abs. Error: {abserror}", color="red")
            dzAX.set_xlabel('Actual Distances')
            dzAX.set_ylabel('Calculated corrections')
            dZFig.legend()
            
            print("5-step calibration finished with:")
            print(f"Use PLLS:{usePLLS}. Use LPL:{useLPL}")
            print(f"Strength:{aRange}")
            print(f"Range:{aRange}")
            print(f"Errors:{errors}")
            print(f"Total cumulative error:{abserror}")
            print(f"Tolerance:{tolerance}")
            
            strengthFactor = (calibrationDistance+(np.sign(error)*abserror))/calibrationDistance
            #Only allow increase/decreases by 50%
            strengthFactor = np.clip([strengthFactor],0.5,1.5)
            strength = strength * strengthFactor
        
        return strength
        
    def make_Z_image_stack(self,IPAM,SCMH,calibrationDistance):
        calibrationRange = np.arange(-calibrationDistance,calibrationDistance+1,int(calibrationDistance/5))
        actualRange = []
        for position in calibrationRange:
            SCMH.go_to_z(position)
            time.sleep(1)
            SCMH.go_to_z(position)
            SCMH.sleep(1)
            foc = SCMH.get_focus()
            print(f"Taking image at {position} ")
            actualRange.append(foc)          
            time.sleep(7)
            IPAM.send_command("Select Image = ", "Ft")
            IPAM.send_command("Ft only","")
            IPAM.send_command("Save Tiff Image = ", f"FocusImg{position}")
        focusStackCollection = skimage.io.imread_collection(IWE_fp+"\\FocusImg*",plugin = 'tifffile')
        focusStackImages = focusStackCollection.concatenate()
        return calibrationRange,actualRange,focusStackImages  
        
    def reset_AF_manager(self,initImg):
        self.FSComponents = np.zeros(shape = (self.iterations,self.positions,3))
        self.FS = np.zeros(shape = (self.iterations,self.positions))
        self.brects = []
        self.Init_Masks = []
        self.corrections = np.zeros(shape = (self.iterations,self.positions))
        self.compute_initial_setup(initImg)
    
#Takes grayscale imgs
def calculate_power_spectrum(image):
    if(image.ndim != 2):
        pixel_data = image[:, :, 0]
    else:
        pixel_data = image[:,:]

    radii, magnitude, power = rps(pixel_data)
    if sum(magnitude) > 0 and len(np.unique(pixel_data)) > 1:
        valid = magnitude > 0
        radii = radii[valid].reshape((-1, 1))
        power = power[valid].reshape((-1, 1))
        if radii.shape[0] > 1:
            idx = np.isfinite(np.log(power))
            powerslope = scipy.linalg.basic.lstsq(
                np.hstack(
                    (
                        np.log(radii)[idx][:, np.newaxis],
                        np.ones(radii.shape)[idx][:, np.newaxis],
                    )
                ),
                np.log(power)[idx][:, np.newaxis],
            )[0][0]
        else:
            powerslope = 0
    else:
        powerslope = 0
    return powerslope
        
def rps(img):
    assert img.ndim == 2
    radii2 = (np.arange(img.shape[0]).reshape((img.shape[0], 1)) ** 2) + (
        np.arange(img.shape[1]) ** 2
    )
    radii2 = np.minimum(radii2, np.flipud(radii2))
    radii2 = np.minimum(radii2, np.fliplr(radii2))
    maxwidth = (
        min(img.shape[0], img.shape[1]) / 8.0
    )  # truncate early to avoid edge effects
    if img.ptp() > 0:
        img = img / np.median(abs(img - img.mean()))  # intensity invariant
    mag = abs(fft2(img - np.mean(img)))
    power = mag ** 2
    radii = np.floor(np.sqrt(radii2)).astype(np.int) + 1
    labels = (
        np.arange(2, np.floor(maxwidth)).astype(np.int).tolist()
    )  # skip DC component
    if len(labels) > 0:
        magsum = nd_sum(mag, radii, labels)
        powersum = nd_sum(power, radii, labels)
        return np.array(labels), np.array(magsum), np.array(powersum)
    return [2], [0], [0]

def calc_Score(img):
    PLLS = calculate_power_spectrum(img)
    LPL = cv2.Laplacian(img, cv2.CV_64F).var()
    print(f"{PLLS}, {LPL*8}")
    return PLLS,LPL*8