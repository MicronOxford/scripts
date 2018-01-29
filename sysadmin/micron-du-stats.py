#!/usr/bin/env python3
# -*- coding: utf-8 -*-

## Copyright (C) 2018 David Pinto
##
## This program is free software: you can redistribute it and/or modify
## it under the terms of the GNU General Public License as
## published by the Free Software Foundation, either version 3 of the
## License, or (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program.  If not, see <http://www.gnu.org/licenses/>.

## NAME
##   micron-du-stats -- read and analyse disk usage logs
##
## SYNOPSIS
##   micron-du-stats [--omero-data OMERO-DU-DIR] [--fs-data FS-DU-DIR]
##
## DESCRIPTION
##   Perform the analysis for either the OMERO disk usage or the
##   micron file servers.  Needs the path for a directory where each
##   du timepoint is an individal file.  Files should be named like:
##
##     omero-du-$(date --utc '+\%Y\%m\%d\%H\%M')
##     micronusers-du-$(date --utc '+\%Y\%m\%d\%H\%M')
##

import argparse
import collections
import datetime
import json
import os
import sys

import matplotlib.pyplot

class PIGroup():
    def __init__(self, pi_name, affiliation, unix_gid):
        self.pi_name = pi_name
        self.affiliation = affiliation
        self.unix_gid = unix_gid

class OMEROGroup():
    def __init__(self, omero_gid, name, payee):
        self.omero_gid = omero_gid
        self.name = name
        self.payee = payee

