#!/usr/bin/perl -T
use utf8;

## Copyright (C) 2014 David Pinto <david.pinto@bioch.ox.ac.uk>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU Affero General Public License as published by
## the Free Software Foundation; either version 3 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU Affero General Public License
## along with this program; if not, see <http://www.gnu.org/licenses/>.

## A perl CGI script to get an image from one of the microscopes, run
## Matlab's code (Rainer's fastSPDMome), and display it on the web browser.
## Batch processing will be implemented later on via Omero, this is only so
## that users can see what they are imaging while adjusting parameters.
##
## This requires large files to be uploaded but the generated images, the ones
## sent back to the user for display, should be below 1MB. An alternative would
## be to make users move them into /micron1, and give them the a list of files
## to select from.

use strict;
use warnings;
use POSIX ();     # for &WNOHANG XXX consider replacing with IPC::Run
use IPC::Open2;   # XXX consider replacing with IPC::Run
use File::Copy;
use File::Temp;
use File::Spec;
use File::Basename;
use Graphics::Magick; # for tiff->jpg conversion (firefox does not display tiff)
use CGI; # XXX consider replacing with Dancer or Mojolicious::Lite

## We are running in taint mode so we must set PATH ourselves. Since, we are
## specifying the absolute path to Matlab, we could just clear PATH.
## Unfortunately, the Matlab command is actually a bash script which will need
## the following in the path.
$ENV{PATH} = join(":", qw(/bin /usr/bin));

##
## Temporary and pseudo persistent file configuration
##

## The script will create temporary directories (one for each input image),
## where it keeps all files during the computation. These are cleaned up in
## the end. The files actually served for the web, will be moved out into
## a separate, persistent directory. These files are much smaller (less
## than 1MB), but may accumulate over time.

my $webroot = "fastSPDMome"; # root of all this as viewed from the web
my $srv_root = "/var/lib/"; # directory where $webroot will exist

## Where on the filesystem, all temporary files reside. Automatically
## removed at the end.
my $tmp_dir = File::Temp::newdir(
  POSIX::strftime("%Y%m%d", localtime()) . "-XXXX",
);

## The absolute path, from the POV of the filesystem, of what will be served
## by Apache for this run. Not removed in the end.
my $srv_run = File::Temp::tempdir(
  POSIX::strftime("%Y%m%d", localtime()) . "-XXXX",
  DIR => File::Spec->catfile($srv_root, $webroot)
);

## The directory for this run, POV of the web "$webroot/YYYMMDD-XXXX"
my $web_run = File::Spec->catfile((File::Spec->splitdir($srv_run))[-2, -1]);

##
## CGI configuration
##

## Instead of a simple "500 server error" page, also display the actual error
## message to the browser (we kinda trust the users) and add a message to
## contact micron.
use CGI::Carp qw(fatalsToBrowser);
CGI::Carp::set_message <<"END";
<p>
Please contact David Pinto from Micron via phone on extension 13359 or
mail <a href="mailto:david.pinto\@bioch.ox.ac.uk">david.pinto\@bioch.ox.ac.uk</a>.
</p>
<p>
Please keep this error message and the value '$web_run' for reference.
</p>
END
$CGI::POST_MAX = 1024 * 1000 * 200; # max 200MB file uploads

##
## Computation/Matlab configuration
##

my $matlab_path = '/usr/local/MATLAB/R2010b/bin/matlab';
my @matlab_args = ('-nodisplay', '-nosplash'); # consider -nojvm in the future
my $fastSPDMome_path = '/usr/local/share/fastSPDMome/';

## Maximum time allowed (in seconds) before killing the process.
## This is more than just the time given to Matlab. Even if we give Matlab
## more time, the web client will time out give up on the connection, and the
## the web server timeout our CGI script (default value for Apache in Debian
## is 300sec). Still, all test images thus far take between 2-3min so we should
## be safe.
my $max_time = 4 * 60;

##
## Get parameters via CGI
##
my $cgi = new CGI;

