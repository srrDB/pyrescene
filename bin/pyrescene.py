#!/usr/bin/env python
# encoding: utf-8

# Copyright (c) 2012-2013 pyReScene
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
from datetime import datetime
import sys
import os
import re
import shutil
import fnmatch
import time
import logging

try:
	import _preamble
except ImportError:
	sys.exc_clear()
	
import rescene
from resample.srs import main as srsmain
from rescene.srr import MessageThread
from rescene.main import MsgCode, FileNotFound
from rescene.rar import RarReader, BlockType
from rescene.utility import empty_folder
from resample.fpcalc import ExecutableNotFound, MSG_NOTFOUND
from resample.main import get_file_type, sample_class_factory

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
	"""Gather all 'extension' files from the subdirs."""
	matches = []
	try:
		for dirpath, _dirnames, filenames in os.walk(release_dir):
			for filename in filenames:
				if fnmatch.fnmatchcase(filename.lower(), extention.lower()):
					matches.append(os.path.join(dirpath, filename))
		return matches
	except TypeError:
		# release_dir too long
		# TypeError: must be (buffer overflow), not str
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

def get_music_files(reldir):
	return get_files(reldir, "*.mp3") + get_files(reldir, "*.flac")

def get_proof_files(reldir):
	"""
	Includes proofs, proof RAR files, image files in Sample directories.
	"""
	image_files = (get_files(reldir, "*.jpg") + get_files(reldir, "*.png") + 
	               get_files(reldir, "*.gif") + get_files(reldir, "*.bmp") +
	               get_files(reldir, "*.jpeg"))
	rar_files = get_files(reldir, "*.rar")
	result = []
	for proof in image_files:
		# images in Sample and Proof folders are ok
		# others need to contain the word proof in their path
		if "proof" in proof.lower() or "sample" in proof.lower():
			result.append(proof)
		else:
			# proof file in root dir without the word proof somewhere
			# no spaces: skip personal covers added to mp3 releases
			# NOT: desktop.ini, AlbumArtSmall.jpg, 
			# AlbumArt_{7E518F75-1BC4-4CD1-92B4-B349D9E9248B}_Large.jpg 
			# AlbumArt_{7E518F75-1BC4-4CD1-92B4-B349D9E9248B}_Small.jpg 
			if (os.path.getsize(proof) > 100000 and 
				" " not in os.path.basename(proof) and
				not proof.lower()[:-4].endswith("folder") and
				"albumartsmall" not in proof.lower() and
				not os.path.basename(proof).lower().startswith("albumart_{")):
				# must be named like nfo/rars or start with 00
				if os.path.basename(proof).lower().startswith("00"):
					# this way for mp3 releases
					result.append(proof)
					continue
				# idea is to not have covers that are added later
				s = 10
				for nfo in get_files(reldir, "*.nfo"):
					if os.path.basename(nfo)[:-4][:s] == proof[:-4][:s]:
						result.append(proof)
						continue
				for rar in rar_files:
					if os.path.basename(rar)[:-4][:s] == proof[:-4][:s]:
						result.append(proof)
						continue	
	for proof in rar_files:
		if "proof" in proof.lower():
			# RAR file must contain image file
			for block in RarReader(proof):
				if block.rawtype == BlockType.RarPackedFile:
					if (block.file_name[-4:] in 
						(".jpg", "jpeg", ".png", ".bmp", ".gif")):
						result.append(proof)
						break
	return result

def remove_unwanted_sfvs(sfv_list, release_dir):
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
			"subtitles" == pardir or "sub" == pardir or "subpack" == pardir or
			"vobsubs-full" == pardir or "vobsubs-light" == pardir or
			"codec" == pardir or "codecs" == pardir or "cover" == pardir or
			"covers" == pardir):
			# X-Files.1x00.Pilot.DVDRip.XviD-SDG\Subtitles
			# Scary.Movie.2000.INTERNAL.DVDivX-KiNESiS\Sub\kns-sm-sub.rar
			# Play.Misty.For.Me.1971.DVDRip.XviD.INTERNAL-FaRM/Vobsubs-Full/
			# Kellys.Heroes.1970.iNTERNAL.DVDRip.XviD-BELiAL/Codec/
			# Barnstormers.360.2005.DVDRip.XviD-AEROHOLiCS\Cover\
			continue
		
		# subpack inside release dir
		if "subpack" in sfv.lower() or "subfix" in sfv.lower():
			continue
		
		# Two.Weeks.Notice.DVDRiP.XviD.FIX-FIXRUS inside release dir
		# Mr.Fix.It.2006.PROPER.REPACK.DVDRip.XviD-VoMiT release dir
		if "fix" in pardir and not "fix" in release_dir.lower():
			continue
		
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

def key_sort_music_files(name):
	# nfo files at the top
	if name[-4:].lower() == ".nfo":
		return "-"
	else:
		return name 
	
