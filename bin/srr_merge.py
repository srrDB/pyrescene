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
from os.path import join, dirname, realpath

# for running the script directly from command line
sys.path.append(join(dirname(realpath(sys.argv[0])), '..', 'rescene'))

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
		version="%prog 1.0 (2011-12-27)") # --help, --version
	
	parser.add_option("-o", dest="output_name", 
					help="name (and path) of the new SRR file")
	
	# no arguments given
	if len(sys.argv) < 2:
		print(parser.format_help())
	else:
		(options, args) = parser.parse_args()
		main(options, args)
		