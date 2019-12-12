#!/bin/sh
## Author: David Pinto <david.pinto@bioch.ox.ac.uk>
## This program is granted to the public domain.

## Problem:
##    The OMXmaster system, which does the image acquisition, sits on the OMX
##    room and its software only runs on Windows.  The OMXsi, which does the
##    image reconstruction and display, uses softWoRx which only runs on Linux
##    and sits on the image analysis room.  In addition, having OMXsi on the
##    microscope room means no one else can use it at the same time, and it's
##    heavy processing heats the room too much.  But the user will still want
##    to see the reconstructed images on OMXmaster.
##
## Objective:
##    Have a single icon on the desktop that connects to OMXsi and runs
##    SoftWoRx for each user, as if integrated into Windows.  Previous
##    solution was a Virtual Machine on OMXmaster running Xubuntu, with a
##    single admin account, from where users could use to ssh into OMXsi.
##
##
## Solution:
##    Install Cygwin and its X server, and start xinit with this script which
##    immediately runs softWoRx remotely.  The xterm window must be kept open
##    during the whole session.  Also, the option -nowgl must be passed to the
##    X server if running in multiwindow mode since opengl rendering into
##    non-toplevel windows doesn't work very well, i.e., this script should be
##    called like so:
##
##      xinit /etc/X11/xinit/runDV.xinitrc -- -multiwindow -nowgl
##
## Target:
##    OMXmaster2

host="bioch2125.bioch.ox.ac.uk"
user=`whoami`
app="/opt/bin/runDV"

xterm -e ssh -Y $user@$host $app
