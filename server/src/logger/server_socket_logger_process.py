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
Main program for a logging server that can receive multiple connections from python loggers using a socket_handler.
Logs are saved to a local file with the same name as the name used for the logger on the client.

"""
from _socket import AF_INET, SOCK_STREAM
import os
import sys

# Setup the Python Path as we may be running this via ssh
base_path = os.path.dirname(__file__)
sys.path.append(os.path.abspath(os.path.join(base_path, '..')))
sys.path.append(os.path.abspath(os.path.join(base_path, '../../../../boinc/py')))

from socket import socket, timeout
import argparse
import struct
import cPickle
import logging
import logging.handlers
import signal
from Boinc import boinc_project_path
from threading import Thread
from multiprocessing import Process
import time
from config import LOGGER_SERVER_PORT, LOGGER_LOG_DIRECTORY, LOGGER_MAX_CONNECTION_REQUESTS
from utils.logging_helper import config_logger

STOP_TRIGGER_FILENAME = boinc_project_path.project_path('stop_daemons')

# A list of all child processes (entries added whenever a client connects and removed on disconnect)
child_list = list()

# Set to true when a SIGINT OR SIGHUP is caught
caught_sig_int = False

# Local logger for server logs
server_log = config_logger('ServerLog')
handler = logging.FileHandler('ServerLog.log')
formatter = logging.Formatter('%(asctime)-15s:' + logging.BASIC_FORMAT)
handler.setFormatter(formatter)
server_log.addHandler(handler)


def main():
    """
    Main program.
    1.Gets command line arguments and changes local_port or log_directory to match arguments.
      If no arguments are given, the defaults defined in config are used.
    2.Create log directory if it does not exist
    3.Set up socket to listen on specified port
    loop
        4.When connection is received, create new process to handle client
        5.Clean up any defunct processes

    Will only exit when stop trigger identified or an error occurs
    :return: void
    """

    # Local vars
    local_host = ''
    log_directory = LOGGER_LOG_DIRECTORY
    local_port = LOGGER_SERVER_PORT
    logger_number = 0

    # Get command line args
    parser = argparse.ArgumentParser('Logging server')
    parser.add_argument('-p', type=int, help='Local port that the logging server should listen on')
    parser.add_argument('-d', help='Local directory to save logs to')

    args = vars(parser.parse_args())

    if args['p'] is not None:
        local_port = args.p

    if args['d'] is not None:
        log_directory = args.d

    server_log.info('Local log started')
    server_log.info('Log directory : {0}'.format(log_directory))
    server_log.info('Port : {0}'.format(local_port))
    server_log.info('System path: {0}'.format(sys.path))

    # Need to ensure save directory ends with a /
    if not log_directory.endswith('/'):
        log_directory += '/'

    # Try to create log file directory if it does not exist
    if not os.path.isdir(log_directory):
        try:
            server_log.info('Creating log directory...')
            os.mkdir(log_directory)

        except OSError as e:
            server_log.exception('Error creating log directory')
            # Server_log.info('Log directory already exists')
            sys.exit(0)
    else:
        server_log.info('Log directory already exists at {0}'.format(log_directory))

    # Set up sockets
    server_log.info('Attempting to set up sockets...')

    try:
        server_socket = socket(AF_INET, SOCK_STREAM)
        server_socket.bind((local_host, local_port))

        server_log.info('Listening on %s : %d', local_host, local_port)
        server_socket.listen(LOGGER_MAX_CONNECTION_REQUESTS)

    except IOError as e:
        server_log.exception('Error setting up sockets. Is there another process listening on port {0} ?'.format(local_port))
        sys.exit(0)

    while 1:
        try:
            client_socket, addr = server_socket.accept()
            server_log.info('Incoming connection from {0}'.format(addr))
            server_log.info('Using local logger number {0}'.format(logger_number))

            client_socket.settimeout(60 * 10)  # 10 min timeout

            # Handle each new client in a new process
            pros = Process(target=handle_client, args=(log_directory, client_socket, logger_number, addr))
            pros.start()

            # Keep a list of all processes to terminate later when the program is told to close
            child_list.append(pros)

            # Add 1 to logger number so the next client uses a unique logger
            logger_number += 1

        except IOError as e:  # Socket error
            if e.errno == 4:  # If we received Errno 4, it is because we received a sigint and wish to exit.
                raise
            server_log.exception('Error setting up connection with client {0}'.format(addr))

        except SystemExit:  # sys.exit(0) is called by the maintenance thread.
            # Maintenance Thread has notified us that it's time to shut down
            server_log.info('Shutdown flag identified, shutting down...')
            server_socket.close()
            sys.exit(0)


def handle_client(save_directory, c_socket, l_number, client_addr):
    """
    Handles a single client

    Will receive data from the client until the client either sends no more data or the socket connection is interrupted
    somehow.

    Each log is unpacked from the client and record.name of the first record received is used to determine the name of
    the local file to save to. If the client wishes to switch to a different file they must create a new connection.

    :param save_directory: the location in which to save logs from this client
    :param c_socket: the socket the client is connected on
    :param l_number: the logger number to be used by this handle instance
    :return: void
    """

    file_open = 0

    logger = logging.getLogger(str(l_number))

    while 1:
        # Try to receive a log from the client
        try:
            chunk = c_socket.recv(4)

            if len(chunk) < 4:
                server_log.info('Connection terminated normally')
                c_socket.close()
                exit(0)

            # This chunk of code extracts a log record from the received data and places it into record
            slen = struct.unpack('>L', chunk)[0]
            chunk = c_socket.recv(slen)

            while len(chunk) < slen:
                chunk = chunk + c_socket.recv(slen - len(chunk))

            obj = cPickle.loads(chunk)

            try:
                file_name = obj['filename']
            except KeyError:
                server_log.error('Client connected with no filename to write to!')
                file_name = 'NO_FILE_NAME'

            record = logging.makeLogRecord(obj)

            if file_open == 0:
                # Set up log handler to print logs to file
                formatter = logging.Formatter(file_name + ': %(asctime)-15s:' + logging.BASIC_FORMAT)
                file_handler = logging.FileHandler(save_directory + file_name + '.log')
                file_handler.setFormatter(formatter)
                logger.addHandler(file_handler)
                file_open = 1

                stdouthandle = logging.getLogger().handlers[0]
                stdouthandle.setFormatter(formatter)
            else:
                # Finally, handle the record by printing it to the file specified
                logger.handle(record)

        except IOError:
            server_log.error('Connection closed in an unexpected way.')
            c_socket.close()
            exit(0)

        except timeout:
            server_log.error('Connection timed out {0}'.format(c_socket.getpeername))
            c_socket.close()
            exit(0)


def child_reclaim():
    """
    Reclaims defunct child processes

    Checks for any child processes that have exited and reclaims them, removing their defunct entry from the process
    table.
    :return: void
    """
    more = 1

    while more:
        # Wait for any defunct child processes to remove them from the process table
        try:
            (pid, status) = os.waitpid(-1, os.P_NOWAIT)
            # Remove the dead process from the list of child processes
            for i in child_list:
                if i.pid == pid:
                    child_list.remove(i)
        except OSError as e:
            return

        if pid <= 0:
            more = 0


def sigint_handler(self, sig):
    """
    This method handles the SIGINT and SIGHUP signal. It sets a flag
    but waits to exit until background_management checks this flag
    """
    server_log.info('Caught shutdown signal')

    global caught_sig_int
    caught_sig_int = True


def background_management():
    """
    This method is created as a thread when the program starts. It manages background operations, such as reclaiming
    child processes and detecting shutdown signals
    :return:
    """
    heartbeat = 0
    while 1:
        heartbeat += 1

        if heartbeat == 60:
            server_log.info("Server is active with {0} current connection(s)".format(len(child_list)))
            heartbeat = 0

        child_reclaim()

        if os.path.exists(STOP_TRIGGER_FILENAME):
            server_log.info("Shutdown file identified\n")
            for i in child_list:  # Kill all child processes that have not been claimed by child_reclaim()
                i.terminate()
            sys.exit(0)

        if caught_sig_int:
            server_log.info("SIGINT Received\n")
            for i in child_list:  # Kill all child processes that have not been claimed by child_reclaim()
                i.terminate()
            sys.exit(0)

        time.sleep(1)  # No point in checking constantly, save a bit of CPU time


if __name__ == "__main__":
    # Install sigint handler
    signal.signal(signal.SIGINT, sigint_handler)
    signal.signal(signal.SIGHUP, sigint_handler)

    # Start a thread to do background management tasks
    thread = Thread(target=background_management)
    thread.daemon = True
    thread.start()

    main()