sub untaint_file {
  ## We cannot use the file where it is after upload because the Matlab code
  ## will create other files on the same directory. We could change the Matlab
  ## code to save files somewhere else but we would still have to sanitize
  ## the file names before passing them to Matlab. That would imply moving the
  ## file which we can't do since it's open, so we really have to copy them.
  my $name = shift;
  die ("File too large for upload")
    if ! defined $cgi->param($name);

  my $fh = $cgi->upload($name);
  die ("Failed to upload image")
    if ! $fh;

  ## The filename will be the most vulnerable thing added to the Matlab code.
  ## The only character that could end a string and inject some extra commands
  ## is the quote. That needs to go. However, we are communicating with Matlab
  ## via pipes (see comments below why). This means that a newline could cause
  ## a syntax error, which would cancel further evaluation of code, and
  ## anything after would be evaluated alone, on its own line. So we will just
  ## play safe and keep only the characters we know to be safe.
  my $file_name = (File::Spec->splitpath($cgi->param($name)))[2];
  $file_name =~ s/[^a-z0-9_\-+=\[\]:;"!%() \.]//gi;

  ## Using tempfile means we don't have to worry about removing it in
  ## the end but adds random string to the filename.
  my ($tmpfh, $tmpfile) = File::Temp::tempfile(
    $file_name . "XXXX",  # template must have at least 4 X
    SUFFIX  => '.tif',
    DIR     => $tmp_dir,
    UNLINK  => 1,         # make sure this file is removed when we exit
  );
  print {$tmpfh} $_ while (<$fh>);
  close $tmpfh;
  return $tmpfile;
}

sub untaint_float {
  ## This comes from a text field so we must use a regexp to untaint it. The
  ## following will matches '2', '02', '2.00', and '.2' with optional
  ## whitespace around it.
  my $in = $cgi->param(shift);
  $in =~ m/^\s*   # allow but do not capture prepad whitespace
              (   # start of captured group
               ([0-9]+(\.[0-9]*)?)  # '2', '02', or '2.00' (but not '2.')
               |                    # or
               (\.[0-9]+)           # '.02'
              )   # end of captured group
           \s*$   # allow but do not capture postpad whitespace
          /x;
  return $1;
}

sub untaint_bool {
  ## These come from a checkbox. If defined they were selected.
  my $in = $cgi->param(shift);
  return defined $in ? "true" : "false";
}

my $image_path      = untaint_file  ('data');
my $gain_correction = untaint_float ('gc');
my $pixel_size      = untaint_float ('px');
my $plot_distance   = untaint_bool  ('plotd');
my $filter1         = untaint_bool  ('filter1'); # correction for long-lasting fluorescence
my $filter2         = untaint_bool  ('filter2'); # correction for blinking fluorophores
my $filter3         = untaint_bool  ('filter3'); # cut off small distances

###
### Generate Matlab code
###

my $code = <<END;
status = 0;
try
  addpath ('/usr/local/lib/MATLAB/site-toolboxes/dipimage/dipimage');
  dip_initialise ('silent');
  addpath ('$fastSPDMome_path');
  fastSPDMome ('$image_path', $gain_correction, $filter1, $filter2, $pixel_size, $plot_distance, $filter3);
catch err
  disp (['error: ' err.message()]);
  disp (err.stack ());
  status = 1;
end
exit (status);
END

##
## Call Matlab
##
## Why are we forking a process and communicating over pipes, instead of
## just using "system(..., '-r', command)"? Because:
##    1) '-r' is really not like "--eval". Because the session persists after
##    the command, if there's any syntax error such as:
##            try, foo ('bar' bad-nonescaped-quote'); catch, end, exit (1);
##    there is no catching and the process will hang forever waiting for input.
##    2) the matlab command is actually a bash script and seems to do funny
##    (read, weird) things when there are newlines. I do not know the full
##    extent of things that may break '-r'.
##    3) using pipes makes it much easier to set a maximum allowed time for
##    computation before giving up (which at the moment is most likely caused
##    by the matlab process waiting for input after error instead of exiting).
##    4) I guess in the future, if processing becomes slower, this script will
##    just start the process and return the session. This is closer to that.

sub run_matlab {
  ## We wish we could just use open() to write to Matlab but Matlab does not
  ## have a silent option so we need to redirect its STDOUT somewhere. Because
  ## of that we are using IPC::Open2::open2.

  ## We won't really plan on using this, but sincewe have to redirect it, we
  ## might as well it to somewhere useful in the future instead of devnull.
  open(my $matlab_stdout, ">", File::Spec->catfile($tmp_dir, "matlab.stdout"))
    or die("Could not open file for Matlab's STDOUT");

  my $pid = IPC::Open2::open2($matlab_stdout, my $pipe,
                              $matlab_path, @matlab_args);

  print {$pipe} $code;

  my $p_time    =  0;   # how much time has passed
  my $interval  = 10;   # time interval (seconds) to check process
  my $overtime  =  0;   # has it exceeded the allowed time?
  my $running   =  1;   # is the process still running?
  do {
    sleep ($interval);
    $p_time += $interval;
    ## waitpid returns the process pid after it dies
    $running  = waitpid ($pid, POSIX::WNOHANG) != $pid;
    $overtime = $p_time > $max_time;
  } until (! $running || $overtime);

  die ("error running Matlab: $!")
    if $? != 0;

  if ($overtime) {
    kill "SIGTERM", $pid;
    die ("Computation was taking too long so we stopped it.");
  }
}

sub get_output_files {
  ## FIXME  we should probably make this an argument to the Matlab code or we
  ##        run the risk of not getting the right thing one day. We only check
  ##        for tif files with "_imstres_pz_" on their name. However, because
  ##        the input file may already have it on the name, we check all of
  ##        them and return the one with it near the end. The temporary
  ##        directory should only have the original files plus the generated
  ##        images which have the same basename appended with:
  ##          * [fname '_positions.txt']
  ##          * [fname '_impoints_pz_' num2str(pxlsz) '.tif']
  ##          * [fname '_imstres_pz_' num2str(pxlsz) '.tif']
  ##          * [fname '_locmic_log.txt']
  ##          * [fname '_Distances.tif']

  opendir (my $dirh, $tmp_dir)
    or die $!;
  my @fnames = readdir ($dirh);
  close ($dirh);

  my %files;
  foreach my $key ("imstres", "log", "positions") {
    ## Get file name with the key closer to the end of the filename
    my %rind = map {$_ => rindex ($_, $key)} @fnames;
    $files{$key} = (sort {$rind{$b} <=> $rind{$a}} @fnames)[0];
    ## TODO the file names come untainted from readdir but we can't really
    ##      untaint them. Since only the web browser should be writing to this
    ##      dir, and since it is created and removed at the start and end of the
    ##      script, it should be safe to untaint it this way.
    $files{$key} =~ m/(.*)/;
    $files{$key} = $1;
  }
  return %files;
}

run_matlab();
my %output = get_output_files();

##
## Create HTML to display results
##
sub save_file {
  ## Will move files from the temporary directory, to a more persistent
  ## place, so it can be served by the web browser. This is usually the
  ## equivalent of moving from /tmp/xx to /var/lib/app/xx
  my $fname  = shift;
  my $source = File::Spec->catfile($tmp_dir, $fname);
  my $dest   = File::Spec->catfile($srv_run, $fname);
  ## We do not die if it fails, as we might still have other things to salvage.
  $dest = undef unless File::Copy::move($source, $dest);
  my $dest_web  = File::Spec->catfile("/", $web_run, $fname);
  return ($dest, $dest_web);
}

sub slurp_log {
  ## This either returns the whole log (small file) in a single string,
  ## or an empty string if it failed to open the file.
  my $fpath = shift;
  my $log = "";
  if (open (my $fh, $fpath)) {
    $log = do {local $/; <$fh>};
  }
  return $log;
}

sub get_display {
  ## Not all browsers will be able to display the tiff generated, we need
  ## to convert it into something else such as jpg or png.
  my $tiff_path = shift;
  my $tiff_web  = shift;
  my $jpeg_path = $tiff_path . ".jpg";
  my $jpeg_web  = $tiff_web  . ".jpg";

  my $image = Graphics::Magick->new;
  ## Something bad happened if any of the methods returns non-zero
  if (! $image->Read($tiff_path)
      and ! $image->Write($jpeg_path)) {
    return $cgi->a({href => $tiff_web}, $cgi->img({-src => $jpeg_web}));
  } else {
    return $cgi->a({href => $tiff_web}, "Conversion to JPEG failed. Download TIFF.");
  }
}

sub offer_positions {
  my $positions_web = shift;
  return $cgi->a({href => $positions_web},
                 "Download positions matrix text file");
}

sub center_pre {
  return $cgi->p($cgi->table({-style=>"display: inline-table;text-align:left;"},
    $cgi->Tr([$cgi->td($cgi->pre(shift))])
  ));
}

## The reconstructed image. That's the main thing we care about.
my ($imstres_path, $imstres_webpath) = save_file($output{'imstres'});
my ($positions_path, $positions_webpath) = save_file($output{'positions'});

print $cgi->header();
print $cgi->start_html(-title => 'localized', -BGCOLOR => "#353535");

print $cgi->div({-style=>"text-align:center;color:#CCCCCC"},
  center_pre(slurp_log (File::Spec->catfile($tmp_dir, $output{'log'}))),
  $cgi->p(get_display($imstres_path, $imstres_webpath)),
  $cgi->p(offer_positions($positions_webpath)),
  center_pre($code),
);

print $cgi->end_html();
