#! /usr/bin/env python2.7
#
#    (c) UWA, The University of Western Australia
#    M468/35 Stirling Hwy
#    Perth WA 6009
#    Australia
#
#    Copyright by UWA, 2012
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
During the beta testing we had some pixels that would not converge onto a probability bin properly.

The fix was to just let them through, but the assimilator won't be processing the pixels properly.
So this files looks for area's that haven't had the workunit_id assigned. Then it looks at the workunits in
BOINC to see if has been assimilated
"""

# First check the galaxy exists in the database
import logging
import datetime
from sqlalchemy.engine import create_engine
from sqlalchemy.orm.session import sessionmaker
from config import DB_LOGIN, BOINC_DB_LOGIN
from database.boinc_database_support import Workunit
from database.database_support import Galaxy, Area, PixelResult

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)-15s:' + logging.BASIC_FORMAT)

engine_magphys = create_engine(DB_LOGIN)
Session = sessionmaker(bind=engine_magphys)
session_magphys = Session()

engine_pogs = create_engine(BOINC_DB_LOGIN)
Session = sessionmaker(bind=engine_pogs)
session_pogs = Session()

galaxies = session_magphys.query(Galaxy).all()

for galaxy in galaxies:
    # Have we got work units out there for this galaxy?
    count = session_pogs.query(Workunit).filter(Workunit.name.like('{0}_area%'.format(galaxy.name))).count()
    LOG.info('Working on galaxy %s (%d) - %d work units deployed', galaxy.name, galaxy.version_number, count)
    if not count:
        continue

    # Look for whole areas first
    areas = session_magphys.query(Area).filter_by(galaxy_id=galaxy.galaxy_id).filter_by(workunit_id = None).all()
    for area in areas:
        wu_name = '{0}_area{1}'.format(galaxy.name, area.area_id)
        workunits = session_pogs.query(Workunit).filter_by(name=wu_name).all()

        for workunit in workunits:
            if workunit.assimilate_state == 2:
                LOG.info('%s Found area %d - WU_id %d - fixing', galaxy.name, area.area_id, workunit.id)
                area.workunit_id = workunit.id

                for pixel in area.pixelResults:
                    pixel.workunit_id = workunit.id

                area.update_time = datetime.datetime.now()

    session_magphys.commit()

    # Look for stray pixels
    pixels = session_magphys.query(PixelResult).filter_by(galaxy_id=galaxy.galaxy_id).filter_by(workunit_id = None).all()
    for pixel in pixels:
        wu_name = '{0}_area{1}'.format(galaxy.name, pixel.area_id)
        workunits = session_pogs.query(Workunit).filter_by(name=wu_name).all()

        for workunit in workunits:
            if workunit.assimilate_state == 2:
                LOG.info('%s Found pixel %d in area %d - WU_id %d - fixing', galaxy.name, pixel.pxresult_id, pixel.area_id, workunit.id)
                pixel.workunit_id = workunit.id
                pixel.area.update_time = datetime.datetime.now()

    session_magphys.commit()

LOG.info('Done.')