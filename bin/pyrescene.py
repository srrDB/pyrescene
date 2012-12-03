#!/usr/bin/env python
# encoding: utf-8

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

"""
design decisions:
- must work from DVDRs and directories with read only access: 
  It doesn't write any files in the dirs it processes
- -c parameter pysrs (check against main movie file)
- .ext.txt text files for failed samples

Sorting isn't how we want it in this case:
 E:\Star.Wars.EP.I.The.Phantom.Menace.1999.iNT.DVDRip.XviD-aNBc\CD2\
 E:\Star.Wars.EP.I.The.Phantom.Menace.1999.iNT.DVDRip.XviD-aNBc\Cd1\
"""

from optparse import OptionParser
from tempfile import mkdtemp
import sys
import os
import re
import shutil
import fnmatch
import time

try:
	import _preamble
except ImportError:
	sys.exc_clear()
	
import rescene
from resample.srs import main as srsmain
from rescene.srr import MessageThread
from rescene.main import MsgCode

o = rescene.Observer()
rescene.subscribe(o)

rescene.change_rescene_name_version("pyReScene Auto %s" % rescene.__version__)

def can_create(always_yes, path):
	retvalue = True 
	if not always_yes and os.path.isfile(path):
		print("Warning: %s does not exist. Create it? " % path)
		# http://www.python.org/dev/peps/pep-3111/
		char = raw_input("Do you wish to continue? (Y/N): ").lower()
		while char not in ('y', 'n'):
			char = raw_input("Do you wish to continue? (Y/N): ").lower()
		if char == 'n':
			retvalue = False
	return retvalue

def get_files(release_dir, extention):
	"""Gather all SFV files from the subdirs."""
	matches = []
	for dirpath, _dirnames, filenames in os.walk(release_dir):
		for filename in fnmatch.filter(filenames, extention):
			matches.append(os.path.join(dirpath, filename))
	return matches

def get_sample_files(reldir):
	sample_files = (get_files(reldir, "*.avi") + get_files(reldir, "*.mkv") + 
	                get_files(reldir, "*.mp4") + get_files(reldir, "*.wmv"))
	result = []
	for sample in sample_files:
		# sample folder or 'sample' in the name
		# or a musicvideo file (sfv with same name)
		if ("sample" in sample.lower() or 
		    os.path.exists(sample[:-4] + ".sfv")):
			result.append(sample)
	return result

def get_proof_files(reldir):
	"""Includes proof RAR files."""
	image_files = (get_files(reldir, "*.jpg") + get_files(reldir, "*.png") + 
	               get_files(reldir, "*.gif") + get_files(reldir, "*.bmp") +
	               get_files(reldir, "*.rar"))
	result = []
	for sample in image_files:
		# images in sample folders are ok
		# others need to contain the word proof in their path
		if "proof" in sample.lower() or "sample" in sample.lower():
			if sample[-4:] == ".rar":
				# no body.of.proof. rar files
				if os.path.getsize(sample) % 1000 != 0:
					result.append(sample)
			else:
				result.append(sample)
	return result

def remove_unwanted_sfvs(sfv_list):
	"""
	Remove SFVs from subs and music releases.
	"""
	wanted_sfvs = []
	for sfv in sfv_list:
		sfv_name = os.path.basename(sfv)
		if "subs" in sfv_name.lower() or "vobsub" in sfv_name.lower():
			continue
		# subs not in filename, but the folder is called subs or vobsubs
		pardir = os.path.split(os.path.dirname(sfv))[1].lower()
		if "subs" == pardir or "vobsubs" == pardir or "vobsub" == pardir:
			continue
		
		wanted = True
		# not wanted if SFV contains .mp3 or .flac files
		for sfvf in rescene.utility.parse_sfv_file(sfv)[0]:
			if (sfvf.file_name.endswith(".mp3") or 
				sfvf.file_name.endswith(".flac")):
				wanted = False
				break
		
		# hardcoded for issue on own dvd
		if (sfv.endswith("Happy.Feet.DVDRip.XviD-DiAMOND\dmd-happyfeet-cd2.sfv") or
			sfv.endswith("Happy.Feet.DVDRip.XviD-DiAMOND/dmd-happyfeet-cd2.sfv")):
			wanted = False
		if wanted:		
			wanted_sfvs.append(sfv)
	return wanted_sfvs

def get_start_rar_files(sfv_list):
	"""
	Get the main first RAR files to check sample against.
	"""
	wanted_rars = []
	for sfv in sfv_list:
		first = rescene.utility.first_rars([x.file_name for x in 
				rescene.utility.parse_sfv_file(sfv)[0]])
		if len(first):
			sfile = os.path.join(os.path.dirname(sfv), first[0])
			wanted_rars.append(sfile)
	return wanted_rars

