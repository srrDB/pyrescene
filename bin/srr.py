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

from os.path import join, dirname, realpath
from threading import Thread

# for running the script directly from command line
sys.path.append(join(dirname(realpath(sys.argv[0])), '..'))

import rescene
from rescene.main import MsgCode, FileNotFound

# make it work with Python 3 too
#if sys.hexversion >= 0x3000000:
#	raw_input = input #@ReservedAssignment

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
						print(event.message)
				o.events = []
			time.sleep(self.sleeptime) # in seconds
		return
	
mthread = MessageThread()

# http://stackoverflow.com/questions/4620547/real-time-output-of-subprocess-popen-and-not-line-by-line


# TODO: UNIX return codes OK?

def report_error(status, message):
	parser.exit(status, message)
	
def report_unsupported_flag():
	report_error("Warning: Unsupported flag value encountered in SRR file. "
				 "This file may use features not supported in this version "
				 "of the application")
	
# http://love-python.blogspot.be/2010/03/getch-in-python-get-single-character.html


def can_overwrite(file_path):
	retvalue = True 
	if not options.always_yes and os.path.isfile(file_path):
		# make sure no messages pop up after our question
		time.sleep(MessageThread.sleeptime)
		
		print("Warning: File %s already exists." % file_path)
		# http://www.python.org/dev/peps/pep-3111/
		char = raw_input("Do you wish to continue? (Y/N): ").lower()
		while char not in ('y', 'n'):
			char = raw_input("Do you wish to continue? (Y/N): ").lower()
		if char == 'n':
			retvalue = False
	return retvalue 

rescene.main.can_overwrite = can_overwrite
	
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
			print("\t%s %d" % (sfile.file_name, sfile.file_size))
		print("")
		
	if len(info["rar_files"]):
		print("RAR files:")
		for sfile in info["rar_files"].values():
			try:
				print("\t%s %s %d" % (sfile.file_name, sfile.crc32, 
								sfile.file_size))
			except AttributeError: # No SFV file is used
				print("\t%s %d" % (sfile.file_name, sfile.file_size))
		print("")
		
	if len(info["archived_files"]):
		print("Archived files:")
		for sfile in info["archived_files"].values():
			print("\t%s %s %d" % (sfile.file_name, sfile.crc32, 
								sfile.file_size))
		print("")
		
	if len(info["sfv_comments"]):
		print("SFV comments:")
		for sfvline in info["sfv_comments"]:
			print("\t%s" % sfvline)
		print("")
	
def manage_srr(options, in_folder, infiles, working_dir):
	out_folder = working_dir
	if options.output_dir:
		out_folder = options.output_dir
	save_paths = options.paths
	
	if options.list_info: # -l
		display_info(infiles[0])
	elif options.list_details: # -e
		rescene.print_details(infiles[0])
	elif options.extract: # -x
		mthread.set_messages([])
		# extract ALL possible files
		files = rescene.extract_files(infiles[0], out_folder, save_paths)
		
		# show which files are extracted + success or not
		for efile, success in files:
			if success:
				result = "extracted."
			else:
				result = "not extracted!"
			efile = efile[len(out_folder):]
			print("%s: %s" % (efile, result))
	elif options.store_files: # -s
		mthread.set_messages([MsgCode.STORING])
		rescene.add_stored_files(infiles[0], options.store_files, 
		                         in_folder, save_paths)
	else:
		mthread.set_messages([MsgCode.FILE_NOT_FOUND, MsgCode.UNKNOWN,
							])
#		mthread.set_all(True)
		hints = dict()
		if options.hints:
			for hint in options.hints.split(';'):
				try:
					a, b = hint.split(':')
					hints[a] = b
				except:
					parser.exit(1, "Invalid hint (-H) value: %s" % hint)
			
		try:
			rescene.reconstruct(infiles[0], in_folder, out_folder, save_paths, 
			                    hints, options.no_auto_crc, 
			                    options.auto_locate, options.fake)
		except FileNotFound:
			mthread.done = True
			mthread.join()
			print(sys.exc_info()[1])

def create_srr(options, infolder, infiles, working_dir):
	msgs = [MsgCode.FILE_NOT_FOUND, MsgCode.UNKNOWN, MsgCode.MSG]
	if options.verbose:
		msgs += [MsgCode.BLOCK, MsgCode.FBLOCK, MsgCode.RBLOCK, 
		         MsgCode.NO_FILES, MsgCode.MSG]
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
		if options.parent: # -d
			srr_name = os.path.join(out_folder, 
			                        os.path.split(infolder)[-1] + ".srr")
		else:
			srr_name = os.path.join(out_folder, infiles[0][:-4] + ".srr")
			
#	print("SRR name: %s" % srr_name)
#	print("infiles: %s" % infiles)
#	print("infolder: %s" % infolder)
#	print("store files: %s" % store_files)
	try:
		rescene.create_srr(srr_name, infiles, infolder, 
	                       store_files, save_paths, options.allow_compressed)
		mthread.done = True
		mthread.join()
		print("SRR file successfully created.")
	except (EnvironmentError, ValueError):
		# Can not read basic block header
		# ValueError: compressed SRR
		mthread.done = True
		mthread.join()
		print(sys.exc_info()[1])
		print("SRR creation failed. Aborting.")

