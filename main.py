# -*- coding: utf-8 -*-
"""
Created on Wed Jan 25 11:00:56 2023

@author: ollep
"""

import sys
import os
path = os.getcwd()+"\\src"
sys.path.append(path)
#entry point for PacMan
import PacMan
#Clean up path

#Create instance
instance = PacMan.PacMan(True)
sys.path.pop()
