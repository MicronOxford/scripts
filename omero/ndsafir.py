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
import os.path

import omero_scripts_processing
import omero.scripts
import voluptuous
import dv_utils

class ndsafir(omero_scripts_processing.bin_block):
  """Denoise with NDSAFIR (N Dimensional Structure Adaptive FILtering).

  This patch-based denoising algorithm is described in Boulanger,
  J. et al (2007).  It basically makes use of redundancy in an image
  sequence (i.e. multiple samples of the same features) to average
  equivalent pixels and reduce the apparent noise level.  You can also
  refer to the ndsafir HTML manual from the Sedat lab, but be aware that
  the description of the iterations is somewhat confusing.

  Options
  -------

  Documentation for each of the options is available at the [Micron wiki]
  (http://micronwiki.bioch.ox.ac.uk/wiki/Ndsafir)

  Terms and conditions
  --------------------

  Due to the restrictive terms of the MTA (Material Transfer Agreement),
  please discuss with Micron before using data denoised by this algorithm
  for external presentation or publication.

  References
  ----------

  Jérôme Boulanger, Charles Kervrann, and Patrick Bouthemy. "Space-time
  adaptation for patch-based image sequence restoration." Pattern Analysis
  and Machine Intelligence, IEEE Transactions on 29.6 (2007): 1096-1102.
  """

  title = "Denoise image with NDSAFIR"
  doc = __doc__

  version      = "0.0.7"
  authors      = ["David Pinto"]
  institutions = ["Micron, University of Oxford"]
  contact      = "david.pinto@bioch.ox.ac.uk"

  schema = voluptuous.Schema(
    {
      "time"              : bool,
      "wavelength"        : bool,
      "z-slices"          : bool,
      "patch_radius"      : voluptuous.All(long, voluptuous.Range(min = 1)),
      "island_threshold"  : voluptuous.All(float, voluptuous.Range(min = 0)),
      ## FIXME https://github.com/openmicroscopy/openmicroscopy/issues/2449
#      "adaptability"
#        : voluptuous.All(float, voluptuous.Range(min = 0, max = 10)),
      "iterations"
        : voluptuous.All(long, voluptuous.Range(min = 1, max = 11)),
      "noise_model"
        : voluptuous.All(str, voluptuous.Any("gaussian + poisson",
                                             "poisson",
                                             "gaussian",
                                             "auto")),
      voluptuous.Optional("sampling")
        : voluptuous.All(float, voluptuous.Range(min = 0)),
    },
    required = True,
  )

  def __init__(self, bin_path):
    super(ndsafir, self).__init__(bin_path)
    self.args = [
      ## Defaults chosen for the actual denoising are the same as the
      ## default values of ndsafir when possible. However, some defaults
      ## are image dependent, so we can't replicate them in the GUI

      ## Group 1 - ndsafir dimensionality
      ## FIXME our version of nd-safir crashes if we don't use time
#      omero.scripts.Bool(
#          "time",
#          optional    = False,
#          default     = True,
#          description = "Look for similarities over multiple time points",
#          grouping    = "01",
#      ),
      omero.scripts.Bool(
          "wavelength",
          optional    = False,
          default     = False,
          description = "Look for similarities in multiple channels",
          grouping    = "02",
      ),
      omero.scripts.Bool(
          "z-slices",
          optional    = False,
          default     = True,
          description = "Look for similarities through the image volume",
          grouping    = "03",
      ),

      ## Group 2 - other ndsafir options
      omero.scripts.Int(
          "iterations",
          optional    = False,
          default     = 4,
          description = "Maximum number of iterations",
          grouping    = "04",
      ),
      omero.scripts.Int(
          "patch_radius",
          optional    = False,
          default     = 1,
          description = "Sets the patch radius to be N pixels",
          grouping    = "05",
      ),
      omero.scripts.Int(
          ## ndsafir default is 1 + patch radius
          "sampling",
          optional    = True,
          description = "Set sampling interval (defaults to 1+patch radius)",
          grouping    = "06",
      ),
      omero.scripts.String(
          "noise_model",
          optional    = False,
          default     = "gaussian + poisson",
          values      = ["gaussian + poisson", "gaussian", "auto"],
          description = "Select how to model the noise",
          grouping    = "07",
      ),
      ## FIXME https://github.com/openmicroscopy/openmicroscopy/issues/2449
#      omero.scripts.Float(
#          "adaptability",
#          optional    = False,
#          default     = 0.0,
#          description = "Sets the sampling interval",
#          grouping    = "08",
#      ),
      omero.scripts.Float(
          "island_threshold",
          optional    = False,
          default     = 4.0,
          description = "Sets the sampling interval",
          grouping    = "09",
      ),
    ]

  def get_parent(self, parent):
    """Get a MRC file from the parent image.

    If the parent image is an MRC file (DV files are based on MRC files),
    the original file is downloaded.  Otherwise, creates a MRC file from
    the metadata available on omero.
    """
    super(ndsafir, self).get_parent(parent)

    ## XXX must understand when does an image have multiple imported image
    ## files. Depending on the answer, may require some changes.
    ## Hopefully it is for cases when a ND image comes from multiple
    ## files in which case they wouldn't be mrc files anyway.
    for f in self.parent.getImportedImageFiles():
      fdv = dv_utils.dv_utils(f)
      if fdv.is_dv() or fdv.is_image2000() or fdv.is_imsubs():
        ext = os.path.splitext(f.getName())[1]
        self.fin = self.get_tmp_file(suffix = ext)
        for c in f.getFileInChunks():
          self.fin.write(c)
        self.fin.flush()
        break
    else:
      self.fin = self.get_tmp_file(suffix = ".mrc")
      dv_utils.dv_utils.any2imsubs(self.parent, self.fin)

  def parse_options(self):
    """Build list of input args to call ndsafir.

    Raises:
        omero_scripts_processing.invalid_parameter
    """
    super(ndsafir, self).parse_options()

    ## FIXME our version of nd-safir crashes if we don't use time
    self.options["time"] = True

    try:
      self.options = self.schema(self.options)
    except voluptuous.Invalid as e:
      raise omero_scripts_processing.invalid_parameter(str(e))

    ## Maximum number of iterations is less when using time
    if self.options["time"] and self.options["iterations"] > 5:
      raise omero_scripts_processing.invalid_parameter(
        "if `time', `iterations' must be less than 6")

    opts = [] # list for command line options

    ## Handle the dimensionality option.
    ## For 2D and 5D, it is simple but for the other case, we must
    ## specify the number of dimensions and the dimension type,
    ## e.g., -4d=zt or -3d=w
    dims = ""
    for key in ["z-slices", "time", "wavelength"]:
      if self.options[key]:
        dims += key[0]
    ndims = 2 + len(dims)
    if ndims == 2:
      dopt = "-2d"
    elif ndims > 2 and ndims < 5:
      dopt = "-%id=%s" % (ndims, dims)
    else:
      dopt = "-5d"
    opts.append(dopt)

    ## The option value for "gaussian + poisson" is just "poisson"
    if self.options["noise_model"] == "gaussian + poisson":
      self.options["noise_model"] = "poisson"

    ## The "sampling" option is a bit trickier because it is optional,
    ## and its default is patch radius +1.
    ## XXX: There will be no keys for non-set, optional values, not even
    ## None, see https://github.com/openmicroscopy/openmicroscopy/issues/2462
    if "sampling" not in self.options:
      self.options["sampling"] = float(self.options["patch_radius"] +1)

    opts += [
      "-iter=%i"      % (self.options["iterations"]),
      "-p=%i"         % (self.options["patch_radius"]),
      "-noise=%s"     % (self.options["noise_model"]),
      ## FIXME https://github.com/openmicroscopy/openmicroscopy/issues/2449
#      "-adapt=%f"     % (self.options["adaptability"]),
      "-island=%f"    % (self.options["island_threshold"]),
      "-sampling=%i"  % (self.options["sampling"]),
    ]

    self.bin_opts = opts

  def process(self):
    self.fout = self.get_tmp_file(suffix = ".mrc")
    self.flog = self.get_tmp_file(suffix = ".log")

    ## ndsafir is a bit weird about where it prints log.  The actual log
    ## is being printed to stderr.  Then, it appears it has a bug which
    ## causes the sampling value to be printed to stdout during the first
    ## iteration. We throw this away by redirecting stdout to devnull.
    with open(os.devnull, "w") as null:
      super(ndsafir, self).process(
        [self.bin, self.fin.name, self.fout.name ] + self.bin_opts,
        stderr  = self.flog,
        stdout  = null,
      )

  def send_child(self):
    self.basename = os.path.splitext(self.parent.getName())[0]
    self.child_name = self.basename + "_DN.mrc"

    super(ndsafir, self).send_child()

if __name__ == "__main__":
  chain = omero_scripts_processing.chain([
    ndsafir(bin_path = "/usr/local/priism/bin/ndsafir_priism")
  ])
  chain.launch()

