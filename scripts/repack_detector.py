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

# Author: Gfy <tsl@yninovg.pbz>
# version 1.0 2011-12-15 First version
# version 1.1 2011-12-22 No NFO option

import optparse
import sys
import os
from os.path import join, dirname, realpath

# for running the script directly from command line
sys.path.append(join(dirname(realpath(sys.argv[0])), '..'))

from rescene import info

def main(options, args):
	for lfile in os.listdir(args[0]):
		if lfile[-4:] != ".srr":
			continue
		srr = info(lfile)
		
		has_nfo = False
		for sfile in srr['stored_files']:
			if sfile[-4:] == ".nfo":
				has_nfo = True
				
		if not options.nonfo:
			has_nfo = False
		
		# for each stored lfile: max 3 comment lines
		if (len(srr['sfv_comments']) > 
				3 * len(srr['archived_files']) and not has_nfo):
			print(lfile)
		
if __name__ == '__main__':
	parser = optparse.OptionParser(
		usage="Usage: %prog [directory]\n"
		"This tool will list SRR files with more than three comment lines.\n"
		"For non foreign series, a lot of those will be repacks.",
		version="%prog 1.1 (2011-12-22)") # --help, --version
	
	parser.add_option("-n", "--no-nfo", help="result can not contain nfo",
					  action="store_true", dest="nonfo", default=False)
	
	# no arguments given
	if len(sys.argv) < 2:
		print(parser.format_help())
	else:
		(options, args) = parser.parse_args()
		main(options, args)