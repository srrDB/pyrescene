#!/usr/bin/env python
# -*- coding: latin-1 -*-

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA 02110-1301, USA.

import optparse
import sys
import os
import itertools

def main(options, args):
	for element in args:
		element = os.path.abspath(element)
		if os.path.isdir(element):
			start_count(os.listdir(element), options.reverse)
		elif os.path.isfile(element):
			with open(element, 'r') as rellist:
				start_count(rellist, options.reverse)
		else:
			print("WTF are you supplying me?")
			
def start_count(rellist, reverse):
	cleaned = map(lambda x:  (x.split('-'))[-1], rellist)
	grouped = {}

	for (key, elemiter) in itertools.groupby(sorted(cleaned)):
		grouped[key] = sum(1 for _ in elemiter)
	
	# print the results
	for key in sorted(grouped, key=grouped.__getitem__, reverse=reverse):
		print("%3d;%s" % (grouped[key], key))
	
if __name__ == '__main__':
	parser = optparse.OptionParser(
		usage="Usage: %prog [files]'\n"
		"This tool will group groups and list a count based on directories"
		"or a list of releasenames in a text file.\n",
		version="%prog 0.1 (2012-03-22)") # --help, --version

	parser.add_option("-r", "--reverse", help="reversed output", 
	                  action="store_true", dest="reverse", default=False)
	
	# no arguments given
	if len(sys.argv) < 2:
		print(parser.format_help())
	else:
		(options, args) = parser.parse_args()
		main(options, args)
	