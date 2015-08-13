#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2008-2010 ReScene.com
# Copyright (c) 2012-2015 pyReScene
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

from __future__ import print_function
import optparse
import sys
import os
import time
import traceback

import resample
from resample import file_type_info
from resample.main import FileType, InvalidMatchOffset
from resample import fpcalc
from rescene.utility import sep
from rescene.utility import raw_input, unicode
from rescene.utility import create_temp_file_name, replace_result

_DEBUG = bool(os.environ.get("RESCENE_DEBUG")) # leave empty for False

def can_overwrite(file_path, yes_option=False):
	if not yes_option and os.path.isfile(file_path):
		print("Warning: File %s already exists." % file_path)
		char = raw_input("Do you wish to continue? (Y/N): ").lower()
		while char not in ('y', 'n'):
			char = raw_input("Do you wish to continue? (Y/N): ").lower()
		if char == 'n':
			return False
	return True

def setup_cli_parser():
	parser = optparse.OptionParser(
	usage=("Usage: %prog  <sample file> [<full file>] [options]\n\n"
		
	"To create a ReSample file (SRS), pass in the sample file.\n"
	"This can be an AVI, MKV, MP4, WMV, MP3 or FLAC file.\n"
	"	ex: srs sample.mkv --dd\n"
	"To recreate a sample, pass in the SRS file and the full movie file\n"
	"or the first file of a RAR set containing the full movie.\n"
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
	output.add_option("-m", dest="no_stored_match_offset",
				action="store_true", default=False,
				help="Ignore stored match offset against main movie file.")
	output.add_option("-k", dest="keep_reconstruction_failure",
				action="store_true", default=False,
				help="Keep samples that reconstructed, but failed CRC check. "
				"Not applicable for music to prevent data loss.")
	
	return parser

def main(argv=None, no_exit=False):
	"""
	no_exit: used when this function is called from an other Python program
	"""
	parser = setup_cli_parser()
	
	if argv is None:
		argv = sys.argv[1:]
		
	def pexit(status, msg="", error_print=True):
		if not no_exit:
			parser.exit(status, msg)
		else:
			if status != 0:
				if error_print:
					print(msg, file=sys.stderr)
				raise ValueError(msg)
			else:
				return 0
		
	# no arguments given
	if not len(argv):
		# show application usage
		parser.print_help()
		return pexit(0)
	
	(options, args) = parser.parse_args(args=argv)
	
	if ((options.directory and options.parent_directory) or 
		(options.directory and options.srs_parent_directory) or 
		(options.parent_directory and options.srs_parent_directory)):
		pexit(1, "Make up your mind with the d's...\n")
		
	try:
		ftype_arg0 = ""
			
		# check the arguments for existence
		for ifile in args:
			msg = ""
			ifile_exists = os.path.exists(ifile)
			
			if not ifile_exists and os.name == "nt":
				if os.path.isabs(ifile):
					full = os.path.abspath(ifile)
				else:
					full = os.getcwd() + os.sep + ifile
				ifile = "\\\\?\\" + full
				ifile_exists = os.path.exists(ifile)
		
			if ifile_exists:
				ftype = file_type_info(ifile).file_type
				# check if we already have the type of the first argument
				ftype_arg0 = ftype if not ftype_arg0 else ftype_arg0
				if (ftype == FileType.Unknown and
					ftype_arg0 != FileType.STREAM):
					msg = ("Could not locate MKV, AVI, MP4, WMV, "
					       "FLAC or MP3 data "
					       "in file: %s\n" % os.path.basename(ifile))
					msg += ("File size: %s bytes\n" % 
					        sep(os.path.getsize(ifile)))
			else:
				msg = "Input file not found: %s\n" % os.path.basename(ifile)
				if _DEBUG:
					print(ifile)  # shows the complete path
				
			if msg:
				parser.print_help()
				pexit(1, msg, False)

		sample = resample.sample_class_factory(ftype_arg0)
		is_music = ftype_arg0 in (FileType.FLAC, FileType.MP3)
			
		t0 = time.clock()
		
		# for Windows long path work around
		args0 = ""
		args1 = ""
		if len(args) >= 1: 
			args0 = args[0]
		if len(args) >= 2: 
			args1 = args[1]

		# the check has been done before and succeeded (it must be Windows)
		if not os.path.exists(args0):
			if os.path.isabs(args0):
				full = os.path.abspath(args0)
			else:
				full = os.getcwd() + os.sep + args0
			args0 = "\\\\?\\" + full

		# showing info media file or creating SRS file
		if len(args) == 1 and not args0.lower().endswith(".srs"):
			# create SRS file
			sample_file = os.path.abspath(args0)
	
			if (os.path.getsize(sample_file) >= 0x80000000 and 
				not options.big_file):
				pexit(1, "Samples over 2GiB are not supported without the"
				         " -b switch. Are you sure it's a sample?\n", False)
				
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
				pexit(1, "Output directory does not exist: %s\n" %
				         out_folder, False)
				
			# almost always, unless a specific sample name was given
			if not srs_name: 
				ext = ".srs"
				if options.directory: # --d
					d = os.path.dirname(sample_file).rsplit(os.sep, 1)[1]
					srs_name = os.path.join(out_folder, d + ext)
				elif options.parent_directory: # --dd
					dd = os.path.dirname(sample_file).rsplit(os.sep, 2)[1]
					srs_name = os.path.join(out_folder, dd + ext)
				else:
					samp = os.path.basename(sample_file).rsplit(".", 1)
					srs_name = os.path.join(out_folder, samp[0] + ext)
			srsdir = os.path.dirname(srs_name)
			if not os.path.exists(srsdir):
				pexit(1, "Output directory does not exist: %s\n" % 
				         srsdir, False)
					
			# 1) Profile the sample
			sample_file_data = resample.FileData(file_name=sample_file)
			try:
				tracks, attachments = sample.profile_sample(sample_file_data)
			except resample.IncompleteSample as err:
				pexit(2, str(err), False)
	
			if not len(tracks):
				pexit(2, "No A/V data was found. "
				         "The sample is likely corrupted.\n", False)
			
			# show sample information only, no SRS creation
			if options.info_only: # -i
				return pexit(0)
				
			# no need to try finding these matches
			sample_is_rar = (tracks[1].signature_bytes.startswith(b"Rar!")
				and sample_file.endswith(".vob"))
			if sample_is_rar:
				print("The vobsample is a RAR volume.")

			# 2) check sample against main movie file
			# main AVI, MKV,... file to check against
			if options.check and not sample_is_rar: 
				print("Checking that sample exists "
				      "in the specified full file...")
				main_file_info = file_type_info(options.check)
				if (main_file_info.file_type != sample.file_type and
					sample.file_type != FileType.STREAM):
					msg = "Sample and -c file not the same format.\n"
					pexit(1, msg, False)
				sample.archived_file_name = main_file_info.archived_file
				tracks = sample.find_sample_streams(tracks, options.check)
				
				for track in list(tracks.values()):
					if ((track.signature_bytes and track.match_offset == 0 and
							ftype_arg0 != FileType.MP3 and
							ftype_arg0 != FileType.STREAM) or 
						(track.match_offset == -1 and 
							ftype_arg0 in (FileType.MP3, FileType.STREAM))):
						# 0 is a legal match offset for MP3 and STREAM
						msg = ("\nUnable to locate track signature for"
						       " track %s. Aborting.\n" % track.track_number)
						pexit(3, msg, False)
					elif not track.signature_bytes:
						# main movie file has more tracks? or empty track?
						tracks.pop(track.track_number)
				print("Check Complete. All tracks located.")
			
			# ask the user for permission to replace an existing SRS file
			if not can_overwrite(srs_name, options.always_yes):
				return pexit(0, "\nOperation aborted.\n", False)
			
			srs_name_tmp = create_temp_file_name(srs_name)
				
			sample.create_srs(tracks, sample_file_data, sample_file, 
			                  srs_name_tmp, options.big_file)
			
			replace_result(srs_name_tmp, srs_name)
			
			if no_exit:
				# just print the file name from pyReScene Auto
				# (looks nicer for music)
				success_name = os.path.basename(srs_name) + "\n"
			else:
				success_name = srs_name
			print("Successfully created SRS file: %s" % success_name)
		
		# showing SRS info
		elif (len(args) == 1 and args0.lower().endswith(".srs")
		    	and options.srs_info): # -l
			srs_data, tracks = sample.load_srs(args0)
			
			print("SRS Type   : {0}".format(ftype_arg0))
			print("SRS App    : {0}".format(srs_data.appname))
			msg = unicode("Sample Name: {0}")
			print(msg.format(srs_data.name))
			print("Sample Size: {0}".format(sep(srs_data.size)))
			print("Sample CRC : {0:08X}".format(srs_data.crc32))
			for track in tracks.values():
				offset = ""
				codec = ""
				if track.match_offset:
					offset = " @ {0}".format(sep(track.match_offset))
				if track.codec:
					codec = " [{0}]".format(track.codec)
				print("Track {0}: {1} bytes{2}{3}".format(
					track.track_number, sep(track.data_length), offset, codec))
				if is_music:
					try:
						print("Duration: {0} seconds".format(track.duration))
						print("AcoustID fingerprint: {0}".format( 
						      track.fingerprint.decode("ascii")))
					except AttributeError:
						pass # SRS without fingerprint information
			
		# reconstructing sample
		elif len(args) == 2 and args0.lower().endswith(".srs"):
			# reconstruct sample
			srs = args0
			movie = args1
			# should be the same as srs type
			main_file_info = file_type_info(movie)
			movie_type = main_file_info.file_type
			if movie_type == FileType.Unknown:
				movie_type = FileType.STREAM
			movi = resample.sample_class_factory(movie_type)
			movi.archived_file_name = main_file_info.archived_file
			
			out_folder = "." # current directory
			if options.output_dir:
				out_folder = options.output_dir
				
			if not os.path.exists(out_folder):
				try:
					os.makedirs(out_folder)
				except:
					print("Creating output folder failed.")
					
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
			# always do this search for music files
			if (is_music or not skip_location or 
			    options.no_stored_match_offset):
				tracks = movi.find_sample_streams(tracks, movie)
				
				t1 = time.clock()
				total = t1-t0
				print("Track Location Complete...    "
				      "Elapsed Time: {0:.2f}s".format(total))
				
				for track in tracks.values():
					if ((track.signature_bytes and track.match_offset == 0 and
							ftype_arg0 != FileType.MP3 and
							ftype_arg0 != FileType.STREAM) or 
						(track.match_offset == -1 and 
							ftype_arg0 in (FileType.MP3, FileType.STREAM))):
						# 0 is a legal match offset for MP3 and STREAM
						msg = ("\nUnable to locate track signature for track"
						       " %s. Aborting.\n" % track.track_number)
						pexit(3, msg, False)
						
			# 3) Extract those sample streams to memory
			tracks, attachments = movi.extract_sample_streams(tracks, movie)
			t1 = time.clock()
			total = t1-t0
			print("Track Extraction Complete...  "
			      "Elapsed Time: {0:.2f}s".format(total))
			
			# 4) Check for failure
			for track in tracks.values():
				if track.signature_bytes and (track.track_file == None or 
						track.track_file.tell() < track.data_length):
					if _DEBUG:
						print("Found: {0}".format(track.track_file.tell()))
						print("Expected: {0}".format(track.data_length))
					msg = ("\nUnable to extract correct amount of data for "
					       "track %s. Aborting.\n" % track.track_number)
					pexit(4, msg, False)
					
			# 5) Ask user for overwrite permission
			result_file = os.path.join(out_folder, srs_data.name)
			if not can_overwrite(result_file, options.always_yes):
				pexit(1, "\nOperation aborted.\n", False)
				
			# 6) Recreate the sample
			out_file = create_temp_file_name(result_file)
			sfile = sample.rebuild_sample(srs_data, tracks, attachments, 
										  srs, out_file)
			
			t1 = time.clock()
			total = t1-t0
			print("Rebuild Complete...           "
			      "Elapsed Time: {0:.2f}s".format(total))
			
			# 7) Close and delete the temporary files
			for track in tracks.values():
				if track.track_file:
					track.track_file.close()
			for attachment in attachments.values():
				attachment.attachment_file.close()
				
			print("\nFile Details:   Size           CRC")
			print("                -------------  --------")
			print("Expected    :   {0:>13}  {1:08X}".format(
				sep(srs_data.size), srs_data.crc32))
			print("Actual      :   {0:>13}  {1:08X}\n".format(
				sep(sfile.size), sfile.crc32))
			
			if sfile.crc32 == srs_data.crc32:
				replace_result(out_file, result_file)
				print("\nSuccessfully rebuilt sample: %s" % srs_data.name)
			else:
				#TODO: try again with the correct interleaving for LOL samples
				if not is_music:
					print("This is a known issue for LOL xvid releases.")
					# also for some DOCUMENT releases
					if not options.keep_reconstruction_failure:
						print("Use -k to keep the result for investigation.")
				if options.keep_reconstruction_failure:
					if not is_music:
						replace_result(out_file, result_file)
					elif is_music:
						m = os.path.normpath(os.path.realpath(movie))
						r = os.path.normpath(os.path.realpath(result_file))
						if m == r:
							# always keep original track on retag failure
							print("No replacing of source file for music.")
							print("The .tmp file will be kept:")
							print(os.path.basename(out_file))
						else:
							# only keep broken file if source isn't overwritten
							replace_result(out_file, result_file)
				else:
					# delete reconstruction failure
					if not is_music:
						replace_result(out_file, result_file)
						os.unlink(result_file)
					elif is_music:
						m = os.path.normpath(os.path.realpath(movie))
						r = os.path.normpath(os.path.realpath(result_file))
						if m == r:
							# always keep original track on retag failure!
							print("Music track not deleted!")
						else:
							replace_result(out_file, result_file)
							os.unlink(result_file)
					
				msg = "\nRebuild failed for sample: %s\n" % srs_data.name
				pexit(5, msg, False)
				
		else:
			parser.print_help()
			pexit(1)
		
		return pexit(0)

	except InvalidMatchOffset:
		pexit(6, "The stored main video location is not valid. "
		         "Try again on a different disk or use -m.")
	except (ValueError, AssertionError) as err:
		if _DEBUG:
			traceback.print_exc()
		# strip leading white spaces for each line
		fault = "\n".join(map(str.lstrip, str(err).split("\n")))
		fault = fault.strip("\n").rstrip(".")  # prevent double dots
		if fault == "":
			fault = "AssertionError"  # must never occur!
		if fault.endswith("Aborting"):
			pexit(2, "Corruption detected: %s\n" % fault)
		else:
			pexit(2, "Corruption detected: %s. Aborting.\n" % fault)
	except fpcalc.ExecutableNotFound as err:
		pexit(3, str(err))
	except AttributeError as err:
		if str(err).startswith("Compressed RARs"):
			# AttributeError: Compressed RARs are not supported
			pexit(4, "Cannot verify sample against compressed RARs.")
		elif (str(err) == 
			"You must start with the first volume from a RAR set"):
			pexit(5, str(err))
		else:
			traceback.print_exc()
			pexit(99, "Unexpected Error:\n%s\n" % err)
	except OSError as err:
		# output file already locked by another process
		print("The output file has been locked by another application?")
		pexit(7, str(err))
	except Exception as err:
		traceback.print_exc()
		pexit(99, "Unexpected Error:\n%s\n" % err)

if __name__ == "__main__":
	if "--profile" in sys.argv:
		print("Profiling...")
		sys.argv.remove("--profile")
		import cProfile
		import pstats
		# view with RunSnakeRun
		profile_filename = 'bin.resample_profile.txt'
		cProfile.run('main()', profile_filename)
		statsfile = open("profile_stats.txt", "wb")
		p = pstats.Stats(profile_filename, stream=statsfile)
		stats = p.strip_dirs().sort_stats('cumulative')
		stats.print_stats()
		statsfile.close()
		sys.exit(0)
	main()