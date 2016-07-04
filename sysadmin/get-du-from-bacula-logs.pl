#!/usr/bin/env perl
## Copyright (C) 2016 David Pinto <david.pinto@bioch.ox.ac.uk>
##
## This program is free software; you can redistribute it and/or
## modify it under the terms of the GNU General Public License as
## published by the Free Software Foundation; either version 3 of the
## License, or (at your option) any later version.
##
## This program is distributed in the hope that it will be useful, but
## WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
## General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, see
## <http:##www.gnu.org/licenses/>.

## Usage example:
##  ./get-du-from-bacula-logs.pl log.*

use strict;
use warnings;

##  Backup Level:           Full
##  Client:                 "micron1-fd" 5.2.9 (11Jun12) x86_64-unknown-linux-gnu,suse,12.1
##[...]
##  Scheduled time:         26-Jul-2015 00:10:00
##[...]
##  FD Bytes Written:       6,085,616,295 (6.085 GB)
##[...]
##  Termination:            Backup OK

## $ grep -Phro '(?<=Client:                 ").*(?=")' log.* | sort | uniq
## bioch3165-fd
## bioch4105-fd
## biochstore5-fd
## biochstore6-fd
## ghostjr-fd
## hpswc-fd
## micron1-fd
## micron2-fd
## micron3-fd
## micron5-fd
## micron6-fd
## minfra-fd

##  $ grep -Ph -A 2 '^  Backup Level: +Full' log.* | grep -P -A 1 '^  Client: +"micron[1-6]-fd"' | grep -Po '(?<=^  FileSet:                ").*(?=")' | sort | uniq
##  armitageb4O
##  Catalog
##  Exusers
##  Full Set
##  hpswctest
##  micron3files
##  micron5set1
##  micron5set2
##  micron5set3
##  micron5set4
##  micron5set5
##  micron5set6
##  micron5set7
##  micron5set8
##  micron6dpag0665
##  micron6set1
##  micron6set2
##  Omero1
##  Omero1files
##  RaffOmero
##  snfs3davis
##  Users1A
##  Users1B
##  Users1C
##  Users1D
##  Users1E
##  Users1Test
##  Users1Z
##  Users2
##  Users3
##  wimm

my %filesets = (
#  armitageb4O => 'home',
#  Catalog => 'home',
  Exusers => 'home',
  'Full Set' => 'home',
#  hpswctest => 'home',
#  micron3files => 'omero',
  micron5set1 => 'home',
  micron5set2 => 'home',
  micron5set3 => 'home',
  micron5set4 => 'home',
  micron5set5 => 'home',
  micron5set6 => 'home',
  micron5set7 => 'home',
  micron5set8 => 'home',
  micron6dpag0665 => 'home',
  micron6set1 => 'home',
  micron6set2 => 'home',
  Omero1 => 'omero',
  Omero1files => 'omero',
  RaffOmero => 'omero',
#  snfs3davis => 'home',
  Users1A => 'home',
  Users1B => 'home',
  Users1C => 'home',
  Users1D => 'home',
  Users1E => 'home',
#  Users1Test => 'home',
  Users1Z => 'home',
  Users2 => 'home',
  Users3 => 'home',
#  wimm => 'home',
);


sub process_job
{
  my $fid = shift;
  my $backups = shift;
  my $line;

  do { $line = readline ($fid); return if ! defined $line; }
    until $line =~ /^  Backup Level: *Full/;

  do { $line = readline ($fid); return if ! defined $line; }
    until $line =~ m/^  FileSet: *"([a-zA-Z0-9 \-]*)/;
  my $fileset = $1;

  return unless exists ($filesets{$fileset});

  do { $line = readline ($fid); return if ! defined $line; }
    until $line =~ m/^  Scheduled time: *([a-zA-Z0-9\-]*)/;

  my $time = $1;

  do { $line = readline ($fid); return if ! defined $line; }
    until $line =~ m/^  SD Bytes Written: *([0-9,]*)/;
  my $bytes = $1;

  do { $line = readline ($fid); return if ! defined $line; }
    until $line =~ m/^  Termination:            (.*)$/;

  if ($1 =~ /^Backup OK/)
    {
      $time =~ /^(\d\d)-([a-zA-Z]{3})-(\d\d\d\d)$/;
      my %months = (
        Jan => '01',
        Feb => '02',
        Mar => '03',
        Apr => '04',
        May => '05',
        Jun => '06',
        Jul => '07',
        Aug => '08',
        Sep => '09',
        Oct => '10',
        Nov => '11',
        Dec => '12',
      );
      $time = $3 . $months{$2} . $1;
      $bytes =~ s/,//g;
      $backups->{$fileset}->{$time} = $bytes;
    }

  return;
}

sub main
{
  my $backups = {};

  for my $fpath (@_)
    {
      open (my $fid, "<", $fpath)
        or die "unable to open $fpath for reading: $!";
      while (defined readline ($fid))
        {
          process_job ($fid, $backups);
        }
      close ($fid);
    }

  while (my ($fset, $jobs) = each %$backups)
    {
      my $group = $filesets{$fset};
      open (my $fid, ">", "$group-$fset-usage.csv")
        or die "unable to open for write: $!";

      my @dates = sort (keys %$jobs);
      for my $date (@dates)
        {
          print {$fid} "$date," . $jobs->{$date} . "\n";
        }

      close ($fid);
    }

}

main (@ARGV);
