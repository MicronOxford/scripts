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

import os
import webbrowser

import wx
import wx.lib.intctrl
import wx.lib.mixins.listctrl

NDSAFIR_PATH = "/opt/priism/bin/ndsafir_priism"

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
    sizer.Add(wx.StaticText(self, label="Patch radius"))
    sizer.Add(patch_radius, flag=wx.ALIGN_RIGHT|wx.EXPAND)
    self.options.append(patch_radius)

    noise_model = OptionsPanel.NoiseModelCtrl(self)
    sizer.Add(wx.StaticText(self, label="Noise model"))
    sizer.Add(noise_model, flag=wx.ALIGN_RIGHT|wx.EXPAND)
    self.options.append(noise_model)


    sampling = OptionsPanel.IntOptionCtrl(self, arg_name="sampling", min=1)
    sizer.Add(wx.StaticText(self, label="Sampling"))
    sizer.Add(sampling, flag=wx.ALIGN_RIGHT|wx.EXPAND)
    self.options.append(sampling)

    island = OptionsPanel.FloatOptionCtrl(self, arg_name="island", min=0)
    sizer.Add(wx.StaticText(self, label="Island Threshold"))
    sizer.Add(island, flag=wx.ALIGN_RIGHT|wx.EXPAND)
    self.options.append(island)

    adaptability = OptionsPanel.FloatOptionCtrl(self, arg_name="adapt",
                                                min=0, max=10)
    sizer.Add(wx.StaticText(self, label="Adaptability"))
    sizer.Add(adaptability, flag=wx.ALIGN_RIGHT|wx.EXPAND)
    self.options.append(adaptability)

    self.SetSizer(sizer)

  def create_command_line_options(self):
    return " ".join([x.command_line_argument() for x in self.options])

  class CommandLineCtrl:
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



class AutoWidthListCtrl(wx.ListCtrl, wx.lib.mixins.listctrl.ListCtrlAutoWidthMixin):
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
    self.file_list_ctrl.DeleteAllItems()
    event.Skip()


class NdsafirApplication():
  def __init__(self):
    raise NotImplementedError()

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
    print self.options_panel.create_command_line_options()
    event.Skip()

if __name__ == "__main__":
  app = wx.App(False)
  frame = NdsafirBatchFrame()
  frame.Show()
  import wx.lib.inspection
  wx.lib.inspection.InspectionTool().Show()
  app.MainLoop()
