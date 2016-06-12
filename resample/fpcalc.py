#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2013 pyReScene
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

import subprocess
import inspect
import os
import sys
import tempfile
from distutils.spawn import find_executable
from rescene.utility import fsunicode
from resample.mp3 import Mp3Reader

MSG_NOTFOUND = "The fpcalc executable isn't found."

fpcalc_executable = ""

class ExecutableNotFound(Exception):
	"""The fpcalc.exe executable isn't found."""

def fingerprint(file_name, temp_dir=None, recursive=0):
	"""Calculates the fingerprint of the given file.
	temp_dir: optional temporary directory to use
	recursive: local parameter to prevent endless loop after stripping tags"""
	duration = fp = b""
	bad = False
	fpcalc = find_fpcalc_executable()
	temp_cleanup = False

	try:
		file_name.encode('ascii')
	except:
		# file has special characters
		# I don't know how to pass those to fpcalc
		# => create a temporary file for these rare cases
		# test release: VA-Tony_Hawks_Pro_Skater_4-Soundtrack-2003-RARNeT
		# copy the file with a default name and create the fp for that file
		print("Non-ASCII characters detected: creating temporary file.")
		temp_cleanup = True
		name_suffix = make_temp_suffix(file_name)
		(fd, tmpname) = tempfile.mkstemp(name_suffix, dir=temp_dir)
		os.close(fd)  # we won't use it
		with open(file_name, "rb") as music_file:
			with open(tmpname, "wb") as tmpf:
				tmpf.write(music_file.read())
		file_name = tmpname

	# Set fingerprint length to 120 seconds
	# older fpcalc versions default to 60 seconds
	fprint = custom_popen([fpcalc, '-length', '120', file_name])
	stdout, _stderr = fprint.communicate()

	lines = stdout.split(os.linesep.encode("ascii"))
	for line in lines:
		if line.startswith(b"DURATION="):
			duration = line[len(b"DURATION="):]
		elif line.startswith(b"FINGERPRINT="):
			fp = line[len(b"FINGERPRINT="):]
# 		ERROR: couldn't open the file
# 		ERROR: unable to calculate fingerprint for file
		elif line.startswith(b"ERROR: couldn't open the file"):
			bad = True
# 		ERROR: couldn't find stream information in the file
# 		ERROR: unable to calculate fingerprint for file X.srs, skipping
		elif line.startswith(b"ERROR: couldn't find stream"):
			bad = True

	if not duration or not fp:
		bad = True

	if bad:
		# strip any recognized tags from the music file and try again
		# (ID3v2 tag around RIFF file)
		# e.g. (angelmoon)-hes_all_i_want_cd_pg2k-bmi
		# ERROR: couldn't find stream information in the file
		# ERROR: unable to calculate fingerprint for file x.mp3, skipping
		if recursive > 1:
			# tags have been stripped before already
			raise ValueError("Fingerprinting failed.")
		else:
			recursive += 1

		print("Stripping recognized tags for better fpcalc detection.")
		name_suffix = make_temp_suffix(file_name)
		(fd, stripped) = tempfile.mkstemp(name_suffix, dir=temp_dir)
		os.close(fd)  # we won't use it

		try:
			if recursive < 2:
				with open(stripped, "wb") as tmpf:
					mr = Mp3Reader(file_name)
					for block in mr.read():
						if block.type in ("MP3", "fLaC"):  # main music data
							read = 0
							to_read = 65536
							while read < block.size:
								if read + to_read > block.size:
									to_read = block.size - read
								tmpf.write(mr.read_part(to_read, read))
								read += to_read
							break  # exit for: music data copied
					mr.close()
			else:
				# no double tagging: try to strip away the crap
				# Yano2d-Der_Bunte_Hund_Im_Untergrund-WEB-DE-2014-CUSTODES_INT
				# has Adobe crap and something that looks like ascii art,
				# but in a hex editor
				with open(file_name, "rb") as orig:
					string_index = -1
					current = 0
					# 1) find real mp3 data based on certain strings
					while True:
						orig.seek(current, os.SEEK_SET)
						# +3 for border cases overlap
						bytespart = orig.read(0x10000 + 3)
						if not len(bytespart):
							break
						m1 = bytespart.find(b"Xing")
						m2 = bytespart.find(b"LAME")
						matches = [x for x in [m1, m2] if x >= 0]
						if len(matches):
							string_index = current + min(matches)
							break
						current += 0x10000  # 64KiB batches

					if string_index < 0:
						raise ValueError("Fingerprinting failed: "
							"no MP3 string found.")

					# 2) find last MP3 sync block before found string
					# 256 bytes: random amount that seems enough
					orig.seek(string_index - 0x100, os.SEEK_SET)
					stack = orig.read(0x100)
					sync_index = stack[:-1].rfind(b"\xFF")
					while sync_index > -1:
						next_byte = ord(stack[sync_index:sync_index + 1])
						if next_byte & 0xE0 == 0xE0:
							break
						sync_index = stack.rfind(b"\xFF", 0, sync_index)

					# 3) write out the cleaned music data to fingerprint on
					with open(stripped, "wb") as tmpf:
						sync_start = string_index - (0x100 + sync_index)
						orig.seek(sync_start, os.SEEK_SET)
						tmpf.write(orig.read())

			duration, fp = fingerprint(stripped, temp_dir, recursive)
			bad = False  # it succeeded (exception otherwise)
		except:
			if recursive == 2:
				print("----------------------------------------------------")
				print("Tell me if the .sfv matches the music file!")
				print("Otherwise your file is most likely totally corrupt.")
				print("----------------------------------------------------")
				# Alpha_Blondy_and_The_Wailers-Jerusalem-1986-YARD track 3
			# this would be a very rare case:
			# double bad tagging or just bad data?
			raise
		finally:
			# cleanup temporary stripped file
			print("Removing %s" % stripped)
			os.remove(stripped)

	if temp_cleanup:
		print("Removing %s" % tmpname)
		os.remove(tmpname)

	if bad:
		raise ValueError("Fingerprinting failed.")

	return duration, fp

