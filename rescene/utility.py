#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2008-2010 ReScene.com
# Copyright (c) 2011-2015 pyReScene
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

# Port based on the these files: (MIT license)
#   RarFileNameComparer.cs, RarFileNameFinder.cs, SfvReader.cs
# Everything else: MIT license

import re
import sys
import difflib
import mmap
import warnings
import locale
import os
import shutil
import time
import zlib
from io import BytesIO, TextIOBase, TextIOWrapper
from tempfile import mktemp

try:
	import win32api
	win32api_available = True
except ImportError:
	win32api_available = False

# on Windows:
#   SET NAME=True       configure
#   ECHO %NAME%         check
#   SET NAME=           clear
#   SETX NAME VALUE     set environment variables permanently
_DEBUG = bool(os.environ.get("RESCENE_DEBUG"))  # leave empty for False

# disables the spinner from showing while doing some processing
_SPINNER = not bool(os.environ.get("RESCENE_NO_SPINNER"))

# disables offset information to be printed out in srr -e output
# this way the output become more easy to compare
_OFFSETS = not bool(os.environ.get("RESCENE_NO_OFFSETS"))

# provides the temporary directory location to places where it would be a mess
# to pass it as parameter (fingerprint calculation)
temporary_directory = None

def deprecated(func):
	"""This is a decorator which can be used to mark functions
	as deprecated. It will result in a warning being emmitted
	when the function is used."""
	def newFunc(*args, **kwargs):
		warnings.warn("Call to deprecated function %s." % func.__name__,
					  category=DeprecationWarning)
		return func(*args, **kwargs)
	newFunc.__name__ = func.__name__
	newFunc.__doc__ = func.__doc__
	newFunc.__dict__.update(func.__dict__)
	return newFunc

# compatibility with 2.x
if sys.hexversion < 0x3000000:
	# prefer 3.x behaviour
	range = xrange  # @ReservedAssignment
	str = unicode  # @ReservedAssignment
	unicode = unicode  # @ReservedAssignment # Export to other modules

	def fsunicode(path):
		"""Converts a file system "str" object to Unicode"""
		if isinstance(path, unicode):
			return path
		encoding = sys.getfilesystemencoding()
		return path.decode(encoding or sys.getdefaultencoding())
else:
	unicode = str  # @ReservedAssignment
	def fsunicode(path):
		return path

# Python BUG: http://bugs.python.org/issue1927
try:  # Python < 3
	raw_input = raw_input  # @ReservedAssignment
except NameError:  # Python 3
	raw_input = input  # @ReservedAssignment

try:  # Python < 3
	basestring = basestring  # @ReservedAssignment
except NameError:  # Python 3
	basestring = str  # @ReservedAssignment

class FileType(object):
	"""File types in use to create SRS files for"""
	MKV, AVI, MP4, WMV, FLAC, MP3, STREAM, M2TS, Unknown = (
		"MKV", "AVI", "MP4", "WMV", "FLAC", "MP3",
		"STREAM", "M2TS", "Unknown")

	# the extensions that are supported
	# .m4v is used for some non scene samples, xxx samples and music releases
	# It is the same file format as MP4
	# VA-Anjunabeats_Vol_7__Mixed_By_Above_And_Beyond-(ANJCD014D)-2CD-2009-TT/
	#     301-va-anjunabeats_vol_7__bonus_dvd-tt.m4v
	# Gothic_3_Soundtrack-Promo-CD-2006-XARDAS/
	#     05_g3_makingofst-xardas.wmv
	#     06_g3_makingofst-xardas.m4v
	# Her-Sweet-Hand.11.01.15.Alex.Shy.Definitely.1.Time.Only.XXX.720p.M4V-OHRLY
	#     Sample/ohrly-hsh115asd1to.sample.m4v
	# System_Of_A_Down-Aerials-svcd-wcs
	#     system_of_a_down-aerials-svcd-wcs.m2p
	# System_Of_A_Down-Aerials-svcd-wcs
	#     system_of_a_down-aerials-svcd-wcs.m2p
	StreamExtensions = ('.vob', '.m2ts', '.ts',
	                    '.mpeg', '.mpg', '.m2v', '.m2p')
	VideoExtensions = ('.mp4', '.m4v',  # M4V: used for some XXX releases
	                   '.avi', '.mkv', '.wmv') + StreamExtensions
	AudioExtensions = ('.mp3', '.flac')  # TODO: mp2?

	def __init__(self, file_type, archived_file):
		self.file_type = file_type
		self.archived_file = archived_file

	def __str__(self, *args, **kwargs):
		return self.file_type

