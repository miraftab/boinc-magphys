#! /usr/bin/env python2.7
#
#    (c) UWA, The University of Western Australia
#    M468/35 Stirling Hwy
#    Perth WA 6009
#    Australia
#
#    Copyright by UWA, 2012-2013
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
Register a FITS file ready to be converted into Work Units
"""

import os, sys
base_path = os.path.dirname(__file__)
sys.path.append(os.path.abspath(os.path.join(base_path, '..')))

import argparse

from utils.logging_helper import config_logger

from sqlalchemy.engine import create_engine
from config import DB_LOGIN

from work_generation.register_fits_file_mod import fix_redshift, get_data_from_galaxy_txt, \
    decompress_gz_files, extract_tar_file, find_input_filename, find_sigma_filename, add_to_database, \
    save_data_to_file, clean_unused_fits, move_fits_files

LOG = config_logger(__name__)
LOG.info('PYTHONPATH = {0}'.format(sys.path))

parser = argparse.ArgumentParser()
parser.add_argument('TAR_file', nargs=1, help='the input tar containing the galaxies')
parser.add_argument('TXT_file', nargs=1, help='the input text file containing galaxy summaries')
parser.add_argument('priority', type=int, nargs=1, help='the higher the number the higher the priority')
parser.add_argument('run_id', type=int, nargs=1, help='the run id to be used')
parser.add_argument('tags', nargs='*', help='any tags to be associated with the galaxy')

args = vars(parser.parse_args())

INPUT_FILE = args['TAR_file'][0]
PRIORITY = args['priority'][0]
RUN_ID = args['run_id'][0]
GALAXY_TEXT_FILE = args['TXT_file'][0]
TAGS = args['tags']

# Make sure the file exists
if not os.path.isfile(INPUT_FILE):
    LOG.error('The file %s does not exist', INPUT_FILE)
    exit(1)

# Extract all files from the tar file if they are not already extracted
TAR_EXTRACT_LOCATION = INPUT_FILE[:-4]

extract_tar_file(INPUT_FILE, TAR_EXTRACT_LOCATION)

decompress_gz_files(TAR_EXTRACT_LOCATION)

move_fits_files(TAR_EXTRACT_LOCATION, '..')
TAR_EXTRACT_LOCATION = '.'

all_txt_file_data = get_data_from_galaxy_txt(GALAXY_TEXT_FILE)

all_galaxy_data = []

for txt_line_info in all_txt_file_data:
    single_galaxy_data = dict()
    single_galaxy_data['name'] = txt_line_info[0]

    input_file = find_input_filename(txt_line_info[0], TAR_EXTRACT_LOCATION)
    if input_file is None:
        LOG.error('Galaxy {0} has an input file of None!'.format(single_galaxy_data['name']))
        continue

    sigma = find_sigma_filename(txt_line_info[0], TAR_EXTRACT_LOCATION)
    if sigma is None:
        LOG.error('Galaxy {0} has a sigma file of None!'.format(single_galaxy_data['name']))
        continue

    gal_type = txt_line_info[4]
    if gal_type is '':
        gal_type = 'Unk'

    single_galaxy_data['sigma'] = find_sigma_filename(txt_line_info[0], TAR_EXTRACT_LOCATION)
    single_galaxy_data['redshift'] = float(fix_redshift(txt_line_info[3]))
    single_galaxy_data['input_file'] = input_file
    single_galaxy_data['type'] = gal_type
    single_galaxy_data['priority'] = PRIORITY
    single_galaxy_data['run_id'] = RUN_ID
    single_galaxy_data['tags'] = TAGS

    all_galaxy_data.append(single_galaxy_data)

save_data_to_file(all_galaxy_data, 'GalaxyRun1.txt')

clean_unused_fits(TAR_EXTRACT_LOCATION, all_galaxy_data)

# Connect to the database - the login string is set in the database package
ENGINE = create_engine(DB_LOGIN)
connection = ENGINE.connect()

for galaxy in all_galaxy_data:
    try:
        add_to_database(connection, galaxy)
    except Exception:
        LOG.exception('An error occurred adding {0} to the database'.format(galaxy['name']))

connection.close()