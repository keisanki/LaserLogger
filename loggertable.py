#!/usr/bin/env python3
#
# (c) Florian Schaefer, April 2021

import wx
import wx.grid
import pandas as pd
import numpy as np
import datetime
import paho.mqtt.client as mqtt
from os import replace
from os.path import isfile
import functools
import toptica
import plotframe

ODD_ROW_COLOUR = '#FFFFFF'
EVEN_ROW_COLOUR = '#CCE6FF'
GRID_LINE_COLOUR = '#ccc'

class FloatRenderer(wx.grid.GridCellRenderer):
    """FloatRenderer renders a float value into grid table entry.
    Similar to GridCellFloatRenderer, but shows empty entry if value is None or
    empty string.

    Taken from the "Cam" software."""

    def __init__(self, width = -1, precision = -1):
        """
        @param width: total number of digits
        @param precision: number of digits after comma
        """
        wx.grid.GridCellRenderer.__init__(self)

        self.width = width
        self.precision = precision

        # maintain a list of text dimensions for all rendered strings so far
        self.extents = {}

    def SetParameters(self, format):
        "@param format: format string, e.g., '4,1' for width = 4, precision = 1"
        self.width, self.precision = map(int, format.split(','))

    @property
    def format(self):
        """
        read property for dynamically created format string
        @return: format string
        """
        w,p = self.width, self.precision
        if w==-1 and p==-1:
            return '%f'

        f = '%'
        if w>-1:
            f+= "%d"%w

        if p>-1:
            f+= ".%d"%p

        f += 'f'
        return f

    def Draw(self, grid, attr, dc, rect, row, col, isSelected):
        """
        Implements rendering into grid entry.
        """
        #paint background
        if isSelected:
            dc.Brush = wx.Brush(grid.SelectionBackground)
        else:
            dc.Brush = wx.Brush(attr.BackgroundColour)
        dc.BackgroundMode = wx.SOLID
        dc.Pen = wx.TRANSPARENT_PEN
        dc.DrawRectangle(rect)

        #create string, applying format to value
        value = grid.Table.GetValue(row, col)
        empty = grid.Table.IsEmptyCell(row, col)
        if not empty:
            s = (self.format%float(value)).lstrip()
        else:
            s = '-'

        #draw text
        dc.BackgroundMode = wx.TRANSPARENT
        dc.Font = attr.Font
        dc.TextForeground = attr.TextColour

        if not s in self.extents:
            # sizes not cached -> calculate and store
            self.extents[s] = dc.GetTextExtent(s)
        tw, th = self.extents[s]

        if (attr.GetAlignment()[0] == wx.ALIGN_LEFT):
            xpos = rect.x + 2 + 5
        elif (attr.GetAlignment()[0] == wx.ALIGN_CENTRE):
            xpos = rect.x + round((rect.width-tw)/2)
        else:
            xpos = rect.x + rect.width - tw - 2 - 5

        dc.DrawText(s, xpos, rect.y + 2)
        dc.DestroyClippingRegion()

    def GetBestSize(self, grid, attr, dc, row, col):
        """Calculate size of entry"""

        #create string, applying format to value
        value = grid.Table.GetValue(row, col)
        empty = grid.Table.IsEmptyCell(row, col)
        if not empty:
            s = (self.format%float(value)).lstrip()
        else:
            s = '-'
        dc.Font = attr.Font

        if not s in self.extents:
            # sizes not cached -> calculate and store
            self.extents[s] = dc.GetTextExtent(s)
        tw, th = self.extents[s]

        return wx.Size(tw+2+10, th+2)

    def Clone(self):
        return FloatRenderer(self.width, self.precision)

def changes_data(f):
    """Decorator for methods that change data.
    Needed to see wheter file has been modified after last save. Changes
    attribute 'modified'.

    Taken from the "Cam" software."""
    @functools.wraps(f)
    def wrapper(self, *args, **kwargs):
        if not self.modified and self.parent:
            nb = self.parent.GetParent().GetParent().notebook
            page = nb.GetSelection()
            title = nb.GetPageText(page)
            nb.SetPageText(page, title + ' (*)')
        self.modified = True
        return f(self, *args, **kwargs)
    return wrapper