class SfvEntry(object):
	"""Represents a record from a .sfv file."""
	def __init__(self, file_name, crc32="00000000"):
		self.file_name = file_name.strip('"')
		self.crc32 = crc32

	def get_crc_32(self):
		return self.__crc32
	def set_crc_32(self, value):
		if not bool(re.match("^[\dA-F]{1,8}$", value, re.IGNORECASE)):
			raise ValueError(value + " is not a CRC32 hash.")
		# Baywatch.S11E11.DVDRiP.XViD-NODLABS.srr CRC is missing a zero
		self.__crc32 = value.rjust(8, "0")

	crc32 = property(get_crc_32, set_crc_32, "The crc32 hash.")

	def __lt__(self, other):
		"""The sort routines are guaranteed to use __lt__ when making 
		   comparisons between two objects."""
		ext_self = self.file_name[-4:].lower()
		ext_other = other.file_name[-4:].lower()
		same_base = self.file_name[:-4].lower() == other.file_name[:-4].lower()

		if same_base and ext_self != ext_other:
			if ext_self == ".rar":
				if bool(re.match("\.[r-z]\d{2}$", ext_other)):
					return True
				else:
					return self.file_name < other.file_name  # .rar < .r00
			elif ext_other == ".rar":
				if bool(re.match("\.[r-z]\d{2}$", ext_self)):
					return False
				else:
					return self.file_name < other.file_name  # .r00 > .rar
		# .part1.rar < .part2.rar, r99 < s00, 001 < 002
		return self.file_name < other.file_name

	def __repr__(self):
		return self.file_name + " " + self.crc32

	def __eq__(self, other):
		if type(other) is type(self):
			return (self.file_name.lower() == other.file_name.lower() and
			        self.crc32.lower() == other.crc32.lower())
		return False

	def __ne__(self, other):
		return not self.__eq__(other)

	__hash__ = None  # Avoid DeprecationWarning in Python < 3

def parse_sfv_data(file_data):
	"""Returns a tuple of three lists: (entries, comments, errors).
	Accepts SFV file data as a byte string.
	
	The "comments" and "errors" lists contain
	lines decoded from the file as text strings.
	File names must be iso-8859-1 aka latin1.
	http://en.wikipedia.org/wiki/Extended_ASCII
	Other text is decoded from latin1 using the "replace" error handler.
	"""
	entries = []  # SfvEntry objects
	comments = []
	errors = []  # unrecognized stuff

	# .sfv files without any \n line breaks exist
	# e.g. Need_for_Speed_Underground_2_JPN_NGC-WRG (\r\r instead)
	# (are those made like that or altered on transfer?)
	file_data = file_data.replace(b"\r", b"\n")

	for line in file_data.split(b"\n"):
		if not line.strip():
			# ignore blank lines in parsed result
			pass
		elif line.lstrip().startswith(b";"):
			# comment lines must start with ;
			line = line.decode("latin-1", "replace")
			comments.append(line)
		else:
			# actual data or parsing errors
			line = line.rstrip()
			try:
				text = line.decode("latin-1")
				text = text.replace("\t", "    ")  # convert tabs
				index = text.rindex(" ")  # ValueError: substring not found
				filename = text[:index].strip()
				# A SFV can contain multiple white spaces
				crc = text[index + 1:].lstrip()
				# ValueError: bad CRC e.g. char > F
				entries.append(SfvEntry(filename, crc))
			except ValueError:
				line = line.decode("latin-1", "replace")
				errors.append(line)

	return entries, comments, errors

