#is # -*- coding: utf-8 -*-
"""
PACMan: An chlorophyll-a fluorometry automation software designed for Walz (GMBH) Microscopy IPAM.

Confirmed to be compliant with V 2.51d of Imaging-Win
Confirmed to be compliant with PRIOR ProScan III controller

Copyright (C) 2022  Olle Pontén

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
Contact: olle.ponten@gmail.com

"""
import SCM
import IRHM
import AFM
import pacmangui
import tifffile
import skimage
import skimage.io
import os, time, sys
from datetime import datetime
import matplotlib
matplotlib.use("Qt5Agg")
import numpy as np

import ipdb

global output_dir, gui_ptr
output_dir = 'C:\ImagingPamGigE\Data_RGB'

global ADAPTIVE_POSITIONING, DEBUG, AUTOFOCUS_ROUNDS
ADAPTIVE_POSITIONING = False
DEBUG = True
AUTOFOCUS_ROUNDS = 1

class PacMan:   
    StageCom = None
    IPam = None
    pQueue = None
    AutoFocuser = None
    log_Positions = False
    commandQueue = []
    Experiment_Dir = output_dir

    def __init__(self):    
        
        try:
            self.IPam = IRHM.AIPam()
        except ConnectionError as e:
            print("Error when starting IRHM. Double check ImagingWin is running. Aborting")
            cleanup()
            sys.exit()
        use_Serial = True
        if(use_Serial):
            self.StageCom = SCM.SC()
        else:
            self.StageCom = PycroCom.PCMCom()
        self.cancel_flag = False
        self.AF = True
        self.commandQueue = []
        
    def run_experiment(self, tk_ptr,exp_Settings , Debug = True):
        """
        

        Parameters
        ----------
        Exp_name : Str
            DESCRIPTION.
        Experiment_Rep : int
            DESCRIPTION.
        Experiment_Ints : int
            DESCRIPTION.
        tk_ptr : Tkinter
            DESCRIPTION.
        Debug : TYPE, optional
            DESCRIPTION. The default is True.

        Returns
        -------
        None.

        """
        global experiment, gui_ptr
        #exp_Settings = [exp_Name, exp_Reps,experiment_intervallervall, temp_sep, af_Flag, dark_adapt_Flag, log_Positions]
        #The call is found in pacmangui.py
        gui_ptr = tk_ptr
        gui_ptr.msg_box("Reminder!","Did you remember to turn off the microscope light?")
        experiment_name = exp_Settings[0]
        experiment = experiment_name
        experiment_iterations = exp_Settings[1]
        experiment_Intervall = exp_Settings[2]
        temp_sep = exp_Settings[3]
        self.cancel_flag = False
        self.AF = exp_Settings[4]
        self.dark_adapt_Flag = exp_Settings[5]
        self.log_Positions_flag = exp_Settings[6]
        #Create a list of lists with one lit for every repetition done.
        for i in range(experiment_iterations):
            self.commandQueue.append([])
        logmsg(f"Started Experiment: {experiment_name}", True)
        logmsg(f"Settings: Iterations: {experiment_iterations} Intervall(s): {experiment_Intervall}. Temporal separation(s): {temp_sep}. Dark adaption: {self.dark_adapt_Flag}" ,True)    
        if(self.AF):
            self.AutoFocuser = AFM.AFMan(experiment_iterations,self.StageCom.get_pos_list_length(), self.AF,True,True)
            pacmangui.load_AF()
            logmsg(self.AutoFocuser.GUIGetParams(),True)
        if(self.dark_adapt_Flag):
            self.IPam.send_command('ML','Off')
            logmsg("Dark adapting for 30 minutes")
            self.waiting(1800)
        logmsg(self.StageCom.retrieve_pos_list(),True)
        for i,iteration in enumerate(self.commandQueue):
            if(len(iteration)>0):
                print(f"Scheduled commands to run at iteration {i}")
                for com in iteration:
                    print(com)
        self.IPam.send_command('ML','On')
        if(not self.cancel_flag):
            self.execute_acquisition(temp_Sep = temp_sep, script_Args = [True, experiment_name,0])
        #Compute initial setup.
        if(self.AF):
            self.AutoFocuser.compute_initial_setup(self.save_initial_imgs(experiment_name),True)
        logmsg("Starting up first wait intervall after initial imgs.")
        self.IPam.send_command('ML','Off')
        self.waiting(intervall = experiment_Intervall)
        for Current_Iteration in range(experiment_iterations): 
            if(not self.cancel_flag):
                if(len(self.commandQueue[Current_Iteration])>0):
                    for com in self.commandQueue[Current_Iteration]:
                        logmsg(f"Executing command {com[0]} with parameter {com[1]}",True)
                        if("TempSep" in com[0]):
                            logmsg(f"Changing temporal separation to: {com[1]} seconds",True)
                            temp_sep = int(com[1])
                        elif("IterSep" in com[0]):
                            logmsg(f"Changing iteration wait time to: {com[1]} seconds",True)
                            experiment_Intervall = int(com[1])
                        print(self.IPam.send_command(com[0], com[1]))
                self.IPam.send_command('ML','On')
                self.waiting(5)
                logmsg(f"Running repetition number: {Current_Iteration+1}/{experiment_iterations}", True)
                self.IPam.send_command("New Record","")
                self.execute_acquisition(temp_Sep = temp_sep, script_Args = [False,experiment_name,Current_Iteration])
                logmsg(f"Successfully completed acquisiton, now waiting for {experiment_Intervall} s", True)
                self.reorder_iteration_images(experiment_name, Current_Iteration)
                starttime = int(round(time.time()))
                #Update progress bar
                progress = round((float(Current_Iteration)/float(experiment_iterations))*100,2)
                tk_ptr.Exp_Progress['value'] = progress
                #Wait until we are done, keeping the GUI active
                #self.IPam.send_command('ML','Off')
                self.waiting(intervall = experiment_Intervall, starttime = starttime)
            else:
                #Handle cancellation
                logmsg("Experiment cancelled",True)
                self.IPam.send_command('ML','Off')
                #self.StageCom.clear_pos_list()
                self.commandQueue.clear()
                tk_ptr.cancel_exp()
                break
        logmsg("Experiment complete",True)
        self.StageCom.prior_command("SERVO,0")

    def execute_acquisition(self, script_Args, temp_Sep = 0, printLog = True):
        """
        Performs movement over the position list, running the defined
        position script at each position in the list
        Parameters
        ----------
        position_Script : Function
            Should be filled with whatever function you want to
            be executed at every position as it moves.

        printLog : Boolean
            Determines whether output should be printed to console
        Returns
        -------
        Log file.

        """
        global output_dir
        IPRH = self.IPam
        SC = self.StageCom
        AFMan = self.AutoFocuser
        iter_Positions = None
        if(self.log_Positions_flag):
            iter_Positions = [None] * SC.get_pos_list_length()
        if(SC.get_pos_list_length() == 0):
            raise ValueError("Position list is empty")     
        iteration = script_Args[2]
        #Reset position
        SC.go_to_position(SC.Pos_List[0][0])
        for pos_idx in range(SC.get_pos_list_length()):
            current_Position = SC.get_pos(pos_idx)
            pos_lbl = current_Position[0]
            pos_coords = current_Position[1]
            if printLog:
                logmsg(f"Moving to position {pos_idx+1}/{SC.get_pos_list_length()}",True)
            if(SC.check_encoder() == False):
                time.sleep(1.0)
                SC.restore_to_z(pos_coords[2])
                time.sleep(1.0)
                SC.focus_loss_counter += 1
            (curx,cury,curz) = SC.get_current_position()
            if(SC.get_pos_list_length() > 1 or (abs(curx-pos_coords[0]) < 3 and abs(cury-pos_coords[1]) < 3 and abs(curz-pos_coords[2]) < 1)):
                SC.go_to_position(pos_coords)
            time.sleep(1.0)
            #Make sure our initial position is as close as possible to original position
            if(iteration == 0):       
                z_dif = SC.get_focus() - pos_coords[2]
                print(f"Missed with: {z_dif}")
                if(abs(z_dif) > 1.5):
                    SC.move_Focus(z_dif)
                    print("Attempting to compensate")
                time.sleep(2.5)
            else:
                if(AFMan is not None and AFMan.AFOn):
                #Apply previous correction if it is large enough.
                    prev_cor = AFMan.corrections[iteration-1,pos_idx]
                    if(prev_cor > 3 and ADAPTIVE_POSITIONING == True):
                        SC.move_focus(prev_cor/3)
                        print(f"Applying old correction/3: {prev_cor/3}")
                        SC.Pos_List[pos_idx][0][2] += prev_cor/3
                    for i in range(AUTOFOCUS_ROUNDS):      
                        print(f"Entering autofocus step {i+1}")
                        z_dif = 0
                        try:
                            z_dif = AFMan.perform_Autofocus(IPRH,iteration, pos_idx, True)
                        except Exception as e:
                            logmsg(f"Autofocus failed: {e}. Switching off autofocus", True)
                            z_dif = 0
                            AFMan.AFOn = False
                        if(abs(z_dif) < 20):
                            SC.move_focus(z_dif)   
                            #Apply correction for next round
                            SC.offset_z(pos_idx,z_dif)
                        else:
                            z_dif = z_dif/3
                            SC.move_focus(z_dif)
                    else:
                        time.sleep(3.0)
            try:
                time.sleep(6.5)
                iter_Positions[pos_idx] = SC.get_current_position(True)
                rc = IPRH.execute_queue(script_Args + [pos_lbl])
            except Exception as e:
                logmsg(f"Unkown exception occured while trying to run position script, {e}",True)
            else:
                print(f"Position script completed with return code: {rc}") 
            if(temp_Sep > 0):
                logmsg(f"Waiting for {temp_Sep} seconds due to temporal separation")
                if(self.waiting(temp_Sep) == False):
                    return
        #Log positions
        if(self.log_Positions_flag):
            with open(output_dir + "/Movements.txt","a") as poslog:
                poslog.writelines(iter_Positions)

    def cancel_exp(self):
        """
        Cancel gracefully

        Returns
        -------
        None.

        """
        self.cancel_flag = True
              
    def waiting(self, intervall, starttime = None):
        """
        Updates the GUI while we wait for the other process to finish

        Parameters
        ----------
        intervall : int
            Time in seconds to wait.

        Returns
        -------
        None.

        """
        global gui_ptr
        if (starttime is None):
            starttime = int(round(time.time()))
        ctime = int(round(time.time()))
        while (ctime < (starttime + (intervall)) and self.cancel_flag == False):
            ctime = int(round(time.time()))
            time.sleep(1/15) #Sleep 1/15th of a second
            gui_ptr.update()
            if(self.cancel_flag == True):
                return False
        return True

    def reorder_iteration_images(self,exp_name, itr_no):
        """
        

        Parameters
        ----------
        itr_no : TYPE
            DESCRIPTION.
        lbls : TYPE
            DESCRIPTION.

        Returns
        -------
        itr_imgs : TYPE
            DESCRIPTION.

        """
        #itr_imgs = []
        lbls = self.StageCom.get_pos_lbls()
        for pos,data in enumerate(self.StageCom.Pos_List):
            pos_fp = output_dir + '\\' + self.IPam.Base_Filename.format(Exp = exp_name, lbl = lbls[pos]) + '.tif'
            #pos_coll = skimage.io.imread_collection(pos_fp,conserve_memory = True, plugin = 'tifffile')
            pos_img = skimage.io.imread(pos_fp,plugin = 'tifffile')
            itr_fp = output_dir + '\\' + self.IPam.Base_Filename.format(Exp = exp_name, lbl = lbls[pos]) + f"_T{itr_no}*.tif"
            itr_coll = skimage.io.imread_collection(itr_fp, conserve_memory = True, plugin = 'tifffile')
            pos_itr_imgs = itr_coll.concatenate()
            f_img = np.concatenate((pos_img, pos_itr_imgs), axis = 0)
            (PosX,PosY,PosZ) = data[0]
            #XPos_Tag = ["XPosition", 'I', 1, PosX]
            #YPos_Tag = ["YPosition", 'I', 1, PosY]
            tifffile.imwrite(pos_fp,f_img,imagej = True, resolution = (0.4,0.4),  metadata = {'unit': 'um',"XPosition":PosX, "YPosition":PosY})
            #Cleanup and delete files
            for fp in itr_coll.files:
                  if (os.path.isfile(fp)):
                      os.remove(fp)
                  else:
                      print(f"File at {fp} not found")
        # del f_img, pos_itr_imgs
        # return itr_imgs
       
    def save_initial_imgs(self,exp_name):
        lbls = self.StageCom.get_pos_lbls()
        startimgs = []
        for pos in range(self.StageCom.get_pos_list_length()):
            pos_fp = output_dir + '\\' + self.IPam.Base_Filename.format(Exp = exp_name, lbl = lbls[pos]) + '.tif'
            pos_img= skimage.io.imread(pos_fp,plugin = 'tifffile')
            pos_img = skimage.img_as_ubyte(pos_img)
            #First image is F0 second is Fm
            startimgs.append(pos_img[0])
        return startimgs
    
    def get_lates_images(self,Fo = False, Fm = True):
        lbls = self.StageCom.get_pos_lbls()
        Curimgs = []
        for pos in range(self.StageCom.get_pos_list_Length()):
            pos_fp = output_dir + '\\' + self.IPam.Base_Filename.format(Exp = self.E_Name, lbl = lbls[pos]) + '.tif'
            pos_img= skimage.io.imread(pos_fp,plugin = 'tifffile')
            #Last Image is Fm, second to last is Fo
            if(Fo):
                Curimgs.append(pos_img[-2])
            if(Fm):
                Curimgs.append(pos_img[-1])
        return Curimgs
        
    def select_exp_dir(self, fp):
        self.Experiment_Dir = fp
        
    def set_start_script(self, fp):
        self.IPam.load_start_script(fp)
        
    def set_pos_script(self,fp):
        self.IPam.load_acquisition_script(fp)
        
    def add_position(self, pos):
       SCM.add_pos(pos)
        
    def add_command(self,rep,com):
        if(len(self.commandQueue) < rep):
            total_reps = rep
            while(total_reps < rep):
                self.commandQueue.append([])
        self.commandQueue[rep].append(com)

