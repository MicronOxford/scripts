#!/bin/bash
## Author: David Pinto <david.pinto@bioch.ox.ac.uk>
## This program is granted to the public domain.

## Prepares ImageJ releases for our needs.
##
## Upgrading ImageJ is not always clean and an upgrade has broke
## installations.  So a clean install solves this issue.  In addition,
## we want all our sytems to behave the same which means preventing
## one from being upgraded without upgrading the others.  So we must
## disable the updater and place ImageJ on a directory where users
## can't mess with.  Just placing ImageJ on a directory where the user
## does not have permissions is not enough because then the updater
## will display error messages to the user that it can't upgrade.
##
## This script will download the latest ImageJ, install the non
## standard plugins that we care about, and disable the updater.
##
## If a user wants to have something different on ImageJ, then he can
## download and maintain his own instance of ImageJ on his home
## directory.
##
## ImageJ now needs Java 8.  In Windows systems, we have to keep a JRE
## installed and up to date already so that's not a problem and we can
## use the nojre version.  In Linux systems, some still only have Java
## 7 so we have the linux64 version for those.
##
## This needs to be run from a system with Java 8 though.

set -e

UPDATER="ImageJ-linux64 --update"
OMERO_PLUGIN="https://github.com/ome/omero-insight/releases/download/v5.5.12/omero_ij-5.5.12-all.jar"
TIMESTAMP=`date --utc '+%Y%m%d-%H%M'`

## Fiji comes in a directory with a silly '.app' on the name.  Remove
## it.  Seems like this is now ImageJ and not Fiji, even the link
## names inside say so, so rename to ImageJ.
FIJI_DIR="Fiji.app"
OUT_DIR="ImageJ"

zipname()
{
    printf "imagej-$1.zip"
}

exit_due_to_file()
{
    FILE=$1
    echo "'$1' already exists. Remove it or run this from somewhere else" >&2
    exit 1
}

download()
{
    VERSION=$1
    URL=https://downloads.imagej.net/fiji/latest/fiji-$VERSION.zip
    ZIPFILE=`zipname $VERSION`
    if [ -e $ZIPFILE ]; then
        exit_due_to_file $ZIPFILE
    fi
    wget $URL -O $ZIPFILE
    if [ $? -ne 0 ]; then
        echo "Failed to download Fiji from $URL" >&2
        exit 1
    fi
}

update_from_site()
{
    SITE_NAME=$1
    SITE_URL=$2
    ./$UPDATER add-update-site $SITE_NAME $SITE_URL
    ./$UPDATER update $(./$UPDATER list-from-site $SITE_NAME | awk '{print $1}')
}

install_omero_plugin()
{
    FNAME="omero_ij-all.jar"
    wget $OMERO_PLUGIN -O plugins/$FNAME
}

disable_updater()
{
    ## We should have a command-line method to disable the updater but
    ## seems like it's simpler to just remove it.  The whole point of
    ## this script is to download a new Fiji installation each time
    ## instead of updating, so doesn't matter if we remove it.
    rm jars/imagej-updater-*
}

configure()
{
    VERSION=$1
    if [ -e $FIJI_DIR ]; then
        exit_due_to_file $FIJI_DIR
    fi
    unzip `zipname $VERSION`
    cd $FIJI_DIR
    update_from_site SIMcheck https://downloads.micron.ox.ac.uk/fiji_update/SIMcheck/
    install_omero_plugin
    disable_updater
    cd ..
}

repackage()
{
    VERSION=$1
    rm -f `zipname $VERSION`
    if [ -e $OUT_DIR ]; then
        exit_due_to_file $OUT_DIR
    fi
    mv $FIJI_DIR $OUT_DIR
    zip -0 -r `zipname $TIMESTAMP-$VERSION` $OUT_DIR
    rm -rf $OUT_DIR
}

for VERSION in linux64 nojre; do
    download $VERSION
    configure $VERSION
    repackage $VERSION
done