def parse_sfv_file(sfv_file):
	"""Parses an SFV file with parse_sfv_data().
	Accepts an open binary file object or a file name."""
	try:
		sfv_file.seek(0)  # start at the beginning of the stream
		sfv_data = sfv_file.read()
	except AttributeError:
		try:
			with open(sfv_file, mode='rb') as fsock:
				sfv_data = fsock.read()
		except IOError:
			if not isinstance(sfv_file, basestring):
				raise
			with open("\\\\?\\" + sfv_file, mode='rb') as fsock:
				sfv_data = fsock.read()
	return parse_sfv_data(sfv_data)

def filter_sfv_duplicates(entries):
	"""Accepts the entries list of the parse functions above.
	The result will be sorted."""
	result = list()
	previous = None
	for entry in sorted(entries):
		if previous is None or not entry.__eq__(previous):
			result.append(entry)
		previous = entry
	return result

def same_sfv(one, two):
	"""Only based on actual content, not comments."""
	onec, _, _ = parse_sfv_file(one)
	twoc, _, _ = parse_sfv_file(two)
	onec.sort()
	twoc.sort()
	return onec == twoc

def next_archive(rfile, is_old=False):
	"""Returns the name of the next possible RAR archive.
	Behaviour undefined for *.part99.rar, *.rrar,...
	It must never occur.
	is_old: When enabled, makes sure the first .rar file is detected as
	        old style volume naming. It makes '.part02.r00' possible.
	        e.g. Doctor.Who.The.Enemy.Of.The.World.S05E17.DVDRip.x264-PFa
	"""
	def inc(extension):
		# create an array of a string so we can manipulate it
		extension = list(extension)
		i = len(extension) - 1  # last element
		while extension[i] == "9":
			extension[i] = "0"
			i -= 1  # go a character back
		else:  # also works with "rstuv"
			extension[i] = chr(ord(extension[i]) + 1)
		return "".join(extension)  # array back to string

	if re.match(".*\.part\d*.rar$", rfile, re.IGNORECASE) and not is_old:
		return inc(rfile[:-4]) + rfile[-4:]
	elif re.match(".*\.rar$", rfile, re.IGNORECASE):
		return rfile[:-4] + ".r00"
	elif not is_rar(rfile):
		raise AttributeError("The extension must be one form a RAR archive.")
	else:
		return inc(rfile)

def is_rar(file_name):
	"""True if file_name is a correctly named RAR file.
	Checks only based on the file name.
	
	Legal extensions:
		- .rar
		- .r00 - r99, s00 - v99   rar cmd creates beyond this limit
		- .000 - .999             001 for Accepted.DVDRip.XViD-ALLiANCE
	Not valid:
		- .cbr
		- .exe                    TODO: SFX support
	"""
	return bool(re.match(".*\.(rar|[r-z]\d{2}|\d{3})$", file_name, re.I))

def first_rars(file_iter):
	"""Tries to pick the first RAR file based on file name."""

	# group 3: when there is a digit before .rar e.g. test3.rar
	fre = ".*((\.part0*1\.rar|(?<!\d)\.rar)|((^|[^\d])(?<!part)(\d+\.rar)))$"

	def is_first(rar):
		if re.match(fre, rar, re.IGNORECASE):
			return True
		return rar.endswith((".000", ".001"))

	def is_dotrar(rar):
		return rar.lower().endswith(".rar")

	# all items will need to be checked at least once: full generator run
	input_files = list(file_iter)

	firsts = list(filter(is_first, input_files))
	# .000? then no .001
	for first in filter(lambda x: x.endswith(".000"), firsts):
		try:
			firsts.remove(first[:-1] + "1")
		except ValueError:
			# the release consists of a a single .000 file only
			# e.g. Ys_6_The_Ark_of_Napishtim_USA_FIX_READNFO_PSP-REBORN
			pass
	# list still empty? A .part2.r00 situation might be the case.
	if not len(firsts):
		firsts = list(filter(is_dotrar, input_files))
		have_r00_follower = []
		for first in firsts:
			if first[:-3] + "r00" in input_files:
				have_r00_follower.append(first)
		if len(have_r00_follower):
			firsts = have_r00_follower
		elif len(input_files) > 1:
			firsts = []  # probably incomplete, so detect nothing
		# else: empty list firsts or
		# there is only a single .rar file provided with a weird name
		# e.g. name.part3.rar (and it gets detected)
	return firsts

