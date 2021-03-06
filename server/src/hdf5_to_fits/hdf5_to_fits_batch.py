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
Batches a set of galaxy requests together and performs them all at once.
The requests are read in from a text document and regex matches to galaxy names in the database.
"""


# Append the python path appropriately
import os
import sys
import argparse
import datetime

base_path = os.path.dirname(__file__)
sys.path.append(os.path.abspath(os.path.join(base_path, '..')))

# Grab a logger for debug messages
from utils.logging_helper import config_logger
LOG = config_logger(__name__)

LOG.info('PYTHONPATH = {0}'.format(sys.path))

from sqlalchemy import select, create_engine
from database.database_support_core import HDF5_FEATURE, HDF5_REQUEST_FEATURE, HDF5_REQUEST_LAYER, HDF5_LAYER, GALAXY, \
    HDF5_REQUEST_GALAXY, HDF5_REQUEST_PIXEL_TYPE, HDF5_PIXEL_TYPE, HDF5_REQUEST
from config import DB_LOGIN

engine = create_engine(DB_LOGIN)


def load_galaxy_file(filename):
    """
    Loads all of the names of galaxies from a galaxy filename.
    One name is loaded per line.
    :param filename: The filename to load from
    :return: A list of galaxy names.
    """

    with open(filename, "r") as f:
        galaxies = f.readlines()

    return galaxies


def split_flp(flp):
    """
    Splits the command line args up in to separate lists for features, layers and pixel types
    :param flp: The args containing features, layers and pixel types
    :return: Three lists. 1 Containing features, 2 Containing layers, 3 Containing pixel types
    """
    features = []
    layers = []
    pixel_types = []

    for k, v in flp.iteritems():
        if k.startswith('f') and v is True:
            features.append(k)

        if k.startswith('l') and v is True:
            layers.append(k)

        if k.startswith('t') and v is True:
            pixel_types.append(k)

    return features, layers, pixel_types


def parse_args():
    """
    Parses the command line arguments provided to this program and returns the following data:
    Email address to send the hdf5 results to.
    Galaxy file name to load results from
    :return: Python dict containing email -> email address and file_name -> galaxy file name mapping.
    """

    parser = argparse.ArgumentParser('Request a batched set of galaxies to be send to the provided email address.')
    parser.add_argument('email', nargs=1, help='Email address to send galaxy data to.')
    parser.add_argument('galaxy_ids', nargs=1, help='The name of the file to load galaxy names from.')

    parser.add_argument('-f0', action='store_true', help='extract best fit')
    parser.add_argument('-f1', action='store_true', help='extract percentile 50')
    parser.add_argument('-f2', action='store_true', help='extract highest probability bin')
    parser.add_argument('-f3', action='store_true', help='extract percentile 2.5')
    parser.add_argument('-f4', action='store_true', help='extract percentile 16')
    parser.add_argument('-f5', action='store_true', help='extract percentile 84')
    parser.add_argument('-f6', action='store_true', help='extract percentile 97.5')

    parser.add_argument('-l0', action='store_true', help='extract f_mu (SFH)')
    parser.add_argument('-l1', action='store_true', help='extract f_mu (IR)')
    parser.add_argument('-l2', action='store_true', help='extract mu parameter')
    parser.add_argument('-l3', action='store_true', help='extract tau_V')
    parser.add_argument('-l4', action='store_true', help='extract sSFR_0.1Gyr')
    parser.add_argument('-l5', action='store_true', help='extract M(stars)')
    parser.add_argument('-l6', action='store_true', help='extract Ldust')
    parser.add_argument('-l7', action='store_true', help='extract T_C^ISM')
    parser.add_argument('-l8', action='store_true', help='extract T_W^BC')
    parser.add_argument('-l9', action='store_true', help='extract xi_C^tot')
    parser.add_argument('-l10', action='store_true', help='extract xi_PAH^tot')
    parser.add_argument('-l11', action='store_true', help='extract xi_MIR^tot')
    parser.add_argument('-l12', action='store_true', help='extract xi_W^tot')
    parser.add_argument('-l13', action='store_true', help='extract tau_V^ISM')
    parser.add_argument('-l14', action='store_true', help='extract M(dust)')
    parser.add_argument('-l15', action='store_true', help='extract SFR_0.1Gyr')

    parser.add_argument('-t0', action='store_true', help='get normal pixels')
    parser.add_argument('-t1', action='store_true', help='get integrated flux pixels)')
    parser.add_argument('-t2', action='store_true', help='get radial pixels')

    return vars(parser.parse_args())


def check_galaxy_names(connection, names):
    """
    Checks the provided list of galaxy names against the database and works out which names don't correspond to a valid
    galaxy.
    :param connection: The database connection to use
    :param names: The galaxy names to check
    :return: Two lists. The first containing valid galaxy names, the second containing the invalid ones.
    """

    good = []
    bad = []

    for gal_name in names:
        # Open the db, do a 'like' match on this galaxy. If it succeeds, place this galaxy in the good list. If it
        # fails, put it in the bad list.
        result = connection.execute(select([GALAXY]).where(gal_name.strip() == GALAXY.c.name)).first()

        if not result:
            bad.append(gal_name)
        else:
            good.append(result['galaxy_id'])

    return good, bad


def check_args(args):
    """
    Checks the command line arguments to ensure there's at least one feature, layer and pixel type.
    :param args: The parsed command line args
    :return: True if the args are fine, False if not.
    """

    has_feature = False
    has_layer = False
    has_pixel = False

    for k, v in args.iteritems():
        if k.startswith('f') and v is True:
            has_feature = True

        if k.startswith('l') and v is True:
            has_layer = True

        if k.startswith('t') and v is True:
            has_pixel = True

        if has_feature and has_layer and has_pixel:
            return True

    return False


def insert_features_layers_pixel_types_db_ids(connection, request_id, features, layers, pixel_types):
    """
    Associates the given features, layers and pixel types to the provided request ID
    :param connection: The database connection
    :param request_id: The ID of the HDF5 request
    :param features: The features requested
    :param layers: The layers requested
    :param pixel_types: The pixel types requested
    :return: Nothing
    """

    for feature in features:
        entry = connection.execute(select([HDF5_FEATURE]).where(HDF5_FEATURE.c.argument_name == feature)).first()

        if not entry:
            LOG.info("Bad feature. Feature does not exist: {0}".format(feature))
        else:
            connection.execute(HDF5_REQUEST_FEATURE.insert(), hdf5_request_id=request_id,
                               hdf5_feature_id=entry['hdf5_feature_id'])

    for layer in layers:
        entry = connection.execute(select([HDF5_LAYER]).where(HDF5_LAYER.c.argument_name == layer)).first()

        if not entry:
            LOG.info("Bad layer. Layer does not exist: {0}".format(layer))
        else:
            connection.execute(HDF5_REQUEST_LAYER.insert(), hdf5_request_id=request_id,
                               hdf5_layer_id=entry['hdf5_layer_id'])

    for pixel_type in pixel_types:
        entry = connection.execute(select([HDF5_PIXEL_TYPE])
                                   .where(HDF5_PIXEL_TYPE.c.argument_name == pixel_type)).first()

        if not entry:
            LOG.info("Bad pixel type. Pixel type does not exist: {0}".format(pixel_type))
        else:
            connection.execute(HDF5_REQUEST_PIXEL_TYPE.insert(), hdf5_request_id=request_id,
                               hdf5_pixel_type_id=entry['hdf5_pixel_type_id'])


def make_request(connection, email_address, galaxy_ids, features, layers, pixel_types):
    """
    Makes a request in the database for the provided galaxies.
    :param connection: The database connection
    :param email_address: The email address requesting the galaxies
    :param galaxy_ids: The database IDs of the galaxies
    :param features: The features of the galaxies to request
    :param layers: The layers of the galaxies to request
    :param pixel_types: The pixel types of the galaxies to request
    :return:
    """

    # Make some new DB entries for these galaxies
    transaction = connection.begin()

    try:

        LOG.info("Making HDF5_REQUEST entry...")
        result = connection.execute(HDF5_REQUEST.insert(), profile_id=0, email=email_address,
                                    created_at=datetime.datetime.utcnow())

        LOG.info("Making features, layers, pixel types entries...")
        insert_features_layers_pixel_types_db_ids(connection, result.inserted_primary_key, features, layers, pixel_types)

        LOG.info("Making galaxy entries...")
        for galaxy in galaxy_ids:
            # We already checked to ensure these are valid, so throw em in.
            connection.execute(HDF5_REQUEST_GALAXY.insert(), hdf5_request_id=result.inserted_primary_key,
                               galaxy_id=galaxy)

        transaction.commit()
    except:
        transaction.rollback()
        raise


def main():
    """
    Main program entry point
    :return:
    """

    args = parse_args()

    LOG.info("Args: {0}".format(args))

    if not check_args(args):
        LOG.info("Arguments are missing feature, layer or pixel type!")
        return

    # Grab the galaxy names
    filename = args['galaxy_ids'][0]
    LOG.info("Loading from file: {0}".format(filename))
    galaxy_names = load_galaxy_file(filename)

    if not galaxy_names:
        LOG.info("Failed to open file, or no galaxies requested!")
        return
    else:
        LOG.info("Loaded {0} galaxy names from {1}".format(len(galaxy_names), filename))

    # Get a DB connection
    connection = engine.connect()

    # Compare the galaxy names against the database to find valid and invalid names.
    LOG.info("Checking galaxy names...")
    galaxy_ids, invalid_names = check_galaxy_names(connection, galaxy_names)

    if len(invalid_names) > 0:
        LOG.info("Failed to find the following galaxies: ")
        count = 0
        for name in invalid_names:
            count += 1
            LOG.info("{0}: {1}".format(count, name))

    if len(galaxy_ids) == 0:
        LOG.info("No valid galaxies in request!")
        return

    if len(galaxy_ids) != 0 and len(invalid_names) == 0:
        LOG.info("Galaxies OK.")

    LOG.info("Getting features, layers and pixel types...")
    features, layers, pixel_types = split_flp(args)
    LOG.info("The following features, layers and pixel types were found")
    LOG.info("Features: {0}".format(features))
    LOG.info("Layers: {0}".format(layers))
    LOG.info("Pixel Types: {0}".format(pixel_types))

    LOG.info("Starting database insertion...")
    make_request(connection, args['email'][0], galaxy_ids, features, layers, pixel_types)
    LOG.info("All done!")

if __name__ == "__main__":
    main()