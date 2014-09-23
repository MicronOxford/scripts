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

import os.path
import struct

import omero_scripts_processing
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