def _create_PI_groups():
    groups = [
        ['Achillefs Kapanidis', 'Physics', 18790],
        ['Alfredo Castello', 'Biochemistry', 18764],
        ['Alison Woollard', 'Biochemistry', 10510],
        ['Andre Furger', 'Biochemistry', 10720],
        ['Andreas Russ', 'Biochemistry', 10730], # FIXME
        ['Andrew King', 'DPAG', 18817],
        ['Armitage and SBCB', 'Biochemistry', 170], # FIXME
        ['Bela Novak', 'Biochemistry', 10930],
        ['Ben Berks', 'Biochemistry', 10560],
        ['Bungo Akiyoshi', 'Biochemistry', 18756],
        ['Catherine Pears', 'Biochemistry', 10140],
        ['Clive Wilson', 'DPAG', 18781],
        ['Colin Kleanthous', 'Biochemistry', 18752],
        ['David Sherrat', 'Biochemistry', 10590],
        ['David Vaux', 'Pathology', 18800],
        ['Duncan Sparrow', 'DPAG', 18772],
        ['Elena Seiradake', 'Biochemistry', 18763],
        ['Elizabeth Robertson', 'Pathology', 18788],
        ['Ervin Fodor', 'Pathology', None],
        ['Eva Gluenz', 'Pathology', None],
        ['External', 'Biochemistry', 12501], # FIXME
        ['Frances Ashcroft', 'DPAG', 18810],
        ['Francis Barr', 'Biochemistry', 18747],
        ['George Tofaris', 'Clinical Neurosciences', 18795],
        ['Hagan Bayley', 'Chemistry', 18773],
        ['Ian Moore', 'Plant Sciences', 18791],
        ['Ilan Davis new', 'Biochemistry', 18819],
        ['Ilan Davis', 'Biochemistry', 1000], # FIXME
        ['Jane Mellor', 'Biochemistry', 10150],
        ['Jason Schnell', 'Biochemistry', None],
        ['John Vakonakis', 'Biochemistry', None],
        ['Jonathan Hodgkin', 'Biochemistry', 10500],
        ['Jordan Raff', 'Pathology', 2700],
        ['Judy Armitage', 'Biochemistry', 10580],
        ['Kay Grünewald', 'STRUBI', 18813],
        ['Keith Gull', 'Pathology', None],
        ['Kevin Foster', 'Zoology', 2702],
        ['Kim Nasmyth', 'Biochemistry', 10790],
        ['Lidia Vasilieva', 'Biochemistry', 2800],
        ['Lothar Schermelleh', 'Biochemistry', 18749],
        ['Luis Alberto Baena-López', 'Pathology', 18784],
        ['Lynne Cox', 'Biochemistry', 10410],
        ['Mark Howarth', 'Biochemistry', 10910],
        ['Mark Leake', 'University of York', None],
        ['Martin Booth', 'Engineering Science', 18783],
        ['Martin Cohn', 'Biochemistry', 18750],
        ['Masud Husain', 'Clinical Neurosciences', 18818],
        ['Mathilda Mommersteeg', 'DPAG', 18794],
        ['Matt Higgins', 'Biochemistry', 10116],
        ['Matthew Freeman', 'Pathology', 18808],
        ['Matthew Whitby', 'Biochemistry', 10620],
        ['Michael Dustin', 'Kennedy', 18796],
        ['Michael Kohl', 'DPAG', 18778],
        ['Micron Extra', 'Biochemistry', 18753], # FIXME
        ['Micron enginners', 'Biochemistry', 18765],
        ['Micron', 'Biochemistry', 18754],
        ['Ming Lei', 'Pharmacology', 18793],
        ['Monika Gullerova', 'Pathology', 18786],
        ['Neil Brockdorff', 'Biochemistry', 10940],
        ['Nicholas Proudfoot', 'Pathology', 18787],
        ['Not assigned', 'Biochemistry', 18755], # FIXME
        ['Paul Klenerman', 'Medicine', 18801],
        ['Paul Riley', 'DPAG', 18779],
        ['Paul Wentworth', 'Biochemistry', 10740],
        ['Penny Handford', 'Biochemistry', 10345],
        ['Petros Ligoxygakis', 'Biochemistry', 10700],
        ['Philip Biggin', 'Biochemistry', None],
        ['Proteomics', 'Biochemistry', 10950], # FIXME
        ['Richard Berry', 'Physics', None],
        ['Richard Wade-Martins', 'DPAG', 18780],
        ['Rob Klose', 'Biochemistry', 10911],
        ['Ruth Brown', 'Biochemistry', 10640], # FIXME
        ['Shabaz Mohammed', 'Biochemistry', 18760],
        ['Shankar Srinivas', 'DPAG', 18766],
        ['Simon Butt', 'DPAG', 18775],
        ['Stephan Uphoff', 'Biochemistry', 18803],
        ['Stephen Taylor', 'WIMM', 18797],
        ['Suzannah Williams', 'Women\' and reproductive health', None],
        ['Terry Butters', 'Biochemistry', 10012],
        ['Tim Nott', 'Biochemistry', None],
        ['Ulrike Gruneberg', 'Pathology', 18777],
        ['Wolfson Imaging Center', 'WIMM', 18767],
    ]
    return [PIGroup(x[0], x[1], x[2]) for x in groups]
PI_GROUPS = _create_PI_groups()

