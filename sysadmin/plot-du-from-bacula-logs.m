#!/usr/local/bin/octave
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

## Example usage:
##
## ./plot-du-from-bacula-logs.m omero-*.csv plot-omero-du.png
##

pkg load financial;

function dmf = day_of_year_fraction (y, m, d)
  t = datenum (y, m, d);
  dm = t - datenum (y, 1, 1) +1;
  dmf = dm ./ yeardays (y);
endfunction

function t = scale_time (t)
  days = rem (t, 100);
  months = (rem (t, 10000) - days) / 100;
  years = round (t / 10000);

  if (any (days > 31))
    error ("what?");
  endif
  if (any (months > 12))
    error ("what?");
  endif

  year_fraction = day_of_year_fraction (years, months, days);
  t = years .+ year_fraction;

endfunction

function [all_t, interp_du] = interpolate_disk_usage (usage)
  all_t = cellindexmat (usage, ":", 1);
  all_t = unique (cell2mat (all_t(:)));

  nu = numel (usage);
  interp_du = zeros (numel (all_t), nu);
  for idx = 1:nu
    t = usage{idx}(:,1);
    du = usage{idx}(:,2);
    interp_du(:, idx) = interp1 (t, du, all_t, "linear", 0);
  endfor

endfunction


function main (varargin)

  data_fpaths = varargin(1:end-1);
  plot_fpath = varargin{end};

  ndata = numel (data_fpaths);
  usage = cell (ndata, 1);
  for f_idx = 1:ndata
    fpath = data_fpaths{f_idx};
    data = load (fpath);
    data = sortrows (data, 1);
    data(:,1) = scale_time (data(:,1));
    data(:,2) /= (1024^4); # disk usage in TB
    usage(f_idx) = data;
  endfor
  [all_t, interp_du] = interpolate_disk_usage (usage);
  total_du = sum (interp_du, 2);

  figure ();
  plot (all_t(1:end-13), total_du(1:end-13), "-r");
  hold on;

  colours = "kgbmcw"; # not red, that is for the total only
  ncolours = numel (colours);
  for idx = 1:ndata
    plot (usage{idx}(:,1), usage{idx}(:,2),
          ["--x" colours(mod (idx-1, ncolours) +1)]);
  endfor
  hold off;
  box ("off");
  print (plot_fpath);

endfunction

main(argv (){:});
