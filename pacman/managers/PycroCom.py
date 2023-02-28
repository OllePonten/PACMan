# -*- coding: utf-8 -*-
"""
Created on Wed Jan 27 11:39:33 2021
Handles communication with MicroManager. Requires Micromanager 2.0 or higher with ZMQ server 
switched on.
@author: Natchos
"""


import sys
from pycromanager import Acquisition, Bridge, multi_d_acquisition_events

class PCMCom:
    
    def __init__(self):
        #Pacman.logmsg("Trying to connect to Micro-Manager",True)
        try:
            self.bridge = Bridge()   
        except TimeoutError:
            print("Could not connect to micro-manager. Timeout error")
            sys.exit()
        self.mm = self.bridge.get_studio()        
        self.MMPos_List = []
        print("Connecto to Micro-Manager")
         
    def reinit(self):
        self.bridge = Bridge()
        self.mm = self.bridge.get_studio()
        
    def retrieve_Pos_List(self):
        pm = self.mm.positions()
        pos_list = pm.get_position_list()
        self.MMPos_List = pos_list
        for idx in range(pos_list.get_number_of_positions()):
            pos = pos_list.get_position(idx)
            print(pos.get_label())
            for ipos in range (pos.size()):
                stage_pos = pos.get(ipos)
                print(stage_pos.get_stage_device_label())
                print("x: ", stage_pos.x, ", y: ", stage_pos.y)
    
    def get_Pos_List_Length(self):
        return self.mm.positions().get_position_list().get_number_of_positions()
    
    def get_current_Position(self, asString = False):
        return self.bridge.get_core().get_position()
    
    def get_List_Handle(self):
        return self.mm.positions().get_position_list()
                
    def go_To_Position(self, idx):
        if(idx < 0 or idx > self.MMPos_List.get_number_of_positions() or not isinstance(idx,int)):
            raise ValueError("Selected index out of list size.")
        self.retrieve_Pos_List()
        pos = self.MMPos_List.get_position(idx)        
        pos.go_to_position(pos,self.bridge.get_core())
        
           
    def get_pos_lbls(self):
        pos_lbls = []
        for pos_idx in range(self.MMPos_List.get_number_of_positions()):
            pos = self.MMPos_List.get_position(pos_idx)
            pos_lbls.append(pos.get_label())
        return pos_lbls
    
    def move_focus(self, dZ):
        self.bridge.get_core().set_relative_position(dZ)
    