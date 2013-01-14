#!/usr/bin/env python
# -*- coding: latin-1 -*-

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

"""
Cut the .nzb files into manageable sizes so that no out of memory error
will be thrown:
- XmlSplit - A Command-line Tool That Splits Large XML Files
    http://xponentsoftware.com/xmlSplit.aspx

- xml_split - split huge XML documents into smaller chunks
    http://www.perlmonks.org/index.pl?node_id=429707
    http://search.cpan.org/~mirod/XML-Twig-3.39/
"""

from xml.dom.minidom import parse, Document
import optparse
import sys
import os
import re
import glob
import unittest

# for running the script directly from command line
sys.path.append(os.path.join(os.path.dirname(
                os.path.realpath(sys.argv[0])), '..'))

try:
    from rescene import merge_srrs
except ImportError:
    print("Can't import the rescene module.")

def folder_join_mapping(folder):
    return_mapping = {}
    for dirpath, dirnames, filenames in os.walk(folder):
        # join the srr files if necessary
        srr_files = []
        releasename = os.path.split(dirpath)[1]
        for file in filenames:
            if file[-4:] == ".srr":
                srr_files.append(os.path.join(releasename, file))
        if len(srr_files):
            return_mapping[releasename] = srr_files
    return return_mapping

def main(options, args):
    relFileMapping = {}
    fileRelMapping = {}
    unknown = []

    def read_tvbinz(sql):
        f = open(sql, 'r')
        for line in f.readlines():
            relname, srr = parseSql(line)
            relFileMapping.setdefault(relname, []).append(srr) 
            fileRelMapping[srr] = relname
                
            # show info while parsing
            if options.releases:
                print(relname)
            if options.srrs:
                print(srr)
        f.close()
    
    def read_nzb(nzb):
        doc = parse(nzb, bufsize=1000)
        for file_node in doc.getElementsByTagName("file"):
            subject = file_node.getAttribute("subject")
            relname, srr = parseSubject(subject)
            if srr == None: 
                unknown.append(subject)
                if options.unknowns:
                    print(subject.encode('utf-8'))
            else:
                relname = relname.strip()
                try:
                    relFileMapping[relname] += [srr] 
                except:
                    relFileMapping[relname] = [srr]
                fileRelMapping[srr] = relname
                    
                # show info while parsing
                if options.releases:
                    print(relname)
                if options.srrs:
                    print(srr)
                    
                # create new nzb files to download samples/srrs/...
                if options.separate and relname[0:4] != "Con.":
                    # Con.Artist, Con.Air folders are not possible in Windows
                    newdoc = Document()
                    top_element = doc.createElementNS(
                                        "http://www.newzbin.com/DTD/2003/nzb", 
                                        "nzb")
                    newdoc.appendChild(top_element)
                    top_element.appendChild(file_node)
                    
                    try: # when the "release name" has a \
                        f = os.path.join(options.separate, relname + ".nzb")
                        print("Writing nzb %s" % os.path.basename(f))
                        with open(f, "ab") as nzb_file:
                            nzb_file.write(newdoc.toxml("utf-8"))
                    except Exception, e:
                        print(e)

    if options.folderjoin:
        options.join_dir = options.folderjoin
        relFileMapping = folder_join_mapping(options.folderjoin)
    else:
        for nzb in args:
            try:
                # resolve wild cards
                for path in glob.glob(nzb):
                    print("Reading %s" % os.path.basename(path))
                    read_nzb(path)
            except Exception, e:
                print("Reading NZB file(s) failed. Trying SQL.")
                print("Reading %s" % os.path.basename(nzb))
