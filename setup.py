#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

from distutils.core import setup
from distutils.command.build_py import build_py
import rescene
import sys

try:
	import py2exe #@UnresolvedImport #@UnusedImport
except:
	pass

class BuildFindUnrarExe(build_py):
	"""Custom build command for unrar.exe build."""
	description = "build exe that can locate unrar"

	def run(self):
		dist = self.distribution
		dist.console = [{
		    'script': "rescene/unrar.py",
		    'icon_resources': [(1, 'images/icon.ico')]
		},]
		dist.command_options["py2exe"]["bundle_files"] = ('setup script', 1)
		self.run_command('py2exe')
		build_py.run(self)
		
class BuildSpecificExe(build_py):
	"""Custom build command for specific EXE build."""
	description = "build a specific pyReScene EXE file"
	user_options = build_py.user_options + [
		# The format is (long option, short option, description).
		("path=", "p", "internal path to script e.g. 'rescene/unrar.py'"),
	]
	
	def initialize_options(self, *args, **kwargs):
		self.path = None
		build_py.initialize_options(self, *args, **kwargs)

	def run(self):
		if not self.path:
			print("Error: --path parameter must be provided")
			print("       for example: -p \"usenet/srr_usenet.py\"")
			return
		dist = self.distribution
		dist.console = [{
		    'script': self.path,
		    'icon_resources': [(1, 'images/icon.ico')]
		},]
		dist.command_options["py2exe"]["bundle_files"] = ('setup script', 1)
		# enable to have one large .exe with everything:
		# dist.zipfile = None
		self.run_command('py2exe')
		build_py.run(self)

config_dict = {
    "name": "pyReScene",
    "packages": ["rescene", "resample"],
    "scripts": [
		"bin/srr.py", 
		"bin/srs.py", 
		"bin/pyrescene.py", 
		"bin/preprardir.py",
		"bin/retag.py"
	],
    "version": rescene.__version__,
    "description": "Python ReScene and ReSample implementation",
    "author": "Gfy", # ~umlaut@adsl-66-136-81-22.dsl.rcsntx.swbell.net (umlaut)
    "author_email": "pyrescene@gmail.com",
    "url": "https://bitbucket.org/Gfy/pyrescene",
    "download_url": "https://bitbucket.org/Gfy/pyrescene/downloads",
    "license": "MIT",
    "keywords": ["rescene", "srr", "resample", "srs", "repackage", "rar",
	            "avi", "mkv", "mp4", "wmv", "warez", "scene", "compressed",
	            "mp3", "flac", "retag"],
    "classifiers": [
		"Development Status :: 4 - Beta",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.2",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Environment :: Console",
        "Intended Audience :: End Users/Desktop",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Topic :: System :: Archiving :: Backup",
        "Topic :: Utilities"
    ], # http://pypi.python.org/pypi?:action=list_classifiers
    "long_description": """\
pyReScene is a port of ReScene .NET to the Python programming language.
ReScene is a mechanism for backing up and restoring the metadata from "scene" 
released RAR files. RAR archive volumes are rebuild using the stored metadata 
in the SRR file and the extracted files from the RAR archive. 
pyReScene consists of multiple related tools.
""",
	# http://www.py2exe.org/index.cgi/ListOfOptions
	"options": {
		'py2exe': {
			'bundle_files': 2,  # bundle everything but the Python interpreter
			'optimize': 2,      # 2 = extra optimization (like python -OO)
			'compressed': True  # compressed zipfile
		}
	},
	# name of shared zipfile to generate
	# None: the files will be bundled within the executable
	# Not .zip because someone extracted it...
	"zipfile": "pyrescenelibrary.dat",
	# targets to build
	"console": [{
		    'script': "bin/srr.py",
		    'icon_resources': [(1, 'images/icon.ico')]
		},
		{
		    'script': "bin/srs.py",
		    'icon_resources': [(1, 'images/icon.ico')]
		},
		{
		    'script': "bin/pyrescene.py",
		    'icon_resources': [(1, 'images/icon.ico')]
		},
		{
		    'script': "bin/preprardir.py",
		    'icon_resources': [(1, 'images/icon.ico')]
		},
# 		{
# 		    'script': "usenet/srr_usenet.py",
# 		    'icon_resources': [(1, 'images/icon.ico')]
# 		},
		{
		    'script': "bin/retag.py",
		    'icon_resources': [(1, 'images/icon.ico')]
		}
	],
			
	"cmdclass": {
		"unrar": BuildFindUnrarExe,
		"exe": BuildSpecificExe,
	}
}

def main():
	"""
	https://docs.python.org/3/distutils/sourcedist.html
	
	build the package:
	$ python setup.py sdist
	
	build the executables:
	$ python setup.py py2exe
	
	build a specific .exe file not in the build above
	$ python setup.py exe --path "usenet/srr_usenet.py"
	"""
		
	if "py2exe" in sys.argv:	
		# files to output in the dist dir with the executables
		# http://www.py2exe.org/index.cgi/data_files
		py2exe_data_files = [("", [
			"bin/windows/add_current_dir_to_path.bat",
			"bin/py2exe/shell_extension-setup.bat",
			"bin/py2exe/shell_extension-srrit.bat",
			"bin/py2exe/auto.bat",
			"bin/py2exe/README.txt",
			#"usenet/srr_usenet_template.cfg",
			"README",
			"NEWS",
			"AUTHORS",
		])]
		config_dict['data_files'] = py2exe_data_files
		
		# TODO: pywin32 a required dependency?

	setup(**config_dict)

if __name__ == '__main__':
	main()

# http://infinitemonkeycorps.net/docs/pph/
# http://as.ynchrono.us/2007/12/filesystem-structure-of-python-project_21.html

# http://packages.python.org/distribute/setuptools.html#specifying-your-project-s-version
# http://stackoverflow.com/questions/458550/standard-way-to-embed-version-into-python-package
# http://guide.python-distribute.org/creation.html#arranging-your-file-and-directory-structure

# http://google-styleguide.googlecode.com/svn/trunk/pyguide.html
# http://docs.python.org/library/pydoc.html

# http://www.pyinstaller.org/
# http://sourceforge.net/projects/cx-freeze/
# http://nuitka.net/pages/overview.html