#!/usr/bin/env python
# -*- coding: utf-8 -*-

## Copyright (C) 2015 David Pinto <david.pinto@bioch.ox.ac.uk>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 3 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, see <http://www.gnu.org/licenses/>.

import sys
import os
import time
import webbrowser
import subprocess
import threading
import errno
import inspect

import wx
import wx.lib.intctrl
import wx.lib.mixins.listctrl
import wx.lib.newevent

## Make it work for old versions of wxPython
try:
  from wx.lib.pubsub import Publisher
  PUBSUB_OLD_API = True
except ImportError:
  import wx.lib.pubsub.pub as Publisher
  PUBSUB_OLD_API = False

if PUBSUB_OLD_API:
  def send_message_to_publisher(sig, msg):
    Publisher.sendMessage(sig, msg)
else:
  def send_message_to_publisher(sig, msg):
    Publisher.sendMessage(sig, msg=msg)


NDSAFIR_PATH = "/opt/priism/bin/ndsafir_priism"

## These events are sent by the worker threads and caught by the main
## thread to update the control/progress dialog.
NdsafirStartEvent, EVT_NDSAFIR_START = wx.lib.newevent.NewEvent()
NdsafirEndEvent, EVT_NDSAFIR_END = wx.lib.newevent.NewEvent()
NdsafirAllDoneEvent, EVT_NDSAFIR_ALL_DONE = wx.lib.newevent.NewEvent()


## Do not use wx.lib.masked.numctrl, it is weirdly broken
class FloatCtrl(wx.TextCtrl):
  """Inspired by wx.lib.intctrl.IntCtrl but supporting float values."""
  def __init__(self, value="", min=float("-Inf"), max=float("Inf"),
               allow_none=False, *args, **kwargs):
    if not allow_none and (not value or value < min):
      value = str(min)
    elif allow_none and not value:
      value = ""
    wx.TextCtrl.__init__(self, value=value, *args, **kwargs)
    self.max = max
    self.min = min
    self.allow_none = allow_none
    self.default_foreground_colour = self.GetForegroundColour()
    self.Bind(wx.EVT_TEXT, self.on_EVT_TEXT)

  def on_EVT_TEXT(self, event):
    value_str = self.GetValue()
    try:
      if not value_str:
        value = None
      else:
        value = float(value_str)
    except ValueError:
      self.SetValue("")
    else:
      if ((not self.allow_none and value is None)
          or (value < self.min or value > self.max)):
        self.SetForegroundColour(wx.RED)
      else:
        self.SetForegroundColour(self.default_foreground_colour)


