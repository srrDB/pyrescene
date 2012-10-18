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

"""Only leave everything related to the samples in the NZB file.
This are the .avi, .mkv, .mp4, .vob or .m2ts files and sometimes par2 files.
No new file will be created if there is no sample data.

python nzb_sample_extract.py file1.nzb dir/file2.nzb
will create file1.nzb and file2.nzb with less data in ./samples in the
directory of file1.nzb and dir/file2.nzb respectively.

python nzb_sample_extract.py /home/user/nzbdir -o /home/user/samples
sets one output directory.

Change log:
-----------

0.1 (2011-12-24)
 - Initial version
0.2 (2012-01-18)
 - Made the regex more strict
 - A bit more documentation
0.3 (2012-01-23)
 - Added option for VOB samples
 - Refactoring bug fixed
 - Made the regex more strict
 - Option to limit the maximum size
0.4 (2012-09-28)
 - more extensions
 - other cli options (for each extension one)
 
"""

import os
import sys
import optparse
import re
import unittest

# for running the script directly from command line
sys.path.append(os.path.join(os.path.dirname(
				os.path.realpath(sys.argv[0])), '..', 'rescene'))

try:
	import nzb_utils
except ImportError:
	print("Can't import the nzb_utils module.")
	
def is_sample(file_name):
	BEGIN = ".*("
	END = ")((\.vol\d+\+\d+)?.par2)?$"
	exts = ""
	
	if options.avisample:
		exts += "|\.avi" 
	if options.mkvsample:
		exts += "|\.mkv" 
	if options.mp4sample:
		exts += "|\.mp4" 
	if options.wmvsample:
		exts += "|\.wmv" 
	if options.vobsample:
		exts += "|\.vob" 
	if options.m2tssample:
		exts += "|\.m2ts" 
	
	if exts == "": # those that are currently SRSable
		print("No extentions given. Testing for AVI and MKV.")
		exts = "\.avi|\.mkv"
	else: # strip leading |
		exts = exts[1:]
	
	match = BEGIN + exts + END
	return re.match(match, file_name.lower())
	
def extract_sample(nzb_file, output_dir):
	sample_nzb = nzb_utils.empty_nzb_document()
	sample_found = False
	
	for nfile in nzb_utils.read_nzb(nzb_file):
		file_name = nzb_utils.parse_name(nfile.subject)
	
		if is_sample(file_name):
			if int(options.max_size) > 0: # we need to check the size
				size = sum([seg.bytes for seg in nfile.segments])
				if int(options.max_size) < size:
					continue # not a sample, skip it
			sample_found = True
			nzb_utils.add_file(sample_nzb, nfile)

	if sample_found:
		snzb_file = os.path.join(output_dir, os.path.basename(nzb_file))
		try:
			os.makedirs(os.path.dirname(snzb_file))
		except:
			pass
		with open(snzb_file, "w") as sample:
			sample.write(nzb_utils.get_xml(sample_nzb))
	
def main(options, args):
	def check_file(pfile):
		if pfile[-4:].lower() == ".nzb":
			if options.output_dir:
				output_dir = options.output_dir
			else:
				output_dir = os.path.join(os.path.dirname(pfile), "samples")
			extract_sample(pfile, output_dir)
	
	for element in args:
		if os.path.isdir(element):
			for lfile in os.listdir(element):
				check_file(lfile)
		elif os.path.isfile(element):
			check_file(element)
		else:
			print("Only existing files or directories are accepted.")
			
class TestRegex(unittest.TestCase):
	""" Code to test the correctness of the sample detection. """
	def test_avi_in_name(self):
		avi = ("[1080]-[FULL]-[#a.b.foreign@EFNet]-[ UCL.2010-2011.Play-Offs."
			"Salzburg.vs.Tel.Aviv.DUTCH.WS.PDTV.XviD-iFH ]-[03/97] \"ucl."
			"2010.2011.playoffs.salzburg.tel.aviv-ifh.r00\" yEnc (1/61)")
		
		file_name = nzb_utils.parse_name(avi)
		self.assertEqual(file_name, 
						"ucl.2010.2011.playoffs.salzburg.tel.aviv-ifh.r00")
		self.assertFalse(is_sample(file_name), "detected as sample")
		
		
if __name__ == '__main__':
	parser = optparse.OptionParser(
		usage="Usage: %prog [directories] [NZBs] [options]'\n"
		"This tool will create new NZB files with only the sample "
		"related data in the 'samples' subdir.\n",
		version="%prog 0.4 (2012-09-28)") # --help, --version

	parser.add_option("-o", dest="output_dir", metavar="DIRECTORY",
					help="moves the new NZB files to DIRECTORY and a "
					"'samples' subfolder will be used if not specified")
	parser.add_option("-a", "--avi", dest="avisample",
					help="create NZBs for .avi", action="store_true")
	parser.add_option("-m", "--mkv", dest="mkvsample",
					help="create NZBs for .mkv", action="store_true")
	parser.add_option("-4", "--mp4", dest="mp4sample",
					help="create NZBs for .mp4", action="store_true")
	parser.add_option("-w", "--wmv", dest="wmvsample",
					help="create NZBs for: .wmv", action="store_true")
	parser.add_option("-v", "--vob", dest="vobsample",
					help="create NZBs for vobsamples", action="store_true")
	parser.add_option("-2", dest="m2tssample",
					help="create NZBs for blu-ray samples: .m2ts", 
					action="store_true")
	parser.add_option("-s", dest="max_size", metavar="SIZE", default=-1,
					help="the sample can be max SIZE bytes large")
	
	# no arguments given
	if len(sys.argv) < 2:
		print(parser.format_help())
	else:
		(options, args) = parser.parse_args()
		main(options, args)
