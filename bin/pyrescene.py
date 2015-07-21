#!/usr/bin/env python
# encoding: utf-8

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

from __future__ import print_function
from optparse import OptionParser, OptionGroup  # argparse new in version 2.7
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
	import win32api
	win32api_available = True
except ImportError:
	win32api_available = False

try:
	import _preamble
except ImportError:
	pass

import rescene
from resample.srs import main as srsmain
from rescene.srr import MessageThread
from rescene.main import MsgCode, FileNotFound, custom_popen
from rescene.rar import RarReader, BlockType
from rescene.utility import empty_folder, _DEBUG, parse_sfv_file
from rescene.unrar import locate_unrar
from resample.fpcalc import ExecutableNotFound, MSG_NOTFOUND
from resample.main import file_type_info, sample_class_factory
from rescene.utility import raw_input, unicode, fsunicode
from rescene.utility import decodetext, encodeerrors
from rescene.utility import create_temp_file_name, replace_result

o = rescene.Observer()
rescene.subscribe(o)

rescene.change_rescene_name_version("pyReScene Auto %s" % rescene.__version__)

unrar_executable = None

def get_unrar():
	"""Locate unrar executable only once"""
	global unrar_executable
	if not unrar_executable:
		unrar_executable = locate_unrar()
	return unrar_executable

def unrar_is_available():
	return os.path.isfile(os.path.abspath(get_unrar()))

def can_create(always_yes, path):
	retvalue = True 
	if not always_yes and os.path.isfile(path):
		print("Warning: %s does not exist. Create it? " % path)
		char = raw_input("Do you wish to continue? (Y/N): ").lower()
		while char not in ('y', 'n'):
			char = raw_input("Do you wish to continue? (Y/N): ").lower()
		if char == 'n':
			retvalue = False
	return retvalue

def get_files(release_dir, extension):
	"""Gather all 'extension' files from the subdirs."""
	matches = []
	try:
		for dirpath, _dirnames, filenames in os.walk(release_dir):
			for filename in filenames:
				if fnmatch.fnmatchcase(filename.lower(), extension.lower()):
					matches.append(os.path.join(dirpath, filename))
		return matches
	except TypeError:
		# release_dir too long
		# TypeError: must be (buffer overflow), not str
		return matches

def get_sample_files(reldir):
	# .m4v is used for some non scene samples and music releases
	# It is the same file format as MP4
	# VA-Anjunabeats_Vol_7__Mixed_By_Above_And_Beyond-(ANJCD014D)-2CD-2009-TT/
	#     301-va-anjunabeats_vol_7__bonus_dvd-tt.m4v
	# Gothic_3_Soundtrack-Promo-CD-2006-XARDAS/
	#     05_g3_makingofst-xardas.wmv
	#     06_g3_makingofst-xardas.m4v
	# System_Of_A_Down-Aerials-svcd-wcs
	#     system_of_a_down-aerials-svcd-wcs.m2p
	sample_files = (get_files(reldir, "*.avi") + get_files(reldir, "*.mkv") + 
	                get_files(reldir, "*.mp4") + get_files(reldir, "*.m4v") +
	                get_files(reldir, "*.wmv"))
	result = []
	not_samples = []
	for sample in sample_files:
		# sample folder or 'sample' in the name
		# or a musicvideo file (SFV with same name)
		if ("sample" in sample.lower() or 
		    os.path.exists(sample[:-4] + ".sfv")):
			result.append(sample)
		else:
			not_samples.append(sample)
			
	# this is for music videos with multiple MKVs
	# this way so we don't always have to read in the SFV files unnecessarily
	if len(not_samples):
		sfv_stored_files = []
		sfv_files = get_files(reldir, "*.sfv")
		for sfv in sfv_files:
			for entry in parse_sfv_file(sfv)[0]:
				sfv_stored_files.append(entry.file_name)
		for nsample in not_samples:
			if os.path.basename(nsample) in sfv_stored_files:
				result.append(nsample)
			
	return result

def get_music_files(reldir):
	# .mp2: seen in very old releases e.g. u-Ziq-In.Pine.Effect-DAC (1998)
	return (get_files(reldir, "*.mp3") + get_files(reldir, "*.mp2") +
			get_files(reldir, "*.flac"))

def get_proof_files(reldir):
	"""
	Includes proofs, proof RAR files, image files in Sample directories.
	Images from Cover(s)/ folder. Mostly seen on XXX and DVDR releases.
	"""
	image_files = (get_files(reldir, "*.jpg") + get_files(reldir, "*.png") + 
	               get_files(reldir, "*.gif") + get_files(reldir, "*.bmp") +
	               get_files(reldir, "*.jpeg"))
	rar_files = get_files(reldir, "*.rar")
	result = []
	for proof in image_files:
		# images in Sample, Proof and Cover(s) subdirs are ok
		# others need to contain the word proof in their path
		lproof = proof.lower()
		if ("proof" in lproof or "sample" in lproof or 
			os.sep + "cover" in lproof):
			result.append(proof)
		else:
			# proof file in root directory without the word proof somewhere
			# no spaces: skip personal covers added to mp3 releases
			# NOT: desktop.ini, AlbumArtSmall.jpg, 
			# AlbumArt_{7E518F75-1BC4-4CD1-92B4-B349D9E9248B}_Large.jpg 
			# AlbumArt_{7E518F75-1BC4-4CD1-92B4-B349D9E9248B}_Small.jpg 
			if (" " not in os.path.basename(proof) and
				not lproof[:-4].endswith("folder") and
				"albumartsmall" not in lproof and
				not os.path.basename(lproof).startswith("albumart_{")):
				# must be named like nfo/sfv/rars or start with 00
				
				# 00 for mp3 releases. Mostly 00- but 00_ exists too:
				# VA-Psychedelic_Wild_Diffusion_Part_1-(ESPRODCD01)-CD-2007-hM
				# or 000- and 01- or 01_
				if os.path.basename(proof).startswith(("00", "01")):
					result.append(proof)
					continue
				# idea is to not have covers that are added later
				# non music releases have a separate folder
				s = 10 # first X characters
				if os.path.getsize(proof) > 100000:
					similar_named = False
					for nfo in get_files(reldir, "*.nfo"):
						if (os.path.basename(nfo)[:-4][:s].lower() == 
							os.path.basename(proof)[:-4][:s].lower()):
							similar_named = True
							break
					# for music releases, NFOs not always start with 00
					# while all the other files do (sfv, m3u, jpg, cue,...)
					# e.g. Hmc_-_187_(UDR011)-VLS-1996-TR
					for sfv in get_files(reldir, "*.sfv"):
						if (os.path.basename(sfv)[:-4][:s].lower() == 
							os.path.basename(proof)[:-4][:s].lower()):
							similar_named = True
							break
					for rar in rar_files:
						if (os.path.basename(rar)[:-4][:s].lower() == 
							os.path.basename(proof)[:-4][:s].lower()):
							similar_named = True
							break
					if similar_named:
						result.append(proof)
				else:
					# TODO: smaller proofs can exist too
					# -> but .startswith("00") already includes those
					# maybe extra option to add all image files
					# and do no separate detection?
					# -> but even directly from topsite there can be
					#    additional unwanted files?
					# small JPGs are most likely site grabs by scripts
					pass
			# ATB_-_Seven_Years-Ltd.Ed.-2005-MOD (small JPG image file)
	for proof in rar_files:
		if "proof" in proof.lower():
			# RAR file must contain image file
			# Space.Dogs.3D.2010.GERMAN.1080p.BLURAY.x264-HDViSiON (bmp proof)
			for block in RarReader(proof):
				if block.rawtype == BlockType.RarPackedFile:
					if (block.file_name[-4:].lower() in 
						(".jpg", "jpeg", ".png", ".bmp", ".gif")):
						result.append(proof)
						break
	return result

