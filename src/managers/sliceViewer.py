 # -*- coding: utf-8 -*-
"""
Created on Wed Mar 17 17:22:13 2021
Shows the latest iterations images as slices.
@author: Olle
"""

import matplotlib.pyplot as plt

class sliceViewer:
    
    def __init__(self, Images, pos_lbls, itr_no, axs):
        """
        Parameters
        ----------
        Images : Numpy Array
            Images of the same size which are to be viewed in a scrollable stack.

        Returns
        -------
        None.

        """
        self.axs = axs 
        self.Imgs = Images
        self.pos_lbls = pos_lbls
        rows, cols, self.slices = Images.shape
        self.ind = 0
        self.slices = self.slices//2
        self.axs[0].set_title(f"Images of iteration nr: {itr_no}")

        self.imFm = self.axs[0].imshow(self.Imgs[self.ind, :, :])
        self.imFo = self.axs[1].imshow(self.Imgs[self.ind+1, :, :])
        self.update()

    def update(self):
        self.imFm.set_data(self.Imgs[self.ind, :, : ])
        self.imFo.set_data(self.Imgs[self.ind, :, : ])
        self.axs[0].set_ylabel('slice %s: Fm' % self.pos_lbls[self.ind])
        self.axs[1].set_ylabel('slice %s: F0' % self.pos_lbls[self.ind])
        self.imFm.axes.figure.canvas.draw()
        self.imFo.axes.figure.canvas.draw()

        
    def on_scroll(self, event):
        if event.key == 'left':
            self.ind = (self.ind - 2) % self.slices
        if event.key == 'right':
            self.ind = (self.ind + 2) % self.slices
        self.update()