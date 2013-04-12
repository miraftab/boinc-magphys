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
Tests for the to_fits module
"""
import unittest


class testToFits(unittest.TestCase):
    """
    A test case for the to_fits module
    """

    def setUp(self):
        """
        Setup data used in tests
        :return:
        """
        pass

    def testCheckResults(self):
        result = ''

def suite():
    """
    Build the test suite
    :return: the suite
    """
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(testToFits))
    return suite

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())