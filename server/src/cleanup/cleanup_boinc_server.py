#! /usr/bin/env python2.7
#
#    Copyright (c) UWA, The University of Western Australia
#    M468/35 Stirling Hwy
#    Perth WA 6009
#    Australia
#
#    All rights reserved
#
#    This library is free software; you can redistribute it and/or
#    modify it under the terms of the GNU Lesser General Public
#    License as published by the Free Software Foundation; either
#    version 2.1 of the License, or (at your option) any later version.
#
#    This library is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#    Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public
#    License along with this library; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston,
#    MA 02111-1307  USA
#
"""
Clean up the BOINC server
"""
import sys
from cleanup.cleanup_boinc_server_mod import archive_boinc_stats, archive_boinc_db_purge
from utils.logging_helper import config_logger

LOG = config_logger(__name__)


if __name__ == '__main__':
    LOG.info('PYTHONPATH = {0}'.format(sys.path))

    # Archive the BOINC stats
    try:
        LOG.info('Archive boinc stats')
        archive_boinc_stats()
    except:
        LOG.exception('archive_boinc_stats(): an exception occurred')

    # Archive the BOINC DB Purge
    try:
        LOG.info('Archive boinc DB purge')
        archive_boinc_db_purge()
    except:
        LOG.exception('archive_boinc_db_purge(): an exception occurred')
