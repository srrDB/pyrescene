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

""" Python alternative for these commands:

Shows which lines in new.txt aren't in mine.txt:
cat mine.txt new.txt | sort | uniq -d | cat new.txt - | sort | uniq -u
change -u at the end to -d to get the duplicates

No problems with different line endings of the text files in Windows. 

There is a tool for it too:
  comm

Author: Gfy """

import sys
import optparse

def read_txt(txt_file):
	with open(txt_file, "U") as f:
		return set(f.readlines())

def print_releases(rellist):
	for line in rellist:
		print(line.replace("\n", ""))

def main(options, args):
	mainl = read_txt(args[0])
	newl = read_txt(args[1])

# 	print(len(newl.difference(mainl)))
# 	print(len(mainl.intersection(newl)))

	if options.dupe:
		print_releases(mainl.intersection(newl))
	if options.uniq:
		print_releases(newl.difference(mainl))

if __name__ == '__main__':
	parser = optparse.OptionParser(
		usage="Usage: %prog [main db txt] [list of new rels]\n",
		version="%prog 0.1 (2012-02-05)")  # --help, --version

	parser.add_option("-d", "--duplicates", help="prints dupes",
	                  action="store_true", default=False, dest="dupe")
	parser.add_option("-u", "--uniques", help="prints uniques",
	                  action="store_true", default=False, dest="uniq")

	# no arguments given
	if len(sys.argv) < 2:
		print(parser.format_help())
	else:
		(options, args) = parser.parse_args()
		main(options, args)