def remove_unwanted_sfvs(sfv_list, release_dir):
	"""
	Remove SFVs from subs and certain rarred proof files.
	"""
	wanted_sfvs = []
	lcrelease_name = os.path.basename(release_dir).lower()
	for sfv in sfv_list:
		sfv_name = os.path.basename(sfv)
		
		# Not for actual subpack releases:
		# The.Terminator.1984.MULTi.SUBPACK.For.720p.DEFiNiTiON-KOENiG
		#     koe.the.terminator.720p.multi.vobsubs.sfv
		# A.Beautiful.Mind.VOBSUBS.DVDRip.DivX-FIXRUS
		#     vobsub_abm.sfv
		# Monster.Inc.DiVX.SUB.PACK-SVENNE
		#     svn-mi.sub.pack.sfv
		# Bitch.Slap.2009.NORDiC.SUBS.XviD-CULTSUBS
		#     bs.nordicsubs-cultsubs.sfv
		if (("vobsub" in sfv_name.lower() or "subtitle" in sfv_name.lower())
			and ("subpack" not in lcrelease_name and
				"vobsub" not in lcrelease_name and
				"subtitle" not in lcrelease_name and
				"sub.pack" not in lcrelease_name)):
			continue # SFV won't be appended to wanted_sfvs
		
		# False positives: 
		# The.Substitute.4.2001.Failure.Is.Not.An.Option.iNT.DVDRip.XVID-vRs
		#     the.substitute.4.vrs.cd1.rar 92341f72
		# RV800-Subsync-(FORM001)-READNFO-VINYL-FLAC-2012-dL
		#     00-rv800-subsync-(form001)-vinyl-flac-2012.sfv
		# Many music releases didn't create at all:
		# Substantial-Art_Is_Where_The_Home_Is-2014-FTD
		#     00-substantial-art_is_where_the_home_is-2014-ftd.sfv
		# The.Dark.Knight.DVDRip.XviD.SUBFIX-DoNE
		#     tdk-subs-done.sfv
		if ("subs" in sfv_name.lower() and 
			# music or release with multiple CDs (xvid)
			(re.match("^000?-|.*(cd\d|flac).*", sfv_name, re.IGNORECASE) or
				"subs" in lcrelease_name or
				"subpack" in lcrelease_name or
				"vobsub" in lcrelease_name or
				"subtitle" in lcrelease_name or
				"subfix" in lcrelease_name or
				"sub.pack" in lcrelease_name)):
			pass # continue to the next checks
		elif "subs" in sfv_name.lower():
			continue # SFV won't be appended to wanted_sfvs
		
		# subs not in filename, but the folder is called subs, vobsubs,...
		pardir = os.path.split(os.path.dirname(sfv))[1].lower()
		if pardir in (
			"subs", "vobsubs", "vobsub", "subtitles", "sub",
			"subpack", "vobsubs-full", "vobsubs-light", "codec",
			"codecs", "cover", "covers",
		):
			# X-Files.1x00.Pilot.DVDRip.XviD-SDG\Subtitles
			# Scary.Movie.2000.INTERNAL.DVDivX-KiNESiS\Sub\kns-sm-sub.rar
			# Play.Misty.For.Me.1971.DVDRip.XviD.INTERNAL-FaRM/Vobsubs-Full/
			# Kellys.Heroes.1970.iNTERNAL.DVDRip.XviD-BELiAL/Codec/
			# Barnstormers.360.2005.DVDRip.XviD-AEROHOLiCS\Cover\
			continue
		
		if (pardir == "proof" or pardir == "proofs"):
			# only if it's one RAR file containing an image
			sfvfiles = rescene.utility.parse_sfv_file(sfv)[0]
			if len(sfvfiles) == 1:
				rar = os.path.join(os.path.dirname(sfv), sfvfiles[0].file_name)
				if os.path.isfile(rar):
					skip = False
					for block in RarReader(rar):
						if block.rawtype == BlockType.RarPackedFile:
							if (block.file_name[-4:].lower() in 
								(".jpg", "jpeg", ".png", ".bmp", ".gif")):
								skip = True
							else:
								skip = False
					if skip:
						continue
		
		if re.match(".*Subs.?CD\d$", os.path.dirname(sfv), re.IGNORECASE):
			# Toy.Story.1995.DVDRip.DivX.AC3.iNTERNAL-FFM/
			#	Subs/CD1/toyst.subs.cd1-iffm.sfv
			continue
		
		# subpack inside release dir not, but subpack release itself yes
		if "subpack" in pardir and not "subpack" in lcrelease_name:
			continue
		if "subfix" in pardir and not "subfix" in lcrelease_name:
			continue
		
		# Two.Weeks.Notice.DVDRiP.XviD.FIX-FIXRUS inside release dir
		# Mr.Fix.It.2006.PROPER.REPACK.DVDRip.XviD-VoMiT release dir
		if "fix" in pardir and not "fix" in lcrelease_name:
			continue
		
		wanted_sfvs.append(sfv)
	
	# If there is no SFV wanted because of 'subs' in the file name
	# Sub.Sam.2012.FESTiVAL.DVDRip.XviD-EXViD exvid-subsam.sfv
	# - Choose the SFV for music
	# - Choose the SFVs for more than 1 archive volume
	# (Vobsubs in a release are most of the time 1 SFV and 1 RAR.
	#  If there are more RARs, there are often more SFVs too.
	#  One SFV with two RAR files does exist in the wild, but
	#  extremely rare.)
	# + 'subs' in sfv names even more so. In that case the vobsubs
	# will be seen as main archive volumes.
	def has_music(sfv_file_lines):
		for sfv_file_line in sfv_file_lines:
			if sfv_file_line.file_name.endswith((".mp3", ".flac", ".mp2")):
				return True
		return False
	
	if len(wanted_sfvs) == 0:
		for sfv in sfv_list:
			sfvfiles = rescene.utility.parse_sfv_file(sfv)[0]
			if len(sfvfiles) > 1 or has_music(sfvfiles):
				wanted_sfvs.append(sfv)
	
	# Still nothing? 
	if len(wanted_sfvs) == 0:
		logging.info("%s might be missing an SFV file." %
		             os.path.basename(release_dir))
				
	return wanted_sfvs

