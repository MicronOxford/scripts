## Copyright (C) 2014 Carnë Draug <carandraug+dev@gmail.com>
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

"""Get and save the 4 lines profile centered at set of point selections.

Given an image with multiple point selections made, gets the horizontal,
vertical, and the two 45 degrees lines profile for each. The data is then
saved into a CVS file, one line profile per column.

Purpose:
    Mutiple point selections were made on the image via some other
    method. The images are transverse plane of centrioles and the
    points correspond to the centriole center. The obtained 4 line
    profile will be later used to measure the diameter.

Target:
    "Saroj Saurya <saroj.saurya@path.ox.ac.uk>" from Jordan Raff lab.
"""

import math
import csv
import os.path

import ij.IJ
import ij.gui
import ij.io

## Settings
line_length = 30
line_width  = 1

def ij_error(msg):
    """Exit with ImageJ error message but also raise Python exception.

    Args:
        msg: error message to be displayed.

    Raises:
        Always an Exception.
    """
    ij.IJ.error("Line profiles", msg)
    raise Exception(msg)

def get_lines_ends(im, x, y, l):
    """Compute end points of the 4 lines.

    Args:
        im: ImagePlus instance of the image to make the selection. Required
            to confirm that coordinates stay withing image bounds.
        x: center of line x coordinate
        y: center of line y coordinate
        l: desired length of the line

    Output:
        A list of 4 elements tuple, with x and y coordinates value for use
        in the ij.gui.Line constructor. Typically, this will be a 4 elements
        list but some, or even all, may be outside image bounds in which case
        they will be removed.
    """
    hl  = float(l) / 2            # half length
    cl = math.sqrt((hl**2) / 2);  # catheti length
    c = [
        (x, y - hl, x, y + hl), # vertical line
        (x - hl, y, x + hl, y), # horizontal line
        (x - cl, y - cl, x + cl, y + cl), # top left -> bottom right
        (x + cl, y - cl, x - cl, y + cl), # top right -> bottom left
    ]
    def within_bounds(sc):
        return (sc[0] >= 0 and sc[1] >= 0
            and sc[2] <= im.getHeight() and sc[3] <= im.getWidth())

    return filter(lambda x: within_bounds(x), c)

def default_save_file(im, suf):
    """Compute best path to save data associated with an image.

    This will be same directory where the image originally was read from. If
    for some reason such data is not available, it uses ImageJ default
    directory.

    Args:
        img: ImagePlus object of image from where data originated.
        suf: suffix added to the image filename.

    Output:
        A 2 element tuple, the first being the absolute directory path, and
        the second a filename.
    """
    fileinfo = im.getOriginalFileInfo()
    ## This covers cases of images opened via non-path methods (such as web
    ## samples which will have fileinfo but not a directory), and completely
    ## new images will not even return a fileinfo
    d = ij.io.OpenDialog.getDefaultDirectory()
    if fileinfo and fileinfo.directory:
        d = fileinfo.directory
    if fileinfo and fileinfo.fileName:
        n = fileinfo.fileName + "-" + suf
    else:
        n = suf
    return (d, n)

im = ij.IJ.getImage()
roi = im.getRoi()
if not roi:
    ij_error("No selection found on current image.")
elif not isinstance (roi, ij.gui.PointRoi):
    ij_error("Selection must be a set of points only.")

data = [] # will be an array of arrays, each array a line profile

p_roi = roi.getPolygon()
for pc in zip(p_roi.xpoints, p_roi.ypoints):
    for ends in get_lines_ends(im, pc[0], pc[1], line_length):
        line = ij.gui.Line(*ends)
        line.setImage(im)
        line.setStrokeWidth(line_width)
        data.append(line.getPixels())

def_fp = default_save_file(im, "data") + tuple([".cvs"])
fp = ij.io.SaveDialog("Select file to save data in CSV format", *def_fp)

## FIXME: submit method to ImageJ that cheks if a path was selected
if not fp.getDirectory():
    ij_error("No file to save selected.")

fpath = os.path.join(fp.getDirectory(), fp.getFileName())
try:
    f = open(fpath, 'wb')
    try:
        writer = csv.writer(f)
        writer.writerows(zip(*data))
    except Exception, ie:
        os.unlink(fpath)
        raise ie
    finally:
        f.close()
except Exception, e:
    ij_error("Error writing CSV file: " + str(e))

