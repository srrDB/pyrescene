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

import os
import sys
import optparse
import shutil

import nzb_utils
import nzb_split

def main(options, args):
	input_dir = os.path.abspath(args[0])
	output_dir = os.path.join(input_dir, "processed")

	# create output folders
	try:
		os.mkdir(output_dir)
		os.mkdir(os.path.join(output_dir, "music"))
		os.mkdir(os.path.join(output_dir, "other"))
	except:
		pass
	
	for nzb_file in os.listdir(input_dir):
		f = os.path.join(input_dir, nzb_file)
		if nzb_file.endswith(".nzb"):
			try:
				(new_name, has_music) = process_nzb(f)
				if has_music:
					odir = os.path.join(output_dir, "music")
				else:
					odir = os.path.join(output_dir, "other")
				shutil.move(f, odir)
				os.rename(os.path.join(odir, nzb_file),
						os.path.join(odir, new_name + ".nzb"))
			except Exception, e:
				print(e)
		else:
			pass # leave it
	
def process_nzb(nzb_file):
	new_name = ""
	has_music = False
	files_in_nzb = nzb_utils.read_nzb(nzb_file)
	
	for nfile in files_in_nzb:
		file_name = nzb_utils.parse_name(nfile.subject)
		if not new_name:
			ln = nzb_split.longest_name(nfile.subject, file_name)
			new_name = ln
		if file_name.endswith(".mp3") or file_name.endswith(".flac"):
			has_music = True
			break
	
	return (new_name, has_music)

if __name__ == '__main__':
	parser = optparse.OptionParser(
		usage="Usage: %prog [input dir]'\n"
		"This tool will rename badly named NZB files to the subject.\n"
		"It uses the longest substring as the new name.\n"
		"After this, the move_scene.py script can be used.\n",
		version="%prog 0.1 (2013-11-26)") # --help, --version

	# no arguments given
	if len(sys.argv) < 2:
		print(parser.format_help())
	else:
		(options, args) = parser.parse_args()
		main(options, args)
