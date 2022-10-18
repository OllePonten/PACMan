# -*- coding: utf-8 -*-
"""
Created on Wed Jan 27 11:39:33 2021
Handles communication with Prior PROScan III. To run as dummy, switch debug to on.
Made to connecto to a Prior ProSCAN III equipped with a H101A motorized stage.
Z position information is given by a Heidenhain MT1281 linear encoder.
Z movement is performed by a PS3H122R stepper motor focus drive
Made by Olle Pontén, Uppsala University for Behrendt Lab
"""


import time
import PacMan
import serial
import sys
import re


global ser,COMPORT, resolution
resolution = 0.1


class SC:    
    
    Pos_List = []
    def __init__(self,COMPORT = 'COM1',debug=False):
        self.DEBUG=debug
        self.split_symbol = '\r'
        PacMan.logmsg("Trying to connect to Stage",True,False)
        global ser
        ser = self.prior_init(COMPORT)
        print(f"Serial connection to Prior initialized over Com: {COMPORT}.")
    
    def prior_init(self,PORT):
        """
        Initialize the connection and set some baseline parameters.

        Parameters
        ----------
        PORT : int
            What COM-port to listen on.

        Returns
        -------
        ser : serial_connection handle

        """
        if(self.DEBUG):
            return
        global resolution
        self.focus_loss_counter = 0
        try:
            global ser
            try:
                ser.close()
            except Exception:
                pass
            ser = serial.Serial(PORT, baudrate = 9600, timeout=0.5)
            time.sleep(1)       # Let it start
            ser.flushInput()    # Flush inp
            ser.flushOutput()   # Flush outp   
            time.sleep(1)       # Let it start          
        except Exception as e:
                print(e)
                print('No serial connection to prior')
                sys.exit()
        try:
            self.init_encoder()
            #Set stage speed to 50 (down from 100)
            self.prior_command('SMS, 50')
            #Set stage acceleration to 50 (down from 100)
            self.prior_command('SAS, 50')
            
            #Set Z speed and acceleration to 30 (down from 100)
            self.prior_command('SMZ, 30')
            self.prior_command('SAZ, 30')     
            #Set Z speed and acceleration to 50 (down from 100)
            #self.prior_command('SMZ, 50')
            #self.prior_command('SAZ, 30')     
            #self.prior_command('UPR, 500')
            #self.prior_command('RES,Z,' + str(resolution))         
            #Turn on backlashes and servo
            #self.prior_command('BLZH, 1')
            #self.prior_command('BLSH, 1')
            #self.prior_command('SERVO, 1')
            #self.prior_command('ENCW, Z, 10')
            self.msg_resp('P')
        except Exception as e:
            print(e)
        return ser

    def prior_command(self,msg, flush = False):
        """
        Sends a serial command. The message needs to be formatted according to relevant Prior serial command syntax.

        Parameters
        ----------
        msg : string
            Serial message (in string format) to be sent to Prior hardware.
        flush : boolean, optional
            Whether to flush the output channel. The default is False.

        Returns
        -------
        None.

        """
        global ser
        if(self.DEBUG):
            return 
        com = msg.encode()+b'\r'
        ser.write(com)
        time.sleep(0.2)
        if(flush):
            ser.flushOutput()
        
    def get_resp(self,size = 256):
        """
        Listen for response on the serial connection to the Prior hardware. 
        Trailing empty character removed and if multiple response are waiting they are split by \r.

        Parameters
        ----------
        size : int, optional
            Maximum accepted size of message (in # of characters). The default is 256.

        Returns
        -------
        string
            Response if response is given. 

        """
        if(self.DEBUG):
            return
        response = ser.read(size).decode('utf-8')
        response = response.split(self.split_symbol)
        ser.flushOutput()
        #Last is always an empty character
        return response[:-1]
    
    def msg_resp(self,msg):
        if(self.DEBUG):
            return
        """
        Sends the command in msg and waits for a response which is then returned.
        Response time dependent on timeout parameter.
    
        Parameters
        ----------
        msg : String
            Serial message (in string format) to be sent to Prior hardware.
    
        Returns
        -------
        get_resp : string
            String formatted response to *msg* command.
    
        """
        self.prior_command(msg, True)
        time.sleep(0.1)
        ret = self.get_resp() 
        try:
            ret.remove('R')
        except:
            pass
        return ret
        
    def retrieve_pos_list(self):
        """
        Return all positions marked as a string. Formatted according to: "X: {pos[0]} Y: {pos[1]} Z: {pos[2]} "

        Returns
        -------
        outstr : str
            String containing all positions.

        """
        outstr = []
        if(len(self.Pos_List) < 0):
            self.load_pos_list_file()
        for pos in self.Pos_List:
            outstr.append(f"{pos}")
            #print(f)
        return outstr
    
    def restore_to_z(self,z_pos):
        """
        Attempts to reenable encoder and move to given z position 

        Parameters
        ----------
        z_pos : float
            z-position to restore to.

        Returns
        -------
        None.

        """
        global resolution
        cur_P = self.msg_resp('P,e')[-1].split(",")
        time.sleep(0.5)
        cur_Ze = float(cur_P[2])*resolution
        PacMan.logmsg(f"Encoder position dropped. Missmatch: {abs(cur_Ze-z_pos)}",True)
        self.init_encoder()
        time.sleep(0.5)
        self.set_Focus(cur_Ze)
        time.sleep(0.5)
        self.go_to_z(z_pos)
            
                
    def get_pos_lbls(self):
        """
        Return the names given to all marked positions

        Returns
        -------
        pos_lbls : array
            All position labels.

        """
        pos_lbls = []
        for pos in self.Pos_List:
            pos_lbls.append(pos[1])
        return pos_lbls
            
    def add_pos(self, pos):
        """
        Add position
        Parameters
        ----------
        x : int
        Returns
        -------
        None.
        """
        global resolution
        if(isinstance(pos,str)):
            cur = self.get_current_position(True).split(",")
            fl = [float(i) for i in cur]
            fl[2] = round(fl[2]*resolution,2)
            pos = [fl[:],pos]   
        elif(isinstance(pos,list)):
            label = pos[0]          
            x = int(pos[1])
            y = int(pos[2])
            z = float(pos[3])
            if(label in self.Pos_List[:][1]):
                raise ValueError("Duplicate position names not allowed.")
            if(isinstance(x,(int,float)) and isinstance(y,(int,float)) and isinstance(z,float) and isinstance(label,str)):
                pos = [[x,y,z],label]
                #self.Pos_List.append(([x,y,z],label))
            else:
                raise ValueError(f"A position value is not of appropriate type: {type(x)}, {type(y)}, {type(z)} or {type(label)}")
        print(f"Added{pos}")
        self.Pos_List.append(pos)
        
    
    def get_focus(self):
        """
        Return current focus position as given by encoder.

        Returns
        -------
        focus, float
            Focus position rounded to closest 0.01 of units used by Prior hardware (normally microns).

        """
        resp = self.msg_resp('PZ')
        try:
            resp.remove('R')
        except:
            pass
        Z = 0.0
        Z = int(resp[0]) * resolution
        return round(Z,3)
     
    def set_focus(self,Z):
        """
        Sets the current focus position

        Parameters
        ----------
        Z : float
            New focus position.

        Returns
        -------
        None.

        """
        global resolution
        target = Z/resolution
        self.msg_resp('PZ,'+str(target))   
     
        
    def go_to_z(self,abs_z):
        """
        Attempt to move straight to a given z position.
        WARNING: THIS CAN ATTEMPT A MOVE THROUGH SOLID OBJECTS.
        WARNING: THE GIVEN Z VALUE IS IN ABSOLUTE NOT RELATIVE MOVEMENT.
        For relative movement use move_focus

        Parameters
        ----------
        abs_z : float
            Focus position to move to.

        Returns
        -------
        None.

        """
        global resolution,ser
        ser.flushOutput()
        try:
            print("Going to:" + str(abs_z/resolution))
            self.prior_command('GZ,'+str(abs_z/resolution))
            time.sleep(0.25)
            ser.flushOutput()
        except Exception as e:
            print(e)
            pass
        
    def move_focus(self,rel_z):
        """
        Attempts to move rel_z units in the z direction.

        Parameters
        ----------
        rel_z : float
            Signed relative movement.

        Returns
        -------
        None.

        """
        global resolution,ser
        ser.flushOutput()
        #Position is returned in resolution step
        if(rel_z > 60):
            print(f"Too large step {rel_z}, splitting")
            rel_z = rel_z/2
            self.move_focus(rel_z)
            time.sleep(1.5)
        cur_pos = self.get_focus()
        #We assume rel_z is given as microns
        target_pos = (rel_z + cur_pos)/(resolution)
        try:
            self.prior_command('GZ,'+str(target_pos))
            time.sleep(0.25)
            ser.flush()
        except Exception as e:
            print(e)
            pass
        
    def get_current_position(self, asString = False):
        """
        Return current 3 dimensional position.

        Parameters
        ----------
        asString : boolean, optional
            Set to True to return as a string, else returns an array. The default is False.

        Returns
        -------
        pos : array/str
            Current position.

        """
        global resolution
        pos = self.msg_resp('P')
        if(asString):
            pos = pos[0]
        else:
            pos = [float(fact) for fact in pos[0].split(",")]
        return pos
    
    def get_pos(self,index, asString = False):
        """
        

        Parameters
        ----------
        index : int
            DESCRIPTION.
        asString : boolean, optional
            DESCRIPTION. The default is False.

        Returns
        -------
        list
            DESCRIPTION.

        """
        global resolution
        if(index == -1):
            index = len(self.Pos_List)-1
        pos = self.Pos_List[index]
        lbl = pos[1]
        coords = pos[0]
        if(asString):
            return str(lbl) + " " + str(coords[:])
        else:
            return [lbl, coords[:]]
    
    def clear_pos_list(self):
        """
        Remove all marked positions

        Returns
        -------
        None.

        """
        self.pos_List = []
    
    def get_pos_list_length(self):
        """
        Returns length of position list

        Returns
        -------
        int
            Number of marked positions

        """
        return len(self.Pos_List)
    
    def remove_pos(self,index):
        """
        Remove a single position from marked list

        Parameters
        ----------
        index : int
            DESCRIPTION.

        Returns
        -------
        None.

        """
        print(f"Removing {self.Pos_List[index]}")
        del self.Pos_List[index]
    
    def move_to_xy(self,position):
        try:
            if('R' not in self.msg_resp('G,'+position)):
                raise ConnectionError('Could not perform x-y move')
        except Exception as e:
            print(e)
            print("Move failed.")
        
    def add_offset(self,index,offset_string):
        #Get dimension
        try:
            dim = re.findall("([XYZ]):",offset_string)[0]
            if(dim == "X"):
                dim = 0
            elif(dim == "Y"):
                dim = 1
            elif(dim == "Z"):
                dim = 2
            else:
                print(f"Badly formatted dimension for offset: {dim}")
                raise ValueError(("Error during addition of offset"))
        except:
            #No dimension specified. Assume only a number, assume dim = Z = 2
            dim = 2
            pass    
        #Slice out the numbers.
        try:
            offset = float(re.findall("(\d+\.\d+)", offset_string)[0])
        except:
            offset = float(re.findall("(\d+)", offset_string)[0])
        if(len(self.Pos_List) >= index):
            self.Pos_List[index][0][dim] = round(self.Pos_List[index][0][dim] + offset,2)
        else:
            raise IndexError("No position with matching index")
    
    def offset_z(self,index,dZ):
        """
        

        Parameters
        ----------
        index : int
            0-indexed position identifier.
        dZ : float
            Z in microns to add.

        Returns
        -------
        None.

        """
        if(len(self.Pos_List) >= index):
            self.Pos_List[index][0][2] = round(self.Pos_List[index][0][2] + offset,2)
        else:
            raise IndexError("No position with matching index")
        
    def go_to_position(self,pos):
        #Perform XY movement before z movement
        global resolution
        #Index
        if(isinstance(pos,int)):
            self.go_to_position(self.Pos_List[pos][0])
            return
        print(pos)
        z = pos[2]/resolution
        # self.prior_command('GZ' + str(z*resolution))
        strpos = 'G,' + str(pos[0]) + ',' + str(pos[1]) + ','+ str(z)
        self.prior_command(strpos,True)
    
    def init_encoder(self,servo = False, reset_pos = False):
        if('0' in self.msg_resp('ENCODER,Z')):
            #Encoder off, try to put it on
            self.prior_command('ENCODER,Z,1')
            if('1' not in self.msg_resp('ENCODER,Z')[-1]):
                raise ConnectionError('Could not enable Z-Encoder')
            else:
                print("Encoder re-enabled")
                
    def check_encoder(self):
        resp = self.msg_resp('Encoder,Z')
        return ('1' in resp)
    
    def __del__(self):
        global ser
        try:
            ser.close()
            del(ser)
        except:
            pass
            
    def load_pos_list_file(self, fp = None):
        #Formatting pos: label,x,y,z
        if(fp == None or fp == ""):
            fp = "Pos.txt"
        try:
            with open(PacMan.IWE_fp + '\\' + str(fp), mode = 'r') as positions_list:
                for line in positions_list:
                    pos = line.split(",")
                    #Make numbers
                    pos[1] = int(float(pos[1]))
                    pos[2] = int(float(pos[2]))
                    pos[3] = float(pos[3])
                    self.add_pos(list(pos))
        except:
            print(f"Couldn't load position, likely bad filename: {fp}")
                
    def save_pos_list_file(self,fp = None):
        if(fp == None or fp == ""):
            fp = "Pos.txt"
        if(len(self.Pos_List) > 0):
            with open(PacMan.IWE_fp + '\\' + str(fp),mode = 'w') as pos_file:
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
        
    def __del__(self):
        global ser
        try:
            if(isinstance(ser,serial.Serial)):
                ser.close()
                del(ser)
        except:
            pass

