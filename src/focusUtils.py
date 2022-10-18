# -*- coding: utf-8 -*-
"""
Created on Sun Apr  4 17:04:30 2021

@author: Olle
"""
import AFM
import numpy as np
import matplotlib.pyplot as plt
import SCM as StageCom
import cv2
import time
import IRHM

#Size filter in pixels, might need to change based on species and objective
MINAREA = 10
MAXAREA = 100
#Particle distance filter. Things that are closer together get merged
MINCELLDISTANCE = 8
#Circularity filter. 1 demands perfect circularity, 0 means no circularity
MINCIRC = 0.6
#Intertia filter. 1 
MININERTIA = 0.4

params = cv2.SimpleBlobDetector_Params()
# Change thresholds
params.minThreshold = 0
params.maxThreshold = 255

# Filter by Area.
params.filterByArea = True
params.minArea = MINAREA
params.maxArea = MAXAREA
# Filter by Circularity
params.filterByCircularity = True
params.minCircularity = MINCIRC
params.maxCircularity = 1

# Filter by InertiaRatio
params.filterByInertia = True
params.minInertiaRatio = MININERTIA
params.maxInertiaRatio = 1

# Distance Between Particles
params.minDistBetweenBlobs = MINCELLDISTANCE

params.filterByColor = False