def _create_omero_groups():
    groups = [
        [   0, 'system', 'Micron'],
        [   1, 'user', 'Micron'],
        [   2, 'guest', 'Micron'],
        [   3, 'sbcbgroup', 'Micron'], # should be empty
        [   4, 'micron', 'Micron'],
        [   5, 'nasmythgroup', 'Kim Nasmyth'],
        [   6, 'davisgroup', 'Ilan Davis'],
        [   7, 'raffgroup', 'Jordan Raff'],
        [   8, 'hodgkingroup', 'Jonathan Hodgkin'],
        [  53, 'Leake', 'Mark Leake'],
        [  54, 'armitagegroup', 'Judy Armitage'],
        [ 103, 'sherrattgroup', 'David Sherrat'],
        [ 153, 'Berry', 'Richard Berry'],
        [ 203, 'whitbygroup', 'Matthew Whitby'],
        [ 253, 'brockdorffgroup', 'Neil Brockdorff'],
        [ 254, 'klosegroup', 'Rob Klose'],
        [ 303, 'Sak_SAPs', 'Jordan Raff'],
        [ 304, 'dpwrussell-test1', 'Micron'], # should be empty
        [ 353, 'woollardgroup', 'Alison Woollard'],
        [ 354, 'kleanthousgroup', 'Colin Kleanthous'],
        [ 403, 'barrgroup', 'Francis Barr'],
        [ 453, 'Williams', 'Suzannah Williams'],
        [ 454, 'Moore Group', 'Ian Moore'],
        [ 455, 'Armitage_external', 'Judy Armitage'],
        [ 503, 'schermellehgroup', 'Lothar Schermelleh'],
        [ 553, 'micron-test', 'Micron'],
        [ 554, 'external', 'Micron'], # should go
        [ 555, 'mellorgroup', 'Jane Mellor'],
        [ 556, 'schnellgroup', 'Jason Schnell'],
        [ 557, 'ligoxygakisgroup', 'Petros Ligoxygakis'],
        [ 558, 'vakonakisgroup', 'John Vakonakis'],
        [ 559, 'campbellgroup', 'Micron'], # should be empty
        [ 560, 'furgergroup', 'Andre Furger'],
        [ 561, 'akiyoshigroup', 'Bungo Akiyoshi'],
        [ 562, 'gullgroup', 'Keith Gull'],
        [ 603, 'cohngroup', 'Martin Cohn'],
        [ 653, 'novakgroup', 'Bela Novak'],
        [ 703, 'wellcomegroup', 'Micron'], # should be empty
        [ 753, 'Private', 'Micron'], # should be empty
        [ 754, 'Gluenz', 'Eva Gluenz'],
        [ 803, 'Fodor', 'Eva Gluenz'],
        [ 853, 'RaffLab_Colla_Cep104', 'Jordan Raff'],
        [ 903, 'howarthgroup', 'Mark Howarth'],
        [ 904, 'microngroup', 'Micron'],
        [ 953, 'mRNA localisation modelling', 'Ilan Davis'],
        [1003, 'mRNA localisation screen', 'Ilan Davis'],
        [1004, 'Brain Development QBrain', 'Ilan Davis'],
        [1053, 'castellogroup', 'Alfredo Castello'],
        [1103, 'sparrowgroup', 'Duncan Sparrow'],
        [1153, 'baenalopezgroup', 'Luis Alberto Baena-López'],
        [1203, 'wilsongroup', 'Clive Wilson'],
        [1204, 'robertsongroup', 'Elizabeth Robertson'],
        [1205, 'gullerovagroup', 'Monika Gullerova'],
        [1206, 'buttgroup', 'Simon Butt'],
        [1207, 'rileygroup', 'Paul Riley'],
        [1253, 'Optical Lock-In', 'Micron'],
        [1303, 'mohammedgroup', 'Shabaz Mohammed'],
        [1353, 'taylorgroup', 'Stephen Taylor'],
        [1354, 'nottgroup', 'Tim Nott'],
        [1355, 'vauxgroup', 'David Vaux'],
        [1356, 'tofarisgroup', 'George Tofaris'],
        [1403, 'klenermangroup', 'Paul Klenerman'],
        [1453, 'CoolCyte', 'Ilan Davis'],
        [1503, 'freemangroup', 'Matthew Freeman'],
        [1504, 'grunewaldgroup', 'Kay Grünewald'],
        [1553, 'bayleygroup', 'Hagan Bayley'],
        [1554, 'fostergroup', 'Kevin Foster'],
        [1555, 'dropletnetworkpacking', 'Kevin Foster'],
        [1603, 'deepsim', 'Micron'],
        [1604, 'berksgroup', 'Ben Berks'],
        [1653, 'AdultBrain smFISH', 'Micron'],
        [1654, 'boothgroup', 'Martin Booth'],
        [1655, 'uphoffgroup', 'Stephan Uphoff'],
        [1703, 'gruneberggroup', 'Ulrike Gruneberg'],
        [1704, 'biggingroup', 'Philip Biggin'],
    ]
    omero_groups = dict()
    for x in groups:
        pi = x[2]
        pi_grp = [grp for grp in PI_GROUPS if grp.pi_name == pi]
        if len(pi_grp) != 1:
            raise RuntimeError("no unique PI group for '%s', found %s"
                               % (pi, pi_grp))
        omero_groups[x[0]] = OMEROGroup(x[0], x[1], pi_grp[0])
    return omero_groups
