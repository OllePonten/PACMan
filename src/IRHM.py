# -*- coding: utf-8 -*-
"""
Created on Sun Dec 27 13:59:47 2020
Class that handles interaction with ImagingWin software, v 2.51 and above.
@author: Olle Pontén
"""
#CLSID: {69072C2D-6ED1-4051-BF8D-70286A303CDD}
#IID: {E07C24C7-56CE-409F-AB60-DC7EDE9D9888}
#Co-class UUID: {A012D9CB-1CB1-444E-A63E-C79F069B8BC1}
#Co-class: CLSDID: {69072C2D-6ED1-4051-BF8D-70286A303CDD}
#C:\Users\Olle\anaconda3\Lib\site-packages\win32com\client\combrowse.py for com browser
#runfile('C:/Users/Olle/anaconda3/Lib/site-packages/win32com/client/combrowse.py', wdir='C:/Users/Olle/anaconda3/Lib/site-packages/win32com/client')
#AIPam = win32com.client.Dispatch("ImagingWin.AutoIPam")
#AIPAM = win32com.client.Dispatch("{69072C2D-6ED1-4051-BF8D-70286A303CDD}")
# def getShell():
#     thelist = []
#     def findit(hwnd,ctx):
#         if win32gui.GetWindowText(hwnd) == "ImagingWin v2.51d": # check the title
#             thelist.append(hwnd)

#     win32gui.EnumWindows(findit,None)
#     return thelist

#Switch to pythoncom with ctypes:

from comtypes import client as ctClient 
import comtypes
import ctypes
import collections
import psutil

DEBUG = False

#CommandList = np.ndarray(1,2)
Command = collections.namedtuple('Command', ['cmd','param'])

File_Specified_Commands = ["Export to Tiff File = ", "Save PIM File = ", "Save Tiff Image = ", "Save Jpeg Image = "] 
Base_Filename = ''
Pos_Filename = ''