def runandshow(img,sparams = None):
    if sparams is None:
        global params
        sparams = params
    detector = cv2.SimpleBlobDetector_create(sparams)
    img = img[50:img.shape[0]-50,50*2:img.shape[1]-50*2]
    img = cv2.GaussianBlur(img,(3,3),0)
        
    #thresh_binary = cv2.adaptiveThreshold(img, 1, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 6)
    #ret1, thresh_binary = cv2.threshold(img,25,1,cv2.THRESH_BINARY)
    ret3,thresh_binary = cv2.threshold(img,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    binimg = thresh_binary
    th = cv2.multiply(img, thresh_binary)
    reversed_binimg =(1-binimg)*255 
    keypoints = detector.detect(th)  
    im_with_kp = cv2.drawKeypoints(th, keypoints, np.array([]),(0,0,255), cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS)
    img_disp = np.hstack((cv2.cvtColor(img,cv2.COLOR_GRAY2BGR),cv2.cvtColor(thresh_binary,cv2.COLOR_GRAY2BGR),im_with_kp))
    cv2.imshow("KP",img_disp)
    print(len(keypoints))
    #return keypoints

def make_z_stack(step=1, extent = 10):
    import skimage.io, tifffile,os
    import SeriCom
    import IPAMRH
    IPAMC = IPAMRH.AIPam()
    SeriC = SeriCom.SC()
    IWE_fp = 'C:\ImagingPamGigE\Data_RGB'
    SeriC.msg_resp("PZ 0")
    IPAMC.send_command("Select Image = ", "Ft")
    IPAMC.send_command("Ft only","")
    IPAMC.send_command("Save Tiff Image = ", "FocusImg0")
    Positions = [0]
    for fac in range(-1,2,2):
        for i in range(1,extent+1,step):            
            foc = SeriC.get_focus()
            print(f"Taking image {i*fac} ")
            time.sleep(2.5)
            print(f"Position: {foc}\n")
            Positions.append(foc)          
            time.sleep(8)
            IPAMC.send_command("Select Image = ", "Ft")
            IPAMC.send_command("Ft only","")
            IPAMC.send_command("Save Tiff Image = ", f"FocusImg{i*fac}")
            SeriC.go_to_z(i*fac)
            time.sleep(2.5)
            SeriC.go_to_z(i*fac)
        time.sleep(2.5)
        SeriC.go_to_z(0)
    focus_stack_col = skimage.io.imread_collection(IWE_fp+"\\FocusImg*",plugin = 'tifffile')
    focus_stack_imgs = focus_stack_col.concatenate()
    tifffile.imwrite(IWE_fp+"\\"+"Z_Stack.tif",focus_stack_imgs,imagej = True)
    with open (IWE_fp+"\\focus_pos.txt", mode ="a") as file:
        for focpos in Positions:
            file.write('%s\n' % focpos)   
    for fp in focus_stack_col.files:
        if (os.path.isfile(fp)):
            os.remove(fp)
        else:
            print(f"File at {fp} not found")
            
    
        
def rAFD(IMGs, AF = None,xticks=None):
    import AutoFocus as AFM
    if AF is None:
        AF = AFM.AFMan(len(IMGs-1),1)
    AF.compute_Initial_Setup([IMGs[0]],True)
    for idx,img in enumerate(IMGs[1:]):
        AF.perform_Autofocus(img, idx+1, 0, True)
        #AF.calc_score()
    fig,(ax2,ax3,ax4,ax5) = plt.subplots(4)
    fig.tight_layout(pad=3.0)
    #ax1.set_title('Avg_Scaled_Direction')
    #ax1.plot(AF.FSComponents[:,0,0])
    ax2.set_title('PLLS')
    ax2.plot(AF.FSComponents[:,0,1]/AF.FSComponents[0,0,1])
    ax3.set_title('Theta')                         
    ax3.plot(AF.FSComponents[:,0,0]/AF.FSComponents[0,0,0])
    ax4.set_title('Focus Score and Z corr')
    ax4.plot(AF.FS[:],color = "red")
    ax5.plot(AF.corrections[:], color = "green")
    if(xticks == None):
        plt.xticks(np.arange(1,len(IMGs),int(len(IMGs)/10)))
    else:
        plt.xticks(xticks)

def AF_Scoring(IMGs, AF = None,xticks=None,fp=None,plot=False):
    import AFM
    import ipdb
    if AF is None:
        AF = AFM.AFMan(len(IMGs),1,LPL=True,PLLS=True)
    AF.compute_initial_setup([IMGs[0]],True)
    print("Init done")
    for idx,img in enumerate(IMGs[1:]):
        AF.do_autofocus(img, idx+1, 0, True)
        #AF.calc_score()
    if(xticks is None):
        xticks = range(0,len(IMGs)-1)
    if(plot):
        fig,(ax1,ax2) = plt.subplots(2)
        fig.suptitle("Autofocus Scoring")
        fig.tight_layout(pad=3.0)
        ax1.set_ylabel('Focus score')
        ax1.scatter(xticks, AF.FSComponents[:,0,1]/AF.FSComponents[0,0,1])
        ax2.set_ylabel('Magnitude of Z correction')
        ax2.scatter(xticks, AF.corrections[:])
        plt.xlabel("Z distance from focal plane")
        fig.savefig(fname = fp+"/Focus_Score")
        plt.close()
    #return xticks,AF.FSComponents[:,0,1]/AF.FSComponents[0,0,1], AF.corrections[:]
    return xticks,AF.FS, [x[0] for x in AF.corrections]

   
def read_xticks(fp):
    num_list = []
    with open(fp,'r') as fh:
        for line in fh:
            num_list.append((float(line)))
    return num_list

def read_cor_xticks_stack(fp):
    import tifffile
    import numpy as np
    positions = read_xticks(fp+"/focus_pos.txt")
    stack = tifffile.imread(fp+"/Z_stack.tif")
    cor_pos =[0]
    cor_pos.extend(positions[10:0:-1])
    cor_pos.extend(positions[11:])
    cor_stack = np.append(stack[0,None],stack[10:0:-1][:,:],axis=0)
    cor_stack = np.append(cor_stack,stack[11:][:,:],axis=0)
    return cor_pos,cor_stack

def perform_scoring(fp):
    pos,imgs = read_cor_xticks_stack(fp)
    xticks, fs, z_cor = AF_Scoring(IMGs = imgs,xticks=pos,fp=fp)
    if(sum(fs) == 0):
        return z_cor,xticks
    with open(fp+".txt", mode = "w") as fh:
        for i in range(len(xticks)):
            fh.write(str(xticks[i]) + "," + str(fs[i]) + "," + str(z_cor[i])+"\n")
    #plt.plot(xticks,z_cor)
    return z_cor,xticks,fs
    
#The below function attempts to correct in a single position. It prints the 
#iteration and the correction applied. Micromanager 2.0 and imagingwin needs to be running, and the ipamremotescript
#Proper useage/commands are as follows (iphython console). Make sure you are running in proper working directory:

def single_pos_Autofocus(IPAM, InitImg, factor, AF = None):
    SC = StageCom.StageCom()
    import cv2
    import IPAMRH
    IWE_fp = "C:/"
    IPAMR = IPAMRH.AIPam()
    IPAMR.send_command("Ft only","")
    IPAMR.send_command("Select Image", "Ft")
    IPAMR.send_command("Save Tiff Image = ", "FocusImg")
    #imgsrc = cv2.imread("FocusImg.tif", cv2.IMREAD_GRAYSCALE)
    imgsrc=cv2.imread(IWE_fp+"\FocusImg.tif",cv2.IMREAD_GRAYSCALE)
    #single_pos_Autofocus(IPAMR,imgsrc,1)
    if AF is None:
        AF = AFM.AFMan(1,10)
    AF.compute_initial_setup([InitImg],True)
    for i in range(100):
         time.sleep(2.0)
         dz = AF.do_autofocus(IPAM,1,0,True)
         print(str(i) + "\t" + str(dz))
         correction = factor*dz
         SC.move_focus(correction)
         
            
def SSIM(imgstack):
    from skimage.metrics import structural_similarity
    import tifffile
    scores = []
    if(type(imgstack) == str):
        #If we don't get an tiff-stack, assume its coming directly as a ImagingWin output stack
        imgstack = tifffile.imread(imgstack)
)        imgstack = imgstack[4:]
    imgstack = make_Yield_Images(imgstack)
    for img in imgstack:
        score = structural_similarity(imgstack[0],img)
        scores.append(score)
    
    for score in scores:
        print(f"SSIM: {score}")
    return scores
    
