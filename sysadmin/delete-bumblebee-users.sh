#!/bin/bash

## Copyright (C) 2019 David Miguel Susano Pinto <david.pinto@bioch.ox.ac.uk>
##
## Copying and distribution of this file, with or without modification,
## are permitted in any medium without royalty provided the copyright
## notice and this notice are preserved.  This file is offered as-is,
## without any warranty.

## Synopsis:
##
##   This script marks booking system users as deleted if their AD
##   account is locked or disabled.
##
## Problem:
##
##   The booking system (bumblebee) is not synchronised with the
##   department AD server and authentication is done against the
##   university SSO accounts.  This means that someone with an active
##   Oxford account but a deactivated department account, can still
##   book a department instrument.  This is the case of someone that
##   moved to another department.
##
##   Users in this situation will not have a card to get in the
##   department and will not be able to login on the instrument
##   computer.  However, being able to book an instrument they don't
##   have access to is a problem because it can misled into thinking
##   they still have legitimate access.
##
##   The proposed solution is to delete users from the booking system
##   once their department account is deactivated.  There is no system
##   in place that prevents a user from using an instrument without
##   booking it though.  This is expected to work because:
##
##     1) even more obvious to the user that he can't use it;
##     2) while there is nothing in place to prevent user from using
##        the instrument, it may lead to clashes with other users that
##        book it and will be noticeable by facility staff that happen
##        to be around.
##
## Notes:
##
##   The biochemistry department booking system is also used in the
##   pathology department.  This means two things:
##
##     1) when checking for deactivated accounts, we need to skip all
##        users that do not have a biochemistry at all since they may
##        be pathology users.
##
##     2) a user with a deactivated biochemistry account may still be
##        an active user of the booking system.  They may no longer
##        have a biochemistry account and only be using instruments in
##        pathology that they still need to book.  We don't have a
##        solution for this.
##
## Caveats:
##
##   This solves the problem that arises after a user without build
##   access gets in the building.  This happens because they followed
##   someone or someone else let them in.  The problem also requires
##   that they login on the system with a group or instrument account
##   that shouldn't exist in the first place.  Alternatively, that the
##   someone that let them in the building in the first place logs
##   them in the system with their account.  At this point, if the
##   user can't log in the booking system, they might as well ask the
##   person that would let them in the build to book the system on
##   their behalf.
##
##   A user that once had a biochemistry account and wants to use the
##   booking system outside the department will be marked as deleted.
##   They will need to have their biochemistry account re-activated.

##
## LDAP settings
##

LDAP_URI="ldaps://bioch-ad2.bioch.ox.ac.uk"

LDAP_SEARCHBASE="dc=bioch,dc=ox,dc=ac,dc=uk"

LDAP_BINDDN=""

## beware of newline at the end of the password file
LDAP_PASSFILE="/path/to/the/file/with/password"




##
## Bumblebee settings
##

DB_NAME="bumblebeedb"

## If you're not using unix sockets for authentication then something
## like "--defaults-extra-file=...".  Also include "--host=..." if not
## on localhost.
DB_CONNECTION_OPTIONS=""


print_undeleted_bumblebee_users()
{
    mariadb ${DB_CONNECTION_OPTIONS} \
            --database "${DB_NAME}" \
            --batch --skip-column-names \
            --execute 'SELECT username
                           FROM users
                           WHERE deleted=0;'
}


should_delete_user()
{
    local user_cn="$1"

    local control_flag=$(ldapsearch -H "${LDAP_URI}" \
                                    -b "${LDAP_SEARCHBASE}" \
                                    -D "${LDAP_BINDDN}" \
                                    -y "$LDAP_PASSFILE" \
                                    -W "cn=${user_cn}" \
                                    userAccountControl \
                             | grep '^userAccountControl:' \
                             | cut -d':' -f 2)

    ## The flag is actually 32 bits and there's many bits that lead to
    ## a disabled account.  See
    ## https://docs.microsoft.com/en-us/windows/win32/adschema/a-useraccountcontrol
    ## for details.  A normal account is 0x00000200 (512) but while
    ## that works for most users, some people like Jeremy Rowntree and
    ## Penny Handford are special and have passwords that never expire
    ## and so also have flag 0x00010000 (65536).  We probably should
    ## be checking for the bits that cause an account to be disabled
    ## but I think it may be simpler to just check for these two
    ## cases.

    if [ -z $control_flag ] ; then
        ## Leave users without biochemistry AD accounts alone.
        echo "no"
    elif [ $control_flag -eq 512 ]; then
        ## A normal account without any extra flags. Let it be.
        echo "no"
    elif [ $control_flag -eq 66048 ]; then
        ## A special user whose account never expires (512+65536). Let it be.
        echo "no"
    else
        echo "yes"
    fi
}


delete_user()
{
    local username="$1"

    mariadb ${DB_CONNECTION_OPTIONS} \
            --database "${DB_NAME}" \
            --execute 'UPDATE users
                           SET deleted=1
                           WHERE username="'"${username}"'";'
}


check_required_vars()
{
    for REQUIRED_VAR in "LDAP_URI" "LDAP_SEARCHBASE" "LDAP_BINDDN" "LDAP_PASSFILE" "DB_NAME"; do
        if [ -z "${!REQUIRED_VAR}" ]; then
            echo "$REQUIRED_VAR is not set" >&2
            exit 1
        fi
    done

    if [ ! -f "${LDAP_PASSFILE}" ]; then
        echo "LDAP_PASSFILE '${LDAP_PASSFILE}' is not a regular file" >&2
        exit 1
    fi
}


main()
{
    check_required_vars

    for USERNAME in $(print_undeleted_bumblebee_users); do
        if [ $(should_delete_user "$USERNAME") = "yes" ]; then
            delete_user "$USERNAME"
        fi
    done
}

main