#                read_tvbinz(nzb)
                
    if options.rename_dir:
        print("This does not for SRR files that need to be merged.")
        failed = []
        # try to rename all available files in the directory
        # for single SRR files
        for file in os.listdir(options.rename_dir):
            if fileRelMapping.has_key(file):
                bad = renameSrr(options.rename_dir, file, fileRelMapping[file])
                if bad:
                    failed.append(bad)
            else:
                print("File '%s' not in NZB." % file)
                
        printList(failed)
        
    if options.join_dir:
        # join srr files from a multiple cd release before renaming
        failed = []
        failed_join = []
        haveSubs = []
        
        # rel -> srr: "dupe" files (e.g. a repost)
        # srr -> rel: needs to be joined
        for release in relFileMapping.keys():
            # remove duplicates and sort
            files = sorted(set(relFileMapping[release]))
            
            # a file with the name 'subs' or 'extras' in it? put it at the end
            for file in files:
                if re.match(".*(subs|extras|proof|sample).*", file, re.I):
                    files.remove(file)
                    files.append(file)
                    haveSubs.append(release)
            relFileMapping[release] = files
            
            if len(files) > 1: # join SRR files to renamed one
                if options.joins:
                    print(release)
                    for srr in files:
                        print("\t%s" % srr) 
                else:
                    bad = joinSrr(options.join_dir, release, files)
                    if bad:
                        failed_join.append(bad)
            else: # rename SRR file
                bad = renameSrr(options.join_dir, file, release)
                if bad:
                    failed.append(bad)
        
        print("Failed files: ")
        printList(failed)
        print("Have subs SRR files: ")
        printList(set(haveSubs))
        print("Failed to join files: ")
        printList(failed_join)
        
    # list all SRR files under the release name
    if options.both:
        for release in relFileMapping.keys():
            print(release)
            for srr in relFileMapping[release]:
                print("\t%s" % srr)     
        
    if options.list_dir:
        # lists all files in the given directory without their extension
        # so it can be used for the list search on srrdb.com
        for file in os.listdir(options.list_dir):    
            if os.path.isfile(os.path.join(options.list_dir, file)):
                print(file[:-4])

def renameSrr(dir, file, releaseName):
    old = os.path.join(dir, file)
    new = os.path.join(dir, "renamed", releaseName + ".srr")
    print(("Renaming %s to %s..." % (old, new))),
    try:
        os.renames(old, new)
        print("done!")
    except:
        print("failed!")
        # move unrenamed files to a separate dir
        new = os.path.join(dir, "unrenamed", file)
        print("Renaming %s to %s..." % (old, new))
        try:
            os.renames(old, new)    
        except: pass
        return file
    
def joinSrr(dir, release, files):
    dir = os.path.abspath(dir)
    try:
        os.makedirs(os.path.join(dir, "joined"))
    except: pass # Path already exists
    
    try:
        merge_srrs([os.path.join(dir, f) for f in files], 
                    os.path.join(dir, "joined", release + ".srr"),
                    "pyReScene Merge Script")
        # move original unjoined files
        for f in files:
            os.renames(os.path.join(dir, f), 
                       os.path.join(dir, "joined-orig", f))
    except:
        # one of the files was not found
        return files
        
def printList(list):
    for item in list:
        print("\t%s" % item)
                    
def parseSubject(subject): #[#altbin@EFNet]-[FULL]-[RELNAM
    exts = "\.(srr|srs|avi|mkv)"
    #exts = "\.(avi)"
    patternEfnet = (".*\[(.*EFNet|#a.b.teevee)\]-(?:\[(FULL|PART|Movie-Info.org)\]-)?"
                    "\[?\s?(?P<release>[^\s\[\]]+(?=(\]|\s.*\]|-\s)))"
                    "(\s.*)?\]?-?"
                    ".*(&quot;|\")(?P<file>.*" + exts + ")(&quot;|\").*")
    patternXvid = ("#alt.binaries.movies.xvid: (?P<release>[^\s]+)"
                   " - (&quot;|\")(?P<file>.*" + exts + ")(&quot;|\").*")
    patternAbmm = ("#a.b.mm@efnet - req \d+ - (?P<release>[^\s]+)"
                   " - (&quot;|\")(?P<file>.*" + exts + ")(&quot;|\").*")
                
    m = re.match(patternEfnet, subject, re.IGNORECASE)
    if m:
        return m.group("release", "file")
    m = re.match(patternXvid, subject, re.IGNORECASE)
    if m:
        return m.group("release", "file")
    m = re.match(patternAbmm, subject, re.IGNORECASE)
    if m:
        return m.group("release", "file")
    else:
        return (None, None)
    