class LoggerTable(wx.grid.GridTableBase):
    """Custom grid table that uses a Pandas dataframe as backend storage
    to hold and format the logged data.

    See also https://stackoverflow.com/questions/64743632/how-to-display-pandas-dataframe-within-a-wxpython-tab"""
    def __init__(self, parent, filename, mqtt_broker = None):
        """Initialize table object (load CSV file, prepare wx.Grid, connect to MQTT)"""
        wx.grid.GridTableBase.__init__(self)

        #TODO: Raise an error if file does not exist or is not readable

        # import CSV data
        self.filename = filename
        try:
            # read special information on automatic data import
            self.autoinfoline = pd.read_csv(filename, nrows=1)
            # import main part of log file
            self.data = pd.read_csv(filename, parse_dates=['Time\nStart', 'Time\nStop'], skiprows=[1])
        except Exception as e:
            dlg = wx.MessageDialog(parent,
                                    "Could not open or read '{}' for import:\n{}\n\n"
                                    "Check filename, permissions and content.\n"
                                    "Will skip this file for now.".format(filename, e),
                                    "File import failed",
                                    wx.OK|wx.ICON_ERROR)
            dlg.ShowModal()
            dlg.Destroy()
            self.data = None
            return
        # put newest entries top
        self.data = self.data.iloc[::-1]
        self.data.reset_index(drop=True)

        # at least try to convert isotope column into integers
        # conversion will fail if there are empty columns, in that case float64 will be kept
        # (this way in the saved CSV file we won't have fractional numbers)
        self.data['Lock\nIsotope'] = self.data['Lock\nIsotope'].astype('int', errors='ignore')

        # keep a reference to the calling wx.Grid
        self.parent = parent

        # create a list of all column groups (e.g. Time, LD, TA, SHG)
        self.colgroups = [label.split('\n')[0] for label in self.data.columns.to_list()]
        self.colgroups = list(dict.fromkeys(self.colgroups))

        # maintain a convenient list of the column labels
        self.column_labels = self.data.columns.to_list()

        # convert pandas datafrom columns to individual numpy arrays.
        # this is to speed to the table as df.iloc() is very slow.
        self._UpdateNumpyArray()

        # prepare necessary renderers and editors for grid display
        self.renderers = {}
        self.editors = {}
        for label in self.column_labels:
            if "Time" in label:
                renderer = wx.grid.GridCellDateTimeRenderer(outformat="%Y/%m/%d %H:%M", informat="%Y/%m/%d %H:%M")
                editor = wx.grid.GridCellAutoWrapStringEditor()
            elif "Comment" in label:
                renderer = wx.grid.GridCellStringRenderer()
                editor = wx.grid.GridCellAutoWrapStringEditor()
            elif "(THz)" in label:
                renderer = FloatRenderer(precision=7)
                editor = wx.grid.GridCellFloatEditor(precision=7)
            elif "(MHz)" in label:
                renderer = FloatRenderer(precision=3)
                editor = wx.grid.GridCellFloatEditor(precision=3)
            elif "Temp" in label:
                renderer = FloatRenderer(precision=3)
                editor = wx.grid.GridCellFloatEditor(precision=3)
            elif "(mA)" in label:
                renderer = FloatRenderer(precision=1)
                editor = wx.grid.GridCellFloatEditor(precision=1)
            elif "(mV)" in label:
                renderer = FloatRenderer(precision=0)
                editor = wx.grid.GridCellFloatEditor(precision=1)
            elif "(V)" in label:
                renderer = FloatRenderer(precision=3)
                editor = wx.grid.GridCellFloatEditor(precision=3)
            elif "(mW)" in label:
                renderer = FloatRenderer(precision=1)
                editor = wx.grid.GridCellFloatEditor(precision=1)
            elif "Isotope" in label:
                renderer = FloatRenderer(precision=0)
                editor = wx.grid.GridCellFloatEditor(precision=0)
            else:
                renderer = FloatRenderer(precision=1)
                editor = wx.grid.GridCellFloatEditor(precision=3)

            self.renderers[label] = renderer
            self.editors[label] = editor

        # table is not (yet) modified
        self.modified = False

        # parse autofill information
        self.autoinfo = {}
        for header, autoinfo in self.autoinfoline.iloc[0].to_dict().items():
            try:
                parts = autoinfo.split('://')
                if len(parts) == 2:
                    typeinfo = parts[0]
                    if typeinfo == "toptica":
                        # Toptica laser -> separate ip:port/uri format
                        ip, rest = parts[1].split(":", 1)
                        port, uri = rest.split("/", 1)
                        self.autoinfo[header] = {
                                    "type": typeinfo,
                                    "ip": ip,
                                    "port": int(port),
                                    "uri": uri
                                }
                    else:
                        self.autoinfo[header] = {
                                    "type": typeinfo,
                                    "uri": parts[1]
                                }
                else:
                    # invalid information
                    print("Error: Cannot parse {} of {}".format(self.autoinfo, header))
            except:
                pass

        # set up MQTT
        self.mqtt_prefs = {
            "mqtt_broker_ip": mqtt_broker,
            "mqtt_subscribe_topics": []
            }
        self.mqtt_prefs['mqtt_subscribe_topics'] = [value['uri'] for value in self.autoinfo.values() if value['type']=='mqtt']
        self.mqtt_connected = False
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.OnMQTTConnected
        self.mqtt_client.on_disconnect = self.OnMQTTDisconnected
        self.MQTTconnect()

        # set up some storage space for MQTT messages
        self.mqtt_data = {}

    ### MQTT

    def OnMQTTConnected(self, client, userdata, flags, rc):
        """Callback function when connected to broker"""

        for topic in self.mqtt_prefs['mqtt_subscribe_topics']:
            self.mqtt_client.subscribe(topic)

        self.mqtt_client.on_message=self.OnMQTTMessage

        self.mqtt_connected = True

    def OnMQTTDisconnected(self, client, userdata, rc):
        """Callback function when disconnected from broker"""
        self.mqtt_connected = False

    def MQTTconnect(self):
        """Helper function to connect to MQTT broker"""
        if not self.mqtt_prefs["mqtt_broker_ip"]:
            return

        if self.mqtt_prefs['mqtt_broker_ip']:
            try:
                self.mqtt_client.connect(self.mqtt_prefs['mqtt_broker_ip'], keepalive=10)
                self.mqtt_client.loop_start()
            except Exception as e:
                dlg = wx.MessageDialog(self.parent,
                                        "Could not connect to MQTT broker:\n{}\n\n"
                                        "Please check broker IP in the preferences.\n"
                                        "Continuing without MQTT support.".format(e), "MQTT error",
                                        wx.OK|wx.ICON_ERROR)
                dlg.ShowModal()
                dlg.Destroy()

    def OnMQTTMessage(self, client, userdata, message):
        """Callback function for MQTT to handle incoming messages"""

        if "wavemeter" in message.topic:
            if not message.topic in self.mqtt_data.keys():
                self.mqtt_data[message.topic] = np.empty([0, 1])

            try:
                value = float(message.payload)
                self.mqtt_data[message.topic] = np.append(self.mqtt_data[message.topic], value)
                if len(self.mqtt_data[message.topic]) > 30:
                    self.mqtt_data[message.topic] = self.mqtt_data[message.topic][1:]
            except:
                pass
        else:
            try:
                self.mqtt_data[message.topic] = float(message.payload)
            except:
                pass

        return

    def MQTTResetData(self):
        """Reset (that is forget) all values received via MQTT"""
        self.mqtt_data = {}

    ### Grid management

    def _UpdateNumpyArray(self):
        """Helper function to rebuild our numpy representation of the data"""

        self.np_columns = []
        for label in self.column_labels:
            self.np_columns.append(self.data[label].to_numpy())

    def GetNumberRows(self):
        return len(self.data)

    def GetNumberCols(self):
        return len(self.column_labels)

    def IsEmptyCell(self, row, col):
        try:
            #val = self.data.iloc[row, col]
            val = self.np_columns[col][row]
            if pd.isnull(val) or val=='':
                return True
            else:
                return False

        except IndexError:
            return True

    def GetValue(self, row, col):
        #value = self.data.iloc[row, col]
        value = self.np_columns[col][row]
        if pd.isnull(value) or value=='':
            return None

        if "Time" in self.GetColLabelValue(col):
            #return value.strftime("%Y/%m/%d %H:%M")
            return value.astype('datetime64[s]').astype(datetime.datetime).strftime("%Y/%m/%d %H:%M")

        return value

    @changes_data
    def SetValue(self, row, col, value):
        label = self.GetColLabelValue(col)
        if "Time" in label:
            try:
                value = pd.to_datetime(value)
            except:
                value = None
        elif not "Comment" in label:
            try:
                value = np.float64(value)
            except:
                value = None

        # update Pandas dataframe
        # (not necessary as the numpy array is still pointing to the original
        # dataframe and updating the numpy array below will also update the
        # original Pandas dataframe data))
        #self.data.iloc[row, col] = value

        # update numpy array (also updates Pandas data)
        self.np_columns[col][row] = value

    def GetColLabelValue(self, col):
        return self.column_labels[col]

    def GetTypeName(self, row, col):
        label = self.GetColLabelValue(col)

        typename = wx.grid.GRID_VALUE_FLOAT
        if "Time" in label:
            typename = wx.grid.GRID_VALUE_STRING
        elif "Comment" in label:
            typename = wx.grid.GRID_VALUE_STRING

        return typename

    def GetAttr(self, row, col, prop):
        attr = wx.grid.GridCellAttr()

        if row % 2 == 1:
            color = wx.Colour(EVEN_ROW_COLOUR)
        else:
            color = wx.Colour(ODD_ROW_COLOUR)

        label = self.GetColLabelValue(col)
        grouplabel = label.split('\n')[0]
        if self.colgroups.index(grouplabel) % 2 == 1:
            color = color.ChangeLightness(90)

        attr.SetBackgroundColour(color)

        # everything but comments shall be centered
        if "Comment" in label:
            align = wx.ALIGN_LEFT
        else:
            align = wx.ALIGN_CENTRE
        attr.SetAlignment(hAlign=align, vAlign=-1)

        # set the appropriate renderer
        self.renderers[label].IncRef()
        attr.SetRenderer(self.renderers[label])
        # set the appropriate editor
        self.editors[label].IncRef()
        attr.SetEditor(self.editors[label])

        return attr

    def DeleteCols(self, pos=0, numcols=1):
        pass

    def AppendCols(self, numcols=1, updateLabels=True):
        pass

    @changes_data
    def DeleteRows(self, pos=0, numRows=1):
        """Delete some rows somewhere in the table"""

        indexes = self.data.index[range(pos,pos+numRows)]
        self.data.drop(index=indexes, inplace=True)
        # rebuild index (remembering that the internal order is acutally reversed)
        self.data = self.data.iloc[::-1]
        self.data.reset_index(inplace=True, drop=True)
        self.data = self.data.iloc[::-1]
        # rebuild numpy representation of data
        self._UpdateNumpyArray()

        msg = wx.grid.GridTableMessage(self,
                                       wx.grid.GRIDTABLE_NOTIFY_ROWS_DELETED,
                                       pos, numRows)
        self.GetView().ProcessTableMessage(msg)

        return True

    @changes_data
    def AppendRows(self, numRows=1):
        """Append empty rows to the end of the table"""
        curRows = self.GetNumberCols()
        self.data = self.data.reindex(self.data.index.tolist() + list(range(curRows,curRows+numRows)))
        self.data = self.data.iloc[::-1]
        # rebuild numpy representation of data
        self._UpdateNumpyArray()

        msg = wx.grid.GridTableMessage(self,
                                       wx.grid.GRIDTABLE_NOTIFY_ROWS_APPENDED,
                                       numRows)
        self.GetView().ProcessTableMessage(msg)

        return True

    @changes_data
    def InsertRows(self, pos=0, numRows=1):
        """Insert empty rows somewhere in table"""
        # list of current indexex
        indexlist = self.data.index.tolist()
        # number of rows currently in the dataframe
        curRows = self.GetNumberRows()
        # insert new rows where indicated
        newlist = indexlist[:pos]+list(range(curRows,curRows+numRows))+indexlist[pos:]
        # rebuild dataframe
        self.data = self.data.reindex(newlist)
        # rebuild numpy representation of data
        self._UpdateNumpyArray()

        msg = wx.grid.GridTableMessage(self,
                                       wx.grid.GRIDTABLE_NOTIFY_ROWS_INSERTED,
                                       pos,
                                       numRows)
        self.GetView().ProcessTableMessage(msg)

        return True

    ### Internal functions

    def Save(self):
        """Save logbook data to CSV file"""
        if self.filename is None:
            return False

        # maintain a list of 9 backup copies
        for idx in range(8, 0, -1):
            if isfile("{}.{}".format(self.filename, idx)):
                replace("{}.{}".format(self.filename, idx),
                        "{}.{}".format(self.filename, (idx+1)))
        replace(self.filename, "{}.{}".format(self.filename, 1))

        self.autoinfoline.to_csv(self.filename, index=False)
        self.data.iloc[::-1].to_csv(self.filename, index=False, mode='a', header=False)

        if (self.modified):
            nb = self.parent.GetParent().GetParent().notebook
            page = nb.GetSelection()
            title = nb.GetPageText(page)
            if title.endswith(" (*)"):
                # Sometimes the notebook name is unchanged even though the
                # modified flag is set. This should not be happening...
                nb.SetPageText(page, title[0:-4])

        self.modified = False

        return True

    def Autofill(self):
        """Automatically fill in missing entries where possible"""
        dlc = None
        for header, autoinfo in self.autoinfo.items():
            value = None

            # autofill of information provided by MQTT
            if autoinfo['type'] == 'mqtt':
                topic = autoinfo['uri']
                # only proceed if requested information is really available
                if topic in self.mqtt_data.keys():
                    value = self.mqtt_data[topic]

                    # wavemeter -> take average first and convert to THz
                    if "wavemeter" in topic:
                        value = round(np.mean(value)/1e6, 7)

            # autofill of information provided by Toptica lasers -> (param-disp 'XYZ)
            if autoinfo['type'] == 'toptica':
                if dlc == None or dlc.ip != autoinfo['ip'] or dlc.port != autoinfo['port']:
                    # only create new DLCpro object if old one is not suited
                    dlc = toptica.DLCpro(ip=autoinfo['ip'], port=autoinfo['port'])
                value = float(dlc.getParam(autoinfo['uri']))

                # heuristic rounding of values
                if "voltage" in autoinfo['uri']:
                    value = round(value, 3)
                if "current" in autoinfo['uri']:
                    value = round(value, 2)
                if "temp" in autoinfo['uri']:
                    value = round(value, 3)
                if "power" in autoinfo['uri']:
                    value = round(value, 2)

            # put value into proper column (only if this cell is empty)
            column = self.data.columns.get_loc(header)
            cell = self.data.iloc[0, column]
            if (pd.isnull(cell) and not pd.isnull(value)) \
               or (type(cell) == str and len(cell) == 0):
                self.data.iloc[0, column] = value

        # update display
        msg = wx.grid.GridTableMessage(self, wx.grid.GRIDTABLE_REQUEST_VIEW_GET_VALUES)
        self.GetView().ProcessTableMessage(msg)

        return True

    def GetHours(self):
        """Calculate and return the total logged hours of operation"""
        td = self.data['Time\nStop'].astype('datetime64') - self.data['Time\nStart'].astype('datetime64')
        return td.sum().total_seconds() / 3600

