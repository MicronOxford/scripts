#!/usr/bin/python
# -*- coding: utf-8 -*-

## Copyright (C) 2021 David Miguel Susano Pinto <david.pinto@bioch.ox.ac.uk>
##
## Copying and distribution of this file, with or without modification,
## are permitted in any medium without royalty provided the copyright
## notice and this notice are preserved.  This file is offered as-is,
## without any warranty.

"""Script to convert Lisa Rodermund's tiff before upload to IDR.

Lisa list of images to upload include some tiff files that are not
handled by BioFormats.  So we need to open them on ImageJ and save
them before uploading them to the IDR FTP server.

"""

import tempfile
import ftplib
import os
import os.path
import subprocess
import sys

local_base = '/var/lib/omero/main/ManagedRepository/'

ij_path = "./ImageJ/ImageJ"

ftp_host = ""
ftp_port = 21
ftp_user = ""
ftp_pass = ""


desc_filepath = sys.argv[1]
if not os.access(desc_filepath, os.R_OK):
    raise Exception("can't read file: %s" % desc_filepath)

ftp_conn = ftplib.FTP()

ftp_conn.connect(ftp_host, ftp_port)
ftp_conn.login(ftp_user, ftp_pass)
ftp_conn.set_pasv(True)

ftp_conn.cwd('/incoming')
try:
    ftp_conn.mkd('lisa-rodermund')
except ftplib.error_perm as e:
    if str(e).startswith('550 '):
        # we hope this is because the directory already exists
        pass
    else:
        raise
ftp_conn.cwd('/incoming/lisa-rodermund')


def read_original_fpaths(desc_filepath):
    fpaths = []
    with open(desc_filepath, 'r') as desc_fh:
        for line in desc_fh:
            local_original_path = os.path.join(local_base, line.split(',')[0])
            if local_original_path.endswith(".tif"):
                fpaths.append(local_original_path)
    return fpaths


def generate_ij_macro(original_path, converted_path):
    code = """
setBatchMode(true);
open("%s");
saveAs("Tiff", "%s");
close();
setBatchMode(false);
run("Quit");
""" %(original_path, converted_path)
    return code


for local_original_path in read_original_fpaths(desc_filepath):
    fname = os.path.basename(local_original_path)
    converted_fname = fname[:-4] + "-converted.ome.tif"

    with tempfile.TemporaryDirectory() as tmpdirname:
        local_converted_path = os.path.join(tmpdirname, converted_fname)

        ijm_code = generate_ij_macro(local_original_path, local_converted_path)
        ijm_path = os.path.join(tmpdirname, 'convert.ijm')
        with open(ijm_path, 'w') as macro_fh:
            print(ijm_code, file=macro_fh)

        # This always succeds (or hangs) because an error in the
        # macro is caught and ij exits "cleanly".
        subprocess.run(["xvfb-run", "-a", ij_path, "-macro", ijm_path])

        print('uploading ' + converted_fname)
        with open(local_converted_path, 'rb') as data_fh:
            try:
                ftp_conn.storbinary('STOR %s' % converted_fname, data_fh)
            except ftplib.error_perm as e:
                if str(e).startswith('553 '):  # Could not create file
                    # We hope this is because it has already been uploaded
                    print('it was already uploaded')
                    pass
                else:
                    raise
            else:
                print('done')

try:
    ftp_conn.quit()
except:
    ftp_conn.close()
