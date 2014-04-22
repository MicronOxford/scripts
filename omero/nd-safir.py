#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

## TODO consider use http://micronwiki.bioch.ox.ac.uk/wiki/Priism_Denoise and
##      http://micronwiki.bioch.ox.ac.uk/wiki/Priism/IVE,_Denoising,_Priithon_%26_Editor
##      to expand what options to use on the description below.
"""
Run nD-SAFIR - image denoising on selected images.

This patch-based denoising algorithm is described in Boulanger, J. et al (2007).
Basically it makes use of redundancy in an image sequence (i.e. multiple
samples of the same features) to average equivalent pixels and reduce the
apparent noise level. You can also refer to the ndsafir HTML manual from the
Sedat lab, but be aware that the description of the iterations is somewhat
confusing.

Terms and conditions
--------------------
Due to the restrictive terms of the MTA (Material Transfer Agreement), please
discuss with Micron before using data denoised by this algorithm for external
presentation or publication.

References
----------
Boulanger, Jerome, Charles Kervrann, and Patrick Bouthemy. "Space-time
adaptation for patch-based image sequence restoration." Pattern Analysis and
Machine Intelligence, IEEE Transactions on 29.6 (2007): 1096-1102.
"""

import tempfile
import os
import os.path
import subprocess

import omero.scripts
import omero.gateway
import omero.util.script_utils
import distutils.spawn

from omero.rtypes import rstring, rlong, robject

NDSAFIR  = distutils.spawn.find_executable ("ndsafir_priism")
TIFF2MRC = distutils.spawn.find_executable ("tiff2mrc")

def is_mrc (img):
    """
    Return true if image has an mrc image file.

    The specs for this image format say that long #53 should have the string
    "map" but apparently this is not being enforced. A MRC file created with
    Priism's tiff2mrc does not have this string, even though it bother to
    create the "Converted by tiff2mrc" string in the label field.

    Because of this, we end being limited to check the file extension :(

    @type  img: OriginalFileWrapper
    @param img: Image of unknown format.
    @rtype: Boolean
    @return: True if image has an mrc file, False otherwise.
    """
    rv = False
    ## XXX Unfortunately, the magic/signature of the MRC file format is not
    ## usually enforced so many MRC files won't actually have it. If we decide
    ## to enforce MRC file specs, this is how to do it. Note that the specs
    ## do not specify if it's "MAP ", " MAP", or lower case so when I can find
    ## a true MRC file that follow the specs, we can finish this:
    ##
    ##  http://www2.mrc-lmb.cam.ac.uk/image2000.html  <-- MRC specs
    ##
    ## s = f.getFileInChunks (buf = 53*4).next ()
    ## # see "f.getFileInChunks (buf=256*4).next ()[56*4:]" to read the label
    ## if (s[52*4:53*4] == "MAP ")
    ##     rv = True

    ## identify format based on file extension
    ext = os.path.splitext (img.getName ())[1]
    if (ext.lower() == ".mrc"):
        rv = True
    return rv

def get_mrc_fpath (img):
    """
    Get filepath for a mrc file of the image.

    This will check if the imported file was an MRC file in which case a
    path for this is generated. If not, then an OmeTIFF file is generated
    and the converted to MRC using Priism's TIFF2MRC.

    @type  img: _ImageWrapper
    @param img: Image of unknown format.
    @rtype:     String
    @return:    Filepath for a MRC file.
    """

    mrcpath = ""
    for f in img.getImportedImageFiles ():
        if is_mrc (f):
            tmpf = tempfile.NamedTemporaryFile (suffix = ".mrc", delete = False)
            for c in f.getFileInChunks ():
                tmpf.write (c)
            tmpf.close ()
            mrcpath = tmpf.name

    if not mrcpath:
        raise Exception ("Conversion of tiff2mrc not yet implemented")

    return mrcpath


def run_ndsafir (objs, params, client):
    """
    Run ndsafir program on the image.
    """

    if not NDSAFIR:
        raise Exception ("Unable to find ndsafir_priism in the system")

    ## Construct args we will use when calling ndsafir_priism
    opts = []
    opts.append ("-noise=%s"    % params["noise_model"])
    opts.append ("-p=%s"        % params["patch_radius"])
    opts.append ("-sampling=%s" % params["sampling"])

    ## For whatever reason, the ndsafir version we got seems to only work with
    ## MRC files. When a TIFF file is used, it just hangs forever and takes up
    ## all CPU. Apparently, the version Sussex got works fine with TIFFs but is
    ## not multi-thread. Could it be an issue with my build?
    for iw in objs:
        fin  = get_mrc_fpath (iw)
        fout = tempfile.NamedTemporaryFile (suffix = ".mrc", delete = False).name

        try:
            ## TODO create a log file to where we redirect STDOUT and STDERR
            ##      and attache to the denoised image
            args = [NDSAFIR, fin, fout] + opts
            ret = subprocess.call (args)
            if (ret != 0):
                raise Exception ("Trouble running ND-safir")

        except OSError, e:
            raise Exception ("%s execution failed: %s" % (args[0], e))

#        os.unlink (fin)
#        os.unlink (fout)


def runAsScript (doc):
    """
    The main entry point of the script, as called by the client via the
    scripting service, passing the required parameters.
    """

    ## TODO still missing more options from the application
    ## TODO select where to save the denoise images. As a new dataset or
    ##      as an attachment like BatchExport?
    client = omero.scripts.client (
        "Denoise image with ND-SAFIR",
        doc,
        omero.scripts.String (
            "Data_Type", optional = False, grouping = "1.1",
            values = ["Dataset", "Image"], default = "Image",
            description = "Choose Images by their IDs or via their 'Dataset'",
        ),
        omero.scripts.List (
            "IDs", optional = False, grouping = "1.2",
            description = "List of Dataset IDs or Image IDs",
        ),
        ## Defaults chosen for the actual denoising are the same as the
        ## default values of ndsafir
        omero.scripts.String (
            "noise_model", grouping = "2", default = "poisson",
            values = ["poisson", "gaussian", "auto"],
            description = "Select how to model the noise",
        ),
        omero.scripts.Int (
            "patch_radius", grouping = "3", default = 1,
            description = "Sets the patch radius to be N pixels"
        ),
        omero.scripts.Int (
            "sampling", grouping = "4", default = 1,
            description = "Sets the sampling interval"
        ),

        version      = "0.0.1",
        authors      = ["David Pinto"],
        institutions = ["Micron, University of Oxford"],
        contact      = "david.pinto@bioch.ox.ac.uk",
    )

    try:
        parameterMap = {}
        for key in client.getInputKeys ():
            if client.getInput (key):
                parameterMap[key] = client.getInput (key, unwrap = True)

        conn = omero.gateway.BlitzGateway (client_obj = client)
        objs, msg = omero.util.script_utils.getObjects (conn, parameterMap)

        if not objs:
            client.setOutput ("Message", rstring ("No images found on selected IDs"))
        else:
            run_ndsafir (objs, parameterMap, client)

    except Exception as e:
        client.setOutput ("Message", rstring ("Error: %s" % str (e)))

    finally:
        client.setOutput ("Message", rstring ("Finished denoising successfully"))
        client.closeSession ()

if (__name__ == "__main__"):
    runAsScript (__doc__)