def get_unwanted_sfvs(allsfvs, wantedsfvs):
	return list(set(allsfvs)-set(wantedsfvs))
	
def get_start_rar_files(sfv_list):
	"""
	Get the main first RAR files to check sample against.
	"""
	wanted_rars = []
	for sfv in sfv_list:
		firsts = rescene.utility.first_rars(x.file_name for x in 
		         rescene.utility.parse_sfv_file(sfv)[0])
		# Asterix.and.Obelix.Mission.Cleopatra.2002.DVDRip.XviD-AEN/Subs/
		# aaomc-nl-subs-aen.sfv contains two different RAR sets:
		# aaomc-nl-subs-aen.rar and aaomc-uk-subs-aen.rar
		for first in firsts:
			wanted_rars.append(os.path.join(os.path.dirname(sfv), first))
	return wanted_rars

def work_dir_file(relfile, release_dir, working_dir):
	path = os.path.relpath(relfile, release_dir)
	dest_file = os.path.join(working_dir, path)
	return dest_file

def copy_to_working_dir(working_dir, release_dir, copy_file):
	"""
	working_dir: temporary directory with all the files to store in the SRR
	release_dir: release folder with path
	copy_file: file somewhere inside the release_dir
	"""
	dest_file = work_dir_file(copy_file, release_dir, working_dir)
	
	try:
		# make in between dirs
		os.makedirs(os.path.dirname(dest_file))
	except:
		pass
	
	try:
		# copy over file
		shutil.copyfile(copy_file, dest_file)	
	except IOError as e:
		print("Could not copy %s." % copy_file)
		print("Reason: %s" % e)
		if "[Errno 2] No such file or directory" in str(e) and os.name == "nt":
			print("Trying again!")
			try:
				shutil.copyfile("\\\\?\\" + copy_file, dest_file)
			except IOError:
				print("Failed again...")

	return dest_file

def key_sort_music_files(name):
	# nfo files at the top
	if name[-4:].lower() == ".nfo":
		return "-"
	else:
		return name
	
def is_storable_fix(release_name):
	"""Tests if we can store the main RAR file of this release."""
	#Rules.of.Engagement.S02E03.Mr.Fix.It.DVDRip.XviD-SAiNTS
	#Ron.White.You.Cant.Fix.Stupid.XviD-LMG
	#not: Rar|sub|audio|sample|
	return (re.match(
			".*(SFV|PPF|sync|proof?|dir|nfo|Interleaving|Trackorder).?"
			"(Fix|Patch).*", release_name, re.IGNORECASE) or 
			re.match(".*\.(FiX|FIX)(\.|-).*", release_name) or
			re.match(".*\.DVDR.Fix-.*", release_name) or
			re.match(".*\.DVDR.REPACK.Fix-.*", release_name))
	