def parseSql(line):
    pattern = "\(\d+, '(?P<file>.*)', '(?P<release>.*)'.*"
    m = re.match(pattern, line, re.IGNORECASE)
    if m:
        return m.group("release", "file")
    else:
        return (None, None)

class TestParse(unittest.TestCase):
    def test_parse_sql(self):
        line = "(1, 'FILENAME.srr', 'REL-NAME'),"
        self.assertEqual(parseSql(line), ("REL-NAME", "FILENAME.srr"))
        
    def test_parse(self):
        teevee = ("""[71733]-[FULL]-[#a.b.teevee@EFNet]-"""
                "[ REL-NAME ]-[23/29] - &quot;"
                """FILENAME.srr&quot; yEnc (1/1)""")
        teevee2 = ("[42377]-[FULL]-[#a.b.teevee@EFNet]-[ REL-NAME ]-[02/29] -"
                """ "FILENAME.mkv" yEnc (1/100)""")
        teevee3 = ("[120579]-[FULL]-[#a.b.teevee]-[ REL-NAME ]- "
        		'''"FILENAME.srr"''')
        moovee = ("[1014]-[FULL]-[#a.b.moovee@EFNet]-[ REL-NAME"
                """ ]- "FILENAME.srr" (1/1)""")
        moovee2 = ("[1060]-[FULL]-[#a.b.moovee@EFNet]-[ REL-NAME"
                """ ] "FILENAME.avi" (39/39)""")
        hdtv = ("[7895]-[a.b.hdtv.x264@EFNet]-REL-NAME- "
                "&quot;FILENAME.mkv&quot; (144/144)")
        mdivx = ("[26750]-[#altbin@EFNet]-[FULL]-[REL-NAME"
                        "]- &quot;FILENAME.avi&quot;")
        mdivx2 = ("[26750]-[#altbin@EFNet]-[FULL]-[REL-NAME - Sample"
                        "]- &quot;FILENAME.avi&quot;")
        mxvid = ("#alt.binaries.movies.xvid: REL-NAME - &quot;"
                        "FILENAME.srr&quot; (1/1))")
        abmm = ('#a.b.mm@efnet - req 83717 - REL-NAME - "FILENAME.mkv"')
        sample = ("[5804]-[#a.b.hdtv.x264@EFNet]-[REL-NAME SAMPLE]- "
                '"FILENAME.mkv" (4/4)')
        
        self.assertEqual(parseSubject(teevee3), ("REL-NAME", "FILENAME.srr"))
        self.assertEqual(parseSubject(teevee), ("REL-NAME", "FILENAME.srr"))
        self.assertEqual(parseSubject(teevee2), ("REL-NAME", "FILENAME.mkv"))
        self.assertEqual(parseSubject(moovee), ("REL-NAME", "FILENAME.srr"))
        self.assertEqual(parseSubject(moovee2), ("REL-NAME", "FILENAME.avi"))
        self.assertEqual(parseSubject(mdivx), ("REL-NAME", "FILENAME.avi"))
        self.assertEqual(parseSubject(mdivx2), ("REL-NAME", "FILENAME.avi"))
        self.assertEqual(parseSubject(mxvid), ("REL-NAME", "FILENAME.srr"))
        self.assertEqual(parseSubject(abmm), ("REL-NAME", "FILENAME.mkv"))
        self.assertEqual(parseSubject(hdtv), ("REL-NAME", "FILENAME.mkv"))
        self.assertEqual(parseSubject(sample), ("REL-NAME", "FILENAME.mkv"))

