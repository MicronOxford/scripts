#!/cygdrive/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe
## Author: David Pinto <david.pinto@bioch.ox.ac.uk>
## This program is granted to the public domain.

## Problem:
##    We moved our Imaris installation from MicronB to Z1-workstation.
##    We sent an email to all the users and posted a note about it right
##    above the monitor.  Unfortunately, most users are illeterate.
##
## Objective:
##    If a user tries to start Imaris on this system, or open an image
##    which before had Imaris as default application, remind them that
##    the Imaris installation moved to another system.
##
## Solution:
##    Create a shortcut, with the Imaris icon, which is actually runs a
##    powershell script that tells the user to go to the other computer.
##    Put that shortcut where previously was the Imaris executable.
##
## Target:
##    MicronB
##
## Notes:
##  Actually, we do not have this as a script but as shortcut with the code
##  inlined:
##
##    C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe -WindowStyle Hidden -Command "& {[System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms');[System.Windows.Forms.MessageBox]::Show('Go to Z1-workstation (the computer on your left)');}"
##
##  That is the reason why the message is so small, so it fits under 255
##  characters.

[System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms');
[System.Windows.Forms.MessageBox]::Show('Go to Z1-workstation (the computer on your left)');

