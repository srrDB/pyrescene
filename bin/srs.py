#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2008-2010 ReScene.com
# Copyright (c) 2012 pyReScene
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

import optparse
import sys
import os
import time
import traceback

# for running the script directly from command line
from os.path import join, dirname, realpath
sys.path.append(join(dirname(realpath(sys.argv[0])), '..'))

import resample

from rescene.utility import sep 

def can_overwrite(file_path):
	if not options.always_yes and os.path.isfile(file_path):
		print("Warning: File %s already exists." % file_path)
		char = raw_input("Do you wish to continue? (Y/N): ").lower()
		while char not in ('y', 'n'):
			char = raw_input("Do you wish to continue? (Y/N): ").lower()
		if char == 'n':
			return False
	return True

def sample_class_factory(file_type):
	"""Choose the right class based on the sample's file type."""
	if file_type == resample.FileType.AVI:
		return resample.AviReSample()
	elif file_type == resample.FileType.MKV:
		return resample.MkvReSample()
	elif file_type == resample.FileType.MP4:
		return resample.Mp4ReSample()
		
def main(options, args):
	ftype_arg0 = ""
		
	# check the arguments for existence
	for ifile in args:
		msg = ""
		if os.path.exists(ifile):
			ftype = resample.get_file_type(ifile)
			# check if we already have the type of the first argument or not
			ftype_arg0 = ftype if not ftype_arg0 else ftype_arg0
			if ftype == resample.FileType.Unknown:
				msg = ("Could not locate MKV, AVI or MP4 data "
				       "in file: %s\n" % ifile)
		else:
			msg = "Input file not found: %s\n" % ifile
			
		if msg:
			parser.print_help()
			parser.exit(1, msg)
			
	sample = sample_class_factory(ftype_arg0)

	t0 = time.clock()
	
	# showing info media file or creating SRS file
	if len(args) == 1 and args[0][-4:].lower() != ".srs":
		# create SRS file
		sample_file = os.path.abspath(args[0])

		if os.path.getsize(sample_file) >= 0x80000000 and not options.big_file:
			parser.exit(1, "Samples over 2GB are not supported without the "
			               "-b switch.  Are you sure it's a sample?")
			
		out_folder = os.path.abspath(os.curdir)
		srs_name = None
		
		if options.output_dir: # -o
			if options.output_dir[-4:].lower() == ".srs":
				srs_name = options.output_dir
			else:
				out_folder = options.output_dir
		elif options.srs_parent_directory: # --ddd
			# parent directory of the Sample dir
			out_folder = os.path.dirname(sample_file).rsplit(os.sep, 1)[0]
		if not os.path.exists(out_folder):
			parser.exit(1, "Output directory does not exist: %s" % out_folder)
			
		# almost always, unless a specific sample name was given
		if not srs_name: 
			if options.directory: # --d
				d = os.path.dirname(sample_file).rsplit(os.sep, 1)[1]
				srs_name = os.path.join(out_folder, d + ".srs")
			elif options.parent_directory: # --dd
				dd = os.path.dirname(sample_file).rsplit(os.sep, 2)[1]
				srs_name = os.path.join(out_folder, dd + ".srs")
			else:
				samp = os.path.basename(sample_file)[:-4]
				srs_name = os.path.join(out_folder, samp + ".srs")
		srsdir = os.path.dirname(srs_name)
		if not os.path.exists(srsdir):
			parser.exit(1, "Output directory does not exist: %s" % srsdir)
				
		# 1) Profile the sample
		sample_file_data = resample.FileData(file_name=sample_file)
		try:
			tracks, attachments = sample.profile_sample(sample_file_data)
		except resample.IncompleteSample:
			parser.exit(2, str(sys.exc_info()[1]))

		if not len(tracks):
			parser.exit(2, "No A/V data was found. "
			               "The sample is likely corrupted.")
		
		# show sample information only, no SRS creation
		if options.info_only: # -i
			parser.exit(0)
			
		# 2) check sample against main movie file
		if options.check: # main AVI file to check against
			print("Checking that sample exists in the specified full file...")
			if resample.get_file_type(options.check) != sample.file_type:
				parser.exit(1, "Sample and -c file not the same format.")
			tracks = sample.find_sample_streams(tracks, options.check)
			
			for track in tracks.values():
				if track.signature_bytes and track.match_offset == 0:
					msg = ("\nUnable to locate track signature for track %s. "
							"Aborting." % track.track_number)
					parser.exit(3, msg)
				elif not track.signature_bytes:
					tracks.remove(track)
			print("Check Complete. All tracks located.")
		
		# ask the user for permission to replace an existing SRS file
		if not can_overwrite(srs_name):
			parser.exit(0, "Operation aborted.")
			
		sample.create_srs(tracks, sample_file_data, sample_file, 
		                  srs_name, options.big_file)
		print("Successfully created SRS file: %s" % srs_name)
	
	# showing SRS info
	elif len(args) == 1 and args[0][-4:].lower() == ".srs" and options.srs_info:
		srs_data = sample.srs_info(args[0])
		
		print("SRS Type   : {0}".format(ftype_arg0))
		print("SRS App    : {0}".format(srs_data.appname))
		print("Sample Name: {0}".format(srs_data.name))
		print("Sample Size: {0}".format(sep(srs_data.size)))
		print("Sample CRC : {0:08X}".format(srs_data.crc32))
	
	# reconstructing sample
	elif len(args) == 2 and args[0][-4:].lower() == ".srs":
		# reconstruct sample
		srs = args[0]
		movie = args[1]