def main(options, infiles):
	try:
		mthread.start()
		working_dir = os.path.abspath(os.path.curdir)
		
		# check existence and type of the input files
		for infile in infiles:
			ext = infile[-4:]
			if not os.path.exists(infile):
				print(parser.format_help())
				report_error(1, "Input file not found: %s\n" % infile)
			elif ext != ".srr" and ext != ".sfv" and ext != ".rar":
				print(parser.format_help())
				report_error(-1, "Input file type not recognized: %s\n" %
							 infile)
				
		if not len(infiles):
			print(parser.format_help())
			report_error(1, "No input file(s) specified.")
			
		infolder = working_dir
		if options.input_base: # -i
			infolder = options.input_base
			
		if infiles[0][-4:] == ".srr":
			manage_srr(options, infolder, infiles, working_dir)
		else:
			create_srr(options, infolder, infiles, working_dir)
	except KeyboardInterrupt:
		print()
		print("Ctrl+C pressed. Aborting.")
	except Exception:
		traceback.print_exc()
		parser.exit(99, "Unexpected Error: %s" % sys.exc_info()[1])
	finally:
		mthread.done = True
		mthread.join(0.5)
#		mthread.join(None)

if __name__ == "__main__":
	parser = optparse.OptionParser(
	usage=("Usage: %prog [input file list]  [options]\n"
	"To create a display file (.srr), use the .sfv file(s) accompanied" 
	" with the archives or pick the first .rar file(s).\n"
	"All files referenced by the .sfv"
	" must be in the same folder as the .sfv file.\n"
	"	ex:"
	"\tsrr simpleFileVerification.sfv -s file.nfo \n"
	"\t\tsrr CD1/cd1.sfv CD2/cd2.sfv -s *.nfo -s other.file -d -p\n"
	"To reconstruct a release, use the SRR file created from the release.\n"
	"	ex:"
	"\tsrr file.srr"), 
	version="%prog " + rescene.__version__) # --help, --version
	
	display = optparse.OptionGroup(parser, "Display options")
	creation = optparse.OptionGroup(parser, "Creation options")
	recon = optparse.OptionGroup(parser, "Reconstruction options")
	edit = optparse.OptionGroup(parser, "Edit options")
	parser.add_option_group(display)
	parser.add_option_group(creation)
	parser.add_option_group(recon)
	parser.add_option_group(edit)
	
	parser.add_option("-y", "--always-yes", dest="always_yes", default=False,
					  action="store_true",
					  help="assume Y(es) for all prompts")
	# TODO: prompt for overwriting SRR file
	parser.add_option("-v", help="enable verbose (technical) creation",
						action="store_true", dest="verbose", default=False)
	# TODO: get all the messages in order
	
	display.add_option("-l", "--list", 
					  action="store_true", dest="list_info", default=False,
					  help="list SRR file contents")
	display.add_option("-e", "--details", 
					  action="store_true", dest="list_details", default=False,
					  help="list detailed SRR file info")

	
	creation.add_option("-c", "--compressed",
					 action="store_true", dest="allow_compressed",
					 help="allow SRR creation for compressed RAR files")
	creation.add_option("-p", "--paths",
						help="Store file names with paths "
						"(relative to the input base directory) "
						"Use this switch to recreate the paths.",
						action="store_true", dest="paths", default=False)
	creation.add_option("-d", help="Use parent directory name as "
						"basis for generated .srr file name.",
						action="store_true", dest="parent", default=False)
	creation.add_option("-o", dest="output_dir", metavar="DIRECTORY",
					help="<path>: Specify output file or directory path.")
	creation.add_option("-i", help="<path>: Specify input base directory.",
						dest="input_base", metavar="DIRECTORY")	
	
#	recon.set_description("")
	recon.add_option("-r", action="store_true", dest="auto_locate",
					 help="attempt to auto-locate renamed files "
					 "(must have the same extension)", default=False)
	recon.add_option("-f", "--fake-file", 
					 action="store_true", dest="fake", default=False,
					 help="fills RAR with fake data when the archived file"
					 "isn't found (e.g. no extras) "
					 "this option implies --no-autocrc")
	recon.add_option("-u", "--no-autocrc", 
					 action="store_false", dest="no_auto_crc", default=True,
					 help="disable automatic CRC checking during reconstruction")
	recon.add_option("-H", help="<oldname:newname list>: Specify alternate "
					"names for extracted files.  ex: srr example.srr -h "
					"orginal.mkv:renamed.mkv;original.nfo:renamed.nfo",
					metavar="HINTS", dest="hints")
	
	
#	creation.set_description("These options are used for creating an SRR file.")
	edit.add_option("-x", "--extract",
					  	action="store_true", dest="extract", default=False,
					  	help="extract SRR stored files only")
	edit.add_option("-s", help="<file list>: Store additional files in the"
						" SRR (wildcards supported)", action="append",
						metavar="FILES", dest="store_files")
	
	# no arguments given
	if len(sys.argv) < 2:
		# show application usage
		print(parser.format_help())
	else:	   
		(options, args) = parser.parse_args()
		status = main(options, args)
		sys.exit(status)
	