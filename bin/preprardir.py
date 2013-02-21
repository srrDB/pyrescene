#!/usr/bin/env python
# encoding: utf-8

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

from optparse import OptionParser
import sys
import os
import re
import subprocess
import shutil

try:
	import _preamble
except ImportError:
	sys.exc_clear()
	
import rescene
from rescene.rar import RarReader

def main(options, args):
	for element in args:
		if not os.path.isdir(element):
			print("One of the arguments isn't a folder.")
			return 1
		
	input_dir = args[0]
	output_dir = args[1]
	
	if os.name == "nt": # Windows
		extract_rarexe(input_dir, output_dir)
		copy_license_file(output_dir)
	else:
		print("No support for platforms other than Windows.")

def locate_unrar():
	"""locating installed unrar"""
	if(os.name == "nt"):
		try:
			unrar = os.environ["ProgramW6432"] + "\WinRAR\UnRAR.exe"
			if not os.path.exists(unrar):
				raise KeyError
		except KeyError:
			try:
				unrar = os.environ["ProgramFiles(x86)"] + "\WinRAR\UnRAR.exe"
				if not os.path.exists(unrar):
					raise KeyError
			except KeyError:
				print("Install WinRAR to use all the functionalities.")
				unrar = "UnRAR.exe" 
				
		# define your own path to a program to unrar: (uncomment)
		#unrar = "C:\Program Files\7z.exe"
	else:
		unrar = "/usr/bin/env unrar"
		
	return unrar

def copy_license_file(output_dir):
	unrar = locate_unrar()
	if os.path.isfile(unrar):
		licfile = os.path.join(os.path.basename(unrar), "RarReg.key")
		if os.path.isfile(licfile):
			shutil.copy(licfile, output_dir)
	
def extract_rarexe(source, dest, unrar=locate_unrar()):
	for fname in os.listdir(source):
		tag = versiontag(fname)
		if not tag or not ".exe" in fname:
			continue
		elif tag.large < 2 or tag.beta:
			continue
		date, name = get_rar_date_name(os.path.join(source, fname))
		if date and name:
			new_name = date + "_rar%s.exe" % tag
			print("Extracting %s..." % new_name)
			args = [unrar, "e", os.path.join(source, fname), name, dest]
			
			extract = custom_popen(args)
			if extract.wait() == 0:
				try:
					os.rename(os.path.join(dest, name), 
							  os.path.join(dest, new_name))
				except WindowsError: # [Error 183]
					# ERROR_ALREADY_EXISTS
					os.unlink(os.path.join(dest, name))
			else:
				print("error: %s" % fname)
		else:
			print("error: %s" % fname)

def get_rar_date_name(file_name):
	for block in RarReader(file_name, enable_sfx=True):
		try:
			if block.file_name in ("Rar.exe", "Rar.Exe"):
				t = block.file_datetime
				return ("%d-%02d-%02d" % (t[0], t[1], t[2]), block.file_name)
		except Exception:
			pass
	return None, None

class VersionTag(object):
	def __init__(self, large, small, beta, x64):
		self.large = int(large)
		self.small = int(small)
		if beta:
			self.beta = beta
		else:
			self.beta = ""
		if x64:
			self.x64 = True
		else:
			self.x64 = False
			
	def __str__(self, *args, **kwargs):
		return "%d%02d%s" % (self.large, self.small, self.beta)		
	
def versiontag(file_name):
	"""Returns version tag object."""
	match = re.match("[a-zA-Z]+(?P<x64>-x64-)?"
					 "(?P<large>\d)(?P<small>\d\d?)"
					 "(?P<beta>b\d)?.+", file_name)
	if match:
		x64, large, small, beta = match.group("x64", "large", "small", "beta")
		if len(small) == 1:
			small += "0"
		return VersionTag(large, small, beta, x64)
	return None

def custom_popen(cmd):
	"""disconnect cmd from parent fds, read only from stdout"""
	
	# needed for py2exe
	creationflags = 0
	if sys.platform == 'win32':
		creationflags = 0x08000000 # CREATE_NO_WINDOW

	# 3xPIPE seems unreliable, at least on osx
	try:
		null = open(os.devnull, "wb")
		_in = null
		_err = null
	except IOError:
		_in = subprocess.PIPE
		_err = subprocess.STDOUT

	# run command
	return subprocess.Popen(cmd, stdout=subprocess.PIPE, 
							stdin=_in, stderr=_err, 
							creationflags=creationflags)
		
if __name__ == '__main__':
	parser = OptionParser(
	usage=("Usage: %prog [input dir] [output dir]\n"
	"This tool will extract RAR executables in preparation for "
	"compressed RAR support for pyReScene.\n"
	"Example usage: %prog Z:\\rar\\windows C:\\pyReScene\\rar"), 
	version="%prog " + rescene.__version__) # --help, --version

	if len(sys.argv) != 3:
		# show application usage
		parser.print_help()
	else:
		(options, args) = parser.parse_args()
		sys.exit(main(options, args))
	