def is_good_srr(filepath):
	"""Tests whether the file path only contains / and none
	of the other illegal characters: \/:*?"<>| in Windows.
	
	Stored files in SRRs contain forward slashes.
	RAR uses backward slashes."""
	ILLEGAL_WINDOWS_CHARACTERS = """\:*?"<>|"""
	for char in ILLEGAL_WINDOWS_CHARACTERS:
		if char in filepath:
			return False
	return True

def joinpath(path, start=""):
	"""Validates and joins a sequence of path elements into an OS path
	
	Each path element is an individual directory, subdirectory or file
	name. Raises ValueError if an element name is not supported by the
	OS."""

	illegal_names = frozenset(
		("", os.path.curdir, os.path.pardir, os.path.devnull))
	for elem in path:
		if os.path.dirname(elem) or elem in illegal_names:
			fmt = "Path element not supported by OS: {0!r}"
			raise ValueError(fmt.format(elem))
	return os.path.join(start, *path)

def sep(number, loc=''):
	"""Adds a thousands separator to the number.
	The function is locale aware."""
	locale.setlocale(locale.LC_ALL, loc)
	return locale.format('%d', number, True)

def show_spinner(amount):
	"""amount: a number"""
	if _SPINNER:
		sys.stdout.write("\b%s" % ['|', '/', '-', '\\'][amount % 4])

def remove_spinner():
	"""removes spinner with the backspace char"""
	if _SPINNER:
		sys.stdout.write("\b")

def empty_folder(folder_path):
	if os.name == "nt" and win32api_available:
		folder_path = win32api.GetShortPathName(folder_path)
	for file_object in os.listdir(folder_path):
		file_object_path = os.path.join(folder_path, file_object)
		if os.name == "nt" and win32api_available:
			file_object_path = win32api.GetShortPathName(file_object_path)
		if os.path.isfile(file_object_path):
			os.unlink(file_object_path)
		else:
			try:
				shutil.rmtree(file_object_path)
			except OSError:
				remove_folder(file_object_path)

def remove_folder(path):
	"""Recursively delete a directory tree."""
	if os.name == "nt" and win32api_available:
		path = win32api.GetShortPathName(path)
	names = os.listdir(path)
	for name in names:
		fullname = os.path.join(path, name)
		if os.path.isdir(fullname):
			remove_folder(fullname)
		else:
			try:
				os.remove(fullname)
			except OSError:
				try:
					os.remove("\\\\?\\" + fullname)
				except OSError:  # it's a dir?
					remove_folder(fullname)
	try:
		os.rmdir(path)
	except OSError:
		os.rmdir("\\\\?\\" + path)

def create_temp_file_name(output_file):
	"""Creates file name for the temporary file based on the name of the
	output file to create/overwrite later.
	output_file must be an absolute path.
	Used to prevent overwriting good files with a broken one later on."""
	dirname = os.path.dirname(output_file)
	prefix = os.path.basename(output_file)
	tmpfile = mktemp(".tmp", prefix + "-", dirname)

	# Windows long path support
	if os.name == "nt":
		tmpfile = "\\\\?\\" + os.path.abspath(tmpfile)
		
	assert not os.path.exists(tmpfile), "Temp file must not exist yet"

	return tmpfile

def replace_result(src, dest):
	"""Replaces the destination file with the source file.
	Will not do anything when the source file doesn't exist.
	Used to prevent overwriting good files with a broken one later on."""
	if not src.startswith(dest):
		# Windows long path support
		if os.name == "nt":
			dest = "\\\\?\\" + os.path.abspath(dest)

	# it must come from the above method (create_temp_file_name)
	assert src.startswith(dest), "src and dest not at same location"

	# it is possible a temporary source file was never created
	# (.srr question for replacement is false)
	if os.path.isfile(src):
		# delete previous file if it exists: user allowed to overwrite it
		if os.path.isfile(dest):
			try:
				os.unlink(dest)
			except OSError as delete_error:
				print("Two processes are now trying to delete the same file!")
				print(delete_error)
				if _DEBUG:
					print("  Destination: {0}".format(dest))
