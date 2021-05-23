# based on https://matplotlib.org/stable/gallery/user_interfaces/embedding_in_wx2_sgskip.html

from matplotlib.backends.backend_wxagg import (
    FigureCanvasWxAgg as FigureCanvas,
    NavigationToolbar2WxAgg as NavigationToolbar)
from matplotlib.figure import Figure
from matplotlib.ticker import AutoMinorLocator

import wx
import pandas as pd

import numpy as np

class PlotFrame(wx.Frame):
    def __init__(self, df, title, parent=None):
        wx.Frame.__init__(self, parent=parent, title=title, size=(800, 600))

        # make sure to display all columns
        pd.set_option("display.max.columns", None)

        self.axes = df.plot(
                style='-o',
                subplots = True,
                grid = True
                )
        self.figure = self.axes[0].get_figure()
        self.figure.tight_layout()
        self.canvas = FigureCanvas(self, -1, self.figure)

        for ax in self.axes:
            ax.ticklabel_format(style='plain', useOffset=False, axis='y')
            ax.yaxis.set_minor_locator(AutoMinorLocator(2))
            ax.tick_params(which='both', direction='in')

        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.canvas, 1, wx.LEFT | wx.TOP | wx.EXPAND)
        self.SetSizer(self.sizer)
        #self.Fit() # do not use as this will change the window size
        self.add_toolbar()
        self.Show()

        self.Bind(wx.EVT_CLOSE, self.OnWindowDestroy, self)

    def add_toolbar(self):
        self.toolbar = NavigationToolbar(self.canvas)
        self.toolbar.Realize()
        # By adding toolbar in sizer, we are able to put it at the bottom
        # of the frame - so appearance is closer to GTK version.
        self.sizer.Add(self.toolbar, 0, wx.LEFT | wx.EXPAND)
        # update the axes menu on the toolbar
        self.toolbar.update()

    def OnWindowDestroy(self, e):
        self.Destroy()