#		srs_type = get_file_type(srs)
		# should be the same as srs type
		movie_type = resample.get_file_type(movie)
#		srs_data = FileData()
		movi = sample_class_factory(movie_type)
		
		out_folder = "."
		if options.output_dir:
			out_folder = options.output_dir
			
		if not os.path.exists(out_folder):
			try:
				os.makedirs(out_folder)
			except:
				pass
				print("Creating folder failed.")
				
		# 1) Read in the SRS file
		srs_data, tracks = sample.load_srs(srs)
		
		t1 = time.clock()
		total = t1-t0
		print("SRS Load Complete...          "
		      "Elapsed Time: {0:.2f}s".format(total))
		
		skip_location = True
		for track in tracks.values():
			if track.match_offset == 0:
				skip_location = False
				break
			
		# 2) Find the sample streams in the main movie file
		if not skip_location:
			tracks = movi.find_sample_streams(tracks, movie)
			
			t1 = time.clock()
			total = t1-t0
			print("Track Location Complete...    "
			      "Elapsed Time: {0:.2f}s".format(total))
			
			for track in tracks.values():
				if track.signature_bytes != "" and track.match_offset == 0:
					msg = ("\nUnable to locate track signature for track %s. "
							"Aborting." % track.track_number)
					parser.exit(3, msg)
					
		# 3) Extract those sample streams to memory
		tracks, attachments = movi.extract_sample_streams(tracks, movie)
		t1 = time.clock()
		total = t1-t0
		print("Track Extraction Complete...  "
		      "Elapsed Time: {0:.2f}s".format(total))
		
		# 4) Check for failure
		for track in tracks.values():
			if track.signature_bytes != "" and (track.track_file == None or 
					track.track_file.tell() < track.data_length):
				msg = ("\nUnable to extract correct amount of data for track "
					"%s. Aborting." % track.track_number)
				parser.exit(4, msg)
				
		# 5) Ask user for overwrite permission
		if not can_overwrite(os.path.join(out_folder, srs_data.name)):
			parser.exit(0, "\nOperation aborted.")
			
		# 6) Recreate the sample
		sfile = sample.rebuild_sample(srs_data, tracks, attachments, 
									  srs, out_folder)
		t1 = time.clock()
		total = t1-t0
		print("Rebuild Complete...           "
		      "Elapsed Time: {0:.2f}s".format(total))
		
		# 7) Close and delete the temporary files
		for track in tracks.values():
			track.track_file.close()
		for attachment in attachments.values():
			attachment.attachment_file.close()
			
		print("\nFile Details:   Size           CRC")
		print("                -------------  --------")
		print("Expected    :   {0:>13}  {1:08X}".format(sep(srs_data.size),
		                                                srs_data.crc32))
		print("Actual      :   {0:>13}  {1:08X}\n".format(sep(sfile.size), 
		                                                  sfile.crc32))
		
		if sfile.crc32 == srs_data.crc32:
			print("\nSuccessfully rebuilt sample: {0}".format(srs_data.name))
		else:
			msg = ("\nRebuild failed for sample: {0}".format(srs_data.name))
			parser.exit(5, msg)
			
	else:
		parser.print_help()
		parser.exit(1)
	
	parser.exit(0)
	

