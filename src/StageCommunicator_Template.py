
# -*- coding: utf-8 -*-
"""
Created on Wed Nov 10 11:39:33 2021
Boilerplate code for implementing a generic stage communicator.
Handles communication with {xx}.
Requires {y}
Required to implement following functions with specs:
    get_Pos_List_Length() - Return the number of positions saved
    go_to_position() - Should take a list of 3 numbers as x-y-z coordinates and move the stage to specified position.
    get_Position() - Return position as a list with get_Position()[0] referring to a x-y-z coordinate and get_Position()[1] referring to a string label
    get_current_Position() - Return the current stage position in the [x,y,z] format
    
    
@author: Olle
"""


import time
from ..PacMan import PacMan
import serial
import sys


global ser,COMPORT, resolution
resolution = 0.1


class SC:    
    Pos_List = []
    def __init__(self):
        return None    
        
    
   
    
    def __del__(self):
        global ser
        try:
            if(isinstance(ser,serial.Serial)):
                ser.close()
                del(ser)
        except:
            pass
            
    def load_pos_list_file(self):
        #Formatting pos: label,x,y,z
        fp = "Pos.txt"
        with open(fp, mode = 'r') as positions_list:
            for line in positions_list:
                pos = line.split(",")
                #Make numbers
                pos[1] = int(float(pos[1]))
                pos[2] = int(float(pos[2]))
                pos[3] = float(pos[3])
                self.add_pos(list(pos))
                
    def save_pos_list_file(self):
        fp = "Pos.txt"
        if(len(self.Pos_List) > 0):
            with open(fp,mode = 'w') as pos_file:
                for pos in self.Pos_List:
                    strcoords =  [str(coord) for coord in pos[0]]
                    outstr = str(pos[1]) + "," + ",".join(strcoords) + "\n"
                    print(outstr)
                    pos_file.write(outstr)
                
    def print_settings(self):
        settings = ["Settings"]
        settings.append("ResZ " + self.msg_resp('RES,Z')[0])
        settings.append("Encoder status " + self.msg_resp('ENCODER,Z')[0])
        settings.append("Z acceleration" + self.msg_resp('SAZ')[0])
        settings.append("Z max speed" + self.msg_resp('SMZ')[0])
        settings.append("Backlash for focus " + self.msg_resp('BLZH')[0])
        print(settings)

def disconnect():
    global ser
    ser.close()

if __name__ == '__main__':
    SeriIns = SC()
    
    
def calibrate(SeriIns, start = 1, fin = 10,step = 1, iterations = 10):
    failures = []
    fac = 1
    move = SeriIns.get_focus()
    moves = []
    for i in range(start,fin,step):
        for d in range(iterations):
            if(d%2==0):
                fac = 1
            else:
                fac = -1
            print(f"Moving {i*fac}")
            SeriIns.move_focus(i*fac)
            time.sleep(1)            
            newpos = SeriIns.get_focus()
            acc = newpos - move
            print(f"Actual move {acc}")
            move = newpos
            moves.append([i*fac,acc])
            if(SeriIns.check_encoder() == False):
                failures.append([i*fac,d, abs(acc-move)])
                SeriIns.init_encoder()
    print(SeriIns.print_settings())
    print(failures)
    return failures