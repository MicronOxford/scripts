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

## Problem:
##    Users do not set pixel size correctly when taking images with
##    SoftWoRx.  This affects deconvolution negatively.  While there
##    is a tool to do it interactively, it's a pain to do it in batch.
##
## Solution:
##    Not the cleanest thing but this script will replace the pixel
##    spacing information in the file with "fix" (get it from a file
##    with the correct information)

import os
import sys
import fnmatch

fix = '\xb8\x1e\x85=\xb8\x1e\x85='

for root, dirnames, filenames in os.walk (sys.argv[-1]):
  for filename in fnmatch.filter (filenames, '*.dv'):
    path = os.path.join (root, filename)
    with open (path, "r") as f:
      data = f.read ()

    with open (path, "w") as f:
      f.write (data[0:40])
      f.write (fix)
      f.write (data[48:])