OMERO_GROUPS = _create_omero_groups()

## Mapping SSO to people names.  There's a lot of them but we only use
## this to find the ones with most usage so we can get away with only
## a few.
## for SSO in ... ; do
##   NAME=`ldapsearch ... -W "cn=$SSO" -LLL displayName | grep displayName | sed "s,displayName: ,,"`
##   echo "'$SSO' : '$NAME',"
## done
USERNAMES = {
    'dpag0482' : 'Matthew Stower',
    'dpag0443' : 'Richard Tyser',
    'clab0281' : 'Christoffer Lagerholm',
    'dpag0665' : 'Navrita Mathiah',
    'bioc0759' : 'Richard Parton',
    'path0636' : 'Jordan Raff',
    'path0655' : 'Anna Franz',
    'path0693' : 'Helio Duarte Roque',
    'path1050' : 'Lior Pytowski',
    'bioc1108' : 'Ricardo Nunes Bastos',
    'quee2159' : 'Stephan Uphoff',
    'dpag0033' : 'Tomoko Watanabe',
    'trin2450' : 'Greta Pintacuda',
    'chri3774' : 'Alex Davidson',
    'zool0788' : 'Alan Wainman',
    'dpag0794' : 'Irina Stefana',
    'bioc0882' : 'Ian Dobbie',
    'bioc1117' : 'Sapan Gandhi',
    'wolf4192' : 'Ezequiel Miron Sardiello',
    'bioc1083' : 'Eva Wegel',
    'shug3995' : 'Kirsty Gill',
    'bioc0877' : 'Timothy Weil',
    'bioc1322' : 'Ana Palanca Cunado',
    'bioc1350' : 'Cvic Innocent',
    'bioc1389' : 'Alexander Al Saroori',
    'bioc1194' : 'Justin Demmerle',
    'path0656' : 'Paul Conduit',
    'bioc0847' : 'Tatyana Nesterova',
    'linc3440' : 'Davinderpreet Mangat',
    'bioc0750' : 'Raquel Cardosa de Oliveira',
    'quee2608' : 'Lu Yang',
    'bioc1090' : 'Lothar Schermelleh',
    'shug1880' : 'James Halstead',
    'bioc0954' : 'Christian Lesterlin',
    'bioc0861' : 'Heather Coker',
    'path1006' : 'Anna Caballe',
    'linc3876' : 'Holly Hathrell',
    'bioc0780' : 'Russell Hamilton',
    'path0893' : 'James Bancroft',
    'sedm3887' : 'Felix Castellanos Suarez',
    'mert2301' : 'Francoise Howe',
}


def update_id_maps():
    # bin/omero group list --style plain
    pass

def n_users_stats():
    ## extract users from the booking system from
    ## Export data > Instrument usage by users and select all Micron
    ## and Pathology microscope and export as a csv file
    ##   tail -n +2 FILENAME # remove first two lines of headers
    ##   awk -F, '{print $1}' bioch-active-users | sort -u > uniq-bioch
    ##   awk -F, '{print $1}' path-active-users | sort -u > uniq-path
    ##   sort -u uniq-path uniq-bioch | wc -l
    ##   grep -v -f uniq-bioch uniq-path | wc -l
    ##   grep -v -f uniq-path uniq-bioch | wc -l
    pass


def bytes2GiB(nbytes):
    """Convert bytes to Gi bytes"""
    return nbytes / (1024 ** 3)

def bytes2TiB(nbytes):
    """Convert bytes to Ti bytes"""
    return nbytes / (1024 ** 4)

def TiB2bytes(nTi):
    """Convert Ti bytes to bytes"""
    return nTi * (1024 ** 4)

