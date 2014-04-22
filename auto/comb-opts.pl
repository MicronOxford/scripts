#!/usr/bin/env perl
use utf8;

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

=head1 NAME

comb-opts - generates all possible combinations (cartesian product) of options.

=head1 SYNOPSIS

B<comb-opts> S<[B<--opt1> B<start:step:end>]> S<[B<--opt2> B<foo|bar>]> B<template>

=head1 DESCRIPTION

This command does not have options per se. Each option-looking argument, will
be a key to be used in the B<template>. Each `option' must have a matching
argument that defines a range of values. Each possible combination of values
from each option, also known as carteseian product of a multiset, will be
used to print the B<template>.

For a concrete simple example, the following command:

 comb-opts --m 'gaussian|poisson' --p 0:3:9 \
   'out_file_${m}_${p}.tif -noise=${m} -p=${p}'

will print the following lines:

 out_file_gaussian_0.tif -noise=gaussian -p=0
 out_file_gaussian_3.tif -noise=gaussian -p=3
 out_file_gaussian_6.tif -noise=gaussian -p=6
 out_file_gaussian_9.tif -noise=gaussian -p=9
 out_file_poisson_0.tif -noise=poisson -p=0
 out_file_poisson_3.tif -noise=poisson -p=3
 out_file_poisson_6.tif -noise=poisson -p=6
 out_file_poisson_9.tif -noise=poisson -p=9

each argument separated by the null character, and each template with a
newline, so it can be used with xargs as in:

 comb-opts -p 0:3:9 -m 'gaussian|poisson' \
   'out_file_${p}_${m}.tif -p=${p} -noise=${m}' | xargs -n3 -0 \
   cmd in_file.tif

Which would be the same as running the following commands:

 cmd in_file.tif out_file_gaussian_0.tif -noise=gaussian -p=0
 cmd in_file.tif out_file_gaussian_3.tif -noise=gaussian -p=3
 cmd in_file.tif out_file_gaussian_6.tif -noise=gaussian -p=6
 cmd in_file.tif out_file_gaussian_9.tif -noise=gaussian -p=9
 cmd in_file.tif out_file_poisson_0.tif -noise=poisson -p=0
 cmd in_file.tif out_file_poisson_3.tif -noise=poisson -p=3
 cmd in_file.tif out_file_poisson_6.tif -noise=poisson -p=6
 cmd in_file.tif out_file_poisson_9.tif -noise=poisson -p=9

=head2 Overkill

If you only want to combine a couple options, and you have minimum knowledge
of bash, this is pretty much the same as doing:

 for opt1 in $(seq 0 0.5 3); do
   for opt2 in on off; do
     command -a $opt1 -b $opt2 -c "${opt1}_${opt2}.file";
   done;
 done;

So if this is your case, save yourself some trouble and go with it.

=head1 SEE ALSO

xargs(1)

=cut

use strict;
use warnings;
use Pod::Usage;
use Regexp::Common;
use Math::BigFloat;   # avoid floating point error when using numeric ranges
use Text::ParseWords; # to split the template into parts

my $separator = "\0"; # null is always safer (to use output with xargs -0)

## Input must be an even number. Two arguments per option (name and range
## of values) plus the template at the end.
if ((@ARGV %2) == 0) {
  pod2usage ("Incorrect number of arguments");
}
my $template = pop (@ARGV);

## Get all keys
my %mset = @ARGV;
for (keys %mset) {
  ## confirm that the parsing was correct by checking that keys start
  ## with --. Then remove the -- from the key to ease things later.
  pod2usage ("Field named $_ does not start with --")
    unless $_ =~ s/^--//;
  $mset{$_} = delete $mset{"--$_"};
}

## Prepare the template for printf, get the order keys in the template
## appear, and check that all keys are valid.
my @insets;
while ($template =~ s/\${(.*?)}/\%s/) { # replace each ${key} with %s for printf
  die ("Unknown template key `$1'")
    unless grep {$1 eq $_} keys %mset;
  push (@insets, $1);
}
$template .= $separator;

## Build the set of values for each key. This will replace each value, with a
## reference for an array with the complete set (even if it's only 1 element).
while (my ($key, $val) = each %mset) {
  my @range;

  ## Numeric range
  if ($val =~ m/^($RE{num}{real}):($RE{num}{real})(:($RE{num}{real}))?$/ ) {
    my $start = Math::BigFloat->new($1);
    my $incr  = $3 ? $2 : 1;
    my $last  = $3 ? $4 : $2;

    ## Maybe I'm being overly paranoid with floating point errors??
    my $now = $start;
    for (my $i = 1; $now <= $last; $i++) {
      push (@range, $now);
      $now = $start + $incr * $i;
    }

  ## Multiple string values
  } elsif ($val =~ m/\|/) {
    ## FIXME if someone wants to use an actual | on the text they're screwed
    @range = split ('\|', $val);

  ## options without multiple values, are still treated as single element one
  } else {
    push (@range, $val);
  }

  $mset{$key} = \@range;
}

## Compute the cartesian product -- all combinations from the multiset.
## Create all possible combinations from each set using recursion so we
## can handle an arbitrary number of sets. Recursion depth will be equal
## to the number of sets.

my @keys = keys %mset;
my $n_sets = @keys;

my %prod; # will have each possible combination ready to print
sub cartesian_product {
  my $n = shift;
  if ($n == $n_sets) {
    my @list = map {$prod{$_}} @insets;
    my $str = sprintf $template, @list;
    ## The string really needs to be splitted otherwise it will be
    ## passed as a single long argument with spaces to next command.
    my @args = Text::ParseWords::quotewords ('\s+', 0, $str);
    print join ($separator, @args);
  } else {
    for (my $i = 0; $i < @{$mset{$keys[$n]}}; $i++) {
      $prod{$keys[$n]} = $mset{$keys[$n]}->[$i];
      cartesian_product ($n+1);
    }
  }
}

cartesian_product (0);

