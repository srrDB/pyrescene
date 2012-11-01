#!/usr/bin/env python
# -*- coding: utf-8 -*-

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

import optparse
import sys
import os

# for running the script directly from command line
curdir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(curdir, '..'))
try:
	from rescene import info
except ImportError:
	print("Can't import the 'rescene' module.")
	
def list_srr(sfile):
	for key, value in info(sfile)['archived_files'].items():
#		print(os.path.basename(sfile)[:-4]),
		print("%s\t%s" % (key, value.crc32))

def main(options, args):
	for element in args:
		element = os.path.abspath(element)
		if os.path.isfile(element) and element[-4:] == ".srr":
			list_srr(element)
		elif os.path.isdir(element):
			for dirpath, _dirnames, filenames in os.walk(element):
				for sfile in filenames:
					if sfile[-4:] == ".srr":
						list_srr(os.path.join(dirpath, sfile))
		else:
			print("WTF are you supplying me?")

if __name__ == '__main__':
	parser = optparse.OptionParser(
		usage="Usage: %prog [srr files] [directories]'\n"
		"This tool will list the CRCs of the archived files.\n",
		version="%prog 0.1 (2012-11-01)") # --help, --version
	
	# no arguments given
	if len(sys.argv) < 2:
		print(parser.format_help())
	else:
		(options, args) = parser.parse_args()
		main(options, args)