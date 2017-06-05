#!/usr/bin/env perl

## Copyright (C) 2014, 2015 David Pinto <david.pinto@bioch.ox.ac.uk>
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

use Tie::RefHash;

use Email::Sender::Simple qw(sendmail); # send mail
use Email::Simple;                      # create mail
use Email::Valid;                       # confirm it's not gibberish
use LWP::Simple;                        # get wiki page
use DateTime;                           # date comparisons

my $from  = 'Ian Dobbie <ian.dobbie@bioch.ox.ac.uk>';
my $wiki  = 'http://wiki.micron.ox.ac.uk/w/Speakers_at_lab_meetings';

my @tos;      # valid emails to deliver the message

## we are assuming that there is at most, one talk per day
my %talks;    # all talks listed.  We do search only for the next because we
              # also want to find the talk after (and we don't know if we will
              # read them sorted
tie %talks, 'Tie::RefHash';

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

  if ($section eq "speakers") {
    ## line must be "YYYY/MM/DD - SPEAKER" (whitespace is ignored)
    $line =~ m/(\d{4})\/(\d{2})\/(\d{2})\s*-?\s*(.*)/; # "-?" to support no talks
    $talks{DateTime->new(year => $1, month => $2, day => $3)} = $4;

  } elsif ($section eq "subscriptions") {
    ## line should be a ready to go email address
    my $valid = Email::Valid->address ($line);
    push (@tos, $valid) if $valid;
  }
}

my $next_date = undef;
my $following_date = undef;
my $tomorrow = DateTime->today->add (days => 1);
for my $date (sort keys %talks) {
  if ($date == $tomorrow) {
    $next_date = $date;
  } elsif ($next_date) {
    $following_date = $date;
    last;
  }
}

exit () if (! defined $next_date);

my $subject;

my $next_talk_body;
if ($talks{$next_date}) {
  $subject = "Micron-NanO lab meeting tomorrow at 2 pm";
  $next_talk_body = <<EOF;
We will meet tomorrow at 2 pm in the 1st floor seminar room in Biochemistry.
The speaker will be $talks{$next_date}.
EOF
} else {
  $subject = "No Micron-NanO lab meeting tomorrow";
  $next_talk_body = <<EOF;
This is to remind you that there will be no lab meeting tomorrow.
EOF
}

my $following_talk_body = "";
if ($talks{$following_date}) {
  $following_talk_body = <<EOF;
The speaker for the following meeting will be $talks{$following_date}.
EOF
}

my $body = <<EOF;
Dear all,

$next_talk_body
$following_talk_body
As always, the list of speakers can be found on our wiki [1].

Best regards,
Micron

[1] $wiki
EOF

my $email = Email::Simple->create (
  header => [
    From    => $from,
    To      => join (", ", @tos),
    Subject => $subject,
  ],
  body => $body,
);

sendmail ($email);