# TODO: work in progress missing srs files					
# 					assert False
# 					
# 		# wait 5 seconds for the file to disappear
# 		for _ in range(0, 5):
# 			if os.path.isfile(dest):
# 				time.sleep(1)
# 			else:
# 				break
# 		else:
# 			print("Destination file still not deleted!")

		# concurrency issue: it can fail here with a
		# WindowsError/OSError when the other process made the file
		try:
			os.rename(src, dest)
		except OSError:
			print("Two processes are now trying to output the same file!")
			if _DEBUG:
				print("  Source: {0}".format(src))
				print("  Destination: {0}".format(dest))
			print("This one lost... deleting temp file.")
			os.unlink(src)
			raise

def calculate_crc32(file_name):
	"""Calculates crc32 for a given file and show a spinner."""
	crc = 0
	count = 0
	with open(file_name, "rb") as f:
		x = f.read(65536)
		while x:
			count += 1
			show_spinner(count)
			crc = zlib.crc32(x, crc)
			x = f.read(65536)
		remove_spinner()
	return crc & 0xFFFFFFFF

def capitalized_fn(afile):
	"""
	Checks provided file with the file on disk and returns the imput with
	its exact capitalization on disk. In the second value the capitalization
	is preserved if it was available.
	
	Returns tuple: (exact, capitals)
	exact: what's on disk
	captials: the name with capitals (preservation purposes)
	"""
	exact = capitals = afile
	# 1) find the proper file on disk
	# on Windows it will be found despite capitalization
	# on Linux it could not when the capitals don't match (file name from sfv)
	inputfn = os.path.basename(afile)
	inputdir = os.path.dirname(afile) or os.curdir
	for cfile in os.listdir(inputdir):
		if (cfile.lower() == inputfn.lower() and
		    os.path.isfile(os.path.join(inputdir, cfile))):
			exact = os.path.join(inputdir, cfile)
			break

	# 2) use proper capitalization on both OSes
	# - choose the one with capitals
	# - not conclusive? use original file name
	actualfn = os.path.basename(exact)
	if actualfn.lower() == actualfn:
		# use file name of SFV either way (no difference is possible)
		cpath = inputdir
		capitals = os.path.join(cpath, inputfn)
	elif inputfn.lower() == inputfn:
		# actualfn has capitals and input none
		cpath = inputdir
		capitals = os.path.join(cpath, actualfn)

	return exact, capitals

###############################################################################

def diff_lists(one, two):
	"""Accepts two lists."""
# 	d = difflib.Differ() #linejunk=ignore_newline)
# 	oneclean = []
# 	twoclean = []
# 	for line in one:
# 		oneclean.append(line.encode('ascii', 'replace'))
# 	for line in two:
# 		twoclean.append(line.encode('ascii', 'replace'))
# 	#a = d.compare(oneclean, twoclean)
# 	print("\n".join(list(a)))
#

	# TODO: remove empty lines?

	a = difflib.ndiff(one, two, cleanlines)
	(pos, neg, no) = (0, 0, 0)
	res = []
	for line in a:
		if line[:1] in "+":
			pos += 1
			res.append("+")
		elif line[:1] in "-":
			neg += 1
			res.append("-")
		else:  # ? or space
			no += 1
			res.append(" ")
	# print(res)
	return pos, neg, no

def cleanlines(line):
	length = len(line.strip().replace("\r", "").replace("\n", ""))
	return length == 0

def same_nfo(one, two):
	with open(one, "rt") as f:
		onec = f._read()
	with open(two, "rt") as f:
		twoc = f._read()
	if len(onec) != len(twoc):
		return False
	else:
		_pos, _neg, no = diff_lists(onec, twoc)
		return len(no) == len(onec)

