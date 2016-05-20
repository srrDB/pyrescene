#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2014 pyReScene
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.

"""Runs all tests, without requiring extra packages such as Nose"""

import unittest
import sys
import os

def main():
	# Save script directory before the test modules change the current directory
	curdir = os.path.join(os.getcwd(), os.path.dirname(__file__))

	suite = unittest.TestSuite()

	# These would be automatically discovered in Python 2.7 and 3.2,
	# but Python 2.6's "unittest" module does not support discovery
	suite.addTest(unittest.defaultTestLoader.loadTestsFromNames((
		"rescene.test.test_utility",
		"rescene.test.test_rar",
		"rescene.test.test_osohash",
		"rescene.test.test_rarstream",
		"rescene.test.test_main",
		"resample.test.test_main",
		"resample.test.test_ebml",
		"resample.test.test_mp3",
	)))

	sys.path.append(os.path.join(curdir, "usenet"))

	suite.addTest(unittest.defaultTestLoader.loadTestsFromNames((
		"nzb_sample_extract",
		"nzb_split",
	)))

	import pynzb.tests

	# Not running test_parse_date(), because the parse_date() function is
	# monkey-patched to a version that returns a local time
	for func in ("test_expat", "test_etree"):
		suite.addTest(unittest.FunctionTestCase(getattr(pynzb.tests, func)))

	import pynzb
	if pynzb.LXMLNZBParser:
		suite.addTest(unittest.FunctionTestCase(pynzb.tests.test_lxml))

	sys.path.append(os.path.join(curdir, "scripts", "experiments"))
	suite.addTest(unittest.defaultTestLoader.loadTestsFromName("tvmatch"))

	sys.path.append(os.path.join(curdir, "scripts"))
	suite.addTest(unittest.defaultTestLoader.loadTestsFromName("nzbsrr"))

	return suite

if __name__ == '__main__':
	suite = main()

	kw = dict()
	if sys.version_info >= (3, 2) or sys.version_info >= (2, 7):
		kw.update(buffer=True)
	unittest.main(defaultTest="suite", **kw)
