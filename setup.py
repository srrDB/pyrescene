from distutils.core import setup
import rescene
import sys

# http://infinitemonkeycorps.net/docs/pph/
# http://as.ynchrono.us/2007/12/filesystem-structure-of-python-project_21.html

# http://packages.python.org/distribute/setuptools.html#specifying-your-project-s-version
# http://stackoverflow.com/questions/458550/standard-way-to-embed-version-into-python-package
# http://guide.python-distribute.org/creation.html#arranging-your-file-and-directory-structure

# http://google-styleguide.googlecode.com/svn/trunk/pyguide.html
# http://docs.python.org/library/pydoc.html

# http://www.pyinstaller.org/
# http://sourceforge.net/projects/cx-freeze/

# http://docs.python.org/2/distutils/sourcedist.html
# build the package:
# $ python setup.py sdist

config_dict = {
    "name": "pyReScene",
    "packages": ["rescene", "resample"],
    "scripts": [
		"bin/srr.py", 
		"bin/srs.py", 
		"bin/pyrescene.py", 
		"bin/preprardir.py",
		"bin/retag.py"],
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
"""
}

# for creating Windows EXE files
if 'py2exe' in sys.argv:
	import py2exe #@UnresolvedImport #@UnusedImport
	
	# http://www.py2exe.org/index.cgi/ListOfOptions
	config_dict["options"] = {
		'py2exe': {
			'bundle_files': 2,  # bundle everything but the Python interpreter
	        'optimize': 2,      # 2 = extra optimization (like python -OO)
	        'compressed': True  # compressed zipfile
	     }
	}
	
	# name of shared zipfile to generate
	# None: the files will be bundled within the executable
	config_dict["zipfile"] = "pyrescenelibrary.zip"
	
	# targets to build
	config_dict["console"] = [{
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
	{
	    'script': "bin/retag.py",
	    'icon_resources': [(1, 'images/icon.ico')]
	}]
		
setup(**config_dict)
