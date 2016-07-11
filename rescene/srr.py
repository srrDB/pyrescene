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

from __future__ import print_function

import optparse
import sys
import os
import re
import time
import traceback
import fnmatch
from threading import Thread

import rescene
from rescene.main import MsgCode, FileNotFound, RarNotFound, EmptyRepository
from rescene.utility import sep
from rescene.utility import raw_input
from rescene.utility import encodeerrors
from rescene.utility import calculate_crc32
from rescene.utility import create_temp_file_name, replace_result


o = rescene.Observer()
rescene.subscribe(o)
rescene.change_rescene_name_version(rescene.APPNAME)

class MessageThread(Thread):
	done = False
	sleeptime = 0.2

	def __init__(self, messages_to_display=None):
		Thread.__init__(self)
		self.daemon = True
		self.messages = messages_to_display
		if not messages_to_display:
			self.all = True
			self.messages = []
		else:
			self.all = False
		self.done = False

	def set_messages(self, messages):
		self.messages = messages
		self.all = False

	def set_all(self, status):
		self.all = status

	def run(self):
		while True and (not self.done or len(o.events)):
			if len(o.events):
				for event in o.events:
					if event.code in self.messages or self.all:
						print(event.message, file=sys.stderr)
				o.events = []
			time.sleep(self.sleeptime)  # in seconds
		return

	def wait_for_output(self):
		"""We've got response back from the rescene functions.
		Wait until all those messages are printed before continuing."""
		while len(o.events):
			time.sleep(self.sleeptime)

mthread = MessageThread()

def report_error(status, message):
	parser.exit(status, message)

def report_unsupported_flag():
	report_error("Warning: Unsupported flag value encountered in SRR file. "
				 "This file may use features not supported in this version "
				 "of the application.\n")

def display_info(srr_file):
	"""Print out different sections with SRR info."""
	info = rescene.info(srr_file)

	print("Creating Application:")
	if info["appname"] == "":
		info["appname"] = "Unknown"
	print("\t%s\n" % info["appname"])

	if info["compression"]:
		print("SRR for compressed RARs.\n")

	if len(info["stored_files"]):
		print("Stored files:")
		for sfile in info["stored_files"].values():
			print("\t{0: >9}  {1}".format(sep(sfile.file_size),
				encodeerrors(sfile.file_name, sys.stdout)))
		print()

	if len(info["rar_files"]):
		print("RAR files:")
		for sfile in info["rar_files"].values():
			try:
				print("\t%s %s %d" % (sfile.file_name, sfile.crc32,
								sfile.file_size))
			except AttributeError:  # No SFV file is used
				print("\t%s %d" % (encodeerrors(sfile.file_name, sys.stdout),
				                   sfile.file_size))
		print()

	if len(info["archived_files"]):
		print("Archived files:")
		for sfile in info["archived_files"].values():
			print("\t%s %s %d" % (encodeerrors(sfile.file_name, sys.stdout),
			                      sfile.crc32, sfile.file_size))
		print()

	if len(info["oso_hashes"]):
		print("ISDb hashes:")
		for (name, ohash, size) in info["oso_hashes"]:
			print("\t%s %s %d" % (encodeerrors(name, sys.stdout), ohash, size))
		print()

	if len(info["sfv_comments"]):
		print("SFV comments:")
		for sfvline in info["sfv_comments"]:
			print("\t%s" % encodeerrors(sfvline, sys.stdout))
		print()

