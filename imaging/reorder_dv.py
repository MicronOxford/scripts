#!/usr/bin/env python
## Copyright (C) 2017 David Pinto <david.pinto@bioch.ox.ac.uk>
##
## This program is free software: you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation, either version 3 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program.  If not, see <http://www.gnu.org/licenses/>.

## Problem::
##
## The data is in an array with shape (N,1,A*P*Z,512,512),
##
## Where:
## N= number of Wavelengths,
## A= Num angles,
## P= num phases,
## Z= number of Z slices,
##
## The actual order of A, P, Z can be different but the one we use at
## the moment is Z,P,A
##
## Ie Z changes most slowly, then phase, finally A changing most
## rapidly.
##
## We need data to be output as
##
## (A,Z,P,W,512,512)

import numpy

def reorder(data, order_in, order_out):
  assert sorted(order_in) == sorted(order_out), \
         "ORDER_IN and ORDER do not have same elements"
  assert len(set(order_in)) == len(order_in), \
         "ORDER_IN and ORDER_OUT can't have repeated elements"
  dim_map = dict(zip(order_in, range(len(order_in))))
  return numpy.transpose(data, [dim_map[i] for i in order_out])


def test_reorder():
  a = 3
  p = 5
  z = 8
  x = 10
  y = 10
  zpa = z*p*a
  im = numpy.ones((zpa, x, y), numpy.uint8)
  im *= numpy.arange(zpa).reshape((zpa, 1, 1))
  im = im.reshape((z, p, a, x, y))
  order_in = ("z", "p", "a", "x", "y")
  order_out = ("a", "z", "p", "x", "y")
  imr = reorder (im, order_in, order_out)
  assert imr.shape == (a, z, p, x, y)
  assert numpy.alltrue(imr[0,0,0,:,:] == 0)
  assert numpy.alltrue(imr[1,0,0,:,:] == 1)
  assert numpy.alltrue(imr[0,1,0,:,:] == p*a)
  assert numpy.alltrue(imr[0,0,1,:,:] == a)

  t = 1
  w = 2
  wtzpa = w*zpa
  im = numpy.ones((wtzpa, x, y), numpy.uint8)
  im *= numpy.arange(wtzpa).reshape((wtzpa, 1, 1))
  im = im.reshape((w, t, z, p, a, x, y))
  order_in = ("w", "t", "z", "p", "a", "x", "y")
  order_out = ("w", "t", "a", "z", "p", "x", "y")
  imr = reorder (im, order_in, order_out)
  assert imr.shape == (w, t, a, z, p, x, y)
  assert numpy.alltrue(imr[0,0,0,0,0,:,:] == 0)
  assert numpy.alltrue(imr[0,0,1,0,0,:,:] == 1)
  assert numpy.alltrue(imr[0,0,0,1,0,:,:] == p*a)
  assert numpy.alltrue(imr[0,0,0,0,1,:,:] == a)
  assert numpy.alltrue(imr[1,0,0,0,0,:,:] == zpa)
  assert numpy.alltrue(imr[1,0,1,0,0,:,:] == zpa+1)
  assert numpy.alltrue(imr[1,0,0,1,0,:,:] == zpa+(p*a))
  assert numpy.alltrue(imr[1,0,0,0,1,:,:] == zpa+a)

if __name__ == "__main__":
  test_reorder()