class OptionsPanel(wx.Panel):
  def __init__(self, *args, **kwargs):
    wx.Panel.__init__(self, *args, **kwargs)
    sizer = wx.FlexGridSizer(7, 2)

    self.options = []

    dimensionality = OptionsPanel.DimensionalityCtrl(self)
    sizer.Add(wx.StaticText(self, label="Dimensionality"))
    sizer.Add(dimensionality, flag=wx.ALIGN_RIGHT)
    self.options.append(dimensionality)

    iterations = OptionsPanel.IterationsCtrl(self, dimensionality)
    sizer.Add(wx.StaticText(self, label="Number of iterations"))
    sizer.Add(iterations, flag=wx.ALIGN_RIGHT)
    self.options.append(iterations)

    patch_radius = OptionsPanel.IntOptionCtrl(self, arg_name="p", min=0)
    patch_radius.SetToolTip(wx.ToolTip("Patch radius must be a non-negative"
                                       " integer.  Defaults to 1."))
    sizer.Add(wx.StaticText(self, label="Patch radius"))
    sizer.Add(patch_radius, flag=wx.ALIGN_RIGHT|wx.EXPAND)
    self.options.append(patch_radius)

    noise_model = OptionsPanel.NoiseModelCtrl(self)
    sizer.Add(wx.StaticText(self, label="Noise model"))
    sizer.Add(noise_model, flag=wx.ALIGN_RIGHT|wx.EXPAND)
    self.options.append(noise_model)

    sampling = OptionsPanel.IntOptionCtrl(self, arg_name="sampling", min=1)
    sampling.SetToolTip(wx.ToolTip("Sampling must be positive integer."
                                   " Defaults to 1 + patch radius."))
    sizer.Add(wx.StaticText(self, label="Sampling"))
    sizer.Add(sampling, flag=wx.ALIGN_RIGHT|wx.EXPAND)
    self.options.append(sampling)

    island = OptionsPanel.FloatOptionCtrl(self, arg_name="island", min=0)
    island.SetToolTip(wx.ToolTip("Island threshold must be a non-negative"
                                 " number."))
    sizer.Add(wx.StaticText(self, label="Island Threshold"))
    sizer.Add(island, flag=wx.ALIGN_RIGHT|wx.EXPAND)
    self.options.append(island)

    adaptability = OptionsPanel.FloatOptionCtrl(self, arg_name="adapt",
                                                min=0, max=10)
    adaptability.SetToolTip(wx.ToolTip("Adaptability must be a number"
                                       " between 0 and 10."))
    sizer.Add(wx.StaticText(self, label="Adaptability"))
    sizer.Add(adaptability, flag=wx.ALIGN_RIGHT|wx.EXPAND)
    self.options.append(adaptability)

    self.SetSizer(sizer)

  def command_line_options(self):
    return [x.command_line_argument() for x in self.options]

  class CommandLineCtrl(object):
    def command_line_argument(self):
      """Returns a string with the command line argument"""
      raise NotImplementedError()

  class DimensionalityCtrl(wx.CheckListBox, CommandLineCtrl):
    def __init__(self, *args, **kwargs):
      choices = ["Z-stack", "Time", "Wavelength"]
      wx.CheckListBox.__init__(self, choices=choices, *args, **kwargs)
      self.SetChecked([0, 1]) # Default to use Z and Time
      self.Bind(wx.EVT_CHECKLISTBOX, self.on_EVT_CHECKLISTBOX)

    def on_EVT_CHECKLISTBOX(self, event):
      if event.GetInt() == 1: # user tried to unset time
        self.SetChecked(self.GetChecked() + (1,1))
        wx.MessageBox("ND-SAFIR is buggy and must use the Time dimension",
                      style=wx.OK | wx.ICON_ERROR)
      event.Skip()

    def command_line_argument(self):
      dims = ""
      for (ind, key) in enumerate(("z", "t", "w")):
        if self.IsChecked(ind):
          dims += key
      ndims = 2 + len(self.GetChecked())
      if ndims == 2:
        opt = "-2d"
      elif ndims > 2 and ndims < 5:
        opt = "-%id=%s" % (ndims, dims)
      else:
        opt = "-5d"
      return opt

  class IterationsCtrl(wx.Choice, CommandLineCtrl):
    def __init__(self, parent, dimensionality, *args, **kwargs):
      wx.Choice.__init__(self, parent, choices=[str(x) for x in range(1, 12)],
                         *args, **kwargs)
      self.SetSelection(3)# Default to 4 iterations
      self.dimensionality = dimensionality
      self.Bind(wx.EVT_CHOICE, self.on_EVT_CHOICE)

    def on_EVT_CHOICE(self, event):
      if event.GetInt() > 4 and not self.dimensionality.IsChecked(1):
        self.SetSelection(4)
        wx.MessageBox("Maximum number of iterations is 5 when using Time",
                      style=wx.OK | wx.ICON_ERROR)
      event.Skip()

    def command_line_argument(self):
      return "-iter=%s" % (self.GetStringSelection())

  class NoiseModelCtrl(wx.Choice, CommandLineCtrl):
    def __init__(self, *args, **kwargs):
      wx.Choice.__init__(self, choices=["gaussian + poisson",
                                        "gaussian", "auto"], *args, **kwargs)
      self.SetSelection(0) # Default to "gaussian + poisson"
      self.Bind(wx.EVT_CHOICE, self.on_EVT_CHOICE)

    def on_EVT_CHOICE(self, event):
      if event.GetInt() == 2:
        self.SetSelection(0)
        wx.MessageBox("ND-SAFIR is buggy and fails when using 'auto'",
                      style=wx.OK | wx.ICON_ERROR)
      event.Skip()

    def command_line_argument(self):
      model = self.GetStringSelection()
      if model == "gaussian + poisson":
        model = "poisson"
      return "-noise=%s" % (model)

  class CommandLineOptionCtrl(CommandLineCtrl):
    def __init__(self, arg_name):
      self.arg_name = arg_name
    def command_line_argument(self):
      if self.GetValue():
        return "-%s=%s" % (self.arg_name, self.GetValue())
      else:
        return ""

  class IntOptionCtrl(wx.lib.intctrl.IntCtrl, CommandLineOptionCtrl):
    def __init__(self, parent, arg_name, *args, **kwargs):
      wx.lib.intctrl.IntCtrl.__init__(self, parent=parent, style=wx.TE_RIGHT,
                                      allow_none=True, value=None,
                                      *args, **kwargs)
      OptionsPanel.CommandLineOptionCtrl.__init__(self, arg_name)

  class FloatOptionCtrl(FloatCtrl, CommandLineOptionCtrl):
    def __init__(self, parent, arg_name, *args, **kwargs):
      FloatCtrl.__init__(self, parent=parent, style=wx.TE_RIGHT,
                         allow_none=True, value=None, *args, **kwargs)
      OptionsPanel.CommandLineOptionCtrl.__init__(self, arg_name)


