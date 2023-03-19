# PACMan
An chlorophyll-a fluorometry automation software designed for Walz (GMBH) Microscopy IPAM.

Confirmed to be compliant with V 2.51d of Imaging-Win
Confirmed to be compliant with PRIOR ProScan III controller

PACKAGE REQUIREMENTS:

pyserial
opencv
comtypes
ctypes
numpy
matplotlib
skimage
tkinter/ttk

# REQUIREMENTS
- ImagingWin v2.51 (see Installing ImagingWin)
- Python 3.9
- Pip
- Windows 7/8/10


# Installation of ImagingWin 2.51
- Windows 10:
The remote control functionality is only enabled in specifically the v 2.51 exe version of the ImagingWin program. 
Due to this and ImagingWin supporting Windows 10 only on version >=2.56 the following steps must be taken to allow for remote control on Windows 10 systems: Install ImagingWin =2.56 as usual from Walz IMAGING-PAM download site (https://www.walz.com/products/chl_p700/imaging-pam_ms/downloads.html). After installation: Make copy of the ImagingWin.exe file located in the installation folder. Overwrite the ImagingWin.exe in the installation folder with the v 2.51 exe provided with PACMan. 

# Installation and use of PACMan
- Install correct version of ImagingWin as above
- Install with pip: pip install IPAM-PACMan

In your python IDE of choice:
- import pacman
- PacMan_instance = pacman.PacMan()
This starts PacMan with the GUI turned on, in standard mode.
To start PacMan in CLI mode:
- PacMan_instance = pacman.PacMan(False)

To start PacMan in Debug mode:
- PacMan_instance = pacman.PacMan(True/False,True)

To change PACsettings write pacman.open_settings()

# Version history

v 1.0rc 19/03/2023
- Release Candidate
- Test installation performed
- Bug fixes

v 0.9.7 27/02/2023
- Technical Debt
	- Cleaning upp and testing installation file structure
	- Bug fixes
- Features
	- Added PACSettings.ini: A settings file to tell PACMan what features to use, pointing it to the local ImagingWin installation, default output dir etc.

v 0.9.5 25/01/2023
- Technical debt
	- Moved paths to ensure functionality after installation
- GUI fixes
	- Changed name of buttons to reflect functionality
- Documentation
	- Added error messages when PACMan cannot connect to stage

v 0.9.3 22/09/2022
- Created package 

v 0.4.3 06/03/2022
- Started adding documentation for upload
- Cleaned up the github repository

v 0.4.2 06/12/2021
- About page added
- Cleaned up code slightly

v 0.4 15/11/2021
-Platform independent setup created
-Execute acquistion moved into main class
-Boilerplate code for stage communicator added

v 0.4 17/08/21
- Position list saving added into main
- Command queuing added
- More options for autofocus added
- Autofocus rescaled

v 0.3 3/07/2021
- Direct serial communication added
- Position list saving added (debug mode)

v 0.2.5 06/2022
- Tabs added to GUI. Main/Autofocus/position
- Position list added

v 0.2 05/2022
Autofocus implemented

v 0.1 04/2022
Basic functionality

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
