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

import os
from distutils.spawn import find_executable

try:
	# renamed to winreg in Python 3
	from _winreg import *
except ImportError:
	try:
		from winreg import *
	except ImportError:
		pass

def locate_unrar():
	"""locating installed unrar"""
	if(os.name == "nt"):
		unrar = locate_windows()
	else:
		unrar = locate_unix()
	return unrar

def locate_windows():
	unrar = ""
	try:
		unrar = os.environ["ProgramW6432"] + "\\WinRAR\\UnRAR.exe"
		if not os.path.exists(unrar):
			unrar = os.environ["ProgramW6432"] + "\\Unrar\\UnRAR.exe"
			if not os.path.exists(unrar):
				raise KeyError
	except KeyError:
		try:
			unrar = os.environ["ProgramFiles(x86)"] + "\\WinRAR\\UnRAR.exe"
			if not os.path.exists(unrar):
				unrar = os.environ["ProgramFiles(x86)"] + "\\Unrar\\UnRAR.exe"
				if not os.path.exists(unrar):
					raise KeyError
		except KeyError:
			unrar = try_registry()
			if not unrar:
				print("-----------------------------------------------")
				print("Install WinRAR to use all the functionalities.")
				print("Freeware 'UnRAR for Windows' is already enough.")
				print("http://www.rarlab.com/rar_add.htm")
				print("-----------------------------------------------")
				unrar = "UnRAR.exe" 
			
	# define your own path to a program to unrar: (uncomment)
	#unrar = "C:\Program Files\7z.exe"
	return unrar

def try_registry():
	"""try grabbing location from the Windows registry"""
	try:
		regpath = ("SOFTWARE\\Microsoft\\Windows\\" +
		           "CurrentVersion\\App Paths\\WinRAR.exe")
		key = OpenKey(HKEY_LOCAL_MACHINE, regpath, 0, KEY_READ)
		unrar = os.path.join(QueryValueEx(key, "Path")[0], "UnRAR.exe")
		if os.path.isfile(unrar):
			return unrar
		else:
			raise
	except:
		return None

def locate_unix():
	return find_executable("unrar")

def unrar_is_available():
	return os.path.isfile(os.path.abspath(locate_unrar()))

if __name__ == '__main__':
	print(locate_unrar())
	print(try_registry())