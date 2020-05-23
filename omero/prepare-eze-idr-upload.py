#!/usr/bin/env python
# -*- coding: utf-8 -*-

## Copyright (C) 2020 David Miguel Susano Pinto <david.pinto@bioch.ox.ac.uk>
##
## Copying and distribution of this file, with or without modification,
## are permitted in any medium without royalty provided the copyright
## notice and this notice are preserved.  This file is offered as-is,
## without any warranty.

import os.path
import re

import omero.gateway
import omero.util.sessions


schermellehgroup = 503 # schermellehgroup
basepath = ''

all_experiment_defs = {
    # For experimentA the 575 files required are found in my OMERO profile under:
    # Miron-C127-G1/EM16-09-A-G1/*_SIR_EAL_THR.tif
    # Miron-C127-G1/EM16-09-B-G1/*_SIR_EAL_THR.tif
    # Miron-C127-G1/EM16-12-A/*_SIR_EAL_THR.tif
    # Then in Roel Oldenkamp's profile under:
    # C127-G1/[all directories]/*_SIR_ALN_THR.tif
    # Finally in Ana Rita Faria's profile under:
    # RF2019-01_03/[all sub-directories except RF2019-01_03_1_HeLa_H2B-GFP-Boost_DAPI]/*_SIR_THR_ALN-1.tif
    'experimentA' : [
        {
            'userID' : 952, # Ezequiel
            'project' : '^Miron-C127-G1$',
            'dataset' : '^EM16-09-(A|B)-G1$',
            'image' : '.*_SIR_EAL_THR.tif$',
        },
        {
            'userID' : 952, # Ezequiel
            'project' : '^Miron-C127-G1$',
            'dataset' : '^EM16-12-A$',
            'image' : '.*_SIR_EAL_THR.tif$',
        },
        {
            'userID' : 3453, # Roel
            'project' : '^C127-G1$',
            'dataset' : '.*',
            'image' : '.*_SIR_ALN_THR.tif$',
        },
        {
            'userID' : 3905, # Rita
            'project' : '^RF2019-01_03$',
            'dataset' : '^(?!RF2019-01_03_1_HeLa_H2B-GFP-Boost_DAPI$)',
            'image' : '.*_SIR_THR_ALN-1.tif$',
        },
    ],
    # For experimentB the 943 files required are found in my OMERO profile under:
    # Miron-C127-EdU/EM16-09-A-EdU/*_SIR_EAL_THR.tif
    # Miron-C127-EdU/EM16-09-B-EdU/*_SIR_EAL_THR.tif
    # Miron-C127-EdU/EM16-12-D-ES/*_SIR_EAL_THR.tif
    # Miron-C127-EdU/EM16-12-D-LS/*_SIR_EAL_THR.tif
    # Miron-C127-EdU/EM16-12-D-MS/*_SIR_EAL_THR.tif
    # Then in Roel Oldenkamp's profile under:
    # C127-ES/[all directories]/*_SIR_ALN_THR.tif
    # C127-LS/[all directories]/*_SIR_ALN_THR.tif
    # C127-MS/[all directories]/*_SIR_ALN_THR.tif
    'experimentB' : [
        {
            'userID' : 952, # Ezequiel
            'project' : '^Miron-C127-EdU$',
            'dataset' : '^EM16-09-(A|B)-EdU$',
            'image' : '.*_SIR_EAL_THR.tif$',
        },
        {
            'userID' : 952, # Ezequiel
            'project' : '^Miron-C127-EdU$',
            'dataset' : '^EM16-12-D-(E|L|M)S$',
            'image' : '.*_SIR_EAL_THR.tif$',
        },
        {
            'userID' : 3453, # Roel
            'project' : '^C127-(E|L|M)S$',
            'dataset' : '.*',
            'image' : '.*_SIR_ALN_THR.tif$',
        },
    ],
    # Finally For experimentC the 92 files required are found in Roel Oldenkamp's OMERO profile under:
    # HCT116SCC1mAID-6haux/[all directories]/*_SIR_ALN_THR.tif
    # HCT116SCC1mAID-16hdox-6haux/[all directories]/*_SIR_ALN_THR.tif
    'experimentC' : [
        {
            'userID' : 3453, # Roel
            'project' : '^HCT116SCC1mAID(-16hdox)?-6haux$',
            'dataset' : '.*',
            'image' : '.*_SIR_ALN_THR.tif$',
        },
    ],
}


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


def find_files(conn, defs):
    paths_map = {}
    opts = {
        'owner': defs['userID'],
        'group': schermellehgroup,
    }
    for project in conn.getObjects('Project', opts=opts):
        if re.match(defs['project'], project.getName()) is None:
            continue
        for dataset in project.listChildren():
            if re.match(defs['dataset'], dataset.getName()) is None:
                continue
            for image in dataset.listChildren():
                if re.match(defs['image'], image.getName()) is None:
                    continue
                server_path = image.getImportedImageFilePaths()['server_paths']
                if len(server_path) != 1:
                    # We know that in our filesets there's only one
                    # file per image.
                    raise Exception('we only expect 1 file per image')
                local_path = server_path[0]
                remote_path = os.path.join(project.getName(),
                                           dataset.getName(),
                                           image.getName())
                paths_map[local_path] = remote_path
    return paths_map


conn = get_connection()

for experiment_name, experiment_defs in all_experiment_defs.items():
    for defs in experiment_defs:
        paths_map = find_files(conn, defs)
        for local_path, remote_path in paths_map.items():
            local_path = os.path.join(basepath, local_path)
            remote_path = os.path.join(experiment_name, remote_path)
            if ',' in local_path or ',' in remote_path:
                # If there's a comma on the path it's tricky
                raise Exception('hmmm.... we have commas on the paths')
            print '%s,%s' % (local_path, remote_path)
