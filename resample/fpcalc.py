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
from distutils.spawn import find_executable

MSG_NOTFOUND = "The fpcalc executable isn't found."

fpcalc_executable = ""

class ExecutableNotFound(Exception):
	"""The fpcalc.exe executable isn't found."""
	
def fingerprint(file_name):
	duration = fp = b""
	bad = False
	fpcalc = find_fpcalc_executable()
	
	fprint = custom_popen([fpcalc, file_name])
	stdout, _stderr = fprint.communicate()
			
	lines = stdout.split(os.linesep.encode("ascii"))
	for line in lines:
		if line.startswith(b"DURATION="):
			duration = line[len(b"DURATION="):]
		elif line.startswith(b"FINGERPRINT="):
			fp = line[len(b"FINGERPRINT="):]
#		ERROR: couldn't open the file
#		ERROR: unable to calculate fingerprint for file
		elif line.startswith(b"ERROR: couldn't open the file"):
			bad = True
#		ERROR: couldn't find stream information in the file
#		ERROR: unable to calculate fingerprint for file X.srs, skipping
		elif line.startswith(b"ERROR: couldn't find stream"):
			bad = True
		
	if not duration or not fp:
		bad = True
		
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

	if result:
		print(result)
		fpcalc_executable = result
		return fpcalc_executable
	else:
		raise ExecutableNotFound(MSG_NOTFOUND)
	
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

try:
	unicode
except NameError:  # Python 3
	def fsunicode(path):
		return path
else:  # Python < 3
	def fsunicode(path):
		return unicode(path, sys.getfilesystemencoding())

def custom_popen(cmd):
	"""disconnect cmd from parent fds, read only from stdout"""
	
	# needed for py2exe
	creationflags = 0
	if sys.platform == 'win32':
		creationflags = 0x08000000 # CREATE_NO_WINDOW

	# run command
	return subprocess.Popen(cmd, bufsize=0, stdout=subprocess.PIPE, 
							stdin=subprocess.PIPE, stderr=subprocess.STDOUT, 
							creationflags=creationflags)