def create_srr_for_subs(unrar, sfv, working_dir, release_dir):
	"""
	unrar: location to the unrar executable
	sfv: the sfv file from the vobsubs
	working_dir: our current working directory
		where the generated SRR file will be placed
	release_dir: used to determine in which subfolders the resulting SRR
		file should be placed in the working_dir
	
	return: list of SRR files to add to the main SRR
	"""
	# replicate subdirs from the release folder
	path = os.path.relpath(sfv, release_dir)
	dest_file = os.path.join(working_dir, path)
	try:
		# try to create only the path without SFV/RAR file part
		os.makedirs(os.path.dirname(dest_file))
	except:
		pass # the path already exists

	idx_lang = os.path.join(working_dir, "languages.diz")
	
	# recursively create SRR and extract RARs
	def extract_and_create_srr(folder, srr_out=None, first_rars=None):
		"""
		folder: working dir location for .srr output
		srr_out: location and name of the .srr file to create (first step only)
		first_rars: the first .rar files from the .sfv
		"""
		# find first RAR files in folder
		if first_rars:
			first_level = True # RARS not somewhere in the temp folder
		else:
			first_rars = rescene.utility.first_rars(os.listdir(folder))
			first_rars = [os.path.join(folder, x) for x in first_rars]
			first_level = False
		if not len(first_rars):
			return []
		if not os.path.isdir(folder):
			# create the missing folder
			head, tail =  os.path.split(folder)
			if os.name == "nt" and win32api_available:
				head = win32api.GetShortPathName(head)
			try:
				os.mkdir(os.path.join(head, tail))
			except OSError:
				pass
		
		result = []
		
		for fr in first_rars:
			srr_files_to_store = []
	
			# dest srr name
			new_srr = os.path.join(folder, os.path.basename(fr)[:-4]) + ".srr"

			# use a short random name for the folder
			random_subfolder = (hex(hash(fr)))[-3:]
			dest = os.path.join(folder, random_subfolder)
			counter = 1
			while os.path.exists(dest):
				# for the very rare cases it exists (hash collision)
				dest = os.path.join(folder, str(counter))
				counter += 1
			mk_long_dir(dest)
					
			if not os.path.isdir(dest):
				# otherwise unrar will still extract the files,
				# but it'll put them in the source folder
				# this is never wanted (especially for RAR Subs/ folder!)
				logging.error("Failed to create temp folder for vobsubs: {0}"
				              .format(dest))
				continue
			
			# extract archives
			success = extract_rar(unrar, fr, dest)
			if not success: # probably too long paths issue
				logging.error("Failed to unrar vobsubs: {0}".format(fr))
				continue
			
			# search for idx files and store their language info
			for efile in os.listdir(dest):
				if efile[-4:].lower() == ".idx":
					language_lines = []
					with open(os.path.join(dest, efile), "rb") as idx:
						for line in idx:
							if line.startswith(b"id: "):
								language_lines.append(line)
					with open(idx_lang, "ab") as diz:
						line = "# %s\n" % fsunicode(efile)
						line = line.encode("utf-8", "replace")
						diz.write(line)
						for line in language_lines:
							diz.write(line)
			
			# recursive step for each of the archives
			for srr in extract_and_create_srr(dest):
				srr_files_to_store.append(srr)
		
			if first_level:
				# at same level as SFV (in main SRR), (in temp folder)
				# not in extract folder to prevent possible collisions too
				srr = srr_out  # RAR/SFV without extension

				# only possible for main vobsub set from SFV with multiple RARs
				# Asterix.and.Obelix.Mission.Cleopatra.2002.DVDRip.XviD-AEN
				if srr_out and len(first_rars) > 1:
					# There will be only one root .srr file normally.
					# This could give problems: make one for each set.
					spath = os.path.dirname(srr_out)
					fname = os.path.basename(new_srr)
					srr = os.path.join(spath, fname)
			else:
				srr = new_srr 
			# create SRRs and add SRRs from previous steps
			tmp_srr_name = create_temp_file_name(srr)
			rescene.create_srr(srr, fr, store_files=srr_files_to_store, 
			            save_paths=False, compressed=True, oso_hash=False,
			            tmp_srr_name=tmp_srr_name)
			replace_result(tmp_srr_name, srr)
			result.append(srr)
			
		return result
	
	results = []
	
	# get first RARs from SFV file
	first_rars = get_start_rar_files([sfv])
	if not len(first_rars):
		# it was a bad SFV, but an archive with a similar same name might exist
		sfv_base = sfv[:-4]
		if os.path.isfile(sfv_base + ".rar"):
			first_rars = [sfv_base + ".rar"]
		elif os.path.isfile(sfv_base + ".part1.rar"):
			first_rars = [sfv_base + ".part1.rar"]
		elif os.path.isfile(sfv_base + ".part01.rar"):
			first_rars = [sfv_base + ".part01.rar"]
		elif os.path.isfile(sfv_base + ".001"):
			first_rars = [sfv_base + ".001"]
	if len(first_rars):
		# use a short random name for the first folder
		rand = (hex(hash(first_rars[0])))[-3:]
		srr_folder = os.path.join(os.path.dirname(dest_file), rand)
		counter = 1
		while os.path.exists(srr_folder):
			# for the very rare cases it exists (hash collision)
			srr_folder = os.path.join(os.path.dirname(dest_file), str(counter))
			counter += 1
		# RAR/SFV without extension
		srr = dest_file[:-4] + ".srr"
		for sfile in extract_and_create_srr(srr_folder, srr, first_rars):
			results.append(sfile)
		
	# add languages.diz to the first SRR file only (more SRRs are possible)
	# the file can be missing when the subs are in the .srt format
	# e.g. Battlestar.Galactica.2003.WS.DVDRip.XviD-SFM
	if len(results) and os.path.isfile(idx_lang):
		rescene.add_stored_files(results[0], [idx_lang], save_paths=False)
	
	return results

def extract_rar(unrar, rarfile, destination):
	"""Returns a boolean whether extraction was successful or not."""
	if os.name == "nt" and win32api_available:
		head, tail = os.path.split(rarfile)
		head = win32api.GetShortPathName(head)
		rarfile = os.path.join(head, tail)
	extract = custom_popen([unrar, "e", "-ep", "-o+", 
	                        rarfile, "*", destination])
	(stdout, _) = extract.communicate()
	# even if 'rarfile' isn't the first volume, exctraction still succeeds
			
	if extract.returncode != 0:
		print("Some unrar error occurred:")
		stdout = decodetext(stdout, errors="replace")
		print(encodeerrors(stdout, sys.stdout))
		return False
	return True
			
def mk_long_dir(destination):
	if not os.path.isdir(destination):
		try:
			os.mkdir(destination)
		except OSError:
			# WindowsError: [Error 3]
			try:
				os.mkdir("\\\\?\\" + destination)
			except OSError as e:
				# happens when there is a file with the same name as the dir
				print(e)

