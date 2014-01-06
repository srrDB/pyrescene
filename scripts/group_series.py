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

import optparse
import sys
import os
import re
import itertools

def normalize(name):
    return re.sub("\.|_", ".", name.lower()).strip(".")

def main(options, args):
    for element in args:
        element = os.path.abspath(element)
        if os.path.isfile(element):
            rellist = []
            cleaned = []
            grouped = {}
            # read releases from text document
            with open(element, 'rt') as relnames:
                line = relnames.readline()
                while line:
                    rellist.append(line)
                    line = relnames.readline()
                    
            # try to group the releases together
            for release in rellist:
                m = re.match("(.*)S\d+E\d+.*", release, re.IGNORECASE)
                if not m:
                    m = re.match("(.*)\d+x\d+.*", release, re.IGNORECASE)
                if m:
                    # don't add it to the list if foreign
                    if options.foreign:
                        foreign = (".*(french|german|subpack|"
                                   "dutch|flemish|swedish).*")
                        if re.match(foreign, m.group(0), re.I):
                            continue
                    cleaned.append(normalize(m.group(1)))
                    
            for (key, iterator) in itertools.groupby(cleaned):
                grouped[key] = sum(1 for _ in iterator)
                #print("%03d;%s" % (sum(1 for _ in iter), key))
            
            # print the results
            for key in sorted(grouped, key=grouped.__getitem__, reverse=True):
                print("%3d;%s" % (grouped[key], key))
        else:
            print("WTF are you supplying me?")
         
if __name__ == '__main__':
    parser = optparse.OptionParser(
        usage="Usage: %prog [txt files]'\n"
        "This tool will group series and list a count.\n",
        version="%prog 0.1 (2011-11-23)") # --help, --version
    
    parser.add_option("-f", "--skip-foreign", 
                help="does not add some foreign and subpacks to the count",
                action="store_true", dest="foreign", default=False)

    # no arguments given
    if len(sys.argv) < 2:
        print(parser.format_help())
    else:
        (options, args) = parser.parse_args()
        main(options, args)
    