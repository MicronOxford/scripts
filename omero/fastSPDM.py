#!/usr/bin/env python
# -*- coding: utf-8 -*-

## Copyright (C) 2014 David Pinto <david.pinto@bioch.ox.ac.uk>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU Affero General Public License as published by
## the Free Software Foundation; either version 3 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU Affero General Public License for more details.
##
## You should have received a copy of the GNU Affero General Public License
## along with this program; if not, see <http://www.gnu.org/licenses/>.

import os
import errno

import omero_scripts_processing
import omero.scripts
import voluptuous

class fastSPDM(omero_scripts_processing.matlab_block):
  """Localization microscopy with fastSPDM.

  Options
  -------
  Documentation for each of the options is available at the
  [Micron wiki](http://micronwiki.bioch.ox.ac.uk/wiki/Localization_Microscopy#Software)

  References
  ----------
  Frederik Grüll, Manfred Kirchgessner, Rainer Kaufmann, Michael
  Hausmann, and Udo Kebschull. "Accelerating image analysis for
  localization microscopy with FPGAs." In Field Programmable Logic
  and Applications (FPL), 2011 International Conference on, pp. 1-5.
  IEEE, 2011.
  """

  title = "Reconstruct localization microscopy with fastSPDM"
  doc = __doc__

  version      = "0.0.1"
  authors      = ["David Pinto"]
  institutions = ["Micron, University of Oxford"]
  contact      = "david.pinto@bioch.ox.ac.uk"

  schema = voluptuous.Schema(
    {
      "gc"      : voluptuous.All(long, voluptuous.Range(min = 0)),
      "pxsz"    : voluptuous.All(long, voluptuous.Range(min = 1)),
      "mfcorr"  : bool,
      "nfcorr"  : bool,
    },
    required = True,
  )

  interpreter = "/usr/local/MATLAB/R2010b/bin/matlab"
  interpreter_options = ["-nodisplay", "-nosplash"]

  def __init__(self):
    super(fastSPDM, self).__init__()
    self.args = [
      omero.scripts.Int(
        "gc",
        optional    = False,
        default     = 65,
        description = "Gain correction",
        grouping    = "1",
      ),
      omero.scripts.Int(
        "pxsz",
        optional    = False,
        default     = 20,
        description = "Pixel size",
        grouping    = "2",
      ),
      omero.scripts.Bool(
        "mfcorr",
        optional    = False,
        default     = False,
        description = "Filter long-lasting fluorescence",
        grouping    = "3",
      ),
      omero.scripts.Bool(
        "nfcorr",
        optional    = False,
        default     = False,
        description = "Filter fluorophore blinking",
        grouping    = "4",
      ),
    ]

  def parse_options(self):
    """Validate list of parameters.

    Raises:
        omero_scrits_processing.invalid_parameter
    """
    try:
      self.options = self.schema(self.options)
    except voluptuous.Invalid as e:
      raise omero_scripts_processing.invalid_parameter(str(e))

  def create_code(self):
    """Create Matlab code to be used."""

    self.code = (
      "addpath ('/usr/local/lib/MATLAB/site-toolboxes/dipimage/dipimage');\n"
      "dip_initialise ('silent');\n"
      "addpath ('/home/carandraug/dstorm-tst/locmic/');\n"
      "fastSPDMome ('%s', %i, %s, %s, %i, %s);\n"
    ) % (self.fin.name, self.options['gc'],
         self.bool_py2m(self.options['mfcorr']),
         self.bool_py2m(self.options['nfcorr']),
         self.options['pxsz'], self.bool_py2m(False))

    self.code = self.protect_exit(self.code)

  def run_matlab(self):
    ## 10min should be enough
    super(fastSPDM, self).run_matlab(timeout = 10)

  def send_child(self):
    child_sufix = "_imstres_pz_%i.tif" % self.options["pxsz"]
    fout_name = os.path.splitext(self.fin.name)[0] + child_sufix
    ## FIXME we should not have to actually open a file
    self.fout = open(fout_name, "r")

    self.basename = os.path.splitext(self.parent.getName())[0]
    self.child_name = self.basename + child_sufix

    super(fastSPDM, self).send_child()

    ## Because this was not created as temporary file...
    self.fout.close()
    try:
      os.unlink(fout_name)
    except OSError as e:
      if e.errno != errno.ENOENT: # No such file or directory
        raise

if __name__ == "__main__":
  chain = omero_scripts_processing.chain([fastSPDM()])
  chain.launch()

