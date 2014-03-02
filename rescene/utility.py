#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2008-2010 ReScene.com
# Copyright (c) 2011 pyReScene
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
from io import TextIOWrapper, BytesIO

try:
	import win32api
	win32api_available = True
except ImportError:
	win32api_available = False

_DEBUG = bool(os.environ.get("RESCENE_DEBUG")) # leave empty for False

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
	range = xrange #@ReservedAssignment
	str = unicode #TODO: hmmm @ReservedAssignment
else:
	unicode = str #@ReservedAssignment

try:  # Python < 3
	raw_input = raw_input
except NameError:  # Python 3
	raw_input = input

try:  # Python < 3
	basestring = basestring
except NameError:  # Python 3
	basestring = str

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

		if ext_self != ext_other and ext_self == ".rar" and same_base:
			return True if bool(re.match("\.[r-v]\d{2}$", ext_other)) \
						else self.file_name < other.file_name # .rar < .r00
		elif ext_self != ext_other and ext_other == ".rar" and same_base:
			return False if bool(re.match("\.[r-v]\d{2}$", ext_self)) \
						else self.file_name < other.file_name # .r00 > .rar
		# .part1.rar < .part2.rar, r99 < s00, 001 < 002
		return self.file_name < other.file_name
		
	def __repr__(self):
		return self.file_name + " " + self.crc32
	
	def __eq__(self, other) : 
		return self.__dict__ == other.__dict__
	__hash__ = None  # Avoid DeprecationWarning in Python < 3

def parse_sfv_file(sfv_file):
	"""Returns a tuple of three lists: (entries, comments, errors).
	Accepts an open binary file object, a file name, or a byte string.
	
	The "comments" and "errors" lists contain
	lines decoded from the file as text strings.
	File names must be strictly ASCII.
	Other text is decoded from ASCII using the "replace" error handler.
	"""
	entries = list()  # SfvEntry objects
	comments = list() # and unrecognized stuff
	errors = list()
	
	def parse(file_data):
		for line in file_data.split(b"\n"):
			# empty line, comments or useless text for whatever reason
			if not (line).strip():
				pass # blank line detected
			elif (line).lstrip().startswith(b";"):
			# or len(line) < 10:
				line = line.decode("ascii", "replace")
				comments.append(line)
			else:
				line = (line.rstrip())
				try:
					text = line.decode("ascii")
					text = text.replace("\t", "    ") # convert tabs
					index = text.rindex(" ") # ValueError: substring not found
					filename = text[:index]
					# A SFV can contain multiple white spaces
					crc = text[index+1:].lstrip()
					# ValueError: bad CRC e.g. char > F
					entries.append(SfvEntry(filename, crc))
				except ValueError:
					line = line.decode("ascii", "replace")
					errors.append(line)
	try:
		sfv_file.seek(0) # start at the beginning of the stream
		sfv_data = sfv_file.read()
	except AttributeError:
		try:
			try:
				with open(sfv_file, mode='rb') as fsock:
					sfv_data = fsock.read()
			except IOError:
				if not isinstance(sfv_file, basestring):
					raise
				with open("\\\\?\\" + sfv_file, mode='rb') as fsock:
					sfv_data = fsock.read()
		except IOError:
			sfv_data = sfv_file
	parse(sfv_data)
		
	return entries, comments, errors

def same_sfv(one, two):
	"""Only based on actual content, not comments."""
	onec, _, _ = parse_sfv_file(one)
	twoc, _, _ = parse_sfv_file(two)
	onec.sort()
	twoc.sort()
	return onec == twoc

def next_archive(rfile):
	"""Returns the name of the next possible RAR archive.
	Behaviour undefined for *.part99.rar, *.rrar,...
	It must never occur."""
	def inc(extension):
		# create an array of a string so we can manipulate it
		extension = list(extension)
		i = len(extension) - 1 # last element
		while extension[i] == "9":
			extension[i] = "0"
			i -= 1 # go a character back
		else: # also works with "rstuv"
			extension[i] = chr(ord(extension[i]) + 1)
		return "".join(extension) # array back to string

	if re.match(".*\.part\d*.rar$", rfile, re.IGNORECASE):
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
		- .r00 - r99, s00 - v99
		- .000 - .999             001 for Accepted.DVDRip.XViD-ALLiANCE
	Not valid:
		- .cbr
		- .exe                    TODO: SFX support
	"""
	return bool(re.match(".*\.(rar|[r-v]\d{2}|\d{3})$", file_name, re.I))

def first_rars(file_iter):
	"""Tries to pick the first RAR file based on file name."""
	
	def isfirst(rar):
		if re.match(".*(\.part0*1\.rar|(?<!\d)\.rar)$", rar, re.IGNORECASE):
			return True
		# when there is a digit before the .rar
		if (re.match(".*\.rar$", rar, re.IGNORECASE) and 
		    not re.match(".*part\d+\.rar$", rar, re.IGNORECASE)):
			return True
		if rar.endswith((".000", ".001")):
			return True
		return False
	firsts = list(filter(isfirst, file_iter))
	# .000? then no .001
	for first in filter(lambda x: x.endswith(".000"), firsts):
		firsts.remove(first[:-1] + "1")
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

def sep(number, loc=''):
	"""Adds a thousands separator to the number.
	The function is locale aware."""
	locale.setlocale(locale.LC_ALL, loc)
	return locale.format('%d', number, True)
	
def show_spinner(amount):
	"""amount: a number"""
	sys.stdout.write("\b%s" % ['|', '/', '-', '\\'][amount % 4])

def remove_spinner():
	sys.stdout.write("\b"), # removes spinner
	
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
				except OSError: # it's a dir?
					remove_folder(fullname)
	try:
		os.rmdir(path)
	except OSError:
		os.rmdir("\\\\?\\" + path)
		
###############################################################################

def diff_lists(one, two):
	"""Accepts two lists."""
#	d = difflib.Differ() #linejunk=ignore_newline)
#	oneclean = []
#	twoclean = []
#	for line in one:
#		oneclean.append(line.encode('ascii', 'replace'))
#	for line in two:
#		twoclean.append(line.encode('ascii', 'replace'))
#	#a = d.compare(oneclean, twoclean)
#	print("\n".join(list(a)))
#	

	#TODO: remove empty lines?

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
		else: # ? or space
			no += 1
			res.append(" ")
	#print(res)
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

def decodetext(bytes, *pos, **kw):
	"""Decode a string using TextIOWrapper"""
	return TextIOWrapper(BytesIO(bytes), *pos, **kw).read()


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
	