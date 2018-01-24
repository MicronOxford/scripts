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

## Read our disk usage logs to create some stats.

import datetime
import json
import os
import sys

import matplotlib.pyplot

class PIGroup():
    def __init__(self, pi_name, affiliation):
        self.pi_name = pi_name
        self.affiliation = affiliation

class OMEROGroup():
    def __init__(self, omero_gid, name, payee):
        self.omero_gid = omero_gid
        self.name = name
        self.payee = payee

def _create_PI_groups():
    groups = [
        ['Alfredo Castello', 'Oxford Biochemistry'],
        ['Alison Woollard', 'Oxford Biochemistry'],
        ['Andre Furger', 'Oxford Biochemistry'],
        ['Bela Novak', 'Oxford Biochemistry'],
        ['Ben Berks', 'Oxford Biochemistry'],
        ['Bungo Akiyoshi', 'Oxford Biochemistry'],
        ['Clive Wilson', 'Oxford DPAG'],
        ['Colin Kleanthous', 'Oxford Biochemistry'],
        ['David Sherrat', 'Oxford Biochemistry'],
        ['David Vaux', 'Oxford Pathology'],
        ['Duncan Sparrow', 'Oxford DPAG'],
        ['Elizabeth Robertson', 'Oxford Pathology'],
        ['Ervin Fodor', 'Oxford Pathology'],
        ['Eva Gluenz', 'Oxford Pathology'],
        ['Francis Barr', 'Oxford Biochemistry'],
        ['George Tofaris', 'Oxford Clinical Neurosciences'],
        ['Hagan Bayley', 'Oxford Chemistry'],
        ['Ian Moore', 'Oxford Plant Sciences'],
        ['Ilan Davis', 'Oxford Biochemistry'],
        ['Jane Mellor', 'Oxford Biochemistry'],
        ['Jason Schnell', 'Oxford Biochemistry'],
        ['John Vakonakis', 'Oxford Biochemistry'],
        ['Jonathan Hodgkin', 'Oxford Biochemistry'],
        ['Jordan Raff', 'Oxford Pathology'],
        ['Judy Armitage', 'Oxford Biochemistry'],
        ['Kay Grünewald', 'Oxford STRUBI'],
        ['Keith Gull', 'Oxford Pathology'],
        ['Kevin Foster', 'Oxford Zoology'],
        ['Kim Nasmyth', 'Oxford Biochemistry'],
        ['Lothar Schermelleh', 'Oxford Biochemistry'],
        ['Luis Alberto Baena-López', 'Oxford Pathology'],
        ['Mark Howarth', 'Oxford Biochemistry'],
        ['Mark Leake', 'University of York'],
        ['Martin Booth', 'Oxford Engineering Science'],
        ['Martin Cohn', 'Oxford Biochemistry'],
        ['Matthew Freeman', 'Oxford Pathology'],
        ['Matthew Whitby', 'Oxford Biochemistry'],
        ['Micron', 'Oxford Biochemistry'],
        ['Monika Gullerova', 'Oxford Pathology'],
        ['Neil Brockdorff', 'Oxford Biochemistry'],
        ['Paul Klenerman', 'Oxford Medicine'],
        ['Paul Riley', 'Oxford DPAG'],
        ['Petros Ligoxygakis', 'Oxford Biochemistry'],
        ['Philip Biggin', 'Oxford Biochemistry'],
        ['Richard Berry', 'Oxford Physics'],
        ['Rob Klose', 'Oxford Biochemistry'],
        ['Shabaz Mohammed', 'Oxford Biochemistry'],
        ['Simon Butt', 'Oxford DPAG'],
        ['Stephan Uphoff', 'Oxford Biochemistry'],
        ['Stephen Taylor', 'Oxford WIMM'],
        ['Suzannah Williams', 'Oxford Women\' and reproductive health'],
        ['Tim Nott', 'Oxford Biochemistry'],
        ['Ulrike Gruneberg', 'Oxford Pathology'],
    ]
    return [PIGroup(x[0], x[1]) for x in groups]
