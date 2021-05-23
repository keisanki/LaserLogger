#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
#
# generated by wxGlade 1.0.1 on Thu May 20 15:45:50 2021
#

import wx

# begin wxGlade: dependencies
# end wxGlade

# begin wxGlade: extracode
# end wxGlade


class LaserLoggerFrame(wx.Frame):
    def __init__(self, *args, **kwds):
        # begin wxGlade: LaserLoggerFrame.__init__
        kwds["style"] = kwds.get("style", 0) | wx.DEFAULT_FRAME_STYLE
        wx.Frame.__init__(self, *args, **kwds)
        self.SetSize((1400, 500))
        self.SetTitle("Laser Logger")

        self.frame_main_statusbar = self.CreateStatusBar(1)
        self.frame_main_statusbar.SetStatusWidths([-1])

        # Tool Bar
        self.frame_main_toolbar = wx.ToolBar(self, -1, style=wx.TB_HORZ_TEXT)
        tool = self.frame_main_toolbar.AddTool(wx.ID_ANY, "Quit", wx.Bitmap("./icons/application-exit-symbolic.symbolic.png", wx.BITMAP_TYPE_ANY), wx.NullBitmap, wx.ITEM_NORMAL, "Quit application", "")
        self.Bind(wx.EVT_TOOL, self.OnQuit, id=tool.GetId())
        tool = self.frame_main_toolbar.AddTool(wx.ID_ANY, "Save", wx.Bitmap("./icons/document-save-symbolic.symbolic.png", wx.BITMAP_TYPE_ANY), wx.NullBitmap, wx.ITEM_NORMAL, "Save log", "")
        self.Bind(wx.EVT_TOOL, self.OnSave, id=tool.GetId())
        self.frame_main_toolbar.AddSeparator()
        tool = self.frame_main_toolbar.AddTool(wx.ID_ANY, "New entry", wx.Bitmap("./icons/list-add-symbolic.symbolic.png", wx.BITMAP_TYPE_ANY), wx.NullBitmap, wx.ITEM_NORMAL, "Start new logbook entry", "")
        self.Bind(wx.EVT_TOOL, self.OnNewEntry, id=tool.GetId())
        tool = self.frame_main_toolbar.AddTool(wx.ID_ANY, "Autofill", wx.Bitmap("./icons/document-revert-symbolic-rtl.symbolic.png", wx.BITMAP_TYPE_ANY), wx.NullBitmap, wx.ITEM_NORMAL, "Enter automatic values from TApro and Wavemeter", "")
        self.Bind(wx.EVT_TOOL, self.OnAutofill, id=tool.GetId())
        self.frame_main_toolbar.AddSeparator()
        tool = self.frame_main_toolbar.AddTool(wx.ID_ANY, "Plot", wx.Bitmap("./icons/preferences-system-details-symbolic.symbolic.png", wx.BITMAP_TYPE_ANY), wx.NullBitmap, wx.ITEM_NORMAL, "Plot selected columns (and selected rows)", "")
        self.Bind(wx.EVT_TOOL, self.OnPlot, id=tool.GetId())
        self.SetToolBar(self.frame_main_toolbar)
        self.frame_main_toolbar.Realize()
        # Tool Bar end

        self.panel_main = wx.Panel(self, wx.ID_ANY)

        self.sizer_main = wx.BoxSizer(wx.VERTICAL)

        self.notebook = wx.Notebook(self.panel_main, wx.ID_ANY)
        self.sizer_main.Add(self.notebook, 1, wx.EXPAND, 0)

        self.panel_main.SetSizer(self.sizer_main)

        self.Layout()

        self.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.OnNotebookPageChanged, self.notebook)
        self.Bind(wx.EVT_CLOSE, self.OnQuit, self)
        # end wxGlade

    def OnQuit(self, event):  # wxGlade: LaserLoggerFrame.<event_handler>
        print("Event handler 'OnQuit' not implemented!")
        event.Skip()

    def OnSave(self, event):  # wxGlade: LaserLoggerFrame.<event_handler>
        print("Event handler 'OnSave' not implemented!")
        event.Skip()

    def OnNewEntry(self, event):  # wxGlade: LaserLoggerFrame.<event_handler>
        print("Event handler 'OnNewEntry' not implemented!")
        event.Skip()

    def OnAutofill(self, event):  # wxGlade: LaserLoggerFrame.<event_handler>
        print("Event handler 'OnAutofill' not implemented!")
        event.Skip()

    def OnPlot(self, event):  # wxGlade: LaserLoggerFrame.<event_handler>
        print("Event handler 'OnPlot' not implemented!")
        event.Skip()

    def OnNotebookPageChanged(self, event):  # wxGlade: LaserLoggerFrame.<event_handler>
        print("Event handler 'OnNotebookPageChanged' not implemented!")
        event.Skip()

# end of class LaserLoggerFrame

class LaserLoggerApp(wx.App):
    def OnInit(self):
        self.frame_main = LaserLoggerFrame(None, wx.ID_ANY, "")
        self.SetTopWindow(self.frame_main)
        self.frame_main.Show()
        return True

# end of class LaserLoggerApp

if __name__ == "__main__":
    laserloggerapp = LaserLoggerApp(0)
    laserloggerapp.MainLoop()