def generate_srr(reldir, working_dir, options, mthread):
	if os.listdir(working_dir) != []:
		logging.warning("Failed to clean temp dir: {0}".format(working_dir))
		# Cleaning can fail with PyPy and long dirs: create new working dir
		working_dir = mkdtemp(prefix="SRR-", dir=options.temp_dir)
		print("New temp dir: {0}".format(working_dir))
		
	print(reldir)
	relname = os.path.split(reldir)[1]
	if options.srr_in_reldir:
		srr_directory = reldir
	else:
		srr_directory = options.output_dir
	srr = os.path.join(srr_directory, relname + ".srr")
	tmp_srr_name = create_temp_file_name(srr)
		
	# speedup: don't do stuff when we don't overwrite an existing SRR anyway
	if options.always_no and os.path.exists(srr):
		logging.info("%s: Skipping. SRR already exists." % relname)
		return True
	
	sfvs = get_files(reldir, "*.sfv")
	main_sfvs = remove_unwanted_sfvs(sfvs, reldir)
	main_rars = get_start_rar_files(main_sfvs)
	extra_sfvs = get_unwanted_sfvs(sfvs, main_sfvs)
		
	# create SRR from RARs or from .mp3 or .flac SFV
	if len(main_sfvs):
		try:
			result = rescene.create_srr(srr, main_sfvs, reldir, [], True, 
			                            options.compressed,
									    tmp_srr_name=tmp_srr_name)
			# when the user decides not to overwrite an existing SRR
			if not result:
				return False
		except IOError:
			print("Read error. DVD disk unreadable? Try again!")
			try:
				os.unlink(tmp_srr_name)
			except OSError:
				pass
			return False
		except KeyboardInterrupt as e:
			# always deletes the temp file here
			if e.message != "DONT_DELETE":
				os.unlink(tmp_srr_name)
			raise
		except FileNotFound as e:
			# rescene doesn't leave a half finished file
			print(e)
			return False
		except (ValueError, EnvironmentError) as e:
			# e.g. 0 byte RAR file
			# EnvironmentError: Invalid RAR block length (0) at offset 0xe4e1b1
			try:
				os.unlink(tmp_srr_name)
			except: # WindowsError
				pass
			print(e)
			return False
	else:
		print("No SFV files found.")
		return False
	
	# remove all stored files so we can add them all in the right order again
	rescene.remove_stored_files(tmp_srr_name,
		rescene.info(tmp_srr_name)["stored_files"])
	
	# copy all files to store to the working dir + their paths
	copied_files = []
	is_music = False
	for nfo in get_files(reldir, "*.nfo"):
		if os.path.basename(nfo).lower() in ("imdb.nfo"):
			continue
		copied_files.append(copy_to_working_dir(working_dir, reldir, nfo))

	for m3u in get_files(reldir, "*.m3u"):
		copied_files.append(copy_to_working_dir(working_dir, reldir, m3u))		
		
	for proof in get_proof_files(reldir):
		# also does certain Proof RARs and Covers
		copied_files.append(copy_to_working_dir(working_dir, reldir, proof))
		
	for log in get_files(reldir, "*.log"):
		baselog = os.path.basename(log)
		# blacklist known file names of transfer logs and hidden files
		if (baselog.lower() in ("rushchk.log", ".upchk.log", "ufxpcrc.log") or
			baselog.startswith(b".")):
			continue
		copied_files.append(copy_to_working_dir(working_dir, reldir, log))
		
	for cue in get_files(reldir, "*.cue"):
		copied_files.append(copy_to_working_dir(working_dir, reldir, cue))

	mthread.wait_for_output()
	print()
	
	def get_media_files():
		if options.nosrs:
			return [] # wo don't handle them (traffic, speed, ...)
		else:
			return get_sample_files(reldir) + get_music_files(reldir)
	
	# Create SRS files
	for sample in get_media_files():
		# avoid copying samples
		path = os.path.relpath(sample, reldir)
		dest_dir = os.path.dirname(os.path.join(working_dir, path))
		
		# make in between dirs
		try:
			os.makedirs(dest_dir)
		except:
			pass

		is_music = sample.lower().endswith((".mp3", ".flac", ".mp2"))
		
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
			sys.stderr = open(txt_error_file, "wt")
			keep_txt = False
			try:
				srsmain([sample, "-y", "-o", dest_dir], True)
				if sample[-4:].lower() == "flac":
					copied_files.append(os.path.join(dest_dir, 
						os.path.basename(sample))[:-5] + ".srs")
				else:
					copied_files.append(os.path.join(dest_dir, 
						os.path.basename(sample))[:-4] + ".srs")
			except ValueError as e:
				print("SRS creation failed for %s!" % os.path.basename(sample))
				print()
				
				# do not keep txt files for empty files
				if os.path.getsize(sample) > 0:
					keep_txt = True
					copied_files.append(txt_error_file)
					logging.info("%s: Could not create SRS file for %s." %
					             (reldir, os.path.basename(sample)))
				
				# fpcalc executable isn't found
				if str(e).endswith(MSG_NOTFOUND):
					# do cleanup
					sys.stderr.close()
					sys.stderr = original_stderr
					os.unlink(tmp_srr_name)
					empty_folder(working_dir)
					fpmsg = "Please put the fpcalc executable in your path."
					raise ExecutableNotFound(fpmsg)
					
			sys.stderr.close()
			if not keep_txt:
				os.unlink(txt_error_file)
				
			sys.stderr = original_stderr
		
	# when stored SRS file instead of a sample file
	# or both, but only one SRS will be added 
	for srs in get_files(reldir, "*.srs"):
		path = os.path.relpath(srs, reldir)
		dest_file = os.path.join(working_dir, path)
		if dest_file not in copied_files: # there wasn't a sample
			copied_files.append(copy_to_working_dir(working_dir, reldir, srs))
		else:
			# TODO: pick the best SRS file (checked against main movie file)
			pass

	# stores the main RARs of DVDR fixes
	# these RARs contain cracked .exe files and are not wanted on srrdb.com
	false_positives = [
		"BEYOND.THE.FUTURE.FIX.THE.TIME.ARROWS.EBOOT.PATCH.100.JPN.PS3-N0DRM",
		"The.Raven.Legacy.of.a.Master.Thief.FIX-RELOADED",
		"CHAMPIONSHIP.MANAGER.2003.2004.UPDATE.V4.1.3.PATCH.FIX.CRACKED-DEViANCE",
		"CHAMPIONSHIP.MANAGER.2003.2004.UPDATE.V4.1.4.TIMER.FIX.CRACKED-DEViANCE",
		"CHROME.CRACK.FIX-DEViANCE",
		"F1.Racing.Championship.FIX.READ.NFO-HOTDOX",
		"Hunting_Unlimited_3_V1.1_NOCD_CRACK_NFOFIX-RVL",
		"LMA.Manager.2007.FiX-RELOADED",
		"MSC.PATRAN.V2001.R2A.FIX.FOR.RISE-TFL",
		"RUNAWAY.A.ROAD.ADVENTURE.FIX-DEViANCE",
		"Bubble.Boy.DVDRip.DiVX.FIX-FIXRUS", #contains vobsubs
		# missing file main release
		"Super.Streetfighter.IV.SSFIV.Arcade.Edition.DLC.FIX.READNFO.XBOX360-MoNGoLS",
		]
	release_name = os.path.split(reldir)[1]
	if (is_storable_fix(release_name) and 
		len(main_sfvs) == 1 and len(main_rars) == 1 and 
		len(parse_sfv_file(main_sfvs[0])[0]) == 1 and
		os.path.basename(reldir) not in false_positives and
		# prevent duplicate file add e.g. roor-blueruin-1080p-proof.fix.rar
		# Blue.Ruin.2013.German.DL.Proof.Fix.1080p.BluRay.x264-ROOR
		work_dir_file(main_rars[0], reldir, working_dir) not in copied_files):
		copied_files.append(copy_to_working_dir(
			working_dir, reldir, main_rars[0]))
	
	if options.vobsub_srr and not unrar_is_available():
		options.vobsub_srr = False
		logging.warning("Ignoring --vobsub-srr: unrar unavailable")
	if options.vobsub_srr:
		unrar = get_unrar()
		for esfv in extra_sfvs:
			skip = False
			# not for Proof RARs that are already stored inside the SRR
			for cfile in copied_files:
				if cfile.endswith((os.path.basename(esfv)[:-3] + "rar")):
					skip = True
					break
			# not for dirfix releases moved to the main folder
			subdir = os.path.basename(os.path.normpath(os.path.dirname(esfv)))
			if "dirfix" in subdir.lower():
				skip = True
			if skip:
				continue
			
			try:
				new_srrs = create_srr_for_subs(
					unrar, esfv, working_dir, reldir)
				for s in new_srrs:
					copied_files.append(s)
			except ValueError as e:
				# No RAR5 support yet
				logging.warning("{0}: {1}".format(str(e), esfv))
			
		r = os.path.split(reldir)[1].lower()
		if "subpack" in r or "subfix" in r:
			for esfv in main_sfvs:
				try:
					new_srrs = create_srr_for_subs(
						unrar, esfv, working_dir, reldir)
					for s in new_srrs:
						copied_files.append(s)
				except ValueError as e:
					# No RAR5 support yet
					logging.warning("{0}: {1}".format(str(e), esfv))

	# TODO: TXT files for m2ts/vob with crc and size?
	# no, basic .srs file with a single track
		
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
					sample = sample_class_factory(
						file_type_info(stored_file).file_type)
					srs_data, _tracks = sample.load_srs(stored_file)
					# accept SRS if it isn't in the SFV
					crc = int(crclist.get(srs_data.name.lower(), "-1"), 16)
					if srs_data.crc32 != crc and crc != -1:
						to_remove.append(stored_file)
						logging.critical("%s: SFV verification failed for %s."
										% (reldir, srs_data.name))
				except IOError: #TODO: supported, no? then remove this
					logging.critical("%s: FLAC with ID3 tag: %s." % 
						             (reldir, os.path.basename(stored_file)))
					to_remove.append(stored_file)
					
		for removed_file in to_remove:
			copied_files.remove(removed_file)
	else:
		# put vobsub SRRs and proof RARs above their SFV file in the list
		to_move = []
		for cfile in copied_files:
			if (cfile[-4:].lower() in (".srr", ".rar") and
				cfile[:-4].lower() + ".sfv" in 
				[x.lower() for x in copied_files]):
				to_move.append(cfile)
		for move in to_move:
			copied_files.remove(move)
			index = [x.lower() for x in copied_files
			        ].index(move[:-4].lower() + ".sfv")
			copied_files.insert(index, move)

	# apply exclude list
	for cfile in copied_files[:]:
		if os.path.basename(cfile) in options.skip_list:
			print("Skipped over stored file: %s" % os.path.basename(cfile))
			copied_files.remove(cfile)
	
	# some of copied_files can not exist
	# this can be the case when the disk isn't readable
	rescene.add_stored_files(
		tmp_srr_name, copied_files, working_dir, True, False)
	replace_result(tmp_srr_name, srr)

	try:
		empty_folder(working_dir)
	except OSError as oserr:
		mthread.wait_for_output()
		print("Could not empty temporary working directory:")
		print(working_dir)
		print("This is a know problem for PyPy users.")
		print("(And sadly others too, but less often.)")
		# TODO: sure this isn't because of left open file handles?
		if _DEBUG:
			print("Actual error: {0}".format(str(oserr)))
	
	return True