PI_GROUPS = _create_PI_groups()
INSTITUTES = list(set([x.affiliation for x in PI_GROUPS]))

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

def update_id_maps():
    # bin/omero group list --style plain
  pass

def load_omero_du(dir_path):
    """Read the omero du data from a directory.

    Returns a dict of nested dicts like this:

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
        fparts = fname.split("-")
        if len(fparts) != 3 or fparts[0:2] != ['omero', 'du']:
            raise RuntimeError("not an omero-du filename '%s'" % fname)

        date = datetime.datetime.strptime(fparts[2], '%Y%m%d%H%M')
        with open(os.path.join(dir_path, fname), 'r') as fh:
            omerodu[date] = json.load(fh)
    return omerodu

def plot_total_du(du):
    total_du = dict()
    for date, du in du.items():
        total = 0
        for users in du.values():
            total += sum(users.values())
        total /= (1024.0 ** 4) # from bytes to TB (powers of 1024)
        total_du[date] = total

    fig, ax = matplotlib.pyplot.subplots()
    ax.plot_date(*zip(*sorted(total_du.items())))

    ## Only label the year but have ticks for every month.
    ax.xaxis.set_major_locator(matplotlib.dates.YearLocator())
    ax.xaxis.set_minor_locator(matplotlib.dates.MonthLocator())
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%Y'))

    matplotlib.pyplot.title("OMERO total disk usage")
    matplotlib.pyplot.ylabel("Disk Usage in TB (powers of 1024)")
    matplotlib.pyplot.show()

def plot_by_institute(du):
    last_du = du[sorted(du.keys())[-1]]
    group_total = dict()
    for gid, users in last_du.items():
        group_total[gid] = sum(users.values())

    institute_du = {l : 0 for l in INSTITUTES}
    for gid, grp_du in group_total.items():
        omero_grp = OMERO_GROUPS[int(gid)]
        institute_du[omero_grp.payee.affiliation] +=grp_du

    institute_du = {k:v for k,v in institute_du.items() if v > 0}
    for l, x, in institute_du.items():
        institute_du[l] /= 1024.0 ** 4

    lpos = range(len(institute_du.keys()))
    fig, ax = matplotlib.pyplot.subplots()
    ax.barh(lpos, [institute_du[l] for l in institute_du.keys()],
            align='center')

    ax.set_yticks(lpos)
    ax.set_yticklabels([l.replace('Oxford ', '') for l in institute_du.keys()])
    ax.invert_yaxis()  # labels read top-to-bottom
    matplotlib.pyplot.title("OMERO disk usage by Department")
    matplotlib.pyplot.xlabel("Disk Usage in TB (powers of 1024)")
    matplotlib.pyplot.show()

def plot_by_group(du):
    last_du = du[sorted(du.keys())[-1]]
    group_total = dict()
    for gid, users in last_du.items():
        group_total[gid] = sum(users.values())

    pi_group_du = {grp.pi_name : 0 for grp in PI_GROUPS}
    for gid, grp_du in group_total.items():
        omero_grp = OMERO_GROUPS[int(gid)]
        pi_group_du[omero_grp.payee.pi_name] +=grp_du

    pi_group_du = {k:v for k,v in pi_group_du.items() if v > 0}
    for l, x, in pi_group_du.items():
        pi_group_du[l] /= 1024.0 ** 4

    lpos = range(len(pi_group_du.keys()))
    fig, ax = matplotlib.pyplot.subplots()
    ax.barh(lpos, [pi_group_du[grp] for grp in pi_group_du.keys()],
            align='center')

    ax.set_yticks(lpos)
    ax.set_yticklabels(list(pi_group_du.keys()))
    # ax.invert_yaxis()  # labels read top-to-bottom
    matplotlib.pyplot.title("OMERO disk usage by PI group")
    matplotlib.pyplot.xlabel("Disk Usage in TB (powers of 1024)")
    matplotlib.pyplot.show()

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

def main(argv):
    omerodu = load_omero_du(argv[0])
    plot_by_institute(omerodu)
    plot_by_group(omerodu)
    plot_total_du(omerodu)


if __name__ == "__main__":
    main(sys.argv[1:])
