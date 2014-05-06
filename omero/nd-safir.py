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

Options
-------
Documentation for each of the options is available on the [Micron wiki]
(http://micronwiki.bioch.ox.ac.uk/wiki/Ndsafir)

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
import struct

import omero.scripts
import omero.gateway
import omero.util.script_utils
import distutils.spawn

import omero.rtypes
from omero.rtypes import rstring, rlong, robject

NDSAFIR  = distutils.spawn.find_executable("ndsafir_priism")
TIFF2MRC = distutils.spawn.find_executable("tiff2mrc")

def is_mrc (img):
    """
    Return true if image has an mrc image file.

    There seems to be at least 2 variants of the MRC format. An old one
    which Priism uses, and a new version, also known as MRC Image2000.
    There is no "signature" on the header of the old version, we can only
    check if the file extension is correct.

    @type  img: OriginalFileWrapper
    @param img: Image of unknown format.
    @rtype: Boolean
    @return: True if image has an mrc file, False otherwise.
    """
    ## Docs:
    ##  * Original MRC image2000 specs:
    ##      http://www2.mrc-lmb.cam.ac.uk/image2000.html
    ##  * IMOD reference for file specs with mention of old format:
    ##      http://bio3d.colorado.edu/imod/doc/mrc_format.txt
    ##  * Priism take on the subject:
    ##      http://msg.ucsf.edu/IVE/IVE4_HTML/mrc2image2000.html
    rv = False

    ext = os.path.splitext (img.getName ())[1]
    s = img.getFileInChunks (buf = 53*4).next ()

    ## New versions of the MRC format are supposed to have this signature
    ## but I'm unsure if Priism is even capable of reading them...
    if (len (s) >= 53*4 and s[52*4:53*4] == "MAP "):
        rv = True
    ## old versions will need to check with file extension
    elif (ext.lower() == ".mrc"):
        rv = True

    return rv

def is_dv (img):
    """
    Return true if image has a dv image file.

    @type  img: OriginalFileWrapper
    @param img: Image of unknown format.
    @rtype: Boolean
    @return: True if image has a dv file, False otherwise.
    """
    ## According to bioformats's DeltavisionReader.java (which is GPL), a
    ## DV file must read 0xa0c0 or 0xc0a0 at pos 96.
    rv = False
    s = img.getFileInChunks (buf = 98).next ()
    if (len (s) >= 98):
        m = struct.unpack ("H", s[96:98])
        if (m == 49312 or m == 41152):
            rv = True
    return rv


def get_valid_fpath(img):
    """
    Get filepath for the input file of the image.

    This will check if the imported file was a valid format for nd-safir
    in which case a path to it is returned. If not, then an OmeTIFF file
    is first generated and the converted to MRC using Priism's TIFF2MRC.

    @type  img: _ImageWrapper
    @param img: Image of unknown format.
    @rtype:     String
    @return:    Filepath for a MRC file.
    """

    vpath = ""
    for f in img.getImportedImageFiles ():
        if (is_dv (f) or is_mrc (f)):
            ext  = os.path.splitext (f.getName ())[1]
            tmpf = tempfile.NamedTemporaryFile (suffix = ext, delete = False)
            for c in f.getFileInChunks ():
                tmpf.write (c)
            tmpf.close ()
            vpath = tmpf.name

    if not vpath:
        raise Exception ("Conversion of tiff2mrc not yet implemented")

    return vpath


def run_ndsafir (imgs, params, client):
    """
    Run ndsafir program on the image.

    @type  imgs:   List of _ImageWrapper
    @param imgs:
    @type  params: dict
    @param params:
    @type  client: omero.gateway._BlitzGateway
    @param client:
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
    for iw in imgs:
        fin  = get_valid_fpath (iw)
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

def get_ndsafir_args (params):
    """Build list of input args to call ndsafir.

    @type  params: dict
    @param params: unwrapped and processed by omero.util.script_utils.parseInputs
    @rtype:  list
    @return: the arguments (options) that go on the end of ndsafir call.
    """

    ## Construct args we will use when calling ndsafir_priism
    ## Note that ndsafir is very much non-standard when it comes to options.
    ## Each key-value are a single argument, not separate ones. Also, the
    ## non-option input file will comes before the actual options.
    opts = []
    try:
        for key, val in params.iteritems():
            opt = ""

            if key == "iterations":
                if val < 1:
                    raise ValueError("`iterations' must be a positive integer")
                elif params["time"] and val > 5:
                    raise ValueError("if `time', `iterations' must be less than 6")
                elif not params["time"] and val > 11:
                    raise ValueError("`iterations' must be less than 11")
                opt = "-iter=%i" % val

            elif key == "patch_radius":
                if val < 1:
                    raise ValueError("`patch_radius' must be a positive integer")
                opt = "-p=%i" % val

            elif key == "noise_model":
                if val == "gaussian + poisson":
                    val = "poisson"
                elif val != "gaussian" and val != "auto":
                    raise ValueError("unknown `noise_model' %s" % val)
                opt = "-p=%s" % val

            elif key == "adaptability":
                if val < 0 or val > 10:
                    raise ValueError("`adaptability' must be between 0 and 10")
                opt = "-adapt=%f" % val

            elif key == "island_threshold":
                if val < 0:
                    raise ValueError("`island threshold' must be non-negative")
                opt = "-island=%f" % val

            else:
                continue

            opts.append(opt)

        ## FIXME: client.getInputKeys() will not get keys with no value. This
        ##        should probably be fixed upstream and then moved back into
        ##        the loop over key names.
        ## sampling is a bit trickier because it's optional so it can
        ## be dependent on patch radius.
        if "sampling" not in params.keys():
            val = params["patch_radius"] +1 # default
        else:
            if params["sampling"] < 0: # certainly there must be an upper limit?
                raise ValueError("`sampling' must be a positive integer")
            val = params["sampling"]
        opts.append("-sampling=%i" % val)

    ## catch issues with printf style
    except TypeError as e:
        raise "option %s - %s" % (key, str (e))

    except Exception as e:
        raise "bad value for option %s" % key

    return opts

## TODO we should contribute this to script_utils
def get_images(client, params):
    """Get images from IDs, either image or dataset IDs.

    @type  client: omero.scripts.client
    @param client: Connect.
    @type  params: dict
    @param params: parameters given to the client, with at least the fields Ids
    and Data_Type.

    @rtype:  _ImageWrapper
    @return: List of all images corresponding to the listed IDs.
    """
    conn = omero.gateway.BlitzGateway(client_obj=client)
    objs, msg = omero.util.script_utils.getObjects(conn, params)

    if params["Data_Type"] == "Image":
        imgs = objs
    else:
        ## flatten list from generators
        imgs = [img for ds in objs for img in ds.listChildren()]
    return imgs, msg

def main(doc):
    """Main entry point of the script, as called by the client via the
    scripting service, passing the required parameters.

    @type  doc: str
    @param doc: Help/Documentation to be displayed at start of plugin.
    """

    ## TODO still missing more options from the application
    ## FIXME it seems that we can't group related options together without
    ##       having a parent and a parent requires some sort of an option.
    client = omero.scripts.client (
        "Denoise image with ND-SAFIR",
        doc,

        ## Group 1 - selection of objects
        omero.scripts.String(
            "Data_Type", optional=False, default="Image",
            values=["Dataset", "Image"],
            description="Choose Images by their IDs or via their 'Dataset'",
            grouping="01",
        ),
        omero.scripts.List(
            "IDs", optional=False,
            description="List of Dataset IDs or Image IDs",
            grouping="02",
        ),

        ## Group 2 - ndsafir options

        ## Defaults chosen for the actual denoising are the same as the
        ## default values of ndsafir when possible. However, some defaults
        ## are image dependent, so we can't replicate them in the GUI

        ## Group 2.1 - ndsafir dimensionality
        omero.scripts.Bool(
            "time", optional=False, default=False,
            description="Look for similarities over multiple time points",
            grouping="03",
        ),
        omero.scripts.Bool(
            "wavelength", optional=False, default=False,
            description="Look for similarities in multiple channels",
            grouping="04",
        ),
        omero.scripts.Bool(
            "z-slices", optional=False, default=False,
            description="Look for similarities through the image volume",
            grouping="05",
        ),
        ## Group 2.2 - other ndsafir options
        omero.scripts.Int(
            "iterations", optional=False, default=4,
            description="Maximum number of iterations",
            grouping="06",
        ),
        omero.scripts.Int(
            "patch_radius", optional=False, default=1,
            description="Sets the patch radius to be N pixels",
            grouping="07",
        ),
        omero.scripts.Int(
            ## ndsafir default is 1 + patch radius
            "sampling", optional=True,
            description="Set sampling interval (defaults to 1+patch radius)",
            grouping="08",
        ),
        omero.scripts.String(
            "noise_model", optional=False, default="gaussian + poisson",
            values=["gaussian + poisson", "gaussian", "auto"],
            description="Select how to model the noise",
            grouping="09",
        ),
        ## FIXME https://github.com/openmicroscopy/openmicroscopy/issues/2449
#        omero.scripts.Float(
#            "adaptability", optional=False, default=0.0,
#            description="Sets the sampling interval",
#            grouping="10",
#        ),
        omero.scripts.Float(
            "island_threshold", optional=False, default=4.0,
            description="Sets the sampling interval",
            grouping="11",
        ),

        ## TODO
        ## Group 3 - output options

        version      = "0.0.2",
        authors      = ["David Pinto"],
        institutions = ["Micron, University of Oxford"],
        contact      = "david.pinto@bioch.ox.ac.uk",
    )

    try:
        ## FIXME: remove the unwrap in later versions (post 5.0.1). See
        ##          https://github.com/openmicroscopy/openmicroscopy/issues/2439
        ## FIXME: remove the session=None option to parseInputs in later
        ##        versions (post 5.0.1). See
        ##          https://github.com/openmicroscopy/openmicroscopy/pull/2438
        params = omero.rtypes.unwrap(
            omero.util.script_utils.parseInputs(client, session=None)
        )
        imgs, msg = get_images(client, params)

        if not imgs:
            client.setOutput ("Message", rstring ("No images: %s" % msg))
        else:
            run_ndsafir (imgs, params, client)

    except Exception as e:
        client.setOutput("Message", rstring("Error: %s" % str(e)))

    finally:
        client.closeSession()

if __name__ == "__main__":
    main(__doc__)

