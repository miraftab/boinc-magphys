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
Migrate the files and database
"""
import logging
import os
import sys
from sqlalchemy import create_engine
from config import DB_LOGIN
from v2_00.migrate_database import migrate_database
from v2_00.migrate_files import migrate_files
from v2_00.remove_galaxies_with_no_hdf5_file import remove_galaxies_with_no_hdf5_file

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)-15s:' + logging.BASIC_FORMAT)

# Setup the Python Path as we may be running this via ssh
base_path = os.path.dirname(__file__)
sys.path.append(os.path.abspath(os.path.join(base_path, '../../../server/src')))
LOG.info('PYTHONPATH = {0}'.format(sys.path))

ENGINE = create_engine(DB_LOGIN)
connection = ENGINE.connect()

try:
    remove_galaxies_with_no_hdf5_file(connection)
    migrate_files(connection)
    migrate_database(connection)

except Exception:
    LOG.exception('Major error')

finally:
    connection.close()