def find_fpcalc_executable():
	# if we already located it before
	global fpcalc_executable
	if fpcalc_executable:
		return fpcalc_executable

	# see if it's in the path + other predefined locations
	# when running from source: check current directory
	# when running from source: check bin directory
	script_dir = os.path.dirname(os.path.abspath(
	                             inspect.getfile(inspect.currentframe())))
	bin_dir = os.path.join(script_dir, "..", "bin")

	path = os.pathsep.join([script_dir, bin_dir, module_path(),
	                        os.getenv('PATH', "")])
	result = find_executable("fpcalc", path=path)

	result = check_fpcalc_validity(result)

	if result:
		print(result)
		fpcalc_executable = result
		return fpcalc_executable
	else:
		raise ExecutableNotFound(MSG_NOTFOUND)

def check_fpcalc_validity(potential_fpcalc_executable):
	"""It tries to run the executable to check viability.
	Windows: (empty fpcalc.exe file in path)
	[Error 193] %1 is not a valid Win32 application
	Linux:
	[Errno 2] No such file or directory
	"""
	# fpcalc was not found
	if potential_fpcalc_executable is None:
		return None

	# something is wrong with the executable
	try:
		custom_popen([potential_fpcalc_executable])
	except (OSError, IOError) as err:
		msg = None
		# Windows help messages
		try:
			if err.winerror == 216:  # errno 8
				msg = "fpcalc.exe has the wrong architecture"
			elif err.winerror == 193:  # errno 22
				msg = "fpcalc.exe is not an executable"
		except:
			pass

		# *nix help messages
		if not msg:
			try:
				if err.errno == 13:  # Permission denied
					msg = "fpcalc has no execution rights"
				elif err.errno == 8:  # Exec format error
					msg = "fpcalc has the wrong architecture"
			except:
				pass
		if msg:
			print(msg)
		return None
	except Exception as ex:
		print("Tell me about this unexpected error below!")
		print(ex)  # any other exception should not happen
		return None

	# the executable ran just fine
	return potential_fpcalc_executable

def make_temp_suffix(file_name):
	nm = "-pyReScene_fpcalc"
	if file_name.endswith(".flac"):
		nm += ".flac"
	else:
		nm += file_name[-4:]
	return nm

# http://www.py2exe.org/index.cgi/WhereAmI
def we_are_frozen():
	"""Returns whether we are frozen via py2exe.
	This will affect how we find out where we are located."""
	return hasattr(sys, "frozen")

def module_path():
	""" This will get us the program's directory,
	even if we are frozen using py2exe"""
	if we_are_frozen():
		return os.path.dirname(fsunicode(sys.executable))
	return os.path.dirname(fsunicode(__file__))

def custom_popen(cmd):
	"""disconnect cmd from parent fds, read only from stdout"""

	# needed for py2exe
	creationflags = 0
	if sys.platform == 'win32':
		creationflags = 0x08000000  # CREATE_NO_WINDOW

	# run command
	return subprocess.Popen(cmd, bufsize=0, stdout=subprocess.PIPE,
							stdin=subprocess.PIPE, stderr=subprocess.STDOUT,
							creationflags=creationflags)