def generate_srr(reldir, working_dir, options):
	assert os.listdir(working_dir) == []
	print(reldir)
	if options.srr_in_reldir:
		srr_directory = reldir
	else:
		srr_directory = options.output_dir
	srr = os.path.join(srr_directory, os.path.split(reldir)[1] + ".srr")
		
	# speedup: don't do stuff when we don't overwrite an existing SRR anyway
	if options.always_no and os.path.exists(srr):
		return False
	
	sfvs = get_files(reldir, "*.sfv")
	main_sfvs = remove_unwanted_sfvs(sfvs, reldir)
	main_rars = get_start_rar_files(main_sfvs)
	
	# create SRR from RARs or from .mp3 or .flac SFV
	if len(main_sfvs):
		try:
			result = rescene.create_srr(srr, main_sfvs, reldir, [], True, 
			                   options.compressed)
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
			except: # WindowsError
				pass
			return False
	else:
		return False
	
	# remove all stored files so we can add them all in the right order again
	rescene.remove_stored_files(srr, rescene.info(srr)["stored_files"])
	
	# copy all files to store to the working dir + their paths
	copied_files = []
	is_music = False
	for nfo in get_files(reldir, "*.nfo"):
		if nfo.lower() in ("imdb.nfo"):
			continue
		copied_files.append(copy_to_working_dir(working_dir, reldir, nfo))

	for m3u in get_files(reldir, "*.m3u"):
		copied_files.append(copy_to_working_dir(working_dir, reldir, m3u))		
		
	for proof in get_proof_files(reldir):
		copied_files.append(copy_to_working_dir(working_dir, reldir, proof))
		
	for log in get_files(reldir, "*.log"):
		if log.lower() in ("rushchk.log", ".upchk.log"):
			continue
		copied_files.append(copy_to_working_dir(working_dir, reldir, log))
		
	for cue in get_files(reldir, "*.cue"):
		copied_files.append(copy_to_working_dir(working_dir, reldir, cue))
		
	# when stored SRS file instead of a sample file
	# or both, but only one SRS will be added later
	for srs in get_files(reldir, "*.srs"):
		copied_files.append(copy_to_working_dir(working_dir, reldir, srs))

	# Create SRS files
	for sample in get_sample_files(reldir) + get_music_files(reldir):
		# avoid copying samples
		path = os.path.relpath(sample, reldir)
		dest_dir = os.path.dirname(os.path.join(working_dir, path))
		
		# make in between dirs
		try:
			os.makedirs(dest_dir)
		except:
			pass

		is_music = (sample.lower().endswith(".mp3") or
		            sample.lower().endswith(".flac"))
		
		# optionally check against main movie files
		# if an SRS file can be created, it'll be added
		found = False
		if options.sample_verify and not is_music:
			print("Checking against the following main files:")
			for mrar in main_rars:
				print("\t%s" % mrar)
			for main in main_rars:
				try:
					srsmain([sample, "-y", "-o", dest_dir, "-c", main], True)
					copied_files.append(os.path.join(dest_dir, 
						os.path.basename(sample))[:-4] + ".srs")
					found = True
					break
				except ValueError:
					print("Sample not found in %s." % main)	
			if not found:
				logging.info("%s: Sample failed to verify against main files: "
				             "%s" % (reldir, os.path.basename(sample)))
		if not found:
			original_stderr = sys.stderr
			txt_error_file = os.path.join(dest_dir, 
				os.path.basename(sample)) + ".txt"
			sys.stderr = open(txt_error_file, "wb")
			keep_txt = False
			try:
				srsmain([sample, "-y", "-o", dest_dir], True)
				if sample[-4:].lower() == "flac":
					copied_files.append(os.path.join(dest_dir, 
						os.path.basename(sample))[:-5] + ".srs")
				else:
					copied_files.append(os.path.join(dest_dir, 
						os.path.basename(sample))[:-4] + ".srs")
			except ValueError:
				keep_txt = True
				copied_files.append(txt_error_file)
				logging.info("%s: Could not create SRS file for %s." %
				             (reldir, os.path.basename(sample)))
				
				# fpcalc executable isn't found
				if str(sys.exc_info()[1]).endswith(MSG_NOTFOUND):
					# do cleanup
					sys.stderr.close()
					sys.stderr = original_stderr
					os.unlink(srr)
					empty_folder(working_dir)
					raise ExecutableNotFound("Please put the fpcalc "
						"executable in your path.")
					
			sys.stderr.close()
			if not keep_txt:
				os.unlink(txt_error_file)
				
			sys.stderr = original_stderr
		
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
	
	# remove possible duplicate SRS files
	copied_files = list(set(copied_files))
		
	if is_music:
		# sort files on filename, but nfo file first
		copied_files.sort(key=key_sort_music_files)
		
		# don't add files that fail sfv
		crclist = {}
		for sfv in sfvs:
			for sfvf in rescene.utility.parse_sfv_file(sfv)[0]:
				crclist[sfvf.file_name.lower()] = sfvf.crc32
		
		to_remove = []
		for stored_file in copied_files:
			if stored_file[-4:].lower() == ".srs":
				try:
					sample = sample_class_factory(get_file_type(stored_file))
					srs_data, _tracks = sample.load_srs(stored_file)
					# accept SRS if it isn't in the SFV
					crc = int(crclist.get(srs_data.name.lower(), "-1"), 16)
					if srs_data.crc32 != crc and crc != -1:
						to_remove.append(stored_file)
						logging.critical("%s: SFV verification failed for %s."
										% (reldir, srs_data.name))
				except IOError:
					logging.critical("%s: FLAC with ID3 tag: %s." % 
						             (reldir, os.path.basename(stored_file)))
					to_remove.append(stored_file)
					
		for removed_file in to_remove:
			copied_files.remove(removed_file)
			
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
			
