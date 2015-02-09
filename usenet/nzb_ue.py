#!/usr/bin/env python
# -*- coding: latin-1 -*-

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

def main(options, args):
	nzbdir = args[0]
	for nzbfile in os.listdir(nzbdir):
		if not nzbfile.endswith(".nzb"):
			continue
		
		with open(os.path.join(nzbdir, nzbfile), "r") as file:
			for line in file.readlines():
				match = re.match(
					".* poster=\".*uncle eric.*", line)
				if match:
					print(nzbfile)
					break
		
if __name__ == '__main__':
	parser = optparse.OptionParser(
		usage="Usage: %prog directory\n"
		"Lists uncle eric's posts. (often repacks)",
		version="%prog 1.0 (2011-12-15)") # --help, --version
	
	# no arguments given
	if len(sys.argv) < 2:
		print(parser.format_help())
	else:
		(options, args) = parser.parse_args()
		main(options, args)