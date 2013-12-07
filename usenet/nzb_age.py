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
import re
import datetime

def main(options, args):
	if len(args) < 2:
		print("Usage: start-end directory")
		sys.exit(1)

	(start, end) = args[0].split("-")
	(start, end) = (int(start), int(end))
	process_dir = args[1]
	print("Start: %d days, end: %d days." % (start, end))
	
	if options.output_dir:
		print("Moving NZB files to %s" % options.output_dir)

	for nzbfile in os.listdir(process_dir):
		if not nzbfile.endswith(".nzb"):
			continue
		date = None
		# not parsing the whole file, just what we need
		with open(os.path.join(process_dir, nzbfile), "r") as file:
			for line in file.readlines():
				match = re.match(".* date=\"(\d+)\".*", line)
				if match:
					date = datetime.datetime.fromtimestamp(int(match.group(1)))
					break
		if date:
			diff = datetime.datetime.now() - date
			if start < diff.days < end:
				if options.output_dir:
					old = os.path.join(process_dir, nzbfile)
					os.renames(old, os.path.join(options.output_dir, nzbfile))
				else:
					print(nzbfile)
		else:
			print("Bad NZB file: %s" % nzbfile)
		
if __name__ == '__main__':
	parser = optparse.OptionParser(
		usage="Usage: %prog from-to directory\n"
			  "       e.g. %prog 1000-1200 . -o /will/move/nzbs/to\n"
		"This tool will list or move NZB files between a certain age, "
		"expressed in days.\n",
		version="%prog 1.0 (2011-12-15)") # --help, --version
	
	parser.add_option("-o", help="where to move the matched NZBs to.",
					dest="output_dir", metavar="DIRECTORY", default=None)
	
	# no arguments given
	if len(sys.argv) < 2:
		print(parser.format_help())
	else:
		(options, args) = parser.parse_args()
		main(options, args)