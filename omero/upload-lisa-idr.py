# -*- coding: utf-8 -*-

## Copyright (C) 2021 David Miguel Susano Pinto <david.pinto@bioch.ox.ac.uk>
##
## Copying and distribution of this file, with or without modification,
## are permitted in any medium without royalty provided the copyright
## notice and this notice are preserved.  This file is offered as-is,
## without any warranty.

import ftplib
import os
import os.path
import sys

local_base = '/OMERO/ManagedRepository/'
remote_base = '/incoming/lisa-rodermund/'

ftp_host = ''
ftp_port = 21
ftp_user = ''
ftp_passwd = ''


desc_filepath = sys.argv[1]
if not os.access(desc_filepath, os.R_OK):
    raise Exception("can't read file: %s" % desc_filepath)

ftp_conn = ftplib.FTP()

ftp_conn.connect(ftp_host, ftp_port)
ftp_conn.login(ftp_user, ftp_passwd)
ftp_conn.set_pasv(True)

ftp_conn.cwd('/incoming')
try:
    ftp_conn.mkd('lisa-rodermund')
except ftplib.error_perm as e:
    if e[0].startswith('550 '):
        # we hope this is because the directory already exists
        pass
    else:
        raise

with open(desc_filepath, 'r') as desc_fh:
    for line in desc_fh:
        line = line.rstrip()  # drop newline
        local_rel_path, omero_path = line.split(',')
        omero_fname = os.path.basename(omero_path)

        local_abs_path = os.path.join(local_base, local_rel_path)
        remote_abs_path = os.path.join(remote_base, omero_fname)

        remote_basedir, remote_filename = os.path.split(remote_abs_path)

        print('moving to ' + remote_basedir)
        ftp_conn.cwd(remote_basedir)
        print('storing %s' % local_abs_path)
        with open(local_abs_path, 'rb') as data_fh:
            ftp_conn.storbinary('STOR %s' % remote_filename, data_fh)

try:
    ftp_conn.quit()
except:
    ftp_conn.close()