def make_Yield_Images(img_stack):
    """
    Parameters
    ----------
    img_stack : Numpy, shape = 2x, 480, 640
        Input image stack of only Fo/Fm.

    Returns
    -------
    Yield image stack: x,480,640. Range of values are 0.0 to 1.0

    """
    #Assumes the initial 4 images have been removed
    Fo = img_stack[::2]
    Fm = img_stack[1::2]
    Fm = np.asarray(Fm,dtype=np.int8)
    #Yield is defined as Fv/Fm or (Fm-Fo)/Fm
    Yield = []
    for i in range(len(Fo)):
        Mask = np.where(Fm[i] > int(0.05*256),1,0)
        #Mask = Mask.astype(np.uint8)        
        #Mask = cv2.medianBlur(Mask,3)
        #Mask = np.where(Mask>0,1,0)
        Fv = np.subtract(Fm[i],Fo[i],dtype = np.int8)
        #Floor to zero
        Fv = np.multiply(np.clip(Fv,0,255),Mask)
        #ipdb.set_trace()
        #cYield = np.divide(Fv,Fm[i],out=np.zeros_like(Fv),where=Fm[i]!=0)
        cYield = np.divide(Fv.astype(np.float16),Fm[i].astype(np.float16),out=np.zeros_like(Fv, dtype=np.float16),where=Fm[i]!=0)
        Yield.append(cYield)
    return np.asarray(Yield)

# import matplotlib.pyplot as plt 

# dirs = ["C:/Users/ollpo511/Documents/U-Print/Behrendt/Z_Stacks/03_10_Chalmy_10x",
# "C:/Users/ollpo511/Documents/U-Print/Behrendt/Z_Stacks/16_09_4019",
# "C:/Users/ollpo511/Documents/U-Print/Behrendt/Z_Stacks/28_09_Chlamy_10x",
# "C:/Users/ollpo511/Documents/U-Print/Behrendt/Z_Stacks/29_09_421_10x",
# "C:/Users/ollpo511/Documents/U-Print/Behrendt/Z_Stacks/30_09_421_10x/1"]
# #"C:/Users/ollpo511/Documents/U-Print/Behrendt/Z_Stacks/30_09_421_10x/2"]
# plt.close()
# fs = []
# xticks = []
# zcors = []
# for sd in dirs:
#     z,x,f = perform_scoring(sd)
#     xticks.append(x)
#     zcors.append(z)
#     fs.append(f)
    
# for idx in range(0,len(dirs)):
#     plt.scatter(xticks[idx],zcors[idx],label=dirs[idx])
# plt.legend()

# avgz = np.mean(zcors,0)
# avgzer = np.std(zcors,0)
# avgx = np.mean(xticks,0)
    
# plt.errorbar(avgx,avgz,yerr=avgzer)
    
    
    
    
    