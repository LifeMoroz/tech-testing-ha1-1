#!/usr/bin/env python2.7

import os
import sys
import unittest

source_dir = os.path.join(os.path.dirname(__file__), 'source')
sys.path.insert(0, source_dir)

loader = unittest.TestLoader()
testdir = os.path.abspath(os.path.dirname(__file__)) + '/source/tests/'
suite = loader.discover(testdir, pattern='*.py')

if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(not result.wasSuccessful())