if __name__ == '__main__':
    parser = optparse.OptionParser(
        usage="Usage: %prog [nzb files] [options]'\n"
        "This tool will list the scene names and the srr name.\n",
        version="%prog 0.2 (2011-10-19)") # --help, --version
    
    parser.add_option("-r", "--releases", help="prints releases", 
                     action="store_true", default=False, dest="releases")
    parser.add_option("-s", "--srrs", help="prints SRRs", 
                     action="store_true", default=False, dest="srrs")
    parser.add_option("-b", "--both", help="prints both releases and the SRRs", 
                     action="store_true", default=False, dest="both")
    parser.add_option("-j", "--joins", help="prints SRRs to be joined"
                     "(no actual joining will occur)", 
                     action="store_true", default=False, dest="joins")
    parser.add_option("-u", "--unknowns", help="prints unparseable subjects", 
                     action="store_true", default=False, dest="unknowns")
    
    parser.add_option("--rename", help="renames SRR files in DIRECTORY "
                     "(stop using this one)", 
                     dest="rename_dir", metavar="DIRECTORY")
    parser.add_option("--join", 
                     help="joins before renaming SRR files in DIRECTORY", 
                     dest="join_dir", metavar="DIRECTORY")
    parser.add_option("--list", help="list release names of SRR files", 
                     dest="list_dir", metavar="DIRECTORY")
    parser.add_option("--separate", dest="separate", metavar="DIRECTORY",
                     help="split NZB to [release name].nzb in DIRECTORY")
    parser.add_option("--folder-join", 
                     help="joins before renaming SRR files in DIRECTORY. "
                     "No nzb necessary. Joins SRRs found in given folder.", 
                     dest="folderjoin", metavar="DIRECTORY")
    
    parser.add_option("--unittest", help="runs the unit tests", dest="test",
                     action="store_true", default=False)
    
    # no arguments given
    if len(sys.argv) < 2:
        print(parser.format_help())
    else:       
        (options, args) = parser.parse_args()
        if options.test:
            suite = unittest.TestLoader().loadTestsFromTestCase(TestParse)
            unittest.TextTestRunner(verbosity=2).run(suite)
        else:
            main(options, args)
        
"""
Shows which lines in new.txt aren't in mine.txt:
cat mine.txt new.txt | sort | uniq -d | cat new.txt - | sort | uniq -u
change -u at the end to -d to get the duplicates

cat rellist2011-10-20_nosample.txt efnet_mkv\zzmkvSamplesRellist.txt | sort | uniq -d | wc -l

$ /bin/cat newest.txt srr/_.srr600d_sha0lin/__rellist.txt | /bin/sort | /bin/uniq -d | /bin/cat srr/_.srr60_sha0lin/__rellist.txt - | /bin/sort | /bin/uniq -u

grep 'does not exist' all.txt > does_not_exist.txt

19:38 < sha0lin> they have this regex on hdbits, maybe you will get more groups with it
19:38 < sha0lin> \b(/(C/)Z|AE|AJ8|AJP|Arucard|AW|BBW|BG|BoK|CRiSC|Crow|CtrlHD|D4|DiGG|DiR|DiRTY|disc|DBO|DON|DoNOLi|D/-Z0N3|EbP|ESiR|ETH|fLAMEhd|FPG|FSK|Ft4U|fty|Funner|GMoRK|GoLDSToNE|H2|h264iRMU|HDB|HDC|HDBiRD|HDL|HDxT|H/@M|hymen|HZ|iLL|IMDTHS|iNFLiKTED|iOZO|J4F|JAVLiU|JCH|k2|KTN|KweeK|lulz|M794|MAGiC|MCR|MdM|MMI|Mojo|NaRB|NiX|NWO|OAS|ONYX|PerfectionHD|PHiN|PiNG|Prestige|Prime|PXE|QDP|QXE|Redµx|REPTiLE|RuDE|S26|sJR|SK|SLO|SPeSHaL|SrS|Thora|tK|TM|toho|

iconv < file.nfo -f cp437 -t utf8 > file.utf8
"""
