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

"""
This tool will merge a split up a NZB file.
The file with the shortest file name will be picked to put the result.
The other files will be removed.

Changelog:
0.1: initial version (2011-01-31)
"""

import os
import sys
import optparse
import nzb_utils

def merge_nzbs(nzbdir):
	nzb_files = [os.path.join(nzbdir, e) for e in os.listdir(nzbdir)
	             if not os.path.isdir(e) and e[-4:].lower() == ".nzb"]
	if len(nzb_files) > 1:
		nzb_files.sort(key=lambda f: len(f))

		read_nzbs = {}
		for nfile in nzb_files:
			read_nzbs[nfile] = nzb_utils.read_nzb(nfile)

		doc = nzb_utils.empty_nzb_document()
		for nzb in nzb_files:
			for nfile in read_nzbs[nzb]:
				nzb_utils.add_file(doc, nfile)

		# shortest directory name we will overwrite
		with open(nzb_files[0], "w") as nzb:
			nzb.write(nzb_utils.get_xml(doc))

		# remove other nzb files
		for nzbfile in nzb_files[1:]:
			print("Removing %s" % os.path.basename(nzbfile))
			os.remove(nzbfile)

def main(options, args):
	main_dir = os.path.abspath(args[0])
	for ldir in os.listdir(main_dir):
		if os.path.isdir(ldir):
			merge_nzbs(os.path.join(main_dir, ldir))

if __name__ == '__main__':
	parser = optparse.OptionParser(
		usage="Usage: %prog [input dir]'\n"
		"This tool will merge a split up NZB file. "
		"All files must be in their own releasedir.\n",
		version="%prog 0.1 (2012-01-31)")  # --help, --version

	# no arguments given
	if len(sys.argv) < 2:
		print(parser.format_help())
	else:
		(options, args) = parser.parse_args()
		main(options, args)