def get_release_directories(path):
	"""Generator that yields all possible release directories."""
	path = os.path.abspath(path)
	last_release = ""
	
	if os.name != "nt":
		# wait until the DVD drive is mounted
		limiter = 0  # prevent endless loop
		# TODO: check what the actual problem is here. empty directory?
		while not len(os.listdir(path)) and limiter < 30:
			print("Waiting 5 seconds for mount.")
			time.sleep(5)
			limiter += 5
	else:
		try:
			# so it can work with longer directories
			if not is_release(path):
				path = win32api.GetShortPathName(path)
		except:
			pass
		
	for dirpath, dirnames, filenames in os.walk(path):
		# The directory list is in arbitrary order, but on Windows it seems 
		# to be sorted alphabetical by default.
		dirnames.sort() # force alphabetical order 
		if _DEBUG:
			print(dirpath)
			print(dirnames)
			print(filenames)
		if (last_release in dirpath and last_release and 
			# keep release names that start with the same string,
			# so that they won't be skipped
			# e.g.  ReleaseName-CUTG
			#       ReleaseName-CUTGRP
			# (subdirs have a separator more)
			dirpath.rfind(os.sep) != last_release.rfind(os.sep)):
			continue # subfolders of a found release
		
		if is_release(dirpath, dirnames, filenames):
			last_release = dirpath
			try:
				# so we don't take a short release name as SRR name
				head, tail = os.path.split(last_release)
				yield os.path.join(win32api.GetShortPathName(head), tail)
			except:
				yield last_release
			