def empty_folder(folder_path):
	for file_object in os.listdir(folder_path):
		file_object_path = os.path.join(folder_path, file_object)
		if os.path.isfile(file_object_path):
			os.unlink(file_object_path)
		else:
			shutil.rmtree(file_object_path)

def copy_to_working_dir(working_dir, release_dir, copy_file):
	path = os.path.relpath(copy_file, release_dir)
	dest_file = os.path.join(working_dir, path)
	
	# make in between dirs
	try:
		os.makedirs(os.path.dirname(dest_file))
	except:
		pass
	
	try:
		# copy over file
		shutil.copyfile(copy_file, dest_file)	
	except IOError:
		print("Could not copy %s." % copy_file)
		
	return dest_file

def generate_srr(reldir, working_dir, options):
	assert os.listdir(working_dir) == []
	
	mthread = MessageThread()
	msgs = [MsgCode.FILE_NOT_FOUND, MsgCode.UNKNOWN, MsgCode.MSG]
	mthread.set_messages(msgs)
	mthread.start()
	
	print(reldir)
	srr = os.path.join(options.output_dir, os.path.split(reldir)[1] + ".srr")
	
	sfvs = get_files(reldir, "*.sfv")
	main_sfvs = remove_unwanted_sfvs(sfvs)
	main_rars = get_start_rar_files(main_sfvs)
	
	if len(main_sfvs):
		try:
			rescene.create_srr(srr, main_sfvs, reldir, [], True, 
			                   options.compressed)
			mthread.done = True
			mthread.join()
		except IOError:
			print("Read error. DVD disk unreadable? Try again!")
			os.unlink(srr)
			return False
		except KeyboardInterrupt:
			os.unlink(srr)
			raise
	else:
		return False
	
	# remove all stored files so we can add them all in the right order again
	rescene.remove_stored_files(srr, rescene.info(srr)["stored_files"])
	
	# copy all files to store to the working dir + their paths
	copied_files = []
	for nfo in get_files(reldir, "*.nfo"):
		copied_files.append(copy_to_working_dir(working_dir, reldir, nfo))
		
	for proof in get_proof_files(reldir):
		copied_files.append(copy_to_working_dir(working_dir, reldir, proof))	
		
	# when stored SRS file instead of a sample file
	for srs in get_files(reldir, "*.srs"):
		copied_files.append(copy_to_working_dir(working_dir, reldir, srs))

	# Create SRS files
	for sample in get_sample_files(reldir):
		current_sample = copy_to_working_dir(working_dir, reldir, sample)
		
		# optionally check against main movie files
		# if an SRS file can be created, it'll be added
		found = False
		if options.sample_verify:
			print("Checking against the following main files:")
			for mrar in main_rars:
				print("\t%s" % mrar)
			for main in main_rars:
				try:
					srsmain([current_sample, "-y", "-o", 
					         os.path.dirname(current_sample),
					         "-c", main], True)
					copied_files.append(current_sample[:-4] + ".srs")
					found = True
					break
				except ValueError:
					print("Sample not found in %s." % main)			
		if not found:
			try:
				srsmain([current_sample, "-y", "-o", 
				         os.path.dirname(current_sample)], True)
				copied_files.append(current_sample[:-4] + ".srs")
			except ValueError:
				with open(current_sample + ".txt", "wb") as stderr:
					stderr.write(sys.exc_info()[1].message)
				copied_files.append(current_sample + ".txt")
				
		os.unlink(current_sample)
		
	#TODO: TXT files for m2ts with crc?
		
	copied_sfvs = [] # SFVs in the working dir
	for sfv in sfvs:
		copied_sfvs.append(copy_to_working_dir(working_dir, reldir, sfv))
		
	# add RAR sfv files at the bottom
	rarsfv = []
	for sfv in sfvs:
		handled = False
		for msfv in main_sfvs:
			if sfv == msfv:
				handled = True
				rarsfv.append(copied_sfvs[sfvs.index(sfv)])
		if not handled:
			copied_files.append(copied_sfvs[sfvs.index(sfv)])
	for sfv in rarsfv:
		copied_files.append(sfv)
	
	# some of copied_files can not exist
	# this can be the case when the disk isn't readable
	rescene.add_stored_files(srr, copied_files, working_dir, True, False)

	empty_folder(working_dir)
	
	return True

