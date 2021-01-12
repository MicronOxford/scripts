#!/usr/bin/env python
# -*- coding: utf-8 -*-

## Copyright (C) 2020 David Miguel Susano Pinto <david.pinto@bioch.ox.ac.uk>
##
## Copying and distribution of this file, with or without modification,
## are permitted in any medium without royalty provided the copyright
## notice and this notice are preserved.  This file is offered as-is,
## without any warranty.

import getpass

import omero.gateway

lisa_uid = 3802
lothar_gid = 503
project_id = 7257

opts = {
    'owner': lisa_uid,
    'group': lothar_gid,
}


def get_connection():
    hostname = input("Server: ")
    username = input("Username: ")
    password = getpass.getpass()
    conn = omero.gateway.BlitzGateway(username, password, host=hostname,
                                      secure=True)
    if not conn.connect():
        raise RuntimeError("failed to connect '%s@%s'.  Wrong password"
                           % (username, hostname))
    conn.c.enableKeepAlive(60)
    return conn


conn = get_connection()

if not conn.setGroupForSession(lothar_gid):
    raise RuntimeError('failed to change group')

project = conn.getObject("Project", project_id)
if project is None:
    raise RuntimeError('failed to get project')

for dataset in project.listChildren():
    for image in dataset.listChildren():
        print("%s\t%s" % (dataset.name, image.name))

conn.close()
