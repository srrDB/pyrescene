#!/usr/bin/env python
"""Runs all tests, without requiring extra packages such as Nose"""

import unittest
import sys
import os, os.path

# Save script directory before the test modules change the current directory
dir = os.path.join(os.getcwd(), os.path.dirname(__file__))

suite = unittest.TestSuite()

# These would be automatically discovered in Python 2.7 and 3.2, but Python
# 2.6's "unittest" module does not support discovery
suite.addTest(unittest.defaultTestLoader.loadTestsFromNames((
	"rescene.test.test_utility",
	"rescene.test.test_rar",
	"rescene.test.test_osohash",
	"rescene.test.test_rarstream",
	"rescene.test.test_main",
	"resample.test.test_main",
	"resample.test.test_ebml",
)))

sys.path.append(os.path.join(dir, "usenet"))

suite.addTest(unittest.defaultTestLoader.loadTestsFromNames((
	"nzb_sample_extract",
	"nzb_split",
)))

import pynzb.tests

# Not running test_parse_date(), because the parse_date() function is monkey-
# patched to a version that returns a local time
for func in ("test_expat", "test_etree"):
	suite.addTest(unittest.FunctionTestCase(getattr(pynzb.tests, func)))

import pynzb
if pynzb.LXMLNZBParser:
	suite.addTest(unittest.FunctionTestCase(pynzb.tests.test_lxml))

sys.path.append(os.path.join(dir, "experiments"))
suite.addTest(unittest.defaultTestLoader.loadTestsFromName("tvmatch"))

sys.path.append(os.path.join(dir, "scripts"))
suite.addTest(unittest.defaultTestLoader.loadTestsFromName("nzbsrr"))

unittest.main(defaultTest="suite")