#Remove old hanging imagingwin instance
def cleanup():
    import cv2
    import psutil
    processes = dict()
    for proc in psutil.process_iter():
        try:
            # Get process name & pid from process object.
            processName = proc.name()
            processID = proc.pid
            processes[processName] = processID
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    if('ImagingWin.exe' in processes.keys()):
        os.kill(processes['ImagingWin.exe'],9)
    cv2.destroyAllWindows() 


msgbuffer = []
def logmsg(msg, toFile = False, toGUI = True):
    """
    Logs message to GUI and text file

    Parameters
    ----------
    msg : string
        Message to log.
    toFile : boolean, optional
        Whether to write to log file or only to window console. The default is False.
    toGUI : TYPE, optional
        Whether to write to window console. The default is True.

    Returns
    -------
    None.

    """
    global msgbuffer, output_dir, experiment    
    if(toGUI):
        pacmangui.top.log_lbl.configure(text = f"Log: {msg}")
    T = datetime.now().strftime("%d/%m (%H:%M:%S)")
    frmstr = f"T:{T}: {msg}"
    if(toFile):
        msgbuffer.append(frmstr)
    print(frmstr)
    if(len(msgbuffer) > 10 or "Experiment Finished" in msg or "Experiment cancelled" in msg):
        fp = output_dir
        with open(fp + "\\" + f"{experiment}_log.txt", mode='a') as file_object:
            for msgiter in msgbuffer:
                file_object.write('%s\n' % msgiter)   
        msgbuffer.clear()

def get_file_path():
    return output_dir
    
if __name__ == '__main__':
    pacmangui.start()
    print("Exited")