def verify_extracted_files(srr, in_folder, auto_locate):
	"""return codes:
	0: everything verified successfully
	1: corrupt file detected
	2: the file was not found
	10: it was a music release; nothing to verify
	"""
	status = 0
	archived_files = rescene.info(srr)["archived_files"].values()
	if len(archived_files) == 0:
		status = 10  # it's a music release
	for afile in archived_files:
		# skip the directories and empty files
		if afile.crc32 != "00000000" and afile.crc32 != "0":
			name = os.path.join(in_folder, afile.file_name)
			if not os.path.exists(name):
				if not auto_locate:
					print("File %s not found. Skipping." % afile.file_name)
					status = 2
				else:  # look for possible renames
					same_size_list = []
					for root, _dirnames, filenames in os.walk(in_folder):
						for fn in fnmatch.filter(filenames,
									"*" + os.path.splitext(name)[1]):
							f = os.path.join(root, fn)
							if os.path.getsize(f) == afile.file_size:
								same_size_list.append(f)
					# TODO: see if we can use OSO hash here to speed things up
					# it happens that multiple episodes have the same size
					found = False
					for f in same_size_list:
						crc = calculate_crc32(f)
						if afile.crc32 == "%0.8X" % crc:
							found = True
							print("File OK: %s matches %s." %
									(f, afile.file_name))
							break
						else:
							print("%s does not match." % f)
					if not found:
						print("File %s not found. Skipping." % name)
						status = 2
			else:
				crc = calculate_crc32(name)
				if afile.crc32 == "%0.8X" % crc:
					print("File OK: %s." % afile.file_name)
				else:
					print("File CORRUPT: %s!" % afile.file_name)
					status = 1
	return status

def manage_srr(options, in_folder, infiles, working_dir):
	out_folder = working_dir
	if options.output_dir:
		out_folder = options.output_dir
	save_paths = options.paths

	if options.list_info:  # -l
		# no messages. prevents mangled output in case there are any
		# e.g. new style comment block on
		# Friday.the.13th.Part.2.1981.720p.BluRay.x264-CULTHD
		mthread.set_messages([])
		display_info(infiles[0])
	elif options.list_details:  # -e
		mthread.set_messages([])
		rescene.print_details(infiles[0])
	elif options.verify:  # -q
		s = verify_extracted_files(infiles[0], in_folder, options.auto_locate)
		if s == 0:
			print("All files OK!")
		elif s == 10:
			print("No RAR meta data found: nothing to verify.")
		else:
			print("Corrupt and/or missing files!")
		return s
	elif options.extract:  # -x
		status = 0
		mthread.set_messages([])

		# append release name to the output path for all extracted files
		if options.parent:  # -d (additional usage for this option)
			srr = os.path.basename(infiles[0])
			out_folder = os.path.join(out_folder, os.path.splitext(srr)[0])

		# extract ALL possible files
		files = rescene.extract_files(infiles[0], out_folder, save_paths)

		# show which files are extracted + success or not
		for efile, success in files:
			file_name = efile[len(out_folder) + 1:]
			if success:
				print("{0}: extracted.".format(file_name))
			else:
				status = 1
				print("{0}: not extracted!".format(file_name), file=sys.stderr)
		return status
	elif options.extract_regex:
		status = 0  # no unexpected failures, good input
		mthread.set_messages([])

		try:
			to_extract = re.compile(options.extract_regex, re.IGNORECASE)
		except Exception as e:
			print("Unrecognized regular expression: %s" % e)
			print("Some examples:")
			print("\t.*\.nfo$")
			print("\t.*(nfo|sfv)$")
			print("\t^sample/.*")
			return 1
			
		# append release name to the output path for all extracted files
		if options.parent:  # -d (additional usage for this option)
			srr = os.path.basename(infiles[0])
			out_folder = os.path.join(out_folder, os.path.splitext(srr)[0])
			
		def decide_extraction(stored_fn):
			return to_extract.match(stored_fn)

		files = rescene.extract_files(
			infiles[0], out_folder, save_paths, matcher=decide_extraction)

		# show which files are extracted + success or not
		for efile, success in files:
			file_name = efile[len(out_folder) + 1:]
			if success:
				print("{0}: extracted.".format(file_name))
			else:
				status = 1
				print("{0}: not extracted!".format(file_name), file=sys.stderr)

		if not len(files):
			print("No matching files to extract.")

		return status

	elif options.store_files:  # -s
		mthread.set_messages([MsgCode.STORING])
		rescene.add_stored_files(infiles[0], options.store_files,
		                         in_folder, save_paths)
	else:
		# reconstruct (certain) volumes
		mthread.set_messages([MsgCode.FILE_NOT_FOUND, MsgCode.UNKNOWN,
		                      MsgCode.MSG, MsgCode.NO_OVERWRITE,
		                      MsgCode.USER_ABORTED, MsgCode.CRC])
		hints = dict()
		if options.hints:
			for hint in options.hints.split(';'):
				try:
					a, b = hint.split(':')
					hints[a] = b
				except:
					parser.exit(1, "Invalid hint (-H) value: %s" % hint)

		rar_mt = rescene.RarMtSettings()
		rar_mt.mt_set = options.mt_set
		rar_mt.mt_min = options.mt_min
		rar_mt.mt_max = options.mt_max

		try:
			rescene.reconstruct(infiles[0], in_folder, out_folder, save_paths,
			                    hints, options.no_auto_crc,
			                    options.auto_locate, options.fake,
			                    options.rar_executable_dir, options.temp_dir,
			                    options.volume is None, options.volume, rar_mt)
		except (FileNotFound, RarNotFound) as err:
			mthread.done = True
			mthread.join()
			print(err, file=sys.stderr)
			return 1
		except EmptyRepository:
			mthread.done = True
			mthread.join()
			sys.stderr.write("""\
=> Failure trying to reconstruct compressed RAR archives.
=> Use the -z switch to point to a directory with RAR executables.
=> Create this directory by using the preprardir.py script.
""")
			return 1

