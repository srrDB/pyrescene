#!/usr/bin/env python
# encoding: utf-8

# Copyright (c) 2014-2015 pyReScene
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.

"""
This tool fixes the tags of music files.

To do:
	- error handling
	  (Ctr+C when source == dest => broken 0 byte track)
	- testing
"""

from optparse import OptionParser
import sys
import os

try:
	import _preamble
except ImportError:
	pass

import rescene
from resample.srs import main as srsmain
from resample.main import get_file_type, sample_class_factory, FileType

class NoTaggingAvailable(Exception):
	pass

def fix_tracks(srr_file, input_dir, output_dir, always_yes=False):
	if not srr_file.endswith(".srr"):
		raise AttributeError("The first parameter must be an SRR file.")
	if not os.path.isdir(input_dir):
		raise AttributeError("The input location must be a directory.")
	if not os.path.isdir(output_dir):
		try:
			os.makedirs(output_dir)
		except:
			pass
		if not os.path.isdir(output_dir):
			raise AttributeError("Could not create output location.")
	
	stored_files = rescene.info(srr_file)['stored_files']
	
	# extract non SRS files
	successes = 0
	failures = 0
	skips = 0
	srs_files = []
	for sfile in stored_files.keys():
		if sfile.endswith(".srs"):
			srs_files.append(sfile)
		else:
			print("Extracting %s" % sfile)
			rescene.extract_files(srr_file, output_dir, True, sfile)
		
	# fix music files that can be found
	for srs in srs_files:
		print("Using %s" % srs)
		(out, ok) = rescene.extract_files(srr_file, output_dir, True, srs)[0]
		if not ok:
			# file extraction failed or existing .srs not overwritten
			print("Attempt to fix track aborted.")
			continue
		try:
			success = fix_tagging(out, output_dir, input_dir, always_yes)
			if success:
				successes += 1
			else:
				# .srs is not a music file
				skips += 1
		except ValueError:
			# pexit() srs.py only throws ValueError
			failures += 1
		except Exception as e:
			print("Unexpected error!")
			print(str(e))
			failures += 1
		finally:
			os.remove(out)
		
	print("\n\n%d/%d files succeeded. %d failure%s. %s" % (
		successes, failures + successes, failures, 
		"" if failures == 1 else "s",
		"" if not skips else "%s skip%s." % 
	    	(skips, "" if skips == 1 else "s")))
		
def fix_tagging(srs, output_dir, input_dir, always_yes):
	"""Fixes the meta data tags of a music track.
	srs: srs file location
	output_dir: root dir of the fixed release
	input_dir: location to find the track to be fixed
	always_yes: when to always confirm replacements
	"""
	try:
		srs_info = get_srs_info(srs)
	except NoTaggingAvailable as not_music:
		print("")
		print(str(not_music))
		os.remove(srs)
		return False

	original_name = srs_info.sample_name
	print("Fixing %s" % original_name)
	
	musicf = join_fix_case(input_dir, original_name)
	out_subfolder = os.path.dirname(os.path.relpath(srs, output_dir))
	if not os.path.isfile(musicf):
		srr_path = out_subfolder.split("/")
		srr_path.append(original_name)
		musicf = join_fix_case(input_dir, *srr_path)
		if not os.path.isfile(musicf):
			print("Track not found")
			raise ValueError("not found")
	print("From %s" % musicf)
	
	out_location = os.path.join(output_dir, out_subfolder)
	srs_parameters = [srs, musicf, "-o", out_location]
	if always_yes:
		srs_parameters.append("-y")

	# can throw ValueError on pexit()
	srsmain(srs_parameters, no_exit=True) 

	return True

def get_srs_info(srs_file):
	file_type = get_file_type(srs_file)
	if file_type not in (FileType.MP3, FileType.FLAC):
		message = "Not a FLAC or MP3 music file: %s." % srs_file
		raise NoTaggingAvailable(message)
	sample = sample_class_factory(file_type)
	srs_data, _tracks = sample.load_srs(srs_file)
	return srs_data

def join_fix_case(good_base, *parts):
	"""Returns a unix-type case-sensitive path of the joined parts.
	An empty string is returned on failure: file not found."""
	# check if input is already correct
	joined_input = os.path.join(good_base, *parts)
	if os.path.exists(joined_input):
		return joined_input 

	corrected_path = good_base 
	for p in parts:
		if not os.path.exists(os.path.join(corrected_path, p)):
			listing = os.listdir(corrected_path)
			cilisting = [l.lower() for l in listing]
			cip = p.lower()
			if cip in cilisting:
				# get real folder name
				l = listing[cilisting.index(cip)]
				corrected_path = os.path.join(corrected_path, l)
			else:
				# file or path does not exist
				return ""
		else:
			corrected_path = os.path.join(corrected_path, p)

	return corrected_path

def main(argv=None):
	parser = OptionParser(
	usage=("Usage: %prog file.srr -i input_dir -o output_dir\n"
	"This tool fixes the tags of music files.\n"
	"Example usage: %prog rls.srr --output D:\\rls\\"), 
	version="%prog " + rescene.__version__) # --help, --version
	
	parser.add_option("-i", "--input", dest="input_dir", metavar="DIR",
					default=".", help="Specifies input directory. "
					"The default input path is the current directory.")
	parser.add_option("-o", "--output", dest="output_dir", metavar="DIR",
					default=".", help="Specifies output directory. "
					"The default output path is the current directory.")
	parser.add_option("-y", "--always-yes", dest="always_yes", default=False,
					action="store_true", help="assume Yes for all prompts")
	parser.add_option("-n", "--always-no", dest="always_no", default=False,
					action="store_true", help="never overwrite existing files "
					"with the extracted stored files from the SRR")
	
	if argv is None:
		argv = sys.argv[1:]
		
	# no arguments given
	if not len(argv):
		# show application usage
		parser.print_help()
		return 0
	
	(options, args) = parser.parse_args(args=argv)
	
	# no SRR file provided
	if not len(args):
		parser.print_help()
		return 1
	
	def can_overwrite(file_path):
		retvalue = True 
		if (not options.always_yes and 
		    not options.always_no and os.path.isfile(file_path)):
			print("Warning: File %s already exists." % file_path)
			char = raw_input("Do you wish to continue? (Y/N): ").lower()
			while char not in ('y', 'n'):
				char = raw_input("Do you wish to continue? (Y/N): ").lower()
			if char == 'n':
				retvalue = False
		elif options.always_no and os.path.isfile(file_path):
			print("(not replaced)")
			retvalue = False
		return retvalue 
	
	rescene.main.can_overwrite = can_overwrite

	if fix_tracks(args[0], options.input_dir, options.output_dir, 
	              options.always_yes):
		return 0
	else:
		return 1

if __name__ == "__main__":
	sys.exit(main())
	