# The_Guy_Game_USA_DVD9_XBOX-WoD: PART1/wod-guy.part001.sfv
DISK_FOLDERS = re.compile("^(CD|DISK|DVD|DISC|PART)_?\d\d?$", re.IGNORECASE)
RELEASE_FOLDERS = re.compile("^((CD|DISK|DVD|DISC|PART)_?\d\d?|(Vob)?Samples?|"
	"Covers?|Proofs?|Subs?(pack)?|(vob)?subs?)$", re.IGNORECASE)
NOT_SCENE = ["motechnetfiles.nfo", "movie.nfo", "imdb.nfo", "scc.nfo"]

def is_release(dirpath, dirnames=None, filenames=None):
	if dirnames is None or filenames is None:
		dirnames = list()
		filenames = list()
		for x in os.listdir(dirpath):
			if os.path.isfile(os.path.join(dirpath, x)):
				filenames.append(x)
			else:
				dirnames.append(x)
		
	release = False
	# A folder is considered being an original scene release directory when
	# there is a .nfo file or a .sfv file
	# or a .sfv file in a CDx/DiskX subdir (when nfo file is missing)
	for filename in filenames:
		if (filename[-4:].lower() in (".nfo", ".sfv") and
			filename not in NOT_SCENE):
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
	if len(filenames) == 1 and filenames[0].lower().endswith(".nfo"):
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

def is_empty_file(fpath):
	if os.path.isfile(fpath) and os.path.getsize(fpath) == 0:
		return True
	else:
		return False