def get_release_directories(path):
	"""Generator that yields all possible release directories."""
	path = os.path.abspath(path)
	last_release = ""
	
	if os.name != "nt":
		# wait until the DVD drive is mounted
		while not len(os.listdir(path)):
			print("Waiting 2 seconds for mount.")
			time.sleep(2)
		
	for dirpath, dirnames, filenames in os.walk(path):
		if last_release in dirpath and last_release:
			continue # subfolders of a found release
		
		release = False
		# A folder is considered being an original scene release directory when
		# there is an .nfo file or an .sfv file
		# or an .sfv file in a CDx/DiskX subdir (when nfo file is missing)
		for filename in filenames:
			if (filename[-4:].lower() in (".nfo", ".sfv") and
				filename != "motechnetfiles.nfo" and 
				filename != "movie.nfo" and
				filename != "imdb.nfo"):
				release = True
				last_release = dirpath
				break

		if not release:
			# SFV file in one of the interesting subdirs?
			interesting_dirs = []
			for dirname in dirnames:
				if re.match("^(CD|DISK)\d$", dirname, re.IGNORECASE):
					interesting_dirs.append(dirname)
			
			for idir in interesting_dirs:
				for lfile in os.listdir(os.path.join(dirpath, idir)):
					if lfile[-4:].lower() == ".sfv":
						release = True
						last_release = dirpath
						break
				if release:
					break
			
		rel_folders = "^((CD|DISK)\d)|(Vob)?Samples?|Covers?|Proofs?$"
		if release and not re.match(rel_folders, last_release, re.IGNORECASE):
			yield last_release

def main(argv=None):
	parser = OptionParser(
	usage=("Usage: %prog [directories] [options]\n"
	"This tool can automatically create a complete SRR file for a "
	"release directory. Example usage: %prog -r E:\ -o D:\ -s -c"), 
	version="%prog " + rescene.__version__) # --help, --version
	
	parser.add_option("-y", "--always-yes", dest="always_yes", default=False,
					  action="store_true",
					  help="assume Y(es) for all prompts")
	parser.add_option("-r", "--recursive", dest="recursive", default=False,
					  action="store_true",
					  help="recursively create SRR files")
	parser.add_option("-c", "--compressed",
					 action="store_true", dest="compressed",
					 help="allow SRR creation for compressed RAR files")
	parser.add_option("-s", "--sample-verify",
					 action="store_true", dest="sample_verify",
					 help="verifies sample agains main movie files")
	parser.add_option("-o", "--output", dest="output_dir", metavar="DIR",
					default=".",
					help="<path>: Specify output file or directory path. "
					"The default output path is the current directory.")
	parser.add_option("-e", "--eject",
					 action="store_true", dest="eject",
					 help="eject DVD drive after processing")
	
	if argv is None:
		argv = sys.argv[1:]
		
	# no arguments given
	if not len(argv):
		# show application usage
		parser.print_help()
		return 0
	
	(options, indirs) = parser.parse_args(args=argv)

	# check for existence output directory
	options.output_dir = os.path.abspath(options.output_dir)
	if not os.path.exists(options.output_dir):
		if can_create(options.always_yes, options.output_dir):
			os.makedirs(options.output_dir)
			
	# overwrite user input request function
	def can_overwrite(file_path):
		retvalue = True 
		if not options.always_yes and os.path.isfile(file_path):
			print("Warning: File %s already exists." % file_path)
			# http://www.python.org/dev/peps/pep-3111/
			char = raw_input("Do you wish to continue? (Y/N): ").lower()
			while char not in ('y', 'n'):
				char = raw_input("Do you wish to continue? (Y/N): ").lower()
			if char == 'n':
				retvalue = False
		return retvalue 
	rescene.main.can_overwrite = can_overwrite
			
	# create temporary working dir
	working_dir = mkdtemp(".pyReScene")	
	
	drive_letters = []
	failures = False
	aborted = False
	try:
		for reldir in indirs:
			reldir = os.path.abspath(reldir)
			if not options.recursive:
				result = generate_srr(reldir, working_dir, options)
				if not result:
					failures = True
			else:
				for release_dir in get_release_directories(reldir):
					result = generate_srr(release_dir, working_dir, options)
					if not result:
						failures = True
			# gather drive info
			drive_letters.append(reldir[:2])
	except KeyboardInterrupt:
		print("Process aborted.")
		aborted = True
	if failures:
		print("------------------------------------")
		print("Warning: some SRRs were not created!")
		print("------------------------------------")
				
	# delete temporary working dir
	shutil.rmtree(working_dir)
	
	# see if we need to eject a disk drive
	if options.eject and os.name == "nt" and not aborted:
		import ctypes
		import winsound
		
		for drive in drive_letters:
			ctypes.windll.WINMM.mciSendStringW(
				u"open %s type cdaudio alias ddrive" % drive, None, 0, None)
			ctypes.windll.WINMM.mciSendStringW(
				u"set ddrive door open", None, 0, None)
		
		winsound.Beep(1000, 500)
	elif options.eject and not aborted:
		import subprocess
		
		subprocess.call(["eject"])
		print("\a")
	return 0

if __name__ == "__main__":
	sys.exit(main())
	
