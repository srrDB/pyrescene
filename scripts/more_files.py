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

"""Python alternative for this command:

find . -type d -exec sh -c 'set -- "$0"/*.*; [ $# -gt 1 ]' {} \; -print
(too slow on Windows)

Version 0.1 (2012-03-20)
 - Initial version
 
Version 0.2 (2012-09-07)
 - Help updated
 
Version 0.3 (2012-09-23)
 - Works with subdirs too
 
Version 0.4 (2012-11-25)
 - MP4 and WMV support for -c switch
 
Version 0.5 (2016-01-11)
 - Issues fixed when output directory is located at input location
 - VOB and M2TS support for -c switch

Author: Gfy"""

import os
import sys
import optparse
import shutil

def do_move(dest_dir, dir_to_move):
	if dest_dir and os.path.abspath(dest_dir) != dir_to_move:
		shutil.move(dir_to_move, dest_dir)

def list_files(fullreldir):
	# list all file in a given directory, including subdirs
	sampfiles = []
	for dirpath, _dirnames, filenames in os.walk(fullreldir):
		for fname in filenames:
			sampfiles.append(os.path.join(dirpath, fname))
	return sampfiles

def main(options, args):
	if (not options.more and not options.none and
		not options.usenet and not options.capitals and not options.empty):
		print("What should I check for?")
		sys.exit(1)

	if not os.path.exists(options.output_dir):
		print("Trying to create missing output directory")
		os.makedirs(options.output_dir)

	parg = args[0]
	for reldir in os.listdir(parg):
		fullreldir = os.path.abspath(os.path.join(parg, reldir))
		if os.path.isdir(fullreldir):
			sampfiles = list_files(fullreldir)
			if ((len(sampfiles) > 1 and options.more) or
				(not len(sampfiles) and options.none) or
				(options.usenet and any("usenet" in x for x in sampfiles) or
				(options.capitals and any(
					".MKV.txt" in x or ".AVI.txt" in x or
					".MP4.txt" in x or ".WMV.txt" in x or
					".VOB.txt" in x or ".M2TS.txt" in x
					for x in sampfiles))) or
				(options.empty and not any(os.path.getsize(
				        os.path.join(fullreldir, x)) != 0
				        for x in sampfiles))):
				print(reldir)
				do_move(options.output_dir, fullreldir)

if __name__ == '__main__':
	parser = optparse.OptionParser(
		usage="Usage: %prog [arguments] [directory]'\n"
		"This tool will list all directories with multiple files or none.\n",
		version="%prog 0.5 (2016-01-11)")  # --help, --version

	parser.add_option("-m", "--more", help="more than one",
	                  action="store_true", default=False, dest="more")
	parser.add_option("-n", "--none", help="no files in dir",
	                  action="store_true", default=False, dest="none")
	parser.add_option("-e", "--empty", help="empty files in dir",
	                  action="store_true", default=False, dest="empty")
	parser.add_option("-u", "--usenet", help="usenet-space-cowbys.info",
	                  action="store_true", default=False, dest="usenet")
	parser.add_option("-c", "--capitals", help=".MKV.txt, .AVI.txt"
					  ", MP4.txt or WMV.txt",
	                  action="store_true", default=False, dest="capitals")
	parser.add_option("-o", help="move the found directories to this location",
				dest="output_dir", metavar="DIRECTORY", default=None)

	# no arguments given
	if len(sys.argv) < 2:
		print(parser.format_help())
	else:
		(options, args) = parser.parse_args()
		main(options, args)