def main(argv=None):
	start_time = datetime.now()
	parser = OptionParser(
	usage=("Usage: %prog [directories] [options]\n"
	"This tool can automatically create a complete SRR file for a "
	"release directory.\n"
	"Example usage: %prog E:\\ --best --recursive --output D:\\"), 
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
	parser.add_option("--best", dest="best_settings", default=False,
					action="store_true",
					help="same as -csv (compressed, sample verify and vobsubs)")
	parser.add_option("-c", "--compressed",
					action="store_true", dest="compressed",
					help="allow SRR creation for compressed RAR files")
	parser.add_option("-s", "--sample-verify",
					action="store_true", dest="sample_verify",
					help="verifies sample agains main movie files")
	parser.add_option("-v", "--vobsub-srr", dest="vobsub_srr",
					action="store_true", help="include SRRs for vobsubs")
	parser.add_option("-o", "--output", dest="output_dir", metavar="DIR",
					default=".",
					help="<path>: Specify output file or directory path. "
					"The default output path is the current directory.")
	parser.add_option("-d", "--srr-in-reldir",
					action="store_true", dest="srr_in_reldir",
					help="overrides -o parameter")
	parser.add_option("-t", "--temp-dir", dest="temp_dir", default="",
					metavar="DIRECTORY", 
					help="set custom temporary directory")
					# used for vobsub creation

	parser.add_option("-x", "--skip", dest="skip_list", metavar="NAME",
					action="append",
					help="exclude these files from the stored files")
	parser.add_option("--skip-list", dest="skip_file", default="",
					metavar="FILE", 
					help="file with file names to skip for the stored files")

	parser.add_option("--no-srs", action="store_true", dest="nosrs",
					help="disable .srs creation for media files")
					# speedup rerun, less traffic, backup textfiles ...
	parser.add_option("-e", "--eject",
					action="store_true", dest="eject",
					help="eject DVD drive after processing")
	parser.add_option("-l", "--report",
					action="store_true", dest="report",
					help="reports which samples had issues")

	extra = OptionGroup(parser, "Separate features")
	parser.add_option_group(extra)

	extra.add_option("--vobsubs", dest="vobsubs", metavar="VOBSUBS_SFV",
					help="creates an SRR file for the vobsubs RARs only")
	
	listoptions = OptionGroup(parser, "List feature")
	parser.add_option_group(listoptions)
	
	listoptions.add_option("--show-paths", dest="show_paths", 
					action="store_true", help="Shows the complete path. "
					"To be used with the following parameters:")
	listoptions.add_option("--list-releases", dest="list_releases", 
					action="store_true", help="Lists the release names "
					"the script will encounter.")
	listoptions.add_option("--missing-nfos", dest="missing_nfos", 
					action="store_true", 
					help="Lists releases with no nfo file.")
	listoptions.add_option("--missing-samples", dest="missing_samples", 
					action="store_true", 
					help="Lists releases with no sample file.")
	
	if argv is None:
		argv = sys.argv[1:]
		
	# no arguments given
	if not len(argv):
		# show application usage
		parser.print_help()
		return 0
	
	(options, indirs) = parser.parse_args(args=argv)
	
	if options.best_settings:
		options.compressed = True
		options.sample_verify = True
		options.vobsub_srr = True
	
	# extra feature that just prints release names
	if (options.list_releases or options.missing_nfos or 
		options.missing_samples):
		def print_release(release_dir):
			if options.show_paths:
				print(release_dir)
			else:
				_head, tail = os.path.split(release_dir)
				print(tail)
		for procdir in indirs:
			procdir = os.path.abspath(procdir)
			for release_dir in get_release_directories(procdir):
				if options.list_releases:
					print_release(release_dir)
				if options.missing_nfos:
					if not any(f[-4:].lower() == ".nfo" for f in
					                  os.listdir(release_dir)):
						print_release(release_dir)
				if options.missing_samples:
					sdir = next((d for d in
						os.listdir(release_dir) if
						d.lower() == "sample"), None)
					found = False
					if sdir is not None:
						sdir = os.path.join(release_dir, sdir)
						for sfile in os.listdir(sdir):
							if re.match(".*\.(avi|mkv|mp4|wmv|vob|m2ts|mpg)",
									sfile, re.IGNORECASE):
								found = True
								break
					if not found:
						print_release(release_dir)
		return 0
	
	if options.always_yes and options.always_no:
		print("Is it 'always yes' (-y) or 'always no' (-n)?")
		return 1 # failure

	# check for existence output directory
	options.output_dir = os.path.abspath(options.output_dir)
	if not os.path.exists(options.output_dir):
		if can_create(options.always_yes, options.output_dir):
			os.makedirs(options.output_dir)
		else:
			print("No output directory created.")
			return 1 # failure, although user can expect this
			
	# overwrite user input request function
	def can_overwrite(file_path):
		retvalue = True 
		if not options.always_yes and os.path.isfile(file_path):
			# when a user does not want to process releases he has already done
			if options.always_no:
				return False
			print("Warning: File %s already exists." % file_path)
			char = raw_input("Do you wish to continue? (Y/N): ").lower()
			while char not in ('y', 'n'):
				char = raw_input("Do you wish to continue? (Y/N): ").lower()
			if char == 'n':
				retvalue = False
		return retvalue 
	rescene.main.can_overwrite = can_overwrite
			
	if options.report:
		now = datetime.now()
		report_fn = os.path.join(options.output_dir, 
		                "pyReScene_report_%s.txt" % now.strftime("%Y-%m-%d"))
		# log will append by default
		logging.basicConfig(filename=report_fn, level=logging.INFO,
		                    format="%(asctime)s %(levelname)s:%(message)s",
		                    datefmt='%H:%M:%S')
		
	# create temporary working dir
	if options.temp_dir and len(options.temp_dir):
		options.temp_dir = os.path.abspath(options.temp_dir)
	else:
		options.temp_dir = None
	try:
		# 4 + 6 < 12; So no influence for a Windows short path
		working_dir = mkdtemp(prefix="SRR-", dir=options.temp_dir)
	except OSError:
		print("The provided temporary directory does not exist.")
		return 1 # failure
	rescene.utility.temporary_directory = working_dir # for utility (fpcalc)
	print("Temporary directory: {0}".format(working_dir))
	
	# SRR for vobsubs only. Only one file at a time; last file will be used.
	if options.vobsubs:
		if len(indirs):
			print("Warning: ignoring unnecessary parameters.")
			print("Use -v or --vobsub-srr to include SRR files for vobsubs.")
		unrar = get_unrar()
		sfv = os.path.abspath(options.vobsubs)
		try:
			srr_list = create_srr_for_subs(unrar, sfv, working_dir,
			                               os.path.dirname(sfv))	
			for vobsub_srr in srr_list:
				f = os.path.basename(vobsub_srr)
				out = os.path.join(options.output_dir, f)
				if os.path.isfile(out):
					if can_overwrite(out):
						shutil.copy(vobsub_srr, out)
				else:
					shutil.copy(vobsub_srr, out)
			return 0
		except ValueError as e:
			# No RAR5 support yet
			logging.warning("{0}: {1}".format(str(e), sfv))
			return 1 # failure (no .srr created)

	if not options.skip_list:
		options.skip_list = []
	if options.skip_file:
		if not os.path.isfile(options.skip_file):
			print("The list of files to skip, could not be found.")
			return 1 # failure
		with open(options.skip_file, 'r') as skiplist:
			options.skip_list = skiplist.read().splitlines()

	drive_letters = []
	aborted = False
	missing = [] # --always-no: existing SRRs are excluded
	try:
		mthread = MessageThread()
		msgs = [MsgCode.FILE_NOT_FOUND, MsgCode.UNKNOWN, MsgCode.MSG]
		mthread.set_messages(msgs)
		mthread.start()

		for reldir in indirs:
			reldir = os.path.abspath(reldir)
			if not options.recursive:
				result = generate_srr(reldir, working_dir, options, mthread)
				if not result:
					missing.append(reldir)
					logging.warning("%s: SRR could not be created." % 
									reldir)
			else:
				for release_dir in get_release_directories(reldir):
					try:
						result = generate_srr(release_dir, working_dir,
						                      options, mthread)
					except FileNotFound:
						result = False
					if not result:
						missing.append(release_dir)
						logging.warning("%s: SRR could not be created." % 
									release_dir)
			# gather drive info
			drive_letters.append(reldir[:2])
	except KeyboardInterrupt:
		mthread.wait_for_output()
		print("Process aborted.")
		aborted = True
	except AssertionError as err:
		mthread.wait_for_output()
		print(str(err))
		print("Please report me this problem!")
		print("https://bitbucket.org/Gfy/pyrescene/issues")
		aborted = True
	except ExecutableNotFound:
		mthread.wait_for_output()
		print("----------------------------------------------------")
		print("Please put the fpcalc executable in your PATH!")
		print("It is necessary for the creation of music SRS files.")
		print()
		print("It can be downloaded from ")
		print("https://bitbucket.org/acoustid/chromaprint/downloads")
		print("On Debian, install libchromaprint-tools")
		print("----------------------------------------------------")
		aborted = True
	finally:
		try:
			mthread.done = True
			mthread.join()
		except:
			print("Failure stopping the MessageThread.")

	if len(missing):
		print()
		print("------------------------------------")
		print("Warning: some SRRs failed to create!")
		for item in missing:
			print(item)
		print("------------------------------------")
				
	# delete temporary working dir
	try:
		shutil.rmtree(working_dir)
	except OSError as oserr:
		print("Could not empty temporary working directory!")
		print(working_dir)
		print("This is a know problem for PyPy users. (long paths issue)")
		# I've seen this error with CPython too. Something else wrong?
		# The temp dir was actually removed though.
		# TODO: sure this isn't because of left open file handles?
		print("Actual error: {0}".format(str(oserr)))
	
	# see if we need to eject a disk drive
	if options.eject and os.name == "nt" and not aborted:
		import ctypes
		
		for drive in drive_letters:
			ctypes.windll.WINMM.mciSendStringW(
				unicode("open %s type cdaudio alias ddrive") % drive, 
				None, 0, None)
			ctypes.windll.WINMM.mciSendStringW(
				unicode("set ddrive door open"), None, 0, None)
		
		try:
			import winsound #@UnresolvedImport
			winsound.Beep(1000, 500)
		except:
			pass
	elif options.eject and not aborted:
		import subprocess
		
		subprocess.call(["eject"])
		print("\a")
		
	if options.report and is_empty_file(report_fn):
		# stop locking the .log file
		for handler in logging.root.handlers[:]:
			handler.flush()
			handler.close()
			logging.root.removeHandler(handler)
		os.remove(report_fn)
	
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