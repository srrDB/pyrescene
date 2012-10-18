#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2012 pyReScene
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

__version_info__ = ('0', '1')
__version__ = '.'.join(__version_info__)

from rescene.main import *
from rescene.rarstream import *
from rescene.utility import *

# Version history:
# 0.1 (2011-11-11) Initial release

APPNAME = "pyReScene"
APPNAMEVERSION = "pyReScene" + __version__

#
#import os, sys, optparse
#
## make the scripts in the scripts folder work when ran from terminal
#cmd_folder = os.path.dirname(os.path.abspath(__file__))
#if cmd_folder not in sys.path:
#    sys.path.insert(0, cmd_folder)
#    
#import rescene
#import rar
#import utility
#import rarstream
#import osohash 
    
#VERSION = "0.1 (2011-06-06)"
#PACKAGE = "rescene"
#APPNAME = "pyReScene"
#LICENSE = "MIT"
#WEBSITE = ""

# 0.1 (date) ?
#http://packages.python.org/distribute/setuptools.html#specifying-your-project-s-version
#http://stackoverflow.com/questions/458550/standard-way-to-embed-version-into-python-package

# http://guide.python-distribute.org/creation.html#arranging-your-file-and-directory-structure

# http://google-styleguide.googlecode.com/svn/trunk/pyguide.html
# http://docs.python.org/library/pydoc.html