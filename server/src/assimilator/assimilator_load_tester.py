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
__author__ = 'ict310'

from sqlalchemy import create_engine
from database.database_support_core import AREA, PIXEL_RESULT
from config import DB_LOGIN
import time
import datetime
import random

random.seed()
ENGINE = create_engine(DB_LOGIN)


def old(iterations):
    p_start = time.time()
    connection = ENGINE.connect()
    db_time = []
    i = 0
    while i < 300:
        start = time.time()
        transaction = connection.begin()

        a = 0
        while a < iterations:
            area = random.randrange(5, 60, 1)
            wu_id = random.randrange(5, 60, 1)
            connection.execute(AREA.update()
                               .where(AREA.c.area_id == area)
                               .values(workunit_id=wu_id, update_time=datetime.datetime.now()))
            a += 1

        sleepytime = random.randrange(80, 140, 1)
        time.sleep(sleepytime/100.0)

        transaction.commit()
        print 'Time in DB {0}'.format(time.time() - start)
        db_time.append(time.time() - start)
        i += 1

    total = 0
    for dbtime in db_time:
        total += dbtime

    ave = total/len(db_time)
    print 'Total time: {0}'.format(total)
    print 'Ave per transaction: {0}'.format(ave)
    print 'Total program run time: {0}'.format(time.time() - p_start)


def new(iterations):
    p_start = time.time()
    connection = ENGINE.connect()
    db_time = []
    i = 0
    while i < 300:
        db_queue = []

        a = 0
        while a < iterations:
            area = random.randrange(5, 60, 1)
            wu_id = random.randrange(5, 60, 1)
            db_queue.append(AREA.update()
                            .where(AREA.c.area_id == area)
                            .values(workunit_id=wu_id, update_time=datetime.datetime.now()))
            a += 1

        sleepytime = random.randrange(80, 140, 1)
        time.sleep(sleepytime/100.0)

        start = time.time()
        transaction = connection.begin()
        for item in db_queue:
            connection.execute(item)
        transaction.commit()

        i += 1
        print 'Time in DB {0}'.format(time.time() - start)
        db_time.append(time.time() - start)

    total = 0
    for dbtime in db_time:
        total += dbtime

    ave = total/len(db_time)
    print 'Total time: {0}'.format(total)
    print 'Ave per transaction: {0}'.format(ave)
    print 'Total program run time: {0}'.format(time.time() - p_start)


def lock(time_p):
    connection = ENGINE.connect()
    transaction = connection.begin()
    i = 999
    while True:
        wu_id = random.randrange(5, 60, 1)
        connection.execute(
            AREA.update()
                .where(AREA.c.area_id == wu_id)
                .values(workunit_id=wu_id, update_time=datetime.datetime.now()))
        connection.execute(PIXEL_RESULT.update().where(PIXEL_RESULT.c.pxresult_id == wu_id).values(y=i,
                                                                                                   x=i))
        i += 1
        if i > 100000:
            break
    transaction.rollback()


if __name__ == "__main__":
    selection = raw_input('Which version do you want to test with? (new/old)')
    selection2 = raw_input('How many db tasks should be done per transaction?')

    if selection == 'new':
        new(int(selection2))

    if selection == 'old':
        old(int(selection2))

    if selection == 'lock':
        lock(int(selection2))
