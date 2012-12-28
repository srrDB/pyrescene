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
This tool creates an SRR file from a release directory.

design decisions:
- must work from DVDRs and directories with read only access: 
  It doesn't write or move any files in the dirs it processes, unless -d
  option is used to output the SRR file into the release directory.
- -s parameter pysrs (check against main movie file)
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
from rescene.main import MsgCode, FileNotFound

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
	"""Gather all 'extention' files from the subdirs."""
	matches = []
	for dirpath, _dirnames, filenames in os.walk(release_dir):
		for filename in filenames:
			if fnmatch.fnmatchcase(filename, extention.lower()):
				matches.append(os.path.join(dirpath, filename))
			if fnmatch.fnmatchcase(filename, extention.upper()):
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
	"""
	Includes proofs, proof RAR files, image files in Sample directories.
	"""
	image_files = (get_files(reldir, "*.jpg") + get_files(reldir, "*.png") + 
	               get_files(reldir, "*.gif") + get_files(reldir, "*.bmp") +
	               get_files(reldir, "*.jpeg"))
	rar_files = get_files(reldir, "*.rar")
	result = []
	for sample in image_files:
		# images in Sample and Proof folders are ok
		# others need to contain the word proof in their path
		if "proof" in sample.lower() or "sample" in sample.lower():
			result.append(sample)
		else:
			# proof file in root dir without the word proof somewhere
			if os.path.getsize(sample) > 100000:
				result.append(sample)
	for sample in rar_files:
		if "proof" in sample.lower():
			# no "body.of.proof" main rar files
			# + fix problem with .partXX.rar files
			if (os.path.getsize(sample) % 1000 != 0 and
				".part" not in os.path.basename(sample)):
				result.append(sample)
	return result

def remove_unwanted_sfvs(sfv_list):
	"""
	Remove SFVs from subs and music releases.
	"""
	wanted_sfvs = []
	for sfv in sfv_list:
		sfv_name = os.path.basename(sfv)
		if ("subs" in sfv_name.lower() or "vobsub" in sfv_name.lower() or
			"subtitle" in sfv_name.lower()):
			# false positive: the.substitute.4.vrs.cd1.rar 92341f72
			# The.Substitute.4.2001.Failure.Is.Not.An.Option.iNT.DVDRip.XVID-vRs
			if ("subs" in sfv_name.lower() and 
				re.match(".*cd\d.*", sfv_name, re.IGNORECASE)):
				pass
			else:
				continue
		# subs not in filename, but the folder is called subs, vobsubs,...
		pardir = os.path.split(os.path.dirname(sfv))[1].lower()
		if ("subs" == pardir or "vobsubs" == pardir or "vobsub" == pardir or
			"subtitles" == pardir or "sub" == pardir or "subpack" == pardir):
			# X-Files.1x00.Pilot.DVDRip.XviD-SDG\Subtitles
			# Scary.Movie.2000.INTERNAL.DVDivX-KiNESiS\Sub\kns-sm-sub.rar
			continue
		
		# subpack inside release dir
		if "subpack" in sfv.lower() or "subfix" in sfv.lower():
			continue
		
		wanted = True
		# not wanted if SFV contains .mp3 or .flac files
		for sfvf in rescene.utility.parse_sfv_file(sfv)[0]:
			if (sfvf.file_name.endswith(".mp3") or 
				sfvf.file_name.endswith(".flac")):
				wanted = False
				break
		
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
	except IOError, e:
		print("Could not copy %s." % copy_file)
		print("Reason: %s" % e)
		if "[Errno 2] No such file or directory" in str(e) and os.name == "nt":
			print("Trying again!")
			try:
				shutil.copyfile("\\\\?\\" + copy_file, dest_file)
			except IOError, e:
				print("Failed again...")

	return dest_file

def generate_srr(reldir, working_dir, options):
	assert os.listdir(working_dir) == []
	
	mthread = MessageThread()
	msgs = [MsgCode.FILE_NOT_FOUND, MsgCode.UNKNOWN, MsgCode.MSG]
	mthread.set_messages(msgs)
	mthread.start()
	
	print(reldir)
	if options.srr_in_reldir:
		srr_directory = reldir
	else:
		srr_directory = options.output_dir
	srr = os.path.join(srr_directory, os.path.split(reldir)[1] + ".srr")
	
	sfvs = get_files(reldir, "*.sfv")
	main_sfvs = remove_unwanted_sfvs(sfvs)
	main_rars = get_start_rar_files(main_sfvs)
	
	if len(main_sfvs):
		try:
			result = rescene.create_srr(srr, main_sfvs, reldir, [], True, 
			                   options.compressed)
			mthread.done = True
			mthread.join()
			
			# when the user decides not to overwrite an existing SRR
			if not result:
				return False
		except IOError:
			print("Read error. DVD disk unreadable? Try again!")
			os.unlink(srr)
			return False
		except KeyboardInterrupt, e:
			if e.message != "DONT_DELETE":
				os.unlink(srr)
			raise
		except FileNotFound:
			# rescene doesn't leave a half finished file
			return False
		except (ValueError, EnvironmentError):
			# e.g. 0 byte RAR file
			# EnvironmentError: Invalid RAR block length (0) at offset 0xe4e1b1
			try:
				os.unlink(srr)
			except WindowsError:
				pass
			return False
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
		
		# copying the sample file to the temp directory failed
		# temp path too long? nope! rights issue still possible
		if not os.path.exists(current_sample):
			print("!!! Skipping this sample file.")
			continue
		
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
			original_stderr = sys.stderr
			txt_error_file = current_sample + ".txt"
			sys.stderr = open(txt_error_file, "wb")
			keep_txt = False
			try:
				srsmain([current_sample, "-y", "-o", 
				         os.path.dirname(current_sample)], True)
				copied_files.append(current_sample[:-4] + ".srs")
			except ValueError:
				keep_txt = True
				copied_files.append(txt_error_file)
				
			sys.stderr.close()
			if not keep_txt:
				os.unlink(txt_error_file)
				
			sys.stderr = original_stderr
		try:
			os.unlink(current_sample)
		except WindowsError:
			# this should never happen, but apparently it did
			pass
		
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
			print("Waiting 5 seconds for mount.")
			time.sleep(5)
		
	for dirpath, dirnames, filenames in os.walk(path):
		if last_release in dirpath and last_release:
			continue # subfolders of a found release
		
		if is_release(dirpath, dirnames, filenames):
			last_release = dirpath
			yield last_release
			