class LoggerGrid(wx.grid.Grid):
    """Custom WX grid to display the logged data"""

    ID_popup_menu = wx.NewIdRef(count=1)

    def __init__(self, parent, filename, mqtt_broker = None):
        """Initialize grid by loading data and setting up row/column sizes"""
        wx.grid.Grid.__init__(self, parent, wx.ID_ANY)

        # associate Pandas dataframe to the data of this table
        table = LoggerTable(parent, filename, mqtt_broker)
        self.SetTable(table, takeOwnership=True)
        if table.data is None:
            return

        lastcol = self.GetNumberCols()-1
        self.AutoSizeColumns()
        self.SetColLabelSize(int(1.8*self.GetColLabelSize()))
        self.SetRowLabelSize(int(0.7*self.GetRowLabelSize()))
        self.SetColSize(0, int(1.1*self.GetColSize(0)))
        self.SetColSize(1, int(1.1*self.GetColSize(1)))
        self.SetColSize(lastcol, int(1.1*self.GetColSize(lastcol)))

        self.Bind(wx.grid.EVT_GRID_LABEL_RIGHT_CLICK, self.OnLabelRightClick, self)
        self.GetGridColLabelWindow().Bind(wx.EVT_MOTION, self.OnMouseOverColLabel)

    def Save(self):
        """Save the content of the table"""
        return self.GetTable().Save()

    def Plot(self):
        """Open a new window with a plot of the selected columns (and rows)"""
        # obtain selections and create a new dataframe containing only the data to be plotted
        cols = self.GetSelectedCols()
        rows = self.GetSelectedRows()

        # ignore selected start/stop time columns
        cols = [col for col in cols if col > 1]

        if len(cols) == 0:
            dlg = wx.MessageDialog(self,
                    " Please select some columns to plot first. \n (Selected time columns are ignored.)",
                    "Unable to plot", wx.OK|wx.ICON_INFORMATION)
            dlg.ShowModal()
            dlg.Destroy()
            return

        # always include the second column, the stop times, which will be our index
        cols.insert(0, 1)

        df = self.GetTable().data
        colnames = df.columns[cols]
        dfselection = df[colnames]

        # If some rows are selected only include those, otherwise
        # all the data will be included in the plot.
        if len(rows):
            dfselection = dfselection.iloc[rows]

        # use column with stop times as index
        # (this will also create a copy of the dataframe)
        dfselection = dfselection.set_index(dfselection.columns[0], drop=True)

        # rename columns to be more suitable for plot
        dfselection.rename(columns=lambda x: x.replace('\n', ' '), inplace=True)

        # rename also the time column
        dfselection.index.names = ['Date']

        nb = self.GetParent()
        page = nb.GetSelection()
        title = nb.GetPageText(page)

        # create and show plot frame
        try:
            plotframe.PlotFrame(df=dfselection, title=title+" plot", parent=wx.GetTopLevelParent(self))
        except:
            dlg = wx.MessageDialog(self,
                    "Failed to plot. Check\nyour data for consistency",
                    "Unable to plot", wx.OK|wx.ICON_INFORMATION)
            dlg.ShowModal()
            dlg.Destroy()

    def OnLabelRightClick(self, evt):
        """Right click on row or column header. Create popup menu."""

        # remember selected row/column for callback functions
        self.actRow = evt.Row
        self.actCol = evt.Col

        if evt.Col<0 and evt.Row>=0: #right click on row label
            menu = wx.Menu()

            menu.Append(self.ID_popup_menu, 'Delete row {}'.format(evt.Row+1))
            self.Bind(wx.EVT_MENU, self.OnRowMenuClicked, id = self.ID_popup_menu)

            self.PopupMenu(menu)
            menu.Destroy()

        evt.Skip()

    def OnRowMenuClicked(self, event):
        """Callback function for clicking the row popup menu"""
        id = event.GetId()

        if id == self.ID_popup_menu:
            dlg = wx.MessageDialog(self,
                    "Do you really want to delete the\nthe selected row from the logbook?",
                    "Delete row confirmation", wx.YES_NO|wx.NO_DEFAULT|wx.ICON_WARNING)
            result = dlg.ShowModal()
            dlg.Destroy()
            if result == wx.ID_YES:
                self.DeleteRows(pos=self.actRow, numRows=1)

    def OnMouseOverColLabel(self, event):
        """Callback function to display column header tooltips
        (from https://www.blog.pythonlibrary.org/2010/04/04/wxpython-grid-tips-and-tricks/
        and https://groups.google.com/g/wxpython-users/c/bm8OARRVDCs)
        """
        x, y = self.CalcUnscrolledPosition(event.GetPosition())
        col = self.XToCol(x)

        label = self.GetColLabelValue(col)
        autoinfo = self.GetTable().autoinfo
        if label in autoinfo:
            typelabel = autoinfo[label]["type"].upper()

            uritype = "Query"
            if "ip" in autoinfo[label]:
                typelabel += " ({}".format(autoinfo[label]["ip"])
            if "port" in autoinfo[label]:
                typelabel += ":{})".format(autoinfo[label]["port"])
            elif "ip" in autoinfo[label]:
                typelabel += ")"

            if typelabel == "MQTT":
                typelabel += " ({})".format(self.GetTable().mqtt_prefs["mqtt_broker_ip"])
                uritype = "Topic"

            msg = "Type: {}\n{}: {}".format(typelabel, uritype, autoinfo[label]["uri"])
            self.GetGridColLabelWindow().SetToolTip(msg)
        else:
            self.GetGridColLabelWindow().SetToolTip(None)

        event.Skip()


#### Standalone testing setup ###

class TestFrame(wx.Frame):
    def __init__(self, parent):
        wx.Frame.__init__(self, parent, -1, "Logger table test", size=(800, 400))
        LoggerGrid(self, 'logfiles/ErYbLi_lognote_401nm.csv')

if __name__ == '__main__':
    app = wx.App()
    frame = TestFrame(None)
    frame.Show(True)
    app.MainLoop()