class AIPam:    
        Start_Command_Queue = []
        Command_Queue = []
        Attributes = {'Act. Light': 0, 'Meas. Light': 0, 'Sat. Light': 0, 'Clock Time': 0, 'Clock Mode': 0, 'ML': False, 'AL': False, 
                      'Ext': False, 'Gain': 0, 'Damping': 0, 'Act. Width': 0, 'Sat. Width': 0, 'Meas. Width': 0, 'Meas. Freq': 1 }
        def __init__(self, dyn = False):
            self.Command_Queue = []
            processes = dict()
            for proc in psutil.process_iter():
                try:
                    # Get process name & pid from process object.
                    processName = proc.name()
                    processID = proc.pid
                    processes[processName] = processID
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
            if('ImagingWin.exe' not in processes.keys()):
                raise ConnectionError("ImagingWing not started.")
            try:
                self.AutoIPam = ctClient.CreateObject("ImagingWin.AutoIPam", dynamic = dyn)     
                print("IPAM Connection initialized")
                self.silence( True)
            except OSError as err:
                print("Variable error {0}:".format(err))      
            except TypeError as err:
                print(f"Failed with starting with dynamic set to {dyn}. Trying with dynamic: {not dyn}")
                self.AutoIPam = ctClient.CreateObject("ImagingWin.AutoIPam", dynamic = not dyn)     

                
                
        def initialize_connection(self, dyn = False):
            try:
                self.AutoIPam = ctClient.CreateObject("ImagingWin.AutoIPam", dynamic = dyn)               
                print("Connection initialized")
                self.silence( True)
            except OSError as err:
                print("Variable error {0}:".format(err))
                 #Error catching code here
                 
        def silence(self, is_active):
            """ suppress all message boxes / dialogs from ImagingWin software """
            try:
                if is_active:
                    self.AutoIPam.sendCmd(ctypes.pointer(comtypes.BSTR("Ö")), "") # deactivate dialogs
                else:
                    self.AutoIPam.sendCmd(ctypes.pointer(comtypes.BSTR("ß")), "") # activate dialogs
            except Exception as e:
                print(f"Failed to send command: {e}")
                pass
        
        def send_command(self, cmd, param, Debug = False):
            """Sends a command to the ImagingWIN software
            Arguments:
                - cmd - Command string corresponding to ImaginWIN script command 
                - param - Any extra parameter to send with the command
            Equiavalent to IPam.scriptCmd(cmd, param) in the pascal script
            """
            if Debug:
                cmd = ctypes.c_wchar_p(cmd)
                param = ctypes.c_wchar_p(param)       
            return self.AutoIPam.scriptCmd(cmd,param)
            
        def send_core_command(self, s,r):
            #
            s = ctypes.pointer(comtypes.BSTR(s))
            r = ctypes.pointer(comtypes.BSTR(r))
            return self.AutoIPam.scriptCmd(s,r)
        
        def add_command_to_queue(self,cmd,param):
            """Adds a command to the command queue for later execution
            Arguments:
                - cmd - Command string corresponding to ImaginWIN script command 
                - param - Any extra parameter to send with the command
            """
            self.Command_Queue.append(Command(cmd,param))
            #NOTE: Format for = commands is 
            #cmd: 'command ='
            #param: '=param'
            
        def execute_queue(self, q_Args):
            """Execute the current command queue
            """
            if q_Args is None:
                self.send_command(self,"FvFm","")
            if q_Args[0]:
                queue = self.Start_Command_Queue
            else:
                queue = self.Command_Queue
            if(len(queue) == 0):
                raise  ValueError("Command queue is empty")
            for Com in queue:
                if(Com.cmd in str(File_Specified_Commands)):
                    Com = Com._replace(param = Com.param.format(Exp = q_Args[1],time = q_Args[2], lbl = q_Args[3]))
                    #Formats the filename correctly
                ret = self.send_command(Com.cmd,Com.param)
                if(ret != 0):
                    raise Exception(f"Command {Com.cmd},{Com.param} sent to COM object returned {ret}")
            return 0

        
        def print_queue(self,strout = False):
            """Prints the current command queue. 
            Arguments:
                - strout - If set to true the output is also returned as a list of strings.
            """
            ret = []
            for Comidx, Com in enumerate(self.Command_Queue):
                printstr = f"Command {Comidx}: {Com.cmd} {Com.param}"
                print(printstr)
                if(strout):
                    ret.append(printstr)
            if(strout):
                return ret
            
        def load_acquisition_script(self, fn = 'PerPosScript.txt'):
            self.Command_Queue.clear()
            with open(fn) as script_file:
                for line in script_file:
                    read_cmd = line.split(",")
                    #If the parameter specified is a file name, we format this file name
                    #so that we get correct filenames that correspond to our repitition
                    self.add_command_to_queue(read_cmd[0], read_cmd[1].rstrip())
                    if(read_cmd[0] in str(File_Specified_Commands)):
                        self.Pos_Filename = read_cmd[1].rstrip()
                        
        def clear_queues(self):
            self.Command_Queue.clear()
            self.Start_Command_Queue.clear()
            
        def load_start_script(self, fn = 'StartPosScript.txt'):
            self.Start_Command_Queue.clear()
            with open(fn) as script_file:
                for line in script_file:
                    read_cmd = line.split(",")
                    self.Start_Command_Queue.append(Command(read_cmd[0], read_cmd[1].rstrip()))
                    if(read_cmd[0] in str(File_Specified_Commands)):
                        self.Base_Filename = read_cmd[1].rstrip()

            
#wrapped = win32com.server.util.wrap(StatusServerClass)
#flags = pythoncom.REGCLS_MULTIPLEUSE|pythoncom.REGCLS_SUSPENDED
#handle = pythoncom.RegisterActiveObject(wrapped, StatusServerClass._reg_clsid_,flags)
if __name__ == '__main__':
    IPRH = AIPam()