class AutoWidthListCtrl(wx.ListCtrl,
                        wx.lib.mixins.listctrl.ListCtrlAutoWidthMixin):
  """ListCtrl with last column taking up all space.

  In theory, we should be able to do `width=wx.LIST_AUTOSIZE_USEHEADER`
  when inserting the last column that it would "fit the column width to
  heading or to extend to fill all the remaining space for the last column."
  However, that does not happen, and we need to use this mixin class.
  See http://stackoverflow.com/a/11314767/1609556
  """
  def __init__(self, *args, **kwargs):
    wx.ListCtrl.__init__(self, *args, **kwargs)
    wx.lib.mixins.listctrl.ListCtrlAutoWidthMixin.__init__(self)
    self.resizeLastColumn(0)


class FileListPanel(wx.Panel):
  def __init__(self, *args, **kwargs):
    wx.Panel.__init__(self, *args, **kwargs)

    self.file_list_ctrl = AutoWidthListCtrl(self, style=wx.LC_REPORT)
    self.file_list_ctrl.InsertColumn(0, "Path")
    self.file_list_ctrl.InsertColumn(1, "Filename")
    btn_sizer = wx.BoxSizer(wx.VERTICAL)

    add_btn = wx.Button(self, label="Add")
    add_btn.Bind(wx.EVT_BUTTON, self.on_add_EVT_BUTTON)
    btn_sizer.Add(add_btn)

    rm_btn = wx.Button(self, label="Remove")
    rm_btn.Bind(wx.EVT_BUTTON, self.on_rm_EVT_BUTTON)
    btn_sizer.Add(rm_btn)

    clear_btn = wx.Button(self, label="Clear")
    clear_btn.Bind(wx.EVT_BUTTON, self.on_clear_EVT_BUTTON)
    btn_sizer.Add(clear_btn)

    sizer = wx.BoxSizer(wx.HORIZONTAL)
    sizer.Add(self.file_list_ctrl, proportion=1, flag=wx.EXPAND|wx.ALL)
    sizer.Add(btn_sizer)
    self.SetSizer(sizer)

  def on_add_EVT_BUTTON(self, event):
    dialog = wx.FileDialog(self, message = "Select files to add",
                           wildcard = ("DV and MRC files|*.dv;*.mrc|"
                                       "All files|*"),
                           style = (wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
                                    | wx.FD_MULTIPLE))
    if dialog.ShowModal() == wx.ID_OK:
      for file in dialog.GetPaths():
        self.file_list_ctrl.Append(os.path.split(file))
    event.Skip()

  def on_rm_EVT_BUTTON(self, event):
    for sel in iter (self.file_list_ctrl.GetFirstSelected, -1):
      self.file_list_ctrl.DeleteItem(sel)
    event.Skip()

  def on_clear_EVT_BUTTON(self, event):
    self.clear_file_list()
    event.Skip()

  def get_number_of_files(self):
    return self.file_list_ctrl.GetItemCount()

  def get_filepaths(self):
    fpaths = []

    ## FIXME make it remember what is the right way?
    def get_item_text(listctrl, item, col):
      try:
        return listctrl.GetItemText(item=item, col=col)
      except TypeError:
        ## note that GetItem argument is named itemId in older versions
        return listctrl.GetItem(itemId=item, col=col).GetText()

    for i in range(self.get_number_of_files()):
      dir = get_item_text(self.file_list_ctrl, i, 0)
      name = get_item_text(self.file_list_ctrl, i, 1)
      fpaths.append(os.path.join(dir, name))
    return fpaths

  def clear_file_list(self):
    self.file_list_ctrl.DeleteAllItems()