if __name__ == "__main__":
	parser = optparse.OptionParser(
	usage=("Usage: %prog  <sample file> [<full file>] [options]\n\n"
		
	"To create a ReSample file (SRS), pass in the sample MKV or AVI file.\n"
	"	ex: srs sample.mkv -dd\n"
	"To recreate a sample, pass in the SRS file and the full MKV or AVI\n"
	"or the first file of a RAR set containing the MKV or AVI.\n"
	"	ex: srs sample.srs full.mkv\n"
	"	or: srs sample.srs full.rar\n"), 
	version="%prog " + resample.__version__) # --help, --version
	
	creation = optparse.OptionGroup(parser, "Creation options")
	display = optparse.OptionGroup(parser, "Display options")
	output = optparse.OptionGroup(parser, "Output options")
	parser.add_option_group(creation)
	parser.add_option_group(display)
	parser.add_option_group(output)
	
	parser.add_option("-y", "--always-yes", dest="always_yes", default=False,
					  action="store_true",
					  help="assume Y(es) for all prompts")
	
	creation.add_option("-b", "--big-file", 
				action="store_true", dest="big_file", default=False,
				help="Big file. Enables support for 'samples' over 2GB.")
	creation.add_option("-c", "--check",
				dest="check", metavar="FILE",
				help="Check sample against given full MKV or AVI file to make "
				"sure all tracks can be located before saving the .srs file.")

	display.add_option("-i", "--info", action="store_true", dest="info_only",
			   help="Display sample info only. Does not create .srs file.")
	display.add_option("-l", "--srs-info", 
			   action="store_true", dest="srs_info",
			   help="List SRS info only (use only with .srs input file).")

	output.add_option("--d", 
				action="store_true", dest="directory", default=False,
				help="Use sample directory name "
				"as basis for generated .srs file name.")
	output.add_option("--dd", 
				action="store_true", dest="parent_directory", default=False,
				help="Use parent directory name "
				"as basis for generated .srs file name.")
	output.add_option("--ddd", dest="srs_parent_directory", 
				action="store_true", default=False,
				help="Same as above, but puts the .srs file "
				"in the parent directory.")
	output.add_option("-o", "--output",
				dest="output_dir", metavar="DIRECTORY",
				help="Specify output file or directory path for .srs file. "
				"If path is a directory, "
				"the --d and --dd flags will work as normal.")

	# no arguments given
	if len(sys.argv) < 2:
		# show application usage
		print(parser.print_help())
	else:	   
		(options, args) = parser.parse_args()
		
		if ((options.directory and options.parent_directory) or 
			(options.directory and options.srs_parent_directory) or 
			(options.parent_directory and options.srs_parent_directory)):
			parser.exit(1, "Make up your mind with the d's...")
			
		try:
			main(options, args)
		except ValueError:
			parser.exit(2, "Corruption detected: %s. Aborting." % 
					sys.exc_info()[1])
		except Exception:
			traceback.print_exc()
			
			parser.exit(99, "Unexpected Error:\n%s" % sys.exc_info()[1])