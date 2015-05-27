#!/usr/bin/perl -T
use utf8;

## Copyright (C) 2015 David Pinto <david.pinto@bioch.ox.ac.uk>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 3 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, see <http://www.gnu.org/licenses/>.

## Parse an ImageJ update site db.xml file and serve latest release.
##
## Problem
##
## Not everyone uses the ImageJ updater.  We distribute plugins using the
## updater which makes it thougher for those who don't want to.  We could
## link those users to the directory with all the plugins and let them
## download the right version.  This works fine as long as there is only
## one or two plugins in the update site.  Also, the filename of the jar
## file has a timestamp after the file extension, so we can't just link to
## it (apparently, users who don't like to use the updater are smart enough
## to manually download and install the plugin but too stupid to realize
## they have to remove the timestamp from the filename).
##
## Solution
##
## This script parses a specific update site db.xml for a plugin name,
## and serves back a file with the correct file extension.  An alternative
## could be to have this script as a cron job, and updating a symlink to
## the latest jar file.
##
## Usage
##
## As a CGI script, it takes two arguments in the URL:
##
##  site - the name of the update site (name of the the directory where the
##    update site is).
##  plugin - the name of the plugin, excluding the dash before version number
##    but including any underscore it has before the version number, and the
##    ImageJ directory where it is placed.  Example, 'plugins/SIMcheck_' or
##    'jars/scifio-jai-imageio'.
##

use strict;
use warnings;
use 5.012;

use List::Util;
use IO::Uncompress::Gunzip;
use File::Spec;
use CGI;
use CGI::Carp qw(fatalsToBrowser);

use XML::LibXML;

## All of our update sites should be in this directory
my $fiji_update_base_dir = "/var/www/downloads/fiji_update/";

sub get_update_site
{
  my $base_path = shift;
  my $tainted_site = shift;

  ## untaint wanted_site, check if it is a directory here
  my $site_path;
  opendir (my $base_dir, $base_path)
    or die ("Unable to opendir '$base_path': $!");
  while (my $file = readdir ($base_dir))
    {
      if ($tainted_site eq $file)
        {
          $site_path = File::Spec->catfile ($base_path, $file);
          last;
        }
    }
  closedir ($base_dir);

  ## NOTE: do not print the tainted update site name!  Might be used
  ## to inject client-side script
  die ("Unable to find requested update site")
    if ! defined $site_path;

  ## Now check if it is an ImageJ update site
  my $db_file = File::Spec->catfile ($site_path, "db.xml.gz");
  return (-f $db_file) ? $site_path : undef;
}

## Note that jar_name must include the directory path, e.g., "jars/loci-common"
sub find_latest
{
  my $site_path = shift;
  my $jar_name = shift;

  my $db_xml;
  my $db_path = File::Spec->catfile ($site_path, 'db.xml.gz');
  IO::Uncompress::Gunzip::gunzip ($db_path, \$db_xml)
    or die ("gunzip '$db_path' failed: $IO::Uncompress::Gunzip::GunzipError");

  my $dom = XML::LibXML->load_xml (string => (\$db_xml));
  my $root = $dom->documentElement ();
  die ("Invalid db.xml for ImageJ update site")
    if $root->nodeName() ne "pluginRecords";

  ## https://github.com/scijava/scijava-common/blob/scijava-common-2.41.0/src/main/java/org/scijava/util/FileUtils.java#L174
  ## with a few added (?:...) to avoid capture groups we are not interested
  my $re = qr/^(.+?)(?:-\d+(?:\.\d+|\d{7})+[a-z]?\d?(?:-[A-Za-z0-9.]+?|\.GA)*?)?(?:(?:-(?:swing|swt|shaded|sources|javadoc|native))?(?:\.jar(-[a-z]*)?))$/;

  for my $root_child ($root->childNodes ())
    {
      next unless $root_child->nodeName() eq "plugin";

      my $filename_att = List::Util::first {$_->getName () eq "filename"}
                                           $root_child->attributes ();
      next unless defined $filename_att;
      my $filename = $filename_att->getValue ();

      next unless $filename =~ $re && $1 eq $jar_name;

      for my $plugin_child ($root_child->childNodes ())
        {
          next unless $plugin_child->nodeName() eq "version";
          my $timestamp_att = List::Util::first {$_->getName () eq "timestamp"}
                                                $plugin_child->attributes ();
          next unless defined $timestamp_att;
          my $timestamp = $timestamp_att->getValue ();
          return File::Spec->catfile ($site_path,
                                      join ("-", $filename, $timestamp));
        }
    }
  return undef;
}

sub clean_jar_name
{
  my $jar_path = shift;
  my $jar_name = (File::Spec->splitpath ($jar_path))[-1];
  $jar_name =~ s/(?<=\.jar)-\d+$//;
  return $jar_name;
}

sub serve_jar
{
  my $jar_path = shift;
  my $jar_name = shift;

  my $q = CGI->new ();

  print $q->header(
    -type => 'application/x-java-archive',
    -attachment => $jar_name,
  );

  open (my $jar_file, "<", $jar_path)
    or die "Failed to open '$jar_path': $!";

  ## See CGI programming with perl 13.2.1.1
  binmode STDOUT;
  my $buffer;
  print $buffer while (read ($jar_file, $buffer, 4096));

  close $jar_file;
}

## $plugin gets untainted by matching against the directory names and
## selecting the directory that matches.
## $site gets untainted by matching against filenames on the db.xml file.
my $plugin  = CGI::url_param ("plugin") || die ("No plugin specified");
my $site    = CGI::url_param ("site")   || die ("No site specified");

my $site_path = get_update_site ($fiji_update_base_dir, $site);
my $jar_path = find_latest ($site_path, $plugin);
if (! defined $jar_path && ! -f $jar_path)
  { die ("jar file for plugin not found"); }

my $jar_name = clean_jar_name ($jar_path);
serve_jar ($jar_path, $jar_name);

