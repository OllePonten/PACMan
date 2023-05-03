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

from dataclasses import dataclass

from utils import utils
from managers import SCM
from managers import IRHM
from managers import pacmangui as pacmangui
import tifffile
import skimage
import skimage.io
import os, time, sys
import matplotlib
matplotlib.use("Qt5Agg")
import numpy as np
import psutil

global gui_ptr

global DEBUG
DEBUG = False

from enum import Enum
class External_Components(Enum):
    StageCom = 1
    IPAM = 2
    #Lighting = 3
    #Pumps = 4
    Internal = 0

class PacMan:   
    global DEBUG
    StageCom = None
    IPam = None
    pQueue = None
    AutoFocuser = None
    log_Positions = False
    settings = dict()
    commandQueue = []
    rtCommandQueue = []
    Experiment_Dir = ""

    def __init__(self, with_gui = False):           
        try:
            self.IPam = IRHM.AIPam()
        except ConnectionError as e:
            print("Error when starting IRHM. Double check ImagingWin is running. Aborting")
            cleanup()
            sys.exit()
            
        self.settings = utils.read_ini_file("PACSettings.ini")
        if(self.settings['General']['imagingwininstalldir'] == "Default"):
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
                pid = processes['ImagingWin.exe']
                self.settings['General']['imagingwininstalldir'] = psutil.Process(pid).exe()
            utils.logmsg(f"Default install directory extracted from current exe: {self.settings['General']['imagingwininstalldir']}")
        self.output_directory = self.settings['General']['outputdir']
        try: 
            if(self.settings['General']['scmserial']):   
                self.StageCom = SCM.SC()
            else:
                self.StageCom = PycroCom.PCMCom()
        except:
            print("Cannot connect to StageManager, assuming debugging. SCM disabled.")
            DEBUG = True
            self.StageCom = 0
        self.cancel_flag = False
        self.commandQueue = []
        self.rtCommandQueue = []
        if(with_gui):
            pacmangui.start(self)
        
        
    def run_experiment(self, tk_ptr,exp_Settings):
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
        utils.logmsg(f"Started Experiment: {experiment_name}", True)
        utils.logmsg(f"Settings: Iterations: {experiment_iterations} Intervall(s): {experiment_Intervall}. Temporal separation(s): {temp_sep}. Dark adaption: {self.dark_adapt_Flag}" ,True)    
        if(self.dark_adapt_Flag):
            self.IPam.send_command('ML','Off')
            utils.logmsg("Dark adapting for 30 minutes")
            self.waiting(1800)
        utils.logmsg(self.StageCom.retrieve_pos_list(),True)
        for i,iteration in enumerate(self.commandQueue):
            if(len(iteration)>0):
                print(f"Scheduled commands to run at iteration {i}")
                for com in iteration:
                    print(com)
        self.IPam.send_command('ML','On')
        if(not self.cancel_flag):
            self.execute_acquisition(script_Args = [True, experiment_name,0,temp_sep])
        #Compute initial setup.
        if(self.AF):
            self.AutoFocuser.compute_initial_setup(self.save_initial_imgs(experiment_name),True)
        utils.logmsg("Starting up first wait intervall after initial imgs.")
        self.IPam.send_command('ML','Off')
        self.waiting(intervall = experiment_Intervall)
        for Current_Iteration in range(experiment_iterations): 
            utils.logmsg(f"Running repetition number: {Current_Iteration+1}/{experiment_iterations}", True)
            if(not self.cancel_flag):
                if(len(self.commandQueue[Current_Iteration])>0):
                    for com in self.commandQueue[Current_Iteration]:
                        self.apply_command(com)
                self.IPam.send_command('ML','On')
                self.waiting(5)
                self.IPam.send_command("New Record","")
                self.execute_acquisition(script_Args = [False,experiment_name,Current_Iteration,temp_sep])
                utils.logmsg(f"Successfully completed acquisiton, now waiting for {experiment_Intervall} s", True)
                self.reorder_iteration_images(experiment_name, Current_Iteration)
                starttime = int(round(time.time()))
                #Update progress bar
                progress = round((float(Current_Iteration)/float(experiment_iterations))*100,2)
                tk_ptr.Exp_Progress['value'] = progress
                #Wait until we are done, keeping the GUI active
                self.IPam.send_command('ML','Off')
                self.waiting(intervall = experiment_Intervall, starttime = starttime)
            else:
                #Handle cancellation
                utils.logmsg("Experiment cancelled",True)
                self.IPam.send_command('ML','Off')
                #self.StageCom.clear_pos_list()
                self.commandQueue.clear()
                tk_ptr.cancel_exp()
                break
        utils.logmsg("Experiment complete",True)

    def execute_acquisition(self, script_Args, printLog = True):
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
        output_dir = self.output_directory
        IPRH = self.IPam
        SC = self.StageCom
        iter_Positions = None
        temp_sep=script_Args[3]
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
                utils.logmsg(f"Moving to position {pos_idx+1}/{SC.get_pos_list_length()}",True)
            (curx,cury,curz) = SC.get_current_position()
            SC.go_to_position(pos_coords)
            time.sleep(1.0)
            try:
                time.sleep(6.5)
                iter_Positions[pos_idx] = SC.get_current_position(True)
                rc = IPRH.execute_queue(script_Args + [pos_lbl])
            except Exception as e:
                utils.logmsg(f"Unkown exception occured while trying to run position script, {e}",True)
            else:
                print(f"Position script completed with return code: {rc}") 
            if(temp_sep > 0):
                utils.logmsg(f"Waiting for {temp_sep} seconds due to temporal separation")
                if(self.waiting(temp_sep) == False):
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
        remcoms = []
        while (ctime < (starttime + (intervall)) and self.cancel_flag == False):
            ctime = int(round(time.time()))
            time.sleep(1/20) #Sleep 1/25th of a second
            gui_ptr.update()
            #Inefficient lol
            for com in self.rtCommandQueue:
                if(com.Trigger*60+starttime>ctime):
                    self.apply_command(com)
                    self.remcom.append(com)
            [self.rtCommandQueue.remove(remcom) for remcom in remcoms]
            if(self.cancel_flag == True):
                return False
        return True
    
    def apply_command(self,com):
        utils.logmsg(f"Executing command {com.com} with parameter {com.parameter}",True)
        if(com.Target == External_Components.Internal and com.command == "TempSep"):
            utils.logmsg(f"Changing temporal separation to: {com.parameter} seconds",True)
            temp_sep = int(com[1])
        if(com.Target == External_Components.Internal and com.command == "IterSep"): 
            utils.logmsg(f"Changing iteration wait time to: {com.parameter} seconds",True)
            experiment_Intervall = int(com.parameter)
        if(com.Target == External_Components.IPAM):
            utils.logmsg(f"Sending IPAM command: {com.command} with parameter {com.paramater}",True)
            print(self.IPam.send_command(com.command, com.parameter))
        if(com.Target == External_Components.StageCom):
            utils.logmsg(f"Sending Stage command: {com.command} with parameter {com.paramater}",True)
            self.SCM.msg_resp(','.join(com.command,com.parameter))
                    
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
        output_dir = self.output_directory
        lbls = self.StageCom.get_pos_lbls()
        for pos,data in enumerate(self.StageCom.Pos_List):
            pos_fp = self.settings['General']['imagingwininstalldir'] + '\\Data_RGB\\' + self.IPam.Base_Filename.format(Exp = exp_name, lbl = lbls[pos]) + '.tif'
            #pos_coll = skimage.io.imread_collection(pos_fp,conserve_memory = True, plugin = 'tifffile')
            pos_img = skimage.io.imread(pos_fp,plugin = 'tifffile')
            itr_fp = self.settings['General']['imagingwininstalldir'] + '\\Data_RGB\\' + self.IPam.Base_Filename.format(Exp = exp_name, lbl = lbls[pos]) + f"_T{itr_no}*.tif"
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
        output_dir = self.output_directory 
        for pos in range(self.StageCom.get_pos_list_length()):
            pos_fp = output_dir + '\\' + self.IPam.Base_Filename.format(Exp = exp_name, lbl = lbls[pos]) + '.tif'
            pos_img= skimage.io.imread(pos_fp,plugin = 'tifffile')
            pos_img = skimage.img_as_ubyte(pos_img)
            #First image is F0 second is Fm
            startimgs.append(pos_img[0])
        return startimgs
    
    def get_lates_images(self,Fo = False, Fm = True):
        lbls = self.StageCom.get_pos_lbls()
        output_dir = self.output_directory 
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
        
    def queue_command(self,command_string):
        command_string = command_string.replace(' ','')        
        command = command_string.split(',')
        if("R" in command[1]):
            Realtime=True
        elif("I" in command[1]):
            Realtime=False
            rep = int(command[1])
            if(len(self.commandQueue) < rep):
                total_reps = rep
                while(total_reps < rep):
                    self.commandQueue.append([])
        else:
            Realtime=False
            utils.logmsg("No R/I parameter given. Assuming iterations.")
            if(len(command) == 4):
                command.insert("I",1)
        
        #Assumes formatting of: Target,T/I,trigger,command,optional parameter


        if(len(command)<5 or len(command)>6):
            raise ValueError(f"Improperly formatted command: {command}. Kindly format according to: Queue: target, R/I, Trigger,Command,Parameter")
        target = None
        #Have we a defined external component to direct this command to?
        if(command[0] in [c.name for c in External_Components]):
            target = External_Components[command[0]]
        elif(command[0] == "TempSep" or command[0] == "IterSep"):
            target = External_Components.Internal            
        else:
            raise ValueError(f"No appropriate target for command: {command_string}")
            
        #Place in RT queue if RT.
        if(Realtime):
            self.rtCommandQueue.append(QueuedCommand(target=target,Trigger=command[2],command=command[3]),parameter=command[4])
        else:
            self.commandQueue[rep].append(QueuedCommand(target = target,Trigger = command[2], command = command[3], parameter=command[4]))

@dataclass
class QueuedCommand:
    target: External_Components
    command: str
    parameter: str
    Trigger: int

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

if __name__ == '__main__':
    PCM = PacMan(True)
    #pacmangui.start(PCM)
    print("Exited")