###############################################################################

def encodeerrors(text, textio, errors="replace"):
	"""Prepare a string with a fallback encoding error handler
	
	If the string is not encodable to the output stream,
	the string is passed through a codec error handler."""

	encoding = getattr(textio, "encoding", None)
	if encoding is None:
		if isinstance(textio, TextIOBase):
			# TextIOBase, and therefore StringIO, etc,
			# have an "encoding" attribute,
			# despite not doing any encoding
			return text
		# Otherwise assume semantics like Python 2's "file" object
		encoding = sys.getdefaultencoding()

	try:
		text.encode(encoding, textio.errors or "strict")
	except UnicodeEncodeError:
		text = text.encode(encoding, errors).decode(encoding)
	return text

def decodetext(tbytes, *pos, **kw):
	"""Decode a string using TextIOWrapper"""
	return TextIOWrapper(BytesIO(tbytes), *pos, **kw).read()


"""Example SFV files:
; Generated by WIN-SFV32 v1 with MP3-RELEASER [Version:2000.2.2.1] by MorGoTH on 3/11/01 9:42:54 AM (px`hehxW)
; For more information visit http://morgoth.smartftp.com
;
;!SFV_COMMENT_START
;                                  °
;                                  ²
;                                ÞÛ²
;                               ÛÛÛ²
;                               ²ÛÛÛ²Ý
;                              ²ÛÛÛÛ²±
;               °              ²ÛÛÛÛ²²±
;           ÜÜÜÜ±             ÞÛÛÛÛÛ²²²     °    °      ÜÜÜÜ
;            ßÛÛ²ÛÛÜÜÜ     ° °ÛÛÛÛÛÛ²²²Ý    ±    °ÜÜÜÛÛÛÛ²ß
;              ßÛÛÛÛÛÛÛ²ÛÜ²± ÞÛÛÛÛ²Û²²²Ý    ±   ÛÛ²²ßÛÛÛß
;  ²²²²²         ßß²ßß ²±Û²²ÜÜÜÜ ß²ßßÜÜÜÜ   ²²ÛÛ ÜÜ²ÛÛß
;  ±±±±±ÛÜ        ÜÛßßÛÛÜßÞÛ  ÛÛÜ² ÛÛ  ßÛÛÜ  ÛÛ ÛÛßß      °
;    ÛÛÛÛÛÛ      ÜÛß    ßßÛÛ   ÛÛ ÞÛ     ÛÛ  ÛÛ   ÜÜÜÜ    ±
;     ÛÛÛÛÛÛÛ    ÛÛ Û²²²Ü ßÛÛÜÛßß ÛÛÜÜÜ  ÛÛ ÛÛÝ°²ÛÛÛÛÛÛÛÛÛ²ÜÜÜÜÜ
;       ÛÛÛÛÛÛÛÜ ÛÛÜ ßßÛÛÜ ßÛÛÜÜÛÛßß   ßÛÛßß ÛÝ ßÜÜÜÜÛÛÛ²ßßßß
;         ÛÛÛÛÛÛÜÜßß      ÜÛÜ ßß   ßßÛÛÜßß   ÛÝ²²²²ßßßß
;           ßÛÛÛÛÛÛ     ÜÛ²ÛÛß° Ü°Ü   ßßßÛÛÛÜÜ
;               ßÛÛÛÛÛÜ ÛÛß²    ±ÜßÛ±Ü      ßÛ²²² eu
;                ßßÛÛÛ    ±   ßß    ß²        ²°Ü
;                      Ü  ° 4 r e a l ±  Ü      °
;                      ° p r e s e n t s ß±
;                     ß                  ßß
;
;              Created with MorGoTH's MP3 Releaser
;!SFV_COMMENT_END
01-olav_basoski_-_live_at_slam_fm_10-03-01-1real.mp3 2DEA959E

; sfv created by SFV Checker
;
"gh-flow.subs.rar" 83a20923
;
; Total 1 File(s)	Combined CRC32 Checksum: 83a20923
"""