class NdsafirThread(threading.Thread):
  def __init__(self, fin, fout, options, *args, **kwargs):
    threading.Thread.__init__(self, *args, **kwargs)

    self.fin = fin
    self.fout = fout
    self.options = options
    self.process = None

  def run(self):
    args = [NDSAFIR_PATH, self.fin, self.fout] + self.options
    args = filter(None, args) # prune empty strings
    ## alternative program for testing purposes when there's no ndsafir...
#    args = ["perl", "-e", 'use 5.010; for ("foo", "bar", "qux") { say $_; sleep(1);}']
    send_message_to_publisher('NDSAFIR_OUTPUT', msg="$ %s\n" % (" ".join(args)))
    try:
      print args
      self.process = subprocess.Popen(args, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE)
      while self.process.poll() is None:
        out, err = self.process.communicate()
        ## FIXME this does not work great because of buffering
        send_message_to_publisher('NDSAFIR_OUTPUT', msg=out)
        send_message_to_publisher('NDSAFIR_OUTPUT', msg=err)
        time.sleep(.5)

      ## FIXME
      ## Get anything that may have been left?  We cannot because the
      ## file is already closed.  We need some other alternative.
#      out, err = self.process.communicate()
    except OSError as e:
#      out, err = self.process.communicate()
      errmsg = "Failed to nd-safir '%s': %s\n" % (self.fin, e.strerror)
      send_message_to_publisher('NDSAFIR_OUTPUT', msg=errmsg)