def create_srr(options, infolder, infiles, working_dir):
	msgs = [MsgCode.FILE_NOT_FOUND, MsgCode.UNKNOWN, MsgCode.MSG]
	if options.verbose:
		msgs += [MsgCode.BLOCK, MsgCode.FBLOCK, MsgCode.RBLOCK,
		         MsgCode.NO_FILES]
		mthread.set_all(True)
	mthread.set_messages(msgs)

	store_files = options.store_files
	save_paths = options.paths
	out_folder = working_dir

	srr_name = ""
	if options.output_dir:
		if options.output_dir[-4:].lower() == ".srr":
			srr_name = options.output_dir
		else:
			out_folder = options.output_dir

	if not srr_name:
		if options.parent:  # -d
			srr_name = os.path.join(out_folder,
		                        os.path.split(infolder)[-1] + ".srr")
		else:
			srr_name = os.path.join(out_folder,
								os.path.basename(infiles[0])[:-4] + ".srr")

# 	print("SRR name: %s" % srr_name, file=sys.stderr)
# 	print("infiles: %s" % infiles, file=sys.stderr)
# 	print("infolder: %s" % infolder, file=sys.stderr)
# 	print("store files: %s" % store_files, file=sys.stderr)
	try:
		tmp_srr_name = create_temp_file_name(srr_name)
		success = rescene.create_srr(srr_name, infiles, infolder,
	                                 store_files, save_paths,
	                                 options.allow_compressed,
	                                 options.isdb_hash,
	                                 tmp_srr_name=tmp_srr_name)
		replace_result(tmp_srr_name, srr_name)
		mthread.done = True
		mthread.join()
		if success:
			print("SRR file successfully created.")
		else:
			# User did not want to overwrite existing file
			print("SRR file not overwritten.")
	except (EnvironmentError, ValueError, FileNotFound) as err:
		# Can not read basic block header
		# ValueError: compressed SRR
		# ValueError: The file is too small.
		# EmptySfv: can't create a useful file in this case
		# FileNotFound: Linux file systems are case sensitive

		# make sure there is no broken SRR file/temporary file left
		try:
			os.unlink(srr_name)
		except:
			pass
		mthread.done = True
		mthread.join()
		print(err, file=sys.stderr)
		print("SRR creation failed. Aborting.", file=sys.stderr)
		return 1

