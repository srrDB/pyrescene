#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2012-2013 pyReScene
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

import optparse
import sys
import os

try:
	import _preamble
except ImportError:
	pass

from resample.main import file_type_info, sample_class_factory
from rescene.utility import sep

def main(options, args):
	for  dirpath, _dirnames, filenames in os.walk(args[0]):
		for sfile in filenames:
			if sfile[-4:].lower() == ".srs":
				f = os.path.join(dirpath, sfile)
				sample = sample_class_factory(file_type_info(f).file_type)
				srs_data, _tracks = sample.load_srs(f)
				if srs_data.size > int(options.size):
					print(f)
					print(sep(srs_data.size))

if __name__ == '__main__':
	parser = optparse.OptionParser(
		usage="Usage: %prog directory -s size'\n"
		"This tool will list SRS files greater than a certain size.",
		version="%prog 0.2 (2013-04-20)")  # --help, --version
	# 0.1 (2012-10-27)
	# 0.2 (2013-04-20)

	parser.add_option("-s", dest="size",
					help="minimum size of the original sample")

	# no arguments given
	if len(sys.argv) < 2:
		print(parser.format_help())
	else:
		(options, args) = parser.parse_args()
		main(options, args)
