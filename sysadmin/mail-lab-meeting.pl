#!/usr/bin/env perl

## Copyright (C) 2014 David Pinto <david.pinto@bioch.ox.ac.uk>
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

## Short script to send automatic email notifications about upcoming lab
## meeting. Checks a wiki page with the syntax:
##
## * yyyy/mm/dd - speaker name
## * yyyy/mm/dd - speaker name
## * yyyy/mm/dd
## * yyyy/mm/dd - speaker name
##
## == subscriptions ==
## * email address
## * email address
## * email address
## * email address
##
## and on the day before the meeting will send an email to everyone. To send
## emails about a normal date for a meeting that will no happen, simply leave
## empty after date.
##
## This script uses Email::Sender::Simple which requires sendmail to be
## properly configured in the system. Obvioulsy, it also requires access
## to the wiki which may not be true if the wiki is not accessible outside
## the network.

use strict;
use warnings;

use Email::Sender::Simple qw(sendmail); # send mail
use Email::Simple;                      # create mail
use Email::Valid;                       # confirm it's not gibberish
use LWP::Simple;                        # get wiki page
use DateTime;                           # date comparisons

my $from  = 'Eva Wegel <eva.wegel@bioch.ox.ac.uk>';
my $wiki  = 'http://micronwiki.bioch.ox.ac.uk/wiki/Speakers_at_lab_meetings';

my @tos;      # list of valid emails to deliver the message
my $speaker = undef; # undef so we can later decide when send email about no meeting
my $tomorrow = DateTime->today->add (days => 1);

## We could use one of the mediawiki modules but our needs are really
## simple and would complicate installation on the server side.
## We assume that the only thing of interest on this page is in bullet
## lists, and we know which section we are by checking the level 2
## headers, i.e., == section name ==

my $source = get ("$wiki?action=raw");
die "Unable to get wiki page '$wiki'" unless $source;

my $section = "speakers"; # assume page starts with list of speakers
foreach my $line (split /^/, $source) {
  chomp $line;

  ## Capture level 2 headers
  $section = lc ($1) if ($line =~ m/^==\s*(.*?)\s*==$/);

  ## Skip non bullet lists
  next unless $line =~ s/^\*\s*//;

  if ($section eq "speakers" && ! $speaker) {
    ## line must be "YYYY/MM/DD - SPEAKER" (whitespace is ignored)
    $line =~ m/(\d{4})\/(\d{2})\/(\d{2})\s*-?\s*(.*)/; # "-?" to support no talks
    my $dt = DateTime->new(
      year  => $1,
      month => $2,
      day   => $3,
    );
    ## We will only care about tomorrows lab meeting
    next unless $dt == $tomorrow;
    $speaker = $4;

  } elsif ($section eq "subscriptions") {
    ## line should be a ready to go email address
    my $valid = Email::Valid->address ($line);
    push (@tos, $valid) if $valid;
  }
}

my $body;
my $subject;

if (! defined $speaker) {
  exit ();

} elsif ($speaker eq "") {
  $subject = "No Micron-NanO lab meeting tomorrow";
  $body = <<EOF;
Dear all,

just to remind you that there will be no lab meeting tomorrow.

The list of speakers can be found here:

http://micronwiki.bioch.ox.ac.uk/wiki/Speakers_at_lab_meetings

Best regards,
Eva
EOF

} else {
  $subject = "Micron-NanO lab meeting tomorrow at 2 pm";
  $body = <<EOF;
Dear all,

we will meet tomorrow at 2 pm in the 1st floor seminar room in Biochemistry.
The speaker will be $speaker.

The list of speakers can be found here:

http://micronwiki.bioch.ox.ac.uk/wiki/Speakers_at_lab_meetings

Best regards,
Eva
EOF

}

my $email = Email::Simple->create (
  header => [
    From    => $from,
    To      => join (", ", @tos),
    Subject => $subject,
  ],
  body => $body,
);

sendmail ($email);

