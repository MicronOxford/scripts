#!/usr/bin/env python
# -*- coding: utf-8 -*-

## Copyright (C) 2014 David Pinto <david.pinto@bioch.ox.ac.uk>
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

"""Clean plasmid sequence of extra features.

Displays a list of features in sequence for selection and rewrites the file
after removing them.
"""

import sys
import Bio.SeqIO
import Tkinter
import tkFileDialog

## Array of features that we will bother with. Any feature key not listed
## here will be removed right from start and not even displayed.
valid_feats = ['source', 'gene', 'CDS']

class AssociatedVar(Tkinter.BooleanVar):
    """A Tkinter boolean variable associated with any object

    The idea behind this class is to be used together with Tkinter.Checkbox
    and used the ass attribute to get an associated object.
    """
    def __init__(self, master=None, ass=None):
        Tkinter.BooleanVar.__init__(self, master)
        self.ass = ass

class ass_checkbox(Tkinter.Frame):
    """
    """
    def __init__(self, parent=None, feats=[]):
        Tkinter.Frame.__init__(self, parent)
        self.vars = []
        for f in feats:
            var = AssociatedVar(self, f)
            chk = Tkinter.Checkbutton(self, text=f.type, variable=var)
            chk.pack(fill=Tkinter.BOTH)
            self.vars.append(var)

    def get_selected(self):
        return map (lambda x: x.ass, filter (lambda x: x.get(), self.vars))

def select_seq_feats(seq):
    feats = filter(lambda f: f.type in valid_feats, seq.features)

    root = Tkinter.Tk()
    frame = ass_checkbox(root, feats)
    frame.pack()

    Tkinter.Button(root,
        text='Save',
        command=root.quit
    ).pack(side=Tkinter.RIGHT)
    Tkinter.Button(root,
        text='Quit',
        command=exit
    ).pack(side=Tkinter.RIGHT)

    root.mainloop()
    root.destroy()
    return frame.get_selected()

if __name__ == '__main__':
    if (len(sys.argv) > 1):
        filename = sys.argv[1]
    else:
        filename = tkFileDialog.askopenfilename(
            filetypes=[('Genbank files', '.gb'), ('All files', '*')]
        )
    try:
        with open(filename) as f:
            ## for now, we know that there is only one sequence per file so
            ## we can use read
            seq = Bio.SeqIO.read(f, "genbank")
    except IOError:
        print('Ups! No file?')
        sys.exit(1)
    seq.features = select_seq_feats(seq)

    try:
        with open(filename, "w") as f:
            Bio.SeqIO.write(seq, f, "genbank")
    except IOError:
        print('Ups! Failed to write')
        sys.exit(1)

