#!/usr/bin/env python
# -*- coding: utf-8 -*-

## Copyright (C) 2014-2017 David Pinto <david.pinto@bioch.ox.ac.uk>
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

## Usage:
## export PYTHONPATH for OMERO e.g.  export PYTHONPATH=PYTHONPATH:/opt/OMERO.py-5.3.5-ice35-b73/lib/python/
## run ./omero2mrc.py group_id image_id OutputPath

import getpass
import struct
import sys

import numpy
import omero.gateway

def parse_inputs():
  argv = sys.argv
  for x in argv:
      print str(x)
  if len(argv) == 2:
    image_id = int(argv[1])
    group_id = 1004
  elif len(argv) == 3:
    group_id = int(argv[1])
    image_id = int(argv[2])
  else:
    raise RuntimeError("Please specify omero ID and output file name")
  outfile = str(image_id)+".mrc"
  print 'Converting ' + str(image_id)+' to mrc file ' + outfile
  return image_id, outfile ,group_id

def write_imsubs(img, image_id):
    """Save image into a mrc Imsubs (Priism sub-format) file.
    Priism comes a small application (tiff2mrc) that makes this
    conversion.  However, it is unable to handle the ome tiff files
    (can't convert separately sampled tiled image), and does not
    preserve the original image precision.
    If the image is already an mrc file, you're better off using the
    getFileInChunks() method for an individual file.
    Args:
    img: omero.gateway._ImageWrapper
    f: a file handle for a file open for writing
    Returns:
    void
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

    for ch in range(nchan):
        nchan=1
        fpath=str(image_id)+"_CH_"+str(ch)+".mrc"
        print 'test file opening'
        print fpath
        with open(fpath, "w") as fh:
            pass
        print 'passed'

        with open(fpath, "w") as f:
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
                raise TypeError("this image data type cannot be converted to mrc")

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
                raise TypeError("mrc file cannot have more than 5 channels")

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

            w=ch
            planes2get=[]
            for t in range(0, ntime):
             #print 'Converting timepoint '+ str (t) + ' of ' + str(ntime)
             for z in range(0, nzsec):
               #note order for getplanes zctList – A list of indexes: [(z,c,t), ]
               planes2get.append((z,w,t))
               planes = px.getPlanes(planes2get)

            for i, p in enumerate(planes):
               if i%nzsec==0:
                   print 'Converting timepoint '+ str(i/nzsec)+ ' of ' + str(ntime)
               ## https://github.com/openmicroscopy/openmicroscopy/issues/2547
               if p.dtype == "float64":
                 p = p.astype("float32")
               p = numpy.flipud(p)
               p.tofile(f)
            f.flush()
    return

def main():

  image_id, fpath, group_id = parse_inputs()

  hostname = "omero1.bioch.ox.ac.uk"
  username = "lina2728"
  password = getpass.getpass("Password for %s at %s:" % (username, hostname))

  conn = omero.gateway.BlitzGateway(username, password,
                                    host=hostname)
  if not conn.connect():
    raise RuntimeError("Failed to connect to OMERO server")

  #image_id = 380293
  #group_id = 1004
  conn.setGroupForSession(group_id)
  image = conn.getObject("Image", image_id)
  if not image:
    raise RuntimeError("Failed to get image with ID:%i" % image_id)

  #fpath = "/usr/people/lina2728/Live_ch2.mrc"
  write_imsubs(image, image_id)

if __name__ == "__main__":
  main()
