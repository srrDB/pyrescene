#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) Twisted Matrix Laboratories.
# Copyright (c) 2001-2012
# Allen Short
# Andy Gayton
# Andrew Bennetts
# Antoine Pitrou
# Apple Computer, Inc.
# Benjamin Bruheim
# Bob Ippolito
# Canonical Limited
# Christopher Armstrong
# David Reid
# Donovan Preston
# Eric Mangold
# Eyal Lotem
# Itamar Turner-Trauring
# James Knight
# Jason A. Mobarak
# Jean-Paul Calderone
# Jessica McKellar
# Jonathan Jacobs
# Jonathan Lange
# Jonathan D. Simms
# Jürgen Hermann
# Kevin Horn
# Kevin Turner
# Mary Gardiner
# Matthew Lefkowitz
# Massachusetts Institute of Technology
# Moshe Zadka
# Paul Swartz
# Pavel Pergamenshchik
# Ralph Meijer
# Sean Riley
# Software Freedom Conservancy
# Travis B. Hartwell
# Thijs Triemstra
# Thomas Herve
# Timothy Allen
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# This makes sure that users don't have to set up their environment
# specially in order to run these programs from bin/.

# This helper is shared by many different actual scripts. It is not intended to
# be packaged or installed, it is only a developer convenience. By the time
# pyReScene is actually installed somewhere, the environment should 
# already be set up properly without the help of this tool.

import sys
import os

path = os.path.abspath(sys.argv[0])
while os.path.dirname(path) != path:
    if os.path.exists(os.path.join(path, 'rescene', '__init__.py')):
        sys.path.insert(0, path)
        break
    path = os.path.dirname(path)