def main(argv=None):
	global parser
	parser = optparse.OptionParser(
	usage=("Usage: %prog [input file list] [options]\n"
	"To create a ReScene file (.srr), use the .sfv file(s) accompanied"
	" with the archives or pick the first .rar file(s).\n"
	"All files referenced by the .sfv"
	" must be in the same folder as the .sfv file.\n"
	"	ex:"
	"\tsrr simpleFileVerification.sfv -s file.nfo \n"
	"\t\tsrr CD1/cd1.sfv CD2/cd2.sfv -s *.nfo -s other.file -d -p\n"
	"To reconstruct a release, use the SRR file created from the release.\n"
	"	ex:"
	"\tsrr file.srr\n"
	"Do not use this command to create srr files from vobsubs! Use Auto."),
	version="%prog " + rescene.__version__)  # --help, --version

	display = optparse.OptionGroup(parser, "Display options")
	creation = optparse.OptionGroup(parser, "Creation options")
	recon = optparse.OptionGroup(parser, "Reconstruction options")
	edit = optparse.OptionGroup(parser, "Edit options")
	comprr = optparse.OptionGroup(parser, "Compressed reconstruction options")
	parser.add_option_group(display)
	parser.add_option_group(creation)
	parser.add_option_group(recon)
	parser.add_option_group(edit)
	parser.add_option_group(comprr)

	parser.add_option("-y", "--always-yes", dest="always_yes", default=False,
					  action="store_true",
					  help="assume Y(es) for all prompts")
	parser.add_option("-n", "--always-no", dest="always_no", default=False,
					  action="store_true",
					  help="assume N(o) for all prompts")
	parser.add_option("-v", help="enable verbose (technical) creation",
						action="store_true", dest="verbose", default=False)
	# TODO: get all the messages in order

	display.add_option("-l", "--list",
					  action="store_true", dest="list_info", default=False,
					  help="list SRR file contents")
	display.add_option("-e", "--details",
					  action="store_true", dest="list_details", default=False,
					  help="list detailed SRR file info")
	display.add_option("-q", "--verify",
					  action="store_true", dest="verify", default=False,
					  help="verify extracted RAR contents")

	creation.add_option("-c", "--compressed",
					 action="store_true", dest="allow_compressed",
					 help="allow SRR creation for compressed RAR files")
	creation.add_option("-p", "--paths",
						help="Store file names with paths "
						"(relative to the input base directory) "
						"Use this switch to recreate the paths.",
						action="store_true", dest="paths", default=False)
	creation.add_option("-d", help="Use parent directory name as "
						"basis for generated .srr file name. Also extracts to "
						"directory named after .srr file when used together "
						"with -x.",
						action="store_true", dest="parent", default=False)
	creation.add_option("-o", dest="output_dir", metavar="DIRECTORY",
					help="<path>: Specify output file or directory path.")
	creation.add_option("-i", help="<path>: Specify input base directory.",
						dest="input_base", metavar="DIRECTORY")
	creation.add_option("--no-isdb",
						action="store_false", default=True, dest="isdb_hash",
						help="do not attempt to store ISDb hashes "
						"(not recommended)")

# 	recon.set_description("")
	recon.add_option("-r", action="store_true", dest="auto_locate",
					 help="attempt to auto-locate renamed files "
					 "(must have the same extension)", default=False)
	recon.add_option("-f", "--fake-file",
					 action="store_true", dest="fake", default=False,
					 help="fills RAR with fake data when the archived file "
					 "isn't found (e.g. no extras) "
					 "this option implies --no-autocrc")
	recon.add_option("-m", "--volume", dest="volume",
					metavar="VOLUME", help="Specify a single RAR volume "
					"to reconstruct. Provide the extension or file name. "
					"End name with * to trigger entire subset reconstruction.")
	recon.add_option("-u", "--no-autocrc",
					 action="store_true", dest="no_auto_crc", default=False,
					 help="disable automatic CRC checking during reconstruction")
	recon.add_option("-H", help="<oldname:newname list>: Specify alternate "
					"names for extracted files.  ex: srr example.srr -H "
					"orginal.mkv:renamed.mkv;original.nfo:renamed.nfo",
					metavar="HINTS", dest="hints")
	recon.add_option("-z", "--rar-dir", dest="rar_executable_dir",
					metavar="DIRECTORY",
					help="Directory with preprocessed RAR executables created"
					" by the preprardir.py script. This is necessary to "
					"reconstruct compressed archives.")
	recon.add_option("-t", "--temp-dir", dest="temp_dir",
					metavar="DIRECTORY", help="Specify directory "
					"for temp files while reconstructing compressed RARs.")

