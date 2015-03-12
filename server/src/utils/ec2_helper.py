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
Helper functions for EC2
"""
import random
import boto
import time
import datetime
from boto.exception import EC2ResponseError
from boto.utils import get_instance_metadata
from utils.logging_helper import config_logger
from config import AWS_AMI_ID, AWS_KEY_NAME, AWS_SECURITY_GROUPS, AWS_SUBNET_IDS, AWS_SUBNET_DICT, SPOT_PRICE_MULTIPLIER, EC2_IP_ARCHIVE_ADDRESSES, EC2_IP_BUILD_IMAGE_ADDRESSES, BUILD_PNG_IMAGE_DICT, ARCHIVE_DATA_DICT

LOG = config_logger(__name__)


class EC2Helper:
    def __init__(self):
        """
        Get an EC2 connection
        :return:
        """
        # This relies on a ~/.boto file holding the '<aws access key>', '<aws secret key>'
        self.ec2_connection = boto.connect_ec2()

    def get_all_instances(self, boinc_value):
        """
        Get any instances that are running with the specified BOINC tag

        :param boinc_value: the tag value we are looking for
        :return: list of instances
        """
        return self.ec2_connection.get_all_instances(filters={'tag:BOINC': boinc_value})

    def wait_for_running(self, instance):
        """
        Waits until the instance specified is actually running.
        Times out after 10 mins or after several attempts if instance.update() causes an exception
        :param instance:
        :return:
        """
        timeout_counter = 0
        instance_status = ''
        while not instance_status == 'running':
            try:
                instance_status = instance.update()
            except Exception:
                LOG.exception('Error getting instance status')
                timeout_counter += 20

            if timeout_counter == 120:
                LOG.error('Timed out')
                return False

            LOG.info('Not running yet')
            time.sleep(5)
            timeout_counter += 1
        return True

    def run_instance(self, user_data, boinc_value, instance_type, remainder=None):
        """
        Run up an instance

        :param user_data:
        :return:
        """
        random.seed()
        index = random.randint(0, len(AWS_SUBNET_IDS) - 1)
        subnet_id = AWS_SUBNET_IDS[index]
        LOG.info('Running instance: ami: {0}, boinc_value: {1}, subnet_id: {2}'.format(AWS_AMI_ID, boinc_value, subnet_id))
        reservations = self.ec2_connection.run_instances(AWS_AMI_ID,
                                                         instance_type=instance_type,
                                                         instance_initiated_shutdown_behavior='terminate',
                                                         subnet_id=subnet_id,
                                                         key_name=AWS_KEY_NAME,
                                                         security_group_ids=AWS_SECURITY_GROUPS,
                                                         user_data=user_data)
        instance = reservations.instances[0]
        time.sleep(5)
        LOG.info('Assigning the tags')
        self.ec2_connection.create_tags([instance.id],
                                        {'BOINC': '{0}'.format(boinc_value),
                                         'Name': 'pogs-{0}'.format(boinc_value),
                                         'Created By': 'pogs'})

        LOG.info('Try to allocate one of the config IP addresses')

        # try to associate with one of the public ips stored in the text file.
        # if they are all used, do things the old way

        ip = self.get_next_available_address(remainder, instance_type)

        if ip is None:
            # do things the old way
            LOG.info('No IP addresses available, allocating a VPC public IP address')
            allocation = self.ec2_connection.allocate_address('vpc')

            if self.wait_for_running(instance) is False:
                return False

            if self.ec2_connection.associate_address(public_ip=None, instance_id=instance.id, allocation_id=allocation.allocation_id):
                LOG.info('Allocated a VPC public IP address')
            else:
                LOG.error('Could not associate the IP to the instance {0}'.format(instance.id))
                self.ec2_connection.release_address(allocation_id=allocation.allocation_id)

        else:
            # do things the new way
            LOG.info("IP Address chosen: {0}".format(ip))

            found_address = False
            for address in self.ec2_connection.get_all_addresses():
                if address.public_ip == ip:
                    found_address = True

                    allocation_id = address.allocation_id
                    LOG.info('Allocation ID: {0}'.format(allocation_id))
                    break

            if not found_address:
                LOG.error('The address {0} is not reserved!'.format(ip))
                return False

            if self.wait_for_running(instance) is False:
                return

            if self.ec2_connection.associate_address(public_ip=None, instance_id=instance.id, allocation_id=allocation_id):
                LOG.info('Allocated a reserved EC2 ip {0}'.format(ip))
            else:
                LOG.error('Could not associate the IP {0} to the instance {1}'.format(ip, instance.id))
        return True

    def boinc_instance_running(self, boinc_value):
        """
        Is an instance running with this tag?
        :param boinc_value:
        :return:
        """
        reservations = self.get_all_instances(boinc_value)
        count = 0
        for reservation in reservations:
            for instance in reservation.instances:
                LOG.info('instance: {0}, state: {1}'.format(instance.id, instance.state))
                if instance.state == 'pending' or instance.state == 'running':
                    count += 1
        return count > 0

    def disassociate_public_ip(self):
        """
        Release the public IP

        :return:
        """
        association_id, allocation_id, public_ip = self.get_allocation_id()
        LOG.info('Releasing IP address {0}'.format(public_ip))

        if allocation_id is not None and association_id is not None and public_ip is not None:
            LOG.info('Disassociating...')
            self.ec2_connection.disassociate_address(association_id=association_id)
            LOG.info('Disassociated successfully {0}'.format(public_ip))

    def get_allocation_id(self):
        """
        Get the allocation id
        :return:
        """
        metadata = get_instance_metadata()
        for address in self.ec2_connection.get_all_addresses():
            if address.public_ip == metadata['public-ipv4']:
                return address.association_id, address.allocation_id, address.public_ip

        return None, None, None

    def run_spot_instance(self, spot_price, subnet_id, user_data, boinc_value, instance_type, remainder=None):
        """
        Run the ami as a spot instance

        :param spot_price: The best spot price history
        :param user_data:
        :param boinc_value:
        :return:
        """
        now_plus = datetime.datetime.utcnow() + datetime.timedelta(minutes=10)
        spot_request = self.ec2_connection.request_spot_instances(spot_price,
                                                                  image_id=AWS_AMI_ID,
                                                                  count=1,
                                                                  valid_until=now_plus.isoformat(),
                                                                  instance_type=instance_type,
                                                                  subnet_id=subnet_id,
                                                                  key_name=AWS_KEY_NAME,
                                                                  security_group_ids=AWS_SECURITY_GROUPS,
                                                                  user_data=user_data)

        # Wait for EC2 to provision the instance
        instance_id = None
        error_count = 0
        while instance_id is None and error_count < 3:
            spot_request_id = spot_request[0].id
            requests = None
            try:
                requests = self.ec2_connection.get_all_spot_instance_requests(request_ids=[spot_request_id])
            except EC2ResponseError:
                LOG.exception('Error count = {0}'.format(error_count))
                error_count += 1

            if requests is None:
                # Wait for AWS to catch up
                time.sleep(10)
            else:
                LOG.info('{0}, state: {1}, status:{2}'.format(spot_request_id, requests[0].state, requests[0].status))
                if requests[0].state == 'active' and requests[0].status.code == 'fulfilled':
                    instance_id = requests[0].instance_id
                elif requests[0].state == 'cancelled':
                    raise CancelledException('Request {0} cancelled. Status: {1}'.format(spot_request_id, requests[0].status))
                else:
                    time.sleep(10)

        # Give it time to settle down
        LOG.info('Assigning the tags')
        self.ec2_connection.create_tags([instance_id],
                                        {'BOINC': '{0}'.format(boinc_value),
                                         'Name': 'pogs-{0}'.format(boinc_value),
                                         'Created By': 'pogs'})

        reservations = self.ec2_connection.get_all_instances(instance_ids=[instance_id])
        instance = reservations[0].instances[0]

        LOG.info('Try to allocate one of the config IP addresses')

        # try to associate with one of the public ips stored in the text file.
        ip = self.get_next_available_address(remainder, instance_type)

        if ip is None:
            # do things the old way
            LOG.info('No IP addresses available, allocating a VPC public IP address')
            allocation = self.ec2_connection.allocate_address('vpc')

            if self.wait_for_running(instance) is False:
                return False

            if self.ec2_connection.associate_address(public_ip=None, instance_id=instance_id, allocation_id=allocation.allocation_id):
                LOG.info('Allocated a VPC public IP address')
            else:
                LOG.error('Could not associate the IP to the instance {0}'.format(instance_id))
                self.ec2_connection.release_address(allocation_id=allocation.allocation_id)

        else:
            # do things the new way
            LOG.info("IP Address chosen: {0}".format(ip))

            found_address = False
            for address in self.ec2_connection.get_all_addresses():
                if address.public_ip == ip:
                    found_address = True

                    allocation_id = address.allocation_id
                    LOG.info('Allocation ID: {0}'.format(allocation_id))
                    break

            if not found_address:
                LOG.error('The address {0} is not reserved!'.format(ip))
                return False

            if self.wait_for_running(instance) is False:
                return False

            if self.ec2_connection.associate_address(public_ip=None, instance_id=instance.id, allocation_id=allocation_id):
                LOG.info('Allocated a reserved EC2 ip {0}'.format(ip))
            else:
                LOG.error('Could not associate the IP {0} to the instance {1}'.format(ip, instance.id))
        return True

    def get_cheapest_spot_price(self, instance_type, max_price):
        """
        Find the cheapest spot price in a zone we use

        :param instance_type:
        :return:
        """
        LOG.info('instance_type: {0}'.format(instance_type))
        prices = self.ec2_connection.get_spot_price_history(start_time=datetime.datetime.now().isoformat(),
                                                            instance_type=instance_type,
                                                            product_description='Linux/UNIX (Amazon VPC)')

        # Get the zones we have subnets in
        availability_zones = []
        for key, value in AWS_SUBNET_DICT.iteritems():
            availability_zones.append(value['availability_zone'])

        best_price = None
        for spot_price in prices:
            LOG.info('Spot Price {0} - {1}'.format(spot_price.price, spot_price.availability_zone))
            if spot_price.availability_zone not in availability_zones:
                # Ignore this one
                LOG.info('Ignoring spot price {0} - {1}'.format(spot_price.price, spot_price.availability_zone))
            elif spot_price.price != 0.0 and best_price is None:
                best_price = spot_price
            elif spot_price.price != 0.0 and spot_price.price < best_price.price:
                best_price = spot_price
        if best_price is None:
            LOG.info('No Spot Price')
            return None, None

        # Put the bid price at the multiplier than the current price
        bid_price = best_price.price * SPOT_PRICE_MULTIPLIER

        # The spot price is too high
        LOG.info('bid_price: {0}, max_price: {1}, instance: {2}'.format(bid_price, max_price, instance_type))
        if bid_price > max_price:
            LOG.info('Spot Price too high')
            return None, None

        LOG.info('Spot Price {0} - {1}'.format(best_price.price, best_price.availability_zone))

        # Now get the subnet id
        subnet_id = None
        for key, value in AWS_SUBNET_DICT.iteritems():
            if value['availability_zone'] == best_price.availability_zone:
                subnet_id = key
                break

        LOG.info('bid_price: {0}, subnet_id: {1}'.format(bid_price, subnet_id))
        return bid_price, subnet_id

    def get_next_available_address(self, remainder, instance_type):
        """
        Out of the ip addresses in the config file, return the one associated with this instance
        If there are none, return None
        """
        LOG.info("Archive addresses to choose from: {0}".format(EC2_IP_ARCHIVE_ADDRESSES))
        LOG.info("Image addresses to choose from: {0}".format(EC2_IP_BUILD_IMAGE_ADDRESSES))

        if instance_type is ARCHIVE_DATA_DICT['instance_type']:
            # allocate an archive IP
            if remainder is None:
                LOG.error("Archiver with no remainder found!")
                return None

            if remainder >= len(EC2_IP_ARCHIVE_ADDRESSES):
                LOG.error("There is no IP address assigned to this archiver! {0}".format(remainder))
                return None

            return EC2_IP_ARCHIVE_ADDRESSES[remainder]

        if instance_type is BUILD_PNG_IMAGE_DICT['instance_type']:
            # allocate a build_png_image address
            # at the moment there will only be one build png image ip address
            return EC2_IP_BUILD_IMAGE_ADDRESSES[remainder]

        return None


class CancelledException(Exception):
    """
    The request has been cancelled
    """
    pass