def date_from_filename(fname, prefix):
    fparts = fname.split("-")
    if len(fparts) != 3 or fparts[0:2] != [prefix, 'du']:
        raise RuntimeError("not an %s-du filename '%s'"
                           % (prefix, fname))
    return datetime.datetime.strptime(fparts[2], '%Y%m%d%H%M')


class DU():
    def latest(self):
        return self.du[sorted(self.du.keys())[-1]]

    def over_time(self):
        """Returns a dict, keys are datetime, values are number of bytes.
        """
        total_du = dict()
        for date, timepoint in self.du.items():
            total = 0
            for users in timepoint.values():
                total += sum(users.values())
            total_du[date] = total
        return total_du

    def by_pi_group(self):
        grp_map = self.gid_to_PIgroup()

        totals = {g.pi_name : 0 for g in grp_map.values()}
        for gid, users in self.latest().items():
            totals[grp_map[gid].pi_name] += sum(users.values())
        return totals

    def by_institute(self):
        grp_map = self.gid_to_PIgroup()

        totals = {g.affiliation : 0 for g in grp_map.values()}
        for gid, users in self.latest().items():
            totals[grp_map[gid].affiliation] += sum(users.values())
        return totals

    def by_users(self):
        totals = dict()
        for users in self.latest().values():
            for uid, nbytes in users.items():
                totals[uid] = totals.get(uid, 0) + nbytes
        return totals


class OmeroDU(DU):
    def __init__(self, dir_path):
        """Read the omero du data from a directory.
        datetime1:
            omerogroup1:
                omero_user_id_1 : nbytes
                omero_user_id_2 : nbytes
                omero_user_id_3 : nbytes
            omerogroup2:
                omero_user_id_1 : nbytes
                omero_user_id_4 : nbytes
                omero_user_id_5 : nbytes
        datetime2:
            omerogroup1:
                omero_user_id_1 : nbytes
                omero_user_id_3 : nbytes
                omero_user_id_4 : nbytes
            omerogroup3:
                omero_user_id_1 : nbytes
                omero_user_id_6 : nbytes
                omero_user_id_7 : nbytes
        """
        omerodu = dict()
        for fname in os.listdir(dir_path):
            date = date_from_filename(fname, 'omero')
            with open(os.path.join(dir_path, fname), 'r') as fh:
                timepoint = json.load(fh)
                ## convert the numeric ids from str to int
                fixed_timepoint = dict()
                for gid, users in timepoint.items():
                    fixed_group = dict()
                    for uid, nbytes in users.items():
                        fixed_group[int(uid)] = nbytes
                    fixed_timepoint[int(gid)] = fixed_group
                omerodu[date] = fixed_timepoint
        self.du = omerodu

    def gid_to_PIgroup(self):
        return {grp.omero_gid : grp.payee for grp in OMERO_GROUPS.values()}


class FSDU(DU):
    def __init__(self, dir_path):
        """Read the micron file servers data from a directory.

        These are plain text files, one line per usage with:

            unix_username unix_uid primary_group_gid user_quota_blocks

        Caveats:
          * because of the mess of filesystems we have, there may be
            multiple lines per user (one per user per filesystem).
            Multiple lines will need to be added together.
          * users may have data in different groups.. However, we only
            have their primary group.
        """
        du = dict()
        for fname in os.listdir(dir_path):
            date = date_from_filename(fname, 'micronusers')
            timepoint = dict()
            with open(os.path.join(dir_path, fname), 'r') as fh:
                for line in fh:
                    data = line.rstrip().split(' ')
                    username = data[0]
                    unix_gid = int(data[2])
                    n_blocks = int(data[3])

                    ## Richard Bryan won't pre-process the data so some
                    ## users will appear in multiple lines.  We have to
                    ## look for them and add it together.
                    fs_group = timepoint.setdefault(unix_gid, dict())
                    fs_group[username] = fs_group.get(username, 0) + n_blocks

            du[date] = timepoint

        ## A quota block is 1024 bytes (/usr/include/sys/mount.h)
        for timepoint in du.values():
            for fs_group in timepoint.values():
                for username in fs_group.keys():
                    fs_group[username] *= 1024 # convert blocks to bytes
        self.du = du

    def gid_to_PIgroup(self):
        grp_map = dict()
        for grp in PI_GROUPS:
            gid = grp.unix_gid
            if not gid:
                continue # guess this PI does not have a micron group
            if grp_map.get(gid):
                raise RuntimeError("found '%s' and '%s' with unix gid '%i'"
                                   % (grp_map[gid], grp.pi_name, gid))
            grp_map[gid] = grp
        return grp_map