# 	creation.set_description("These options are used for creating an SRR file.")
	edit.add_option("-x", "--extract",
	                action="store_true", dest="extract", default=False,
	                help="extract SRR stored files only")
	edit.add_option("--extract-regex",
	                dest="extract_regex",
					help="extract stored files that match the provided regex")
	edit.add_option("-s", help="<file list>: Store additional files in the"
	                " SRR (wildcards supported)", action="append",
	                metavar="FILES", dest="store_files")
	
	def integer_list(option, opt_str, value, parser):
		try:
			value = [int(mt) for mt in value.split(",")]
		except:
			error_msg = "%s expects only numers and commas" % opt_str
			raise optparse.OptionValueError(error_msg)
		setattr(parser.values, option.dest, value)
		
	comprr.set_description("Set the rar -mt thread parameter to exclude "
		"certain possibilities when reconstructing compressed RARs.")
	comprr.add_option("--mt-set", callback=integer_list,
	                  action="callback", type="string", dest="mt_set",
	                  help="list of possible thread values. e.g. 4,6,8")
	comprr.add_option("--mt-min", default=0,
	                  action="store", type="int", dest="mt_min",
	                  help="minimum thread count to try. e.g. 24")
	comprr.add_option("--mt-max", default=0,
	                  action="store", type="int", dest="mt_max",
	                  help="maximum thread count to try. e.g. 2")

	if argv is None:
		argv = sys.argv[1:]

	# no arguments given
	if not len(argv):
		# show application usage
		parser.print_help()
		return 0

	(options, infiles) = parser.parse_args(args=argv)

	def can_overwrite(file_path):
		retvalue = True
		if (not options.always_yes and
		    not options.always_no and os.path.isfile(file_path)):
			# make sure no messages pop up after our question
			time.sleep(MessageThread.sleeptime)

			print("Warning: File %s already exists." % file_path)
			char = raw_input("Do you wish to continue? (Y/N): ").lower()
			while char not in ('y', 'n'):
				char = raw_input("Do you wish to continue? (Y/N): ").lower()
			if char == 'n':
				retvalue = False
		elif options.always_no and os.path.isfile(file_path):
			retvalue = False
		return retvalue

	rescene.main.can_overwrite = can_overwrite

	if options.temp_dir and not os.path.isdir(options.temp_dir):
		report_error(1, "Provided temporary directory not found.\n")
		
	if options.extract and options.extract_regex:
		report_error(1, "Extract all or follow the regex?\n")

	if options.allow_compressed:
		print("*"*60, file=sys.stderr)
		sys.stderr.write("""\
WARNING: SRR files for compressed RARs are like SRS files:
         you can never be sure they will reconstruct!

         Do NOT use this to create SRR files for VobSubs!
         Use 'pyrescene --vobsubs file.sfv' instead.
""")
		print("*"*60, file=sys.stderr)

	try:
		mthread.start()
		working_dir = os.path.abspath(os.path.curdir)

		# check existence and type of the input files
		for infile in infiles:
			ext = infile[-4:].lower()
			if not os.path.exists(infile):
				print(parser.format_help(), file=sys.stderr)
				report_error(1, "Input file not found: %s\n" % infile)
			elif ext != ".srr" and ext != ".sfv" and ext != ".rar":
				print(parser.format_help(), file=sys.stderr)
				report_error(1, "Input file type not recognized: %s\n" %
							 infile)

		if not len(infiles):
			print(parser.format_help(), file=sys.stderr)
			report_error(1, "No input file(s) specified.\n")

		infolder = working_dir
		if options.input_base:  # -i
			infolder = options.input_base

		if infiles[0].endswith(".srr"):
			parser.exit(manage_srr(options, infolder, infiles, working_dir))
		else:
			parser.exit(create_srr(options, infolder, infiles, working_dir))
	except KeyboardInterrupt:
		print(file=sys.stderr)
		print("Ctrl+C pressed. Aborting.", file=sys.stderr)
		parser.exit(130)  # http://tldp.org/LDP/abs/html/exitcodes.html
	except Exception as err:
		traceback.print_exc()
		parser.exit(99, "Unexpected Error: %s" % err)
	finally:
		mthread.done = True
		mthread.join(0.5)
# 		mthread.join(None)

if __name__ == "__main__":
	if "--profile" in sys.argv:
		print("Profiling...")
		sys.argv.remove("--profile")
		import cProfile
		import pstats
		# view with RunSnakeRun
		profile_filename = 'bin.rescene_profile.txt'
		cProfile.run('main()', profile_filename)
		statsfile = open("profile_stats.txt", "wb")
		p = pstats.Stats(profile_filename, stream=statsfile)
		stats = p.strip_dirs().sort_stats('cumulative')
		stats.print_stats()
		statsfile.close()
		sys.exit(0)
	sys.exit(main())