DISK_FOLDERS = re.compile("^(CD|DISK|DVD|DISC)_?\d$", re.IGNORECASE)
RELEASE_FOLDERS = re.compile("^((CD|DISK|DVD|DISC)_?\d|(Vob)?Samples?|"
	"Covers?|Proofs?|Subs?(pack)?|(vob)?subs?)$", re.IGNORECASE)
			
def is_release(dirpath, dirnames=None, filenames=None):
	if dirnames == None:
		l = lambda x: not os.path.isfile(os.path.join(dirpath, x))
		dirnames = filter(l, os.listdir(dirpath))
	if filenames == None:
		l = lambda x: os.path.isfile(os.path.join(dirpath, x))
		filenames = filter(l, os.listdir(dirpath))
		
	release = False
	# A folder is considered being an original scene release directory when
	# there is a .nfo file or a .sfv file
	# or a .sfv file in a CDx/DiskX subdir (when nfo file is missing)
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
			# Disc_1 and Disc_2 in mp3 rlz
			if DISK_FOLDERS.match(dirname):
				interesting_dirs.append(dirname)
		
		for idir in interesting_dirs:
			for lfile in os.listdir(os.path.join(dirpath, idir)):
				if lfile[-4:].lower() == ".sfv":
					release = True
					break
			if release:
				break
	
	# X3.Gold.Edition-Unleashed has DISC
	if release and not RELEASE_FOLDERS.match(os.path.basename(dirpath)):
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
	
	# a release name doesn't have spaces in its folder name
	(head, tail) = os.path.split(dirpath)
	if not tail:
		(_head, tail) = os.path.split(head)
	if " " in tail: 
		release = False
				
	return release 

def main(argv=None):
	start_time = datetime.now()
	parser = OptionParser(
	usage=("Usage: %prog [directories] [options]\n"
	"This tool can automatically create a complete SRR file for a "
	"release directory.\n"
	"Example usage: %prog --recursive E:\ --output D:\ -s -c"), 
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
	parser.add_option("-l", "--report",
					action="store_true", dest="report",
					help="reports which samples had issues")
	parser.add_option("-t", "--temp-dir", dest="temp_dir", default="",
					metavar="DIRECTORY", help="Specify temporary directory. "
					"Music files and samples will be written to this dir.")
		
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
			
	if options.report:
		now = datetime.now()
		fn = os.path.join(options.output_dir, 
						"pyReScene_report_%s.txt" % now.strftime("%Y-%m-%d"))
		# log will append by default
		logging.basicConfig(filename=fn, level=logging.INFO,
		                    format="%(levelname)s:%(message)s")
		
	# create temporary working dir
	if options.temp_dir and len(options.temp_dir):
		options.temp_dir = os.path.abspath(options.temp_dir)
	else:
		options.temp_dir = None
	working_dir = mkdtemp(".pyReScene", dir=options.temp_dir)
	
	drive_letters = []
	aborted = False
	missing = []
	try:
		mthread = MessageThread()
		msgs = [MsgCode.FILE_NOT_FOUND, MsgCode.UNKNOWN, MsgCode.MSG]
		mthread.set_messages(msgs)
		mthread.start()

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
						logging.warning("%s: SRR could not be created." % 
									release_dir)
			# gather drive info
			drive_letters.append(reldir[:2])
	except KeyboardInterrupt:
		print("Process aborted.")
		aborted = True
	except ExecutableNotFound:
		print("----------------------------------------------------")
		print("Please put the fpcalc executable in your path.")
		print("It can be downloaded from ")
		print("https://bitbucket.org/acoustid/chromaprint/downloads")
		print("It is necessary for the creation of music SRS files.")
		print("----------------------------------------------------")
		aborted = True
	finally:
		try:
			mthread.done = True
			mthread.join()
		except:
			print("Failure stopping the MessageThread.")
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
		
	print(datetime.now()-start_time)
		
	# test the errorlevel with:
	# echo %errorlevel%
	# echo $?
	if aborted or len(missing):
		return 1
	else:
		return 0

if __name__ == "__main__":
	sys.exit(main())
	
