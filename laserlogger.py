#!/usr/bin/env python3
#
# (c) Florian Schaefer, April 2021

import wx
import json
import datetime
import time
import loggertable
from laserloggerGUI import LaserLoggerFrame
import ntptime

# Fix fuzzy fonts on windows
# https://stackoverflow.com/questions/50884283/how-to-fix-blurry-text-in-wxpython-controls-on-windows
import ctypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(True)
except:
    pass

class LaserLogger(LaserLoggerFrame):
    def __init__(self, *args, **kwds):
        """Application initialization"""
        # prepare main window
        LaserLoggerFrame.__init__(self, *args, **kwds)

        # set up keyboard shortcuts
        accel_tbl = wx.AcceleratorTable([
                (wx.ACCEL_CTRL, ord('Q'), self.frame_main_toolbar.GetToolByPos(0).GetId()), # Ctrl-Q -> Quit
                (wx.ACCEL_CTRL, ord('S'), self.frame_main_toolbar.GetToolByPos(1).GetId()), # Ctrl-S -> Save
                (wx.ACCEL_CTRL, ord('N'), self.frame_main_toolbar.GetToolByPos(3).GetId()), # Ctrl-N -> New entry
                (wx.ACCEL_CTRL, ord('A'), self.frame_main_toolbar.GetToolByPos(4).GetId()), # Ctrl-A -> Autofill
                (wx.ACCEL_CTRL, ord('P'), self.frame_main_toolbar.GetToolByPos(6).GetId()), # Ctrl-P -> Plot
            ])
        self.SetAcceleratorTable(accel_tbl)

        # initial settings
        self.prefs_file = "laserlogger_settings.json"
        self.prefs = {
            'logbooks': [
                    {
                        'name': 'logEr 583 nm',
                        'filename': 'logfiles/ErYbLi_lognote_583nm.csv'
                    },
                    {
                        'name': 'Er 401 nm',
                        'filename': 'logfiles/ErYbLi_lognote_401nm.csv'
                    }
                ],
            'mqtt': {
                'broker': '192.168.1.11'
                }
            }
        self.SettingsLoad()
        #self.SettingsSave()

        # convert settings into our own structure (so that we might save the
        # settings dictionary again easily without having the grid in the way)
        self.logbooks = []
        for book in self.prefs['logbooks']:
            self.logbooks.append({
                    'name': book['name'],
                    'filename': book['filename'],
                    'grid': None
                })

        for logbook in self.logbooks:
            logbook['grid'] = loggertable.LoggerGrid(self.notebook, logbook['filename'], self.prefs['mqtt']['broker'])
            if logbook['grid'].GetTable().data is not None:
                self.notebook.AddPage(logbook['grid'], logbook['name'])
            else:
                # failed to create table (probably could not load CSV file)
                logbook['grid'] = None

        # keep only successfully created logbooks
        self.logbooks = [logbook for logbook in self.logbooks if logbook['grid'] is not None]

        # prepare list of images that can be used for the notebook tabs
        il = wx.ImageList(16, 16)
        il.Add(wx.Bitmap('icons/operating.png', wx.BITMAP_TYPE_PNG))
        self.notebook.AssignImageList(il)

        # mark any lasers that are currently in use (i.e. have no stop time)
        for pos in range(len(self.logbooks)):
            nb = self.logbooks[pos]
            if nb['grid'].GetNumberRows() > 0 and not nb['grid'].GetCellValue(0, 1):
                # no end time set yet -> laser is currently in use
                self.notebook.SetPageImage(pos, 0)

        self.Layout()

    ### Status bar

    def SetTimedStatusText(self, text, timeout = None):
        """Set a statusbar message that is cleared after <timeout> sec"""

        self.SetStatusText(text)
        if timeout != None:
            self.timer = wx.Timer(self)
            self.Bind(wx.EVT_TIMER, self.ClearStatusText, self.timer)
            self.timer.Start(timeout * 1000, oneShot = True)

    def ClearStatusText(self, e):
        """Clear the status text in the status bar field"""

        self.SetStatusText("")

    ### GUI callbacks

    def OnQuit(self, e):
        """Quit application with proper cleanup"""

        # First check whether there are unsaved changes
        modified = False
        for logbook in self.logbooks:
            modified |= logbook['grid'].GetTable().modified

        if modified:
            dlg = wx.MessageDialog(self,
                    "There are unsaved changes!\n\nDo you really want to close\nthe Laser Logger program?",
                    "Unsaved changes", wx.YES_NO|wx.NO_DEFAULT|wx.ICON_WARNING)
            result = dlg.ShowModal()
            dlg.Destroy()
            if result == wx.ID_YES:
                # close GUI
                #self.Destroy()
                wx.Exit()
        else:
            # no unsaved changed -> close immediately
            #self.Destroy()
            # Use Exit() instead of Destroy() as this also works after some
            # plot windows were opened and closed.
            wx.Exit()

    def OnSave(self, e):
        """Save logbooks to CSV file"""
        nb = self.GetNotebook()

        # save
        try:
            if nb['grid'].Save():
                self.SetTimedStatusText("Logbook '{}' saved".format(nb['name']), 3)
            else:
                self.SetTimedStatusText("Logbook '{}' could not be saved".format(nb['name']), 5)
        except Exception as e:
            self.SetTimedStatusText("Logbook '{}' could not be saved".format(nb['name']), 5)
            dlg = wx.MessageDialog(self,
                                    "Could not save logbook:\n{}\n\n"
                                    "Please check your file system permissions etc.".format(e), "Save error",
                                    wx.OK|wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()

    def OnNewEntry(self, e):
        """Start a new entry by adding a new line with the current time stamp"""
        nb = self.GetNotebook()

        # just to make sure that the user really wants to start a new entry
        if nb['grid'].GetNumberRows() > 0 and not nb['grid'].GetCellValue(0, 1):
            dlg = wx.MessageDialog(self,
                    "It seems a new entry was already created. Do you really "\
                    "want to add a new entry (instead of using \"Autofill\" "\
                    "to complete the current entry)?",
                    "Create new entry?", wx.YES_NO|wx.NO_DEFAULT|wx.ICON_WARNING)
            dlg.SetYesNoLabels("&Yes, proceed", "&No, cancel")
            result = dlg.ShowModal()
            dlg.Destroy()
            if result != wx.ID_YES:
                return

        # insert a new row at the beginning of the lobook
        nb['grid'].InsertRows(0, 1)

        # put current time as start time into first column
        nb['grid'].SetCellValue(0, 0, self.GetTimeStr())
        nb['grid'].GoToCell(0, 0)

        # reset all MQTT data so that only fresh data will be used for autofill
        nb['grid'].GetTable().MQTTResetData()

        # add an image to the notebook tab to mark that the laser is currently in use
        self.notebook.SetPageImage(self.notebook.GetSelection(), 0)

        self.SetTimedStatusText("Added new entry to '{}' logbook".format(nb['name']), 3)

    def OnAutofill(self, e):
        """Automatically fill in logboog entries where possible"""
        nb = self.GetNotebook()

        # at least one row is needed
        if nb['grid'].GetNumberRows() == 0:
            return

        # just to make sure that the user really wants to autofill
        if nb['grid'].GetCellValue(0, 1):
            dlg = wx.MessageDialog(self,
                    "It seems that the last entry is already complete. "\
                    "Do you really want to (again) autofill the most recent "\
                    "entry (instead of using \"New entry\" to start a new logbook entry)?",
                    "Proceed with autofill?", wx.YES_NO|wx.NO_DEFAULT|wx.ICON_WARNING)
            dlg.SetYesNoLabels("&Yes, proceed", "&No, cancel")
            result = dlg.ShowModal()
            dlg.Destroy()
            if result != wx.ID_YES:
                return

        # only input the stop time if the cell is (still) empty
        if len(nb['grid'].GetCellValue(0, 1)) == 0:
            # put current time as stop time into second column
            nb['grid'].SetCellValue(0, 1, self.GetTimeStr())
            nb['grid'].GoToCell(0, 0)

        # let the notebook handle the rest of the values
        nb['grid'].GetTable().Autofill()

        # remove the notebook image tab to mark that the laser is not in use any more
        self.notebook.SetPageImage(self.notebook.GetSelection(), -1)

        self.SetTimedStatusText("Auto completed entries of '{}' logbook".format(nb['name']), 3)

    def OnPlot(self, e):
        """Open a new window with a plot of the selected columns (and rows)"""
        self.GetNotebook()["grid"].Plot()

    def OnNotebookPageChanged(self, e):
        """Handle notebook page change to display some additional information"""
        nb = self.GetNotebook()
        hrs = nb['grid'].GetTable().GetHours()
        self.SetTimedStatusText("Logbook for \"{}\", total logged operation time: {} h = {} d".format(
            nb['name'], round(hrs, 1), round(hrs/24, 1)))

    ### Internal functions

    def GetNotebook(self):
        """Return dictionary of currently opened notebook tab"""
        pos = self.notebook.GetSelection()
        return self.logbooks[pos]

    def GetTimeStr(self):
        """Obtain the current date/time either from NTP or locally"""
        try:
            # try to get the time from an NTP timeserver first
            timestr = time.strftime("%Y/%m/%d %H:%M:%S", time.localtime(ntptime.RequestTimefromNtp()))
        except:
            # if that fails take the local time of the computer
            timestr = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")

        return timestr

    def SettingsLoad(self):
        """Load preferences and settings from file"""

        try:
            with open(self.prefs_file) as json_data_file:
                loaded_data = json.load(json_data_file)

                try:
                    # Instead of replacing the prefs variable we replace
                    # those keys that are in the preferences file. This ensures
                    # that at least all necessary keys remain defined.
                    for key, value in loaded_data.items():
                        self.prefs[key] = value
                except:
                    pass
        except FileNotFoundError:
            dlg = wx.MessageDialog(self,
                                    "Preferences file not found.\n\n"
                                    "Will continue with internal default settings.", "Load error",
                                    wx.OK|wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()

    def SettingsSave(self):
        """Save preferences and settings to file"""

        try:
            with open(self.prefs_file, 'w') as json_data_file:
                json.dump(self.prefs, json_data_file, indent=4)
                self.SetTimedStatusText("Preferences and settings saved to file", 1)
        except Exception as e:
            dlg = wx.MessageDialog(self,
                                    "Could not save preferences:\n{}\n\n"
                                    "Please check your file system permissions.".format(e),
                                    "Save error",
                                    wx.OK|wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()

class LaserLoggerApp(wx.App):
    def OnInit(self):
        self.frame_main = LaserLogger(None, wx.ID_ANY, "")
        self.SetTopWindow(self.frame_main)
        self.frame_main.Show()
        return True


if __name__ == "__main__":
    laserloggerapp = LaserLoggerApp(0)
    laserloggerapp.MainLoop()
