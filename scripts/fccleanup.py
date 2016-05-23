#!/usr/bin/env python
# -*- coding: latin-1 -*-

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA 02110-1301, USA.

import os, sys, optparse
sys.path.append(os.path.join(os.getcwd(), '..'))
from tempfile import mkstemp
from rescene.rar import RarReader, BlockType, SrrHeaderBlock

def process(rootdir):
    for root, _, files in os.walk(rootdir):
        for file in files:
            if file[-4:].lower() == ".srr":
                fpath = os.path.join(root, file)
                fix(fpath)

        if not options.r:  # not recursive
            break

def fix(srr_file):
    print("Fixing %s" % srr_file)
    blocks = RarReader(srr_file).read_all()

    # directory for the fixed files
    fixeddir = os.path.join(os.path.dirname(srr_file), "fixed")
    try:
        os.makedirs(fixeddir)
    except: pass  # Path already exists

    # create a temporarily file
    tmpfd, tmpname = mkstemp(prefix="remove_", suffix=".srr", dir=fixeddir)
    tmpfile = os.fdopen(tmpfd, "wb")

    try:
        for block in blocks:
            if block.rawtype == BlockType.SrrHeader:
#                tmpfile.write(block.bytes())
                tmpfile.write(SrrHeaderBlock(
                                appname="FireScene Cleanup").bytes())
            if block.rawtype == BlockType.SrrStoredFile:
                # insert block and data after the SRR header
                tmpfile.write(block.bytes())
                tmpfile.write(block.srr_data())
        for block in blocks:
            if block.rawtype != BlockType.SrrHeader and  \
                block.rawtype != BlockType.SrrStoredFile:
                # copy block and data
                tmpfile.write(block.bytes())
        tmpfile.close()
        # os.remove(srr_file)
        os.rename(tmpname, os.path.join(fixeddir, os.path.basename(srr_file)))
    except:
        os.unlink(tmpname)
        raise

def main(options, args):
#    print(options)
#    print(args)
    for dir in args:
        process(dir)

if __name__ == '__main__':
    parser = optparse.OptionParser(
    usage="Usage: %prog [options] srr directory'\n"
    "This tool will fix SRR files for FireScene.\n"
    "SRR files merged with 'ReScene Database Cleanup Script 1.0' don't put "
    "all stored file blocks at the beginning of the SRR file.",
    version="%prog 0.1")  # --help, --version

    param = optparse.OptionGroup(parser, "Parameter list")
    parser.add_option_group(param)

    param.add_option("-r", help="Recurse subdirectories.",
                     action="store_true", default=False)

    # no arguments given
    if len(sys.argv) < 2:
        print(parser.format_help())
    else:
        (options, args) = parser.parse_args()
        main(options, args)
        print("Done.")