class NdsafirMasterThread(threading.Thread):
  def __init__(self, parent, fpaths, options, skip, abort,
               *args, **kwargs):
    """
    Args:
      parent: parent wx to where wx.Events will be post.
      fpaths: a list of file paths.
      options: list of strings, command line options to ndsafir.
      skip: a threading.Event that will signal when to skip a file.
      abort: a threading.Event that will signal when to stop everything.
    """
    threading.Thread.__init__(self, *args, **kwargs)
    self.parent = parent
    self.fpaths = fpaths
    self.options = options
    self.skip = skip
    self.abort = abort

  def run(self):
    for fin in self.fpaths:
      ## Do not forget files without file extension, or even
      ## empty filenames.
      fpath, fname = os.path.split(fin)
      fname, fext = os.path.splitext(fname)
      fout = os.path.join(fpath, fname + "_DN" + fext)

      wx.PostEvent(self.parent, NdsafirStartEvent(fin=fin))
      ndsafir = NdsafirThread(fin=fin, fout=fout, options = self.options)
      ndsafir.start()
      time.sleep(1)
      while ndsafir.is_alive():
        if self.skip.is_set() or self.abort.is_set():
          ## We trust that ndsafir does not block SIGTERM
          ndsafir.process.terminate()
          self.skip.clear()
        time.sleep(1)

      if ndsafir.process.returncode != 0:
        self.unlink(fout)

      if self.abort.is_set():
        break

      wx.PostEvent(self.parent, NdsafirEndEvent(fin=fin))

    wx.PostEvent(self.parent, NdsafirAllDoneEvent())


  def unlink(self, fout):
    try:
      os.unlink(fout)
    except OSError as e:
      if e.errno != errno.ENOENT: # No such file or directory
        errmsg = "Failed to remove output '%s': %s" % (fout, e.strerror)
        send_message_to_publisher('NDSAFIR_OUTPUT', msg=errmsg)


class NdsafirControlDialog(wx.Dialog):
  def __init__(self, parent, fpaths, options, *args, **kwargs):
    wx.Dialog.__init__(self, parent, title="ND-SAFIR running", *args, **kwargs)

    self.fpaths = fpaths
    self.options = options
    self.skip_flag  = threading.Event()
    self.abort_flag = threading.Event()

    sizer = wx.BoxSizer(wx.VERTICAL)

    ## We use the double of the number of files as range for the progress
    ## dialog.  This is because it only accepts integers and we want to
    ## set the progress to the value between the file number, e.g., we
    ## want to set the value to 0.5, when processing the first file.
    self.gauge = wx.Gauge(self, range=len(self.fpaths)*2)
    sizer.Add(self.gauge, flag=wx.TOP|wx.EXPAND|wx.LEFT|wx.RIGHT, border=16)

    self.msg = wx.StaticText(self)
    sizer.Add(self.msg, flag=wx.ALIGN_TOP|wx.ALIGN_CENTER_HORIZONTAL)

    cpane = wx.CollapsiblePane(self, label="Details")
    sizer.Add(cpane, proportion=1, flag=wx.GROW|wx.ALL)
    pane = cpane.GetPane()
    pane_sizer = wx.BoxSizer(wx.VERTICAL)
    self.output = wx.TextCtrl(pane, style=wx.TE_MULTILINE|wx.TE_READONLY|wx.HSCROLL)
    pane_sizer.Add(self.output, proportion=1, flag=wx.GROW|wx.ALL, border=16)
    pane.SetSizer(pane_sizer)

    self.btns = wx.BoxSizer(wx.HORIZONTAL)
    skip_btn = wx.Button(self, label="Skip")
    skip_btn.Bind(wx.EVT_BUTTON, self.on_skip_EVT_BUTTON)
    self.btns.Add(skip_btn)
    abort_btn = wx.Button(self, label="Abort")
    abort_btn.Bind(wx.EVT_BUTTON, self.on_abort_EVT_BUTTON)
    self.btns.Add(abort_btn)
    sizer.Add(self.btns, flag=wx.BOTTOM|wx.ALIGN_CENTER_HORIZONTAL)

    ## Events coming from the ndsafir master thread
    self.Bind(EVT_NDSAFIR_START, self.on_EVT_NDSAFIR_START)
    self.Bind(EVT_NDSAFIR_END, self.on_EVT_NDSAFIR_END)
    self.Bind(EVT_NDSAFIR_ALL_DONE, self.on_EVT_NDSAFIR_ALL_DONE)

    ## Coming from the work threads via pubsub
    Publisher.subscribe(self.on_NDSAFIR_OUTPUT, 'NDSAFIR_OUTPUT')

    self.SetSizerAndFit(sizer)

  def on_abort_EVT_BUTTON(self, event):
    self.abort_flag.set()
    self.EndModal(1)
    event.Skip()

  def on_skip_EVT_BUTTON(self, event):
    self.skip_flag.set()
    event.Skip()

  def on_EVT_NDSAFIR_START(self, event):
    self.msg.SetLabel("Denoising %s" % event.fin)
    self.gauge.SetValue(self.gauge.GetValue() +1)
    event.Skip()

  def on_EVT_NDSAFIR_END(self, event):
    self.gauge.SetValue(self.gauge.GetValue() +1)
    event.Skip()

  def on_EVT_NDSAFIR_ALL_DONE(self, event):
    self.msg.SetLabel("Finished")
    self.gauge.SetValue(self.gauge.GetRange())
    done_btn = wx.Button(self, label="Done")
    done_btn.Bind(wx.EVT_BUTTON, self.on_done_EVT_BUTTON)
    self.btns.DeleteWindows()
    self.btns.Add(done_btn)
    self.Layout()
    event.Skip()

  def on_done_EVT_BUTTON(self, event):
    self.EndModal(0)
    event.Skip()

  def on_NDSAFIR_OUTPUT(self, msg):
    if PUBSUB_OLD_API:
      self.output.write(msg.data)
    else:
      self.output.write(msg)

  def ShowModal(self):
    self.skip_flag.clear()
    self.abort_flag.clear()
    ndsafir_master = NdsafirMasterThread(self, fpaths=self.fpaths,
                                         options=self.options,
                                         skip=self.skip_flag,
                                         abort=self.abort_flag)
    ndsafir_master.start()
    wx.Dialog.ShowModal(self)


