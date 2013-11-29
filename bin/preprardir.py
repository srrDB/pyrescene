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

from __future__ import print_function

from optparse import OptionParser
from datetime import datetime
import sys
import os
import re
import subprocess
import shutil
import tarfile
from contextlib import closing # used for tarfile on Python 2.6

try:
	import _preamble
except ImportError:
	pass

import rescene
from rescene.rar import RarReader
from rescene.main import RETURNCODE
from rescene.unrar import locate_unrar

def main(options, args):
	input_dir = args[0]
	output_dir = args[1]
	
	if not os.path.isdir(input_dir):
		print("The input argument must be a directory.")
		return 1
	
	if not os.path.isdir(output_dir):
		try:
			os.makedirs(output_dir)
		except OSError:
			pass
		if not os.path.isdir(output_dir):
			print("The output argument must be a directory.")
			return 1
	
	try:
		extract_rarbin(input_dir, output_dir)
	except OSError:
		print("Could not find installed UnRAR version.")
		return 1
	copy_license_file(output_dir)

def copy_license_file(output_dir):
	"""From WinRAR order.htm:
	If you use WinRAR, you will need to copy the registration key file 
	(rarreg.key) to a WinRAR folder or to %APPDATA%\WinRAR folder. By default 
	WinRAR folder is "C:\Program Files\WinRAR", but it can be changed by a user
	when installing WinRAR.
	
	If you use RAR/Unix and RAR for OS X, you should copy rarreg.key to your 
	home directory or to one of the following directories: /etc, /usr/lib, 
	/usr/local/lib, /usr/local/etc. You may rename it to .rarreg.key or 
	.rarregkey, if you wish, but rarreg.key is also valid.
	"""
	unrar = locate_unrar()
	if os.path.isfile(unrar):
		# a WinRAR folder
		licfile = os.path.join(os.path.basename(unrar), "RarReg.key")
		if os.path.isfile(licfile):
			shutil.copy(licfile, output_dir)
			return True
	# %APPDATA%\WinRAR folder
	try:
		licfile = os.path.join(os.environ["appdata"], "WinRAR", "RarReg.key")
		if os.path.isfile(licfile):
			shutil.copy(licfile, output_dir)
			return True
	except KeyError:
		pass # KeyError: 'appdata' on Linux
	if os.name == "posix":
		locations = ["~", "/etc", "/usr/lib", 
					"/usr/local/lib", "/usr/local/etc"]
		for loc in locations:
			loc = os.path.expanduser(loc)
			for name in ("rarreg.key", ".rarreg.key", ".rarregkey"):
				reg = os.path.join(loc, name)
				if os.path.isfile(reg):
					shutil.copy(reg, output_dir)
					return True
	return False
	
def extract_rarbin(source, dest, unrar=locate_unrar()):
	dest = os.path.abspath(dest)
	for fname in os.listdir(source):
		tag = versiontag(fname)
		if (not tag or (not ".exe" in fname and not ".tar.gz" in fname and
			not ".sfx" in fname)):
			continue
		elif tag.large < 2:
			continue
		elif not options.enable_beta and tag.beta:
			continue
		archive_name = os.path.join(source, fname)
		date, name = get_rar_date_name(archive_name)
		if date and name:
			if tarfile.is_tarfile(archive_name):
				new_name = date + "_rar%s" % tag
				print("Extracting %s..." % new_name, end=" ")
				with closing(tarfile.open(archive_name)) as tf:
					exe = tf.getmember("rar/rar")
					tf.extract(exe, path=dest)
					try:
						os.rename(os.path.join(dest, "rar", "rar"),
						          os.path.join(dest, new_name))
						print("done.")
					except: # WindowsError: # [Error 183]
						# ERROR_ALREADY_EXISTS
						os.unlink(os.path.join(dest, "rar", "rar"))	
						print("failed.")
					os.rmdir(os.path.join(dest, "rar"))
			else:
				new_name = date + "_rar%s.exe" % tag
				if ".sfx" in fname:
					# no extension for Linux executables
					new_name = new_name[:-4]
				print("Extracting %s..." % new_name, end=" ")
				args = [unrar, "e", archive_name, name, dest]
				extract = custom_popen(args)
				if extract.wait() in (0, 1):
					# Error code 1: when there is some corruption in the file
					# Verifying authenticity information ...  Failed
					# has been seen on wrar260.exe
					try:
						# for rarln271.sfx and others
						name = os.path.basename(name)
						os.rename(os.path.join(dest, name), 
								  os.path.join(dest, new_name))
						if extract.wait() == 1:
							print("done. (Non fatal error(s) occurred)")
						else:
							print("done.")
					except: # WindowsError: # [Error 183]
						# ERROR_ALREADY_EXISTS
						os.unlink(os.path.join(dest, name))
						print("failed.")
				else:
					print(RETURNCODE[extract.wait()])
					# not sure the following is necessary
					# but if the file is extracted to disk,
					# remove it so the next steps can continue successfully
					try:
						os.unlink(os.path.join(dest, name))
					except:
						pass
		else:
			print("error: %s" % fname)

def get_rar_date_name(file_name):
	if file_name.endswith(".exe") or file_name.endswith(".sfx"):
		for block in RarReader(file_name, enable_sfx=True):
			try:
				if block.file_name in ("Rar.exe", "Rar.Exe", "rar\\rar", "rar"):
					t = block.file_datetime
					return ("%d-%02d-%02d" % (t[0], t[1], t[2]), 
					                          block.file_name)
			except Exception:
				pass
	elif tarfile.is_tarfile(file_name):
		with closing(tarfile.open(file_name)) as tf:
			mtime = tf.getmember("rar/rar").mtime
			return (datetime.fromtimestamp(mtime).strftime("%Y-%m-%d"), 
			        "rar/rar")
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
	# Windows
	match = re.match("[a-zA-Z]+(?P<x64>-x64-)?"
					 "(?P<large>\d)(?P<small>\d\d?)"
					 "(?P<beta>b\d)?.+", file_name)
	if match:
		x64, large, small, beta = match.group("x64", "large", "small", "beta")
		if len(small) == 1:
			small += "0"
		return VersionTag(large, small, beta, x64)
	# Linux, OS X, BSD
	match = re.match("rar(osx|linux|bsd)-(?P<x64>x64-)?"
					 "(?P<large>\d)\.(?P<small>\d(\.\d)?)\.?"
					 "(?P<beta>b\d)?\.tar.gz", file_name)
	if match:
		x64, large, small, beta = match.group("x64", "large", "small", "beta")
		if len(small) == 1:
			small += "0"
		else:
			small = small.replace(".", "")
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
	
	parser.add_option("-b", "--beta", dest="enable_beta", default=False,
					  action="store_true",
					  help="extract beta versions too")

	if len(sys.argv) < 3:
		# show application usage
		parser.print_help()
	else:
		(options, args) = parser.parse_args()
		sys.exit(main(options, args))
	