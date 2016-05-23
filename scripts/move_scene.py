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
	rellist = args[0]
	tododirs = args[1:]

	if os.path.isfile(rellist):
		with open(rellist, 'r') as rel:
			groups = get_groups(rel)
		print("Got the groups: %d groups." % len(groups))
	else:
		print("WTF are you supplying me?")

	for tododir in tododirs:
		if os.path.isdir(tododir):
			print("Processing directory '%s'." % tododir)
			for elem in os.listdir(tododir):
				if " " in elem:
					continue
				if elem.lower() == elem:
					continue
				gn = get_groupname(elem)
				if elem == gn:
					continue
				if gn.lower() == gn:
					continue
				if gn in groups:
					print(elem)
					if options.output_dir:
						dest = os.path.join(options.output_dir, elem)
					else:
						dest = os.path.join(tododir, "scene", elem)
					os.renames(os.path.join(tododir, elem), dest)

def get_groupname(release):
	release = release.replace(".nzb", "").replace(".srr", "")
	return (release.split('-'))[-1]

def get_groups(rellist):
	cleaned = map(get_groupname, rellist)
	return [key.replace("\n", "").replace("\r", "")
	        for (key, _) in itertools.groupby(sorted(cleaned))]

# 	grouped = {}
#
# 	for (key, elemiter) in itertools.groupby(sorted(cleaned)):
# 		grouped[key] = sum(1 for _ in elemiter)
#
# 	# print the results
# 	for key in sorted(grouped, key=grouped.__getitem__, reverse=reverse):
# 		print("%3d;%s" % (grouped[key], key))

if __name__ == '__main__':
	parser = optparse.OptionParser(
		usage="Usage: %prog [rellist scene releases] [dir]'\n"
		"This tool will move the releases from all the groups that are in "
		"the release list.\n",
		version="%prog 0.1 (2012-05-13)")  # --help, --version

	parser.add_option("-o", help="output DIRECTORY\n"
				"The default directory is 'scene'.",
				dest="output_dir", metavar="DIRECTORY", default=None)

	# no arguments given
	if len(sys.argv) < 2:
		print(parser.format_help())
	else:
		(options, args) = parser.parse_args()
		main(options, args)