def disconnect():
    global ser
    ser.close()


def calibrate(SeriIns, start = 1, fin = 10,step = 1, iterations = 10):
    """
    Tests the z-movement of the stage

    Parameters
    ----------
    SeriIns : SC handle
        Handle reaching the stage operating software.
    start : float, optional
        Starting step. The default is 1.
    fin : float, optional
        Ending step. The default is 10.
    step : float, optional
        Step size. The default is 1.
    iterations : int, optional
        How many times each step is performed. The default is 10.

    Returns
    -------
    failures : list
        All failed movements.
    moves : list
        All movements. Moves[0] is the expected movement, 
        moves[1] is the actual movement.

    """
    import matplotlib.pyplot as plt
    SeriIns.prior_command("PZ 0")
    failures = []
    fac = 1
    move = SeriIns.get_focus()
    moves = [[],[]]
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
            print(f"Actual move {round(acc,3)}")
            move = newpos
            moves[0].append([i*fac])
            moves[1].append([round(acc,3)])
            if(SeriIns.check_encoder() == False):
                failures.append([i*fac,d, abs(acc-move)])
                SeriIns.init_encoder()
    print(SeriIns.print_settings())
    print(failures)
    return failures, moves

def make_z_stack(step=1, extent = 10):
    import skimage.io, tifffile,os, numpy as np
    import SeriCom
    import IPAMRH
    IPAMC = IPAMRH.AIPam()
    SeriC = SeriCom.SC()
    IWE_fp = 'C:\ImagingPamGigE\Data_RGB'
    SeriC.msg_resp("PZ 0")
    IPAMC.send_Command("Select Image = ", "Ft")
    IPAMC.send_Command("Ft only","")
    IPAMC.send_Command("Save Tiff Image = ", "FocusImg0")
    Positions = [0]
    for fac in range(-1,2,2):       
        for i in np.arange(step,extent+step,step):
            print(f"Taking image {i*fac} ")
            foc = SeriC.get_focus()
            time.sleep(2.5)
            print(f"Position: {foc}\n")
            Positions.append(foc)          
            time.sleep(8)
            IPAMC.send_Command("Select Image = ", "Ft")
            IPAMC.send_Command("Ft only","")
            IPAMC.send_Command("Save Tiff Image = ", f"FocusImg{i*fac}")
            SeriC.go_to_z(i*fac)
            #Stabilize
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
        
            
if __name__ == '__main__':
    import matplotlib.pyplot as plt
    import SCM
    moves= []
    SeriIns = SC()
    moves[0],moves[1] = SCM.calibrate()
    plt.scatter(moves[0],moves[1])
    plt.xlabel("Planned move (um)")
    plt.ylabel("Measured move (um)")
    plt.show()
