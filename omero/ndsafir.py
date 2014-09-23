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
import struct

import omero_scripts_processing
import omero.scripts
import voluptuous
import numpy

class dv_utils():
  """ Small utils for handling DV and MRC files.

  These are temporary functions which I aim to move onto Pillow as
  time allows.
  """

  def __init__(self, img):
    self.img = img
    self.maybe_mrc = True
    ## Read in the basic header. If it doesn't even have it, it
    ## is definitely not a MRC based image file
    self.header = self.img.getFileInChunks(buf = 1024).next()
    if len(self.header) < 1024:
      self.maybe_mrc = False

  def if_maybe_mrc(func):
    """Decorator for is_dvtype type of functions."""
    def wrapper(self):
        if self.maybe_mrc:
          return func(self)
        else:
          return False
    return wrapper

  @if_maybe_mrc
  def is_image2000(self):
    """Return true if image is a MRC image2000 file.

    Returns:
      A boolean value. True if img is an mrc image 2000 file,
      False otherwise.
    """
    ##  * Original MRC image2000 specs:
    ##      http://www2.mrc-lmb.cam.ac.uk/image2000.html

    ## New versions of the MRC format are supposed to have this signature
    ## but I'm still unsure if Priism is capable of reading them...
    if self.header[52*4:53*4] == "MAP ":
      return True
    else:
      return False

  @if_maybe_mrc
  def is_mrc(self):
    """Return true if image is an mrc (original) image file.

    There seems to be multiple variants of the MRC format. The
    very old original one, a old one which Priism uses (imsubs),
    another proprietary bastardized version by API/GE used by
    softWoRx, a version used by Image2000, and probably many
    others.

    For the very old versions there is no "signature" on the
    header, we can only check if the file extension is mrc and
    hope for the best.

    Returns:
      A boolean value. True if img is an mrc file, False
      otherwise.
    """
    ## Docs:
    ##  * IMOD reference for file specs with mention of old format:
    ##      http://bio3d.colorado.edu/imod/doc/mrc_format.txt
    ##  * Priism take on the subject:
    ##      http://msg.ucsf.edu/IVE/IVE4_HTML/mrc2image2000.html
    ## old versions will need to check with file extension
    ext = os.path.splitext(self.img.getName())[1]
    if ext.lower() == ".mrc":
      return True
    else:
      return False

  @if_maybe_mrc
  def is_dv(self):
    """Return true if image has a dv image file.

    Returns:
      A boolean value. True if img is a dv file, False otherwise.
    """
    ## According to bioformats's DeltavisionReader.java (which is GPL), a
    ## DV file must read 0xa0c0 or 0xc0a0 at pos 96.
    m = struct.unpack("H", self.header[96:98])[0]
    if m == 49312 or m == 41152:
      return True
    else:
      return False

  @if_maybe_mrc
  def is_imsubs(self):
    """Return true if image is a MRC IMSubs.

    Returns:
      A boolean value. True if img is an MRC IMSubs file,
      False otherwise.
    """
    ##  * Format specs from IVE:
    ##      http://www.msg.ucsf.edu/IVE/IVE4_HTML/IM_ref2.html
    m = struct.unpack("H", self.header[96:98])[0]
    if m == -16224:
      return True
    else:
      return False

  @staticmethod
  def is_tiff(img):
    """Return true if image is a tiff image file.

    Args:
      img: omero.gateway._OriginalFileWrapper

    Returns:
      A boolean value. True if img is a tiff file,
      False otherwise.
    """
    rv = False
    s = img.getFileInChunks(buf=4).next()
    if len(s) >= 4:
      bito = s[0:2]
      magk = s[2:4]
      if ((bito == "II" and struct.unpack("<H", magk)[0] == 42) or
          (bito == "MM" and struct.unpack(">H", magk)[0] == 42)):
        rv = True
    return rv

  @staticmethod
  def any2imsubs(img, f):
    """Save image into a mrc Imsubs (Priism sub-format) file.

    Priism comes a small application (tiff2mrc) that makes this
    conversion.  However, it is unable to handle the ome tiff
    files (can't convert separately sampled tiled image), and
    does not preserve the original image precision.

    If the image is already an mrc file, you're better off
    using the getFileInChunks() method for an individual file.

    One day we should contribute this to PIL.

    Args:
      img: omero.gateway._ImageWrapper

    Returns:
      A string with the filepath for the generated MRC file.

    Raises:
      TypeError: if the image is of a type, or has features,
        not supported by the MRC format.  For example,
        binary, double, and uint32 precision are not
        suported, or images with more than 5 channels.
    """
    ## File format specs - http://www.msg.ucsf.edu/IVE/IVE4_HTML/IM_ref2.html

    ncols = img.getSizeX()
    nrows = img.getSizeY()
    nzsec = img.getSizeZ()
    nchan = img.getSizeC()
    ntime = img.getSizeT()

    f.write(struct.pack("2i", ncols, nrows))          # width and height
    f.write(struct.pack("1i", nzsec * nchan * ntime)) # number of sections

    pixel_types = {
      "int8"    : None,
      "uint8"   : 0,
      "int16"   : 1,
      "uint16"  : 6,
      "int32"   : 7,
      "uint32"  : None,
      "float"   : 2,
      "double"  : None,
      "bit"     : None,
      "complex" : 4,
      "doublecomplex" : None,
    }

    prc = pixel_types[img.getPixelsType()] # image precision
    ## uint8 has a value of zero which evaluates as false.  Because of
    ## that, we use "is None" instead of "not prc"
    if prc is None:
      raise omero_scripts_processing.invalid_image(
        "this image data type cannot be converted to mrc")

    f.write(struct.pack("4i",
      prc,      # image mode/precision
      0, 0, 0,  # starting point of sub image
    ))

    ## Sampling frequencies in X, Y, and Z
    f.write(struct.pack("3i", ncols, nrows, nzsec))

    ## Cell dimensions (in ångströms). For non-crystallographic data,
    ## set to the sampling frequency times the x pixel spacing.
    f.write(struct.pack("3f",
      ncols * img.getPixelSizeX() * 10000,
      nrows * img.getPixelSizeY() * 10000,
      nzsec * img.getPixelSizeZ() * 10000,
    ))

    f.write(struct.pack("3f", 90, 90, 90))  # cell angles (usually set to 90)
    f.write(struct.pack("3i", 1, 2, 3))     # maps axis to dimension.

    ## These values are supposed to be only for the first 2D image/plane
    px = img.getPrimaryPixels()
    p = px.getPlane()
    f.write(struct.pack("3f", p.min(), p.max(), p.mean()))

    f.write(struct.pack("1i", 0))         # Space group number
    f.write(struct.pack("1i", 0))         # extended header size
    f.write(struct.pack("1h", -16224))    # ID value
    f.write(struct.pack("1h", 0))         # unused
    f.write(struct.pack("1i", 0))         # starting time index
    f.write(struct.pack("24s", " " * 24)) # blank section
    f.write(struct.pack("2h", 0, 0))      # organization of extended header
    f.write(struct.pack("2h", 1, 1))      # sub-resolution version of image

    ## Minimum and maximum intensity of each other channel. If there is
    ## a fifth channel, its data will be later on the header.
    for chan in range(1, min(4, nchan)):
      p = px.getPlane(theC = chan)
      f.write(struct.pack("2f", p.min(), p.max()))
    f.write(struct.pack("%if" % ((4 - nchan) *2), *[0]*((4 - nchan) *2)))

    f.write(struct.pack("1h", 0))       # image type
    f.write(struct.pack("1h", 0))       # lens identification number
    f.write(struct.pack("4h", *[0]*4))  # depends on image type

    ## Minimum and maximum intensity of a 5th channel
    if nchan < 5:
      f.write(struct.pack("2f", 0.0, 0.0))
    elif nchan == 5:
      p = px.getPlane(theC = 4)
      f.write(struct.pack("2f", p.min(), p.max()))
    else:
      raise omero_scripts_processing.invalid_image(
        "mrc file cannot have more than 5 channels")

    f.write(struct.pack("1h", ntime))   # number of time points
    f.write(struct.pack("1h", 0))       # image sequence (0 = ZTW)
    f.write(struct.pack("3f", 0, 0, 0)) # X, Y, and Z tilt angle

    ## Number and lengths of wavelengths
    f.write(struct.pack("1h", nchan))
    for chan in img.getChannels():
      ## Some channels may not have wavelength information, in which
      ## case getEmissionWave returns None.
      f.write(struct.pack("1h", chan.getEmissionWave() or 0))
    for _ in range(0, 5-nchan):
      f.write(struct.pack("1h", 0))

    f.write(struct.pack("3f", 0, 0, 0))     # origin of image
    f.write(struct.pack("i", 0))            # number of useful titles
    f.write(struct.pack("800s", " " * 800)) # space for 10 titles

    for w in range(0, nchan):
      for t in range(0, ntime):
        for z in range(0, nzsec):
          p = px.getPlane(theC=w, theT=t, theZ=z)
          ## https://github.com/openmicroscopy/openmicroscopy/issues/2547
          if p.dtype == "float64":
            p = p.astype("float32")
          p = numpy.flipud(p)
          p.tofile(f.file)
    f.flush()


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
      fdv = dv_utils(f)
      if fdv.is_dv() or fdv.is_image2000() or fdv.is_imsubs():
        ext = os.path.splitext(f.getName())[1]
        self.fin = self.get_tmp_file(suffix = ext)
        for c in f.getFileInChunks():
          self.fin.write(c)
        self.fin.flush()
        break
    else:
      self.fin = self.get_tmp_file(suffix = ".mrc")
      dv_utils.any2imsubs(self.parent, self.fin)

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

