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
OMERO_PLUGIN="http://downloads.openmicroscopy.org/omero/5.3.5/artifacts/OMERO.insight-ij-5.3.5-ice36-b73.zip"
TIMESTAMP=`date --utc '+%Y%m%d-%H%M'`

zipname()
{
    printf "fiji-$1.zip"
}

download()
{
    VERSION=$1
    URL=https://downloads.imagej.net/fiji/latest/fiji-$VERSION.zip
    wget $URL -O `zipname $VERSION`
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
    FNAME="OMERO.insight-ip.zip"
    wget $OMERO_PLUGIN -O $FNAME
    unzip $FNAME -d plugins/
    rm $FNAME
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
    rm -rf Fiji.app
    unzip `zipname $VERSION`
    cd Fiji.app
    update_from_site SIMcheck http://downloads.micron.ox.ac.uk/fiji_update/SIMcheck/
    install_omero_plugin
    disable_updater
    cd ..
}

repackage()
{
    VERSION=$1
    rm -rf `zipname $VERSION`
    ## Remove the silly .app part from the directory name.
    mv Fiji.app Fiji
    zip -0 -r `zipname $TIMESTAMP-$VERSION` Fiji
}

for VERSION in linux64 nojre; do
    download $VERSION
    configure $VERSION
    repackage $VERSION
done