class NdsafirBatchFrame(wx.Frame):
  def __init__(self, parent=None, title="ndsafir batch run", *args, **kwargs):
    wx.Frame.__init__(self, parent=parent, title=title, *args, **kwargs)
    sizer = wx.BoxSizer(wx.VERTICAL)

    conf_sizer = wx.BoxSizer(wx.HORIZONTAL)
    self.options_panel = OptionsPanel(self)
    conf_sizer.Add(self.options_panel)
    self.file_list_panel = FileListPanel(self)
    conf_sizer.Add(self.file_list_panel, proportion=1, flag=wx.EXPAND|wx.ALL)
    sizer.Add(conf_sizer, proportion=1, flag=wx.EXPAND|wx.ALL)

    btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
    help_btn = wx.Button(self, label="Help")
    help_btn.Bind(wx.EVT_BUTTON, self.on_help_EVT_BUTTON)
    btn_sizer.Add(help_btn)

    btn_sizer.AddStretchSpacer()

    exit_btn = wx.Button(self, label="Exit")
    exit_btn.Bind(wx.EVT_BUTTON, self.on_exit_EVT_BUTTON)
    btn_sizer.Add(exit_btn)

    go_btn = wx.Button(self, label="Go")
    go_btn.Bind(wx.EVT_BUTTON, self.on_go_EVT_BUTTON)
    btn_sizer.Add(go_btn)

    sizer.Add(btn_sizer, flag=wx.EXPAND)
    self.SetSizerAndFit(sizer)


  def on_help_EVT_BUTTON(self, event):
    webbrowser.open("http://micronwiki.bioch.ox.ac.uk/wiki/Ndsafir")
    event.Skip()

  def on_exit_EVT_BUTTON(self, event):
    self.Close()
    event.Skip()

  def on_go_EVT_BUTTON(self, event):
    wx.CallAfter(self.go)
    event.Skip()

  def go(self):
    fpaths = self.file_list_panel.get_filepaths()
    options = self.options_panel.command_line_options()

    dialog = NdsafirControlDialog(self, fpaths=fpaths, options=options)
    dialog.ShowModal()

    ## Ideally, we would delete only the items that got properly denoised
    self.file_list_panel.clear_file_list()

if __name__ == "__main__":
  app = wx.App(False)
  frame = NdsafirBatchFrame()
  frame.Show()
  app.MainLoop()
