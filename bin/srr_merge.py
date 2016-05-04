#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2012 pyReScene
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

try:
	import _preamble
except ImportError:
	pass

import rescene

def main(options, args):
	srr_list = args

	if not options.output_name:
		destination = args[0][:-4] + "_joined.srr"
	else:
		destination = options.output_name

	rescene.merge_srrs(srr_list, destination)

if __name__ == '__main__':
	parser = optparse.OptionParser(
		usage="Usage: %prog [srr1, srr2,...] -o output file'\n"
		"This tool will join together two or more SRR files.",
		version="%prog 1.0 (2011-12-27)")  # --help, --version

	parser.add_option("-o", dest="output_name",
					help="name (and path) of the new SRR file")

	# no arguments given
	if len(sys.argv) < 2:
		print(parser.format_help())
	else:
		(options, args) = parser.parse_args()
		main(options, args)