def print_top_users(total_du, threshold=0):
    total_du = {k:v for k,v in total_du.items() if v > threshold}
    total_du = collections.OrderedDict(sorted(total_du.items(),
                                              key=lambda t: t[1],
                                              reverse=True))
    for uid, nbytes in total_du.items():
        print ("%6i GiB   %s (%s)"
               % (bytes2GiB(nbytes), uid,USERNAMES.get(uid, uid)))


def plot_total_by_time(total_du, title="Total disk usage"):
    """Plot total disk usage over time.

    Parameters
    ----------
      total_du: dict
        keys should be datetime objects and values int with number of bytes.
    """

    total_du = {date : bytes2TiB(du) for date, du in total_du.items()}

    fig, ax = matplotlib.pyplot.subplots()
    ax.plot_date(*zip(*sorted(total_du.items())))

    ## Only label the year but have ticks for every month.
    ax.xaxis.set_major_locator(matplotlib.dates.YearLocator())
    ax.xaxis.set_minor_locator(matplotlib.dates.MonthLocator())
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%Y'))

    matplotlib.pyplot.title(title)
    matplotlib.pyplot.ylabel("Disk Usage (TiB)")
    matplotlib.pyplot.show()


def plot_by_group(group_du, title="Disk usage by group", threshold=0):
    """
    Parameters
    ----------
      group_du : dict
        keys are labels for the plot, values are number of bytes.
      title : string
        title for the plot
      threshold : int
        Entries with less than this number of bytes will be ignored.
    """
    group_du = {k:bytes2TiB(v) for k,v in group_du.items() if v > threshold}

    ## Display sorted by group name
    group_du = collections.OrderedDict(sorted(group_du.items(),
                                              key=lambda t: t[0]))
    label_pos = range(len(group_du))

    fig, ax = matplotlib.pyplot.subplots()
    ax.barh(label_pos, group_du.values(), align='center')
    ax.set_yticks(label_pos)
    ax.set_yticklabels(list(group_du.keys()))

    ax.invert_yaxis()  # labels read top-to-bottom
    matplotlib.pyplot.title(title)
    matplotlib.pyplot.xlabel("Disk Usage (TiB)")
    matplotlib.pyplot.show()


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('--omero-data')
    parser.add_argument('--fs-data')
    args = parser.parse_args(argv)

    if args.omero_data:
        omero_du = OmeroDU(args.omero_data)
        plot_total_by_time(omero_du.over_time(),
                           title="OMERO disk usage")

        plot_by_group(omero_du.by_pi_group(),
                      title="OMERO disk usage by PI group",
                      threshold=TiB2bytes(1))

        plot_by_group(omero_du.by_institute(),
                      title="OMERO disk usage by institute",
                      threshold=TiB2bytes(1))

    if args.fs_data:
        fs_du = FSDU(args.fs_data)
        plot_total_by_time(fs_du.over_time(),
                           title="Micron ~ disk usage")

        plot_by_group(fs_du.by_pi_group(),
                      title="Micron ~ disk usage by PI group",
                      threshold=TiB2bytes(1))

        plot_by_group(fs_du.by_institute(),
                      title="Micron ~ disk usage by institute",
                      threshold=TiB2bytes(1))

        users_totals = fs_du.by_users()
        print_top_users(users_totals, threshold=TiB2bytes(0.5))

    return

if __name__ == "__main__":
    main(sys.argv[1:])
