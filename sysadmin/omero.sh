#!/bin/sh
## Author: David Pinto <david.pinto@bioch.ox.ac.uk>
## This program is granted to the public domain.

## This is a launcher for the different OMERO clients in a system. It
## assumes them to be all installed all in the same directory, and
## calls one depending on the first argument. By default, it will call
## OMERO.insight, which is likely the to be the most common.

CLIENTS_DIR="/usr/local/OMERO.clients/"
DEF_CLIENT="insight"

if [ $# -gt 1 ]
then
  echo "error: two many input arguments" >&2
  exit 1
fi

if [ -z "$1" ]
then
  CLIENT=$DEF_CLIENT
else
  CLIENT=$1
fi

case "$CLIENT" in
  "insight")
    CLIENT=$CLIENTS_DIR"OMEROinsight_unix.sh"
    ;;
  "importer")
    CLIENT=$CLIENTS_DIR"OMEROimporter_unix.sh"
    ;;
  "editor")
    CLIENT=$CLIENTS_DIR"OMEROeditor_unix.sh"
    ;;
  *)
    echo "error: unknown client $CLIENT" >&2
    exit 1
    ;;
esac

$CLIENT