def is_release(dirpath, dirnames=None, filenames=None):
	if dirnames == None:
		l = lambda x: not os.path.isfile(os.path.join(dirpath, x))
		dirnames = filter(l, os.listdir(dirpath))
	if filenames == None:
		l = lambda x: os.path.isfile(os.path.join(dirpath, x))
		filenames = filter(l, os.listdir(dirpath))
		
	release = False
	# A folder is considered being an original scene release directory when
	# there is an .nfo file or an .sfv file
	# or an .sfv file in a CDx/DiskX subdir (when nfo file is missing)
	for filename in filenames:
		if (filename[-4:].lower() in (".nfo", ".sfv") and
			filename not in ("motechnetfiles.nfo", "movie.nfo", "imdb.nfo",
							"scc.nfo")):
			release = True
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
					break
			if release:
				break

	rel_folders = ("^((CD|DISK)\d)|(Vob)?Samples?|Covers?|Proofs?|"
	               "Subs?(pack)?|(vob)?subs?$")
	if release and not re.match(rel_folders, dirpath, re.IGNORECASE):
		release = True
	else:
		return False
	
	# season torrent packs have often an additional NFO file in the root
	# don't detect as a release if this is the case
	if len(filenames) == 1 and filenames[0].lower()[-4:] == ".nfo":
		# could still be a regular release with multiple CDs
		# each other subdir must be a release dir -> not reldir itself
		release = False
		for reldir in dirnames:
			if not is_release(os.path.join(dirpath, reldir)):
				release = True
				break
				
	return release 

def main(argv=None):
	parser = OptionParser(
	usage=("Usage: %prog [directories] [options]\n"
	"This tool can automatically create a complete SRR file for a "
	"release directory. Example usage: %prog -r E:\ -o D:\ -s -c"), 
	version="%prog " + rescene.__version__) # --help, --version
	
	parser.add_option("-y", "--always-yes", dest="always_yes", default=False,
					  action="store_true",
					  help="assume Yes for all prompts")
	parser.add_option("-n", "--always-no", dest="always_no", default=False,
					  action="store_true",
					  help="assume No for all prompts")
	
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
	parser.add_option("-d", "--srr-in-reldir",
					 action="store_true", dest="srr_in_reldir",
					 help="overrides -o parameter")
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
	
	if options.always_yes and options.always_no:
		print("Is it 'always yes' (-y) or 'always no' (-n)?")
		return 0

	# check for existence output directory
	options.output_dir = os.path.abspath(options.output_dir)
	if not os.path.exists(options.output_dir):
		if can_create(options.always_yes, options.output_dir):
			os.makedirs(options.output_dir)
		else:
			print("No output directory created.")
			return 0
			
	# overwrite user input request function
	def can_overwrite(file_path):
		retvalue = True 
		if not options.always_yes and os.path.isfile(file_path):
			# when a user does not want to process releases he has already done
			if options.always_no:
				return False
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
	aborted = False
	missing = []
	try:
		for reldir in indirs:
			reldir = os.path.abspath(reldir)
			if not options.recursive:
				result = generate_srr(reldir, working_dir, options)
				if not result:
					missing.append(reldir)
			else:
				for release_dir in get_release_directories(reldir):
					try:
						result = generate_srr(release_dir, working_dir, options)
					except FileNotFound:
						result = False
					if not result:
						missing.append(release_dir)
			# gather drive info
			drive_letters.append(reldir[:2])
	except KeyboardInterrupt:
		print("Process aborted.")
		aborted = True
	if len(missing):
		print("")
		print("------------------------------------")
		print("Warning: some SRRs were not created!")
		for item in missing:
			print(item)
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
		
	if aborted or len(missing):
		return 1
	else:
		return 0

if __name__ == "__main__":
	sys.exit(main())
	
