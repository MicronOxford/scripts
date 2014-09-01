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

"""Denoise with NDSAFIR (N Dimensional Structure Adaptive FILtering).

This patch-based denoising algorithm is described in Boulanger, J. et al (2007).
Basically it makes use of redundancy in an image sequence (i.e. multiple
samples of the same features) to average equivalent pixels and reduce the
apparent noise level. You can also refer to the ndsafir HTML manual from the
Sedat lab, but be aware that the description of the iterations is somewhat
confusing.

Options
-------
Documentation for each of the options is available at the [Micron wiki]
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

import tempfile     # consider replace this with omero.util.temp_files
import sys          # because omero redirection of stderr is buggy
import os
import errno
import os.path
import subprocess
import struct
import time

import omero.scripts
import omero.gateway
import omero.rtypes
import omero.cli

import numpy

## There's two reasons we are using the absolute path:
##    1) security - we should not be trusting PATH since someone could be
##       adding an alternative command there, and indeed that's what happens
##       when using perl's tainted mode (but in the complex system that is
##       omero that's likely a moot point)
##    2) ndsafir binary is not available on the system PATH, it is set up
##       via a profile script which is only executed when starting a login
##       shell. Even if it was available, we should then be using
##       distutils.spawn.find_executable.
NDSAFIR = "/usr/local/priism/bin/ndsafir_priism"

def unlink_force(path):
    """Remove file but ignore nonexistent files.

    Using os.unlink() to remove a non-existing file throws an error. This
    function just ignores it, kind of like "rm -f path".

    Args:
        path: filepath for the file to be removed.

    Returns:
        void

    Raises:
        Same as os.unlink() except the OSError due to non-existing file.
    """
    try:
        os.unlink(path)
    except OSError as e:
        if e.errno != errno.ENOENT: # No such file or directory
            raise

def is_image2000(img):
    """Return true if image is a MRC image2000 file.

    Args:
        img: omero.gateway._OriginalFileWrapper

    Returns:
        A boolean value. True if img is an mrc image 2000 file, False otherwise.
    """
    ##  * Original MRC image2000 specs:
    ##      http://www2.mrc-lmb.cam.ac.uk/image2000.html
    s = img.getFileInChunks(buf=53*4).next()

    ## New versions of the MRC format are supposed to have this signature
    ## but I'm still unsure if Priism is capable of reading them...
    if len(s) >= 53*4 and s[52*4:53*4] == "MAP ":
        return True
    else:
        return False

def is_mrc(img):
    """Return true if image is an mrc (original) image file.

    There seems to be multiple variants of the MRC format. The very old
    original one, a old one which Priism uses (imsubs), another proprietary
    bastardized version by API/GE used by softWoRx, a version used by Image2000,
    and probably many others.

    For the very old versions there is no "signature" on the header, we can
    only check if the file extension is mrc and hope for the best.

    Args:
        img: omero.gateway._OriginalFileWrapper

    Returns:
        A boolean value. True if img is an mrc file, False otherwise.
    """
    ## Docs:
    ##  * IMOD reference for file specs with mention of old format:
    ##      http://bio3d.colorado.edu/imod/doc/mrc_format.txt
    ##  * Priism take on the subject:
    ##      http://msg.ucsf.edu/IVE/IVE4_HTML/mrc2image2000.html
    ## old versions will need to check with file extension
    ext = os.path.splitext(img.getName())[1]
    if ext.lower() == ".mrc":
        return True
    else:
        return False

def is_dv(img):
    """Return true if image has a dv image file.

    Args:
        img: omero.gateway._OriginalFileWrapper

    Returns:
        A boolean value. True if img is a dv file, False otherwise.
    """
    ## According to bioformats's DeltavisionReader.java (which is GPL), a
    ## DV file must read 0xa0c0 or 0xc0a0 at pos 96.
    rv = False
    s = img.getFileInChunks(buf=98).next()
    if len(s) >= 98:
        m = struct.unpack("H", s[96:98])[0]
        if m == 49312 or m == 41152:
            rv = True
    return rv

def is_imsubs(img):
    """Return true if image is a MRC IMSubs.

    Args:
        img: omero.gateway._OriginalFileWrapper

    Returns:
        A boolean value. True if img is an MRC IMSubs file, False otherwise.
    """
    ##  * Format specs from IVE:
    ##      http://www.msg.ucsf.edu/IVE/IVE4_HTML/IM_ref2.html
    rv = False

    s = img.getFileInChunks(buf=98).next()
    if len(s) >= 98:
        m = struct.unpack("H", s[96:98])[0]
        if m == -16224:
            rv = True
    return rv


def is_tiff(img):
    """Return true if image is a tiff image file.

    Args:
        img: omero.gateway._OriginalFileWrapper

    Returns:
        A boolean value. True if img is a tiff file, False otherwise.
    """
    rv = False
    s = img.getFileInChunks(buf=4).next()
    if len(s) >= 4:
        bito = s[0:2]
        magk = s[2:4]
        if ((bito == "II" and struct.unpack("<H", magk)[0] == 42) or
            (bito == "MM" and struct.unpack(">H", magk)[0] == 42)):
            rv = True
    return rv

def any2imsubs(img):
    """Save image into a mrc Imsubs (Priism sub-format) file.

    Priism comes a small application (tiff2mrc) that makes this conversion.
    However, it is unable to handle the ome tiff files (can't convert
    separately sampled tiled image), and does not preserve the original
    image precision.

    If the image is already an mrc file, you're better off using the
    getFileInChunks() method for an individual file.

    One day we should contribute this to PIL.

    Args:
        img: omero.gateway._ImageWrapper

    Returns:
        A string with the filepath for the generated MRC file.

    Raises:
        TypeError: if the image is of a type, or has features, not supported by
            the MRC format. For example, binary, double, and uint32 precision
            are not suported. Images with more than 5 channels.
    """
    ## File format specs - http://www.msg.ucsf.edu/IVE/IVE4_HTML/IM_ref2.html

    ncols = img.getSizeX()
    nrows = img.getSizeY()
    nzsec = img.getSizeZ()
    nchan = img.getSizeC()
    ntime = img.getSizeT()
    with tempfile.NamedTemporaryFile("wb", suffix=".mrc", delete=False) as f:
        try:
            f.write(struct.pack("2i", ncols, nrows))  # width and height
            f.write(struct.pack("1i", nzsec * nchan * ntime)) # number of sections

            pixel_types = {
                "int8"    : None,
                "uint8"   : 0,
                "int16"   : 1,
                "uint16"  : 6,
                "int32"   : 7,
                "uint32"  : None,
                "float"   : 2,
                "double"  : None,
                "bit"     : None,
                "complex" : 4,
                "doublecomplex" : None,
            }

            prc = pixel_types[img.getPixelsType()] # image precision
            ## Note that uint8 has a value of zero which evaluates as false.
            ## Because of that, we use "is None" instead of "not prc"
            if prc is None:
                raise TypeError("this image type cannot be converted to mrc")

            f.write(struct.pack("4i",
                prc,      # image mode/precision
                0, 0, 0,  # starting point of sub image
            ))

            ## Sampling frequencies in X, Y, and Z
            f.write(struct.pack("3i", ncols, nrows, nzsec))

            ## Cell dimensions (in ångströms). For non-crystallographic data,
            ## set to the sampling frequency times the x pixel spacing.
            f.write(struct.pack("3f",
                ncols * img.getPixelSizeX() * 10000,
                nrows * img.getPixelSizeY() * 10000,
                nzsec * img.getPixelSizeZ() * 10000,
            ))

            f.write(struct.pack("3f", 90, 90, 90))  # cell angles (usually just set to 90)
            f.write(struct.pack("3i", 1, 2, 3))     # maps axis to dimension.

            ## These values are supposed to be only for the first 2D image/plane
            px = img.getPrimaryPixels()
            p = px.getPlane()
            f.write(struct.pack("3f", p.min(), p.max(), p.mean()))

            f.write(struct.pack("2i", 0, 0))      # Space group number, and extended header size
            f.write(struct.pack("1h", -16224))    # ID value
            f.write(struct.pack("1h", 0))         # unused
            f.write(struct.pack("1i", 0))         # starting time index
            f.write(struct.pack("24s", " " * 24)) # blank section
            f.write(struct.pack("2h", 0, 0))      # organization of the extended header
            f.write(struct.pack("2h", 1, 1))      # for sub-resolution version of image

            ## Minimum and maximum intensity of each other channel. If there is
            ## a fifth channel, its data will be later on in the header file.
            for chan in xrange(1, min(4, nchan)):
                p = px.getPlane(theC=chan)
                f.write(struct.pack("2f", p.min(), p.max()))
            f.write(struct.pack("%if" % ((4 - nchan) *2), *[0]*((4 - nchan) *2)))

            ## Image type and stuff important if it was a normal image
            f.write(struct.pack("6h", *[0]*6))

            ## Minimum and maximum intensity of a 5th channel
            if nchan < 5:
                f.write(struct.pack("2f", 0.0, 0.0))
            elif nchan == 5:
                p = px.getPlane(theC=4)
                f.write(struct.pack("2f", p.min(), p.max()))
            else:
                raise TypeError("mrc file cannot have more than 5 channels")

            f.write(struct.pack("1h", ntime))   # number of time points
            f.write(struct.pack("1h", 0))       # image sequence (0=ZTW, 1=WZT, 2=ZWT)
            f.write(struct.pack("3f", 0, 0, 0)) # X, Y, and Z tilt angle

            ## Number and lengths of wavelengths
            f.write(struct.pack("1h", nchan))
            rchan = 0 # because we don't trust to match the channels numbers
            for chan in img.getChannels():
                rchan += 1
                ## some channels may not have wavelength information
                length = chan.getEmissionWave()
                if length:
                    f.write(struct.pack("1h", length))
                else:
                    f.write(struct.pack("1h", 0))
            if rchan != nchan:
                ## Fix the information if the numbers don't match. Go back to
                ## the start of this section, write the correct number of
                ## channels, then jump to the last one, and fill the rest with
                ## zeros.
                f.seek(- struct.calcsize("%ih" % (rchan+1)), 1)
                f.write(struct.pack("1h", rchan))
                f.seek(struct.calcsize("%ih" % rchan), 1)
            for empty in xrange(0, 5-rchan):
                f.write(struct.pack("1h", 0))

            f.write(struct.pack("3f", 0, 0, 0))     # origin of image
            f.write(struct.pack("i", 0))            # number of useful titles
            f.write(struct.pack("800s", " " * 800)) # space for 10 titles

            for w in xrange(0, nchan):
                for t in xrange(0, ntime):
                    for z in xrange(0, nzsec):
                        p = px.getPlane(theC=w, theT=t, theZ=z)
                        ## https://github.com/openmicroscopy/openmicroscopy/issues/2547
                        if p.dtype == "float64":
                            p = p.astype("float32")
                        p = numpy.flipud(p)
                        p.tofile(f.file)

        except Exception as e:
            f.close()
            os.unlink(f.name)
            raise

    return f.name

def get_parent_dataset(img):
    """Return dataset ID for an image.

    This assumes that the image is only in one dataset which apparently
    may not always be true. It can be in none or it can be in multiple.

    Args:
        img: omero.gateway._ImageWrapper

    Returns:
        An integer with the dataset ID or None if an image is not part of
        a dataset, such as happens with orphaned images.
    """
    parents = img.listParents()
    if parents:
        for p in parents:
            return p.getId()
    else:
        return None

## According to joshmoore this seems to be the way to do it. Mostly copied
## from MonitorClientI.importFile() at components/tools/OmeroFS/fsDropBoxMonitorClient.py
##
## It takes a ridiculous amount of time, it is very slow, but we won't bother
## because it seems they're already trying to come up with something to do this.
def export_image_file(client, fpath, dataset=None, name=None):
    """Export image file to the OMERO.server.

    Args:
        client: omero.BaseClient to use for the import
        fpath: a string with the filepath for the file to be imported.
        dataset: integer with the dataset ID to where the image should be
            imported.

    Returns:
        An omero.gateway._ImageWrapper with the imported image.

    Raises:
        Exception: if import failed for some reason or even if it was
            successful but we couldn't manage to deduce its ID.
    """

    cli = omero.cli.CLI()
    cli.loadplugins()
    cmd = [
        "-s", "localhost",
        "-k", client.getSessionId(),
        "import",
        "--debug", "ERROR",
    ]
    if dataset:
        cmd.extend(["-d", str(dataset)])
    if name:
        cmd.extend(["-n", str(name)])

    ## The ID of exported image will be printed back to STDOUT. So we need
    ## to catch it in file, and read that file to get its ID. And yeah, this
    ## is a bit convoluted but it is the recommended method.
    cid = None
    with tempfile.NamedTemporaryFile(suffix=".stdout") as stdout:
        ## FIXME when stuff is printed to stderr, the user will get a file
        ##       to download with that text. Unfortunately, non-errors are
        ##       still being printed there. The filtering is broken in 5.0.1
        ##       but on future releases we may be able to simply not set
        ##       "---errs" option.
        ##       https://github.com/openmicroscopy/openmicroscopy/issues/2477
        cmd.extend([
            "---errs", os.devnull,
            "---file", stdout.name,
        ])
        cmd.append(fpath)

        ## FIXME https://github.com/openmicroscopy/openmicroscopy/issues/2476
        STDERR = sys.stderr
        try:
            with open(os.devnull, 'w') as DEVNULL:
                sys.stderr = DEVNULL
                cli.invoke(cmd)
        finally:
            sys.stderr = STDERR
        ret_code = cli.rv

        if ret_code == 0:
            ## we only need to read one line or something is very wrong
            cid = int(stdout.readline())
            if not cid:
                raise Exception("unable to get exported image ID")
        else:
            ## I am not going to redirect stderr to a temp file, read it back
            ## in case of an error, and then print it to stderr myself so that
            ## the user gets a file to download with the errors. This is being
            ## fixed upstream already.
            ## https://github.com/openmicroscopy/openmicroscopy/issues/2477
            raise Exception("failed to import processed image into the database")

    conn = omero.gateway.BlitzGateway(client_obj=client)
    return conn.getObject("Image", cid)

def dress_child(child, parent, attach=()):
    """Fill a new image with data from another.

    Most likely, this is *not* what you want to use. While at first glance
    this looks liek a nifty way to propagate the metadata from a parent
    image to its child, it's actually a really really bad idea. Some examples:

      * if your processing changes the pixel size (such as image reconstruction,
        you should not be importing it back.
      * if a parent was ratted with 3 starts, the child may be worse or better.
        By importing its tags/rates/etc, you're implying that the new child was
        actually rated that way. Worse, you're making it impossible to identity
        them since you can't filter them by finding unstarred/untagged images.
      * if the parent has an attachment with the same image in a different
        format (like Batch_export does), the child should not have this file
        associated.

    Args:
        child: omero.gateway._ImageWrapper of the image that needs to be filled
            with metadata.
        parent: omero.gateway._ImageWrapper of the image from where to copy the
            metadata
        attach: list of omero.gateway.AnnotationWrapper to be added to child in
            addition to everything else in parent.

    Returns:
        void
    """

    for a in attach:
        child.linkAnnotation(a)
    for a in parent.listAnnotations():
        child.linkAnnotation(a)

    child.setDescription(parent.getDescription())

    child.save()
    return None

def adopt_child(parent, child):
    """Connect two images with parent-child relationship.

    Omero does not yet have a concept of parent child relationship. The best
    we can do by now is leave a note on the parent and the child description
    pointing to each other. As long as we are using the correct syntax
    "Image ID: number", the omero clients should interpret it as a link to
    image.

    Note that the link was broken for Omero versions 5.0.1 and 5.0.2.

    Args:
        child: omero.gateway._ImageWrapper
        parent: omero.gateway._ImageWrapper

    Returns:
        void
    """
    def append2description(img, relation, to):
        """Append relationship text to an image description."""
        desc = img.getDescription()
        if desc and desc[-1] != "\n":
            desc += "\n"
        desc += "%s Image ID: %i" % (relation, to.getId())
        img.setDescription(desc)
        img.save()

    append2description(parent, "parent of", child)
    append2description(child, "child of", parent)

    return None

def get_mrc_file(img):
    """Return filepath for a mrc file of a specific image.

    This will check if the imported file was a valid format for nd-safir
    in which case a path to it is returned. If not, then it creates one
    from whatever data it retrieves from the omero server.

    Args:
        img: omero.gateway._ImageWrapper

    Returns:
        String with filepath for a mrc file corresponding to img.
    """

    path = ""
    ## XXX must understand when does an image have multiple imported image
    ##     files. Depending on the answer, may require some heavy redesign.
    ##     Hopefully it is for cases when a ND image comes from multiple
    ##     files in which case they wouldn't be mrc files anyway.
    for f in img.getImportedImageFiles():
        if is_dv(f) or is_image2000(f) or is_imsubs(f) or is_mrc(f):
            ext = os.path.splitext(f.getName())[1]
            tmpf = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
            for c in f.getFileInChunks():
                tmpf.write(c)
            tmpf.close()
            path = tmpf.name
            break

    if not path:
        path = any2imsubs(img)

    return path


def run_ndsafir(fin, args, conn, timeout = lambda : False, time_grain = 10):
    """Run ndsafir program on the image.

    Args:
        fin: a string with the filepath for the input image. Note that the
            ndsafir version we have at the moment only accepts mrc files as
            input.
        args: a list with all the input arguments to pass to the ndsafir
            application.
        conn: omero.gateway._BlitzGateway required to keep the connection
            alive for long processes.
        timeout: an anonymous function that checks if the process should
            timeout (which will raise an exception). Use `lambda : False`
            to never timeout, or `lambda : time.time() > X` where X is
            `time.time() + 60*60*2` to timeout after 2 hours.
        time_grain: interval, in seconds, to check the child process status
            and send Omero server a keep alive token. This should never be
            higher than Omero's server timeout (which defaults 10 minutes).
            See Omero's omero.sessions.timeout

    Returns:
        A tuple with the filepath for the processed image on the first element,
            and for the processing log file on the second.

    Raises:
        Exception: if unable to find the ndsafir application in the system,
            the process failed for some reason, or timeout was reached.
    """
    ## For whatever reason, the ndsafir version we got seems to only work with
    ## MRC files. When a TIFF file is used, it just hangs forever and takes up
    ## all CPU. Apparently, the version Sussex got works fine with TIFFs but is
    ## not multi-thread. Could it be an issue with my build?


    if not NDSAFIR:
        raise Exception("Unable to find ndsafir_priism in the system")

    fout = tempfile.NamedTemporaryFile(suffix=".mrc", delete=False).name

    log = tempfile.NamedTemporaryFile(suffix=".log", delete=False)
    flog = log.name

    args = [NDSAFIR, fin, fout] + args
    try:
        with log:
            log.write("$ %s\n" % " ".join(args))
            log.flush()

            ## ndsafir is a bit weird about where it prints log. The actual
            ## important stuff (the log) is being printed to stderr. Then, it
            ## appears it has a bug which causes the sampling value to be printed
            ## to stdout during the first iteration. This small bug means that
            ## users would get a useless "info" file to download with "sampling=x"
            ## so we redirect stdout to null.
            with open(os.devnull, "w") as null:
                p = subprocess.Popen(args, stderr=log, stdout=null)
                def running():
                    return p.poll() is None
                while not timeout() and running():
                    conn.keepAlive()
                    time.sleep(time_grain)

                if not running() and p.returncode != 0:
                    raise Exception("trouble running ND-safir")
                elif timeout():
                    p.terminate()
                    raise Exception("NDsafir exceedeed time allowed")

    except Exception as e:
        unlink_force(fout)
        unlink_force(flog)
        raise

    return fout, flog

def get_ndsafir_args(params):
    """Build list of input args to call ndsafir.

    Args:
        params: a dict with all the options set during the interface.

    Returns:
        List with the corresponding command line arguments for ndsafir_priism.

    Raises:
        ValueError: in case of invalid values, e.g., negative values for
            options that must be positive.
    """

    ## Construct args we will use when calling ndsafir_priism
    ## Note that ndsafir is very much non-standard when it comes to options.
    ## Each key-value are a single argument, not separate ones. Also, the
    ## non-option input file will comes before the actual options.
    opts = []
    try:
        ## We don't really need the for loop since we will have to treat each
        ## field in a different way. We are only using it to generate error
        ## messages if it fails.
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
                opt = "-noise=%s" % val

            elif key == "adaptability":
                if val < 0 or val > 10:
                    raise ValueError("`adaptability' must be between 0 and 10")
                opt = "-adapt=%f" % val

            elif key == "island_threshold":
                if val < 0:
                    raise ValueError("`island threshold' must be non-negative")
                opt = "-island=%f" % val

            ## FIXME https://github.com/openmicroscopy/openmicroscopy/issues/2449
#            elif key == "adaptability":

            if opt:
                opts.append(opt)

        ## FIXME: client.getInputKeys() will not get keys with no value but
        ##        seems like they don't want to fix this upstream. See
        ##        https://github.com/openmicroscopy/openmicroscopy/issues/2462
        ## The option sampling is a bit trickier because it's optional and
        ## can be dependent on patch radius.
        if "sampling" not in params.keys():
            val = params["patch_radius"] +1 # default
        else:
            if params["sampling"] < 0: # certainly there must be an upper limit?
                raise ValueError("`sampling' must be a positive integer")
            val = params["sampling"]
        opts.append("-sampling=%i" % val)

    except Exception as e:
        raise ValueError("option %s - %s" % (key, str(e)))

    ## handle the dimensionality option
    dims = ""
    for key in ["z-slices", "time", "wavelength"]:
        if params.get(key):
            dims += key[0]
    ndims = 2 + len(dims)
    if ndims == 2:
        opt = "-2d"
    elif ndims > 2 and ndims < 5:
        opt = "-%id=%s" % (ndims, dims)
    else:
        opt = "-5d"
    opts.append(opt)

    return opts

def get_images(conn, ids, data_type="Image"):
    """Get all images from IDs, either image or dataset IDs.

    Retrieves all image from a list of IDs. If the IDs are Dataset IDs, then
    returns all images objects from those datasets.

    Args:
        conn: omero.gateway._BlitzGateway
        ids: list of integers with the IDs to retrieve.
        data_type: string with the data type that ids corresponds to. It can be
            Image or Dataset.

    Returns:
        List of omero.gateway._ImageWrapper
    """
    objs = (conn.getObjects(data_type, ids))
    if data_type == "Image":
        imgs = objs
    else:
        ## flatten list from generators
        imgs = [img for ds in objs for img in ds.listChildren()]
    return imgs

def main(doc):
    """Main entry point of the script.

    Args:
        doc: a string with the help/documentation text that is displayed
            at the start by the omero client.
    """

    ## FIXME it seems that we can't group related options together without
    ##       having a parent and a parent requires some sort of an option.
    ##       See https://github.com/openmicroscopy/openmicroscopy/issues/2463
    client = omero.scripts.client(
        "Denoise image with NDSAFIR",
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
        ## FIXME our version of nd-safir crashes if we don't use time
#        omero.scripts.Bool(
#            "time", optional=False, default=True,
#            description="Look for similarities over multiple time points",
#            grouping="03",
#        ),
        omero.scripts.Bool(
            "wavelength", optional=False, default=False,
            description="Look for similarities in multiple channels",
            grouping="04",
        ),
        omero.scripts.Bool(
            "z-slices", optional=False, default=True,
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

        version      = "0.0.6",
        authors      = ["David Pinto"],
        institutions = ["Micron, University of Oxford"],
        contact      = "david.pinto@bioch.ox.ac.uk",
    )

    try:
        params = client.getInputs(unwrap=True)
        conn = omero.gateway.BlitzGateway(client_obj=client)
        imgs = get_images(conn, params["IDs"], data_type=params["Data_Type"])

        ## FIXME our version of nd-safir crashes if we don't use time
        params["time"] = True
        args = get_ndsafir_args(params)

        nbad = 0
        nimgs = 0 # imgs might be a generator so we can't use len(imgs)
        for parent in imgs:
            nimgs += 1
            try:
                fin = fout = flog = "" # so its defined to unlink later
                basename = os.path.splitext(parent.getName())[0] + "_DN"
                fin = get_mrc_file(parent)
                fout, flog = run_ndsafir(fin, args, conn)
                child = export_image_file(
                    client,
                    fout,
                    dataset=get_parent_dataset(parent),
                    name=basename+os.path.splitext(fout)[1],
                )

                adopt_child(parent, child)
                child.linkAnnotation(
                    conn.createFileAnnfromLocalFile(
                        flog,
                        origFilePathAndName=basename+".log",
                        mimetype="text/plain",
                    )
                )

            except Exception as e:
                ## TODO We are just counting the number of failures and success
                ##      but maybe we could compile a file with all errors and
                ##      give it back to the user at the end?
                nbad += 1
            finally:
                for f in [fin, fout, flog]:
                    unlink_force(f)

        if nimgs == 0:
            msg = "No images selected"
        elif nbad == nimgs:
            msg = "Failed denoising all images"
        elif nbad:
            msg = "Failed denoising %i of %i images" % (nbad, nimgs)
        else:
            msg = "Finished denoising total of %i images" % nimgs
        client.setOutput("Message", omero.rtypes.rstring(msg))

    except Exception as e:
        client.setOutput("Message", omero.rtypes.rstring("Error: %s" % str(e)))

    finally:
        client.closeSession()

if __name__ == "__main__":
    main(__doc__)

