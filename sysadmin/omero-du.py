#!/usr/bin/env python
# -*- coding: utf-8 -*-

## Copyright (C) 2017 David Pinto
## Copyright (C) 2018-2014 University of Dundee
##
## This program is free software: you can redistribute it and/or modify
## it under the terms of the GNU Affero General Public License as
## published by the Free Software Foundation, either version 3 of the
## License, or (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU Affero General Public License for more details.
##
## You should have received a copy of the GNU Affero General Public License
## along with this program.  If not, see <http://www.gnu.org/licenses/>.

## NAME
##   omero-du
##
## SYNOPSIS
##   omero-du [-
##
## DESCRIPTION
##

import argparse
import getpass
import json
import sys

import omero.gateway
import omero.rtypes
import omero.sys

def omero_du(conn):
  queryService = conn.getQueryService()
  params = omero.sys.ParametersI()
  params.theFilter = omero.sys.Filter()

  def getBytes(ctx, eid):
    params.add('eid', omero.rtypes.rlong(eid))
    bytesInGroup = 0

    pixelsQuery = "select sum(cast( p.sizeX as double ) * p.sizeY * p.sizeZ * p.sizeT * p.sizeC * pt.bitSize / 8) " \
                  "from Pixels p join p.pixelsType as pt join p.image i left outer join i.fileset f " \
                  "join p.details.owner as owner " \
                  "where f is null and owner.id = (:eid)"

    filesQuery = "select sum(origFile.size) from OriginalFile as origFile " \
                 "join origFile.details.owner as owner where owner.id = (:eid)"

    # Calculate disk usage via Pixels
    result = queryService.projection(pixelsQuery, params, ctx)
    if len(result) > 0 and len(result[0]) > 0:
      bytesInGroup += result[0][0].val
    # Now get Original File usage
    result = queryService.projection(filesQuery, params, ctx)
    if len(result) > 0 and len(result[0]) > 0:
      bytesInGroup += result[0][0]._val
    return bytesInGroup

  sr = conn.getAdminService().getSecurityRoles()

  du = dict()
  for g in conn.listGroups():
    ## ignore 'user' and 'guest' groups (WTF are this?)
    if g.getId() in (sr.guestGroupId, sr.userGroupId):
      continue

    ## Isn't there a method to get list of experimenters in a group?
    conn.setGroupForSession(g.getId())
    group = conn.getGroupFromContext()
    owners, experimenters = group.groupSummary()

    ctx = conn.SERVICE_OPTS.copy()
    group_du = dict()
    for e in owners + experimenters:
      group_du[e.getId()] = getBytes(ctx, e.getId())
    du[g.getId()] = group_du
  return du

def main(argv):
  parser = argparse.ArgumentParser(
    description="Print detailed omero disk usage"
  )
  parser.add_argument("-s", "--server", help="OMERO server hostname")
  parser.add_argument("-u", "--user", help="OMERO username")
  parser.add_argument("-y", "--passwdfile", help="File with OMERO password")
  args = parser.parse_args(argv)

  passwd = ""
  if args.passwdfile:
    with open(args.passwdfile, "r") as fh:
      passwd = fh.read()
  else:
    passwd = getpass.getpass("Password for %s at %s: "
                             % (args.user, args.server))

  conn = omero.gateway.BlitzGateway(args.user, passwd, host=args.server)
  if not conn.connect():
    raise RuntimeError("Failed to connect to OMERO server")

  du = omero_du(conn)
  print json.dumps(du)

if __name__ == "__main__":
  main(sys.argv[1:])
