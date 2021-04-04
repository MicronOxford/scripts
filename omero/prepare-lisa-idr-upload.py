#!/usr/bin/env python
# -*- coding: utf-8 -*-

## Copyright (C) 2021 David Miguel Susano Pinto <david.pinto@bioch.ox.ac.uk>
##
## Copying and distribution of this file, with or without modification,
## are permitted in any medium without royalty provided the copyright
## notice and this notice are preserved.  This file is offered as-is,
## without any warranty.

import os.path
import re
import sys
import typing

import omero.gateway
import omero.util.sessions

assays_file_column = 16

schermelleh_gid = 503
lisa_uid = 3802
basepath = ''


def read_names(fpath):
    names = set()
    line_count = 0
    with open(fpath, 'r') as fh:
        header = fh.readline().split('\t')
        if header[assays_file_column] != 'Image File':
            raise RuntimeError('column is wrong')
        fh.readline()  # discard line of comments
        for line in fh:
            line_count += 1
            names.add(line.split('\t')[assays_file_column])

    if len(names) != line_count:
        raise RuntimeError('duplicated names? We have %d names from %d lines'
                           % (len(names), line_count))
    return names


def get_connection():
    store = omero.util.sessions.SessionsStore()
    if store.count() < 1:
        raise RuntimeError('no OMERO sessions around')
    session_props = store.get_current()
    session_uuid = session_props[2]
    if not session_uuid:
        raise RuntimeError('current session has no UUID')
    conn = omero.gateway.BlitzGateway(host=session_props[0],
                                      port=session_props[3])
    if not conn.connect(session_uuid):
        raise RuntimeError('failed to connect to session')
    return conn


def find_files(conn, names):
    names = names.copy()
    paths_map = {}
    opts = {
        'owner': lisa_uid,
        'group': schermelleh_gid,
    }
    for project in conn.getObjects('Project', opts=opts):
        # It's all in this project
        if project.getName() != "Xist RNA dynamics":
            continue

        for dataset in project.listChildren():
            for image in dataset.listChildren():
                try:
                    names.remove(image.getName())
                except KeyError:
                    continue

                server_path = image.getImportedImageFilePaths()['server_paths']
                if len(server_path) != 1:
                    # We know that in our filesets there's only one
                    # file per image.
                    raise Exception('we only expect 1 file per image but %s'
                                    % server_path)
                local_path = server_path[0]
                remote_path = os.path.join(project.getName(),
                                           dataset.getName(),
                                           image.getName())
                paths_map[local_path] = remote_path
    if len(names) != 0:
        raise Exception('failed to find the following images: %s' % names)
    return paths_map


conn = get_connection()
names = read_names(sys.argv[1])
paths_map = find_files(conn, names)
for local_path, remote_path in paths_map.items():
    if ',' in local_path or ',' in remote_path:
        # If there's a comma on the path it's tricky
        raise Exception('hmmm.... we have commas on the paths')
    print '%s,%s' % (local_path, remote_path)
