#!/usr/bin/env python
# -*- coding: utf-8 -*-

# MADE BY GUBER - REMOVE THIS TO MAKE YOUR FIRST BORN MY LUNCH
# Copyright (c) 2009 guber
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
import sys
import glob
import re
import fileinput
import subprocess
from optparse import OptionParser

"""
Installation guide for Linux
----------------------------

Install the following software:
 - Mono (mono-runtime)
 - Python3
 
Create a folder /home/user/bin
to create your own bin dir for executable files: (this step is not needed for all distros)
* Create the dir:
    mkdir ~/bin
* To add a directory to your PATH, add
    #my own executable files
    PATH=$PATH:$HOME/bin
  to your .bashrc file
 
Put the files awescript.py, srr.exe and srs.exe in ~/bin
http://pastebin.com/JMWKZqTt (version that always stores paths in the srr)

Create a file "awescript" with the following content:

#!/bin/sh
/usr/bin/python3.2 ~/bin/awescript.py "$1"

Do "whereis python" in the terminal to find out the path of you python installation if needed.
Do "chmod u+x awescript" to change the permissions.

In awescript.py change this:
    path_to_srs = "mono /usr/local/bin/srs.exe"
    path_to_srr = "mono /usr/local/bin/srr.exe"
to this: 
    path_to_srs = "mono /home/user/bin/srs.exe"
    path_to_srr = "mono /home/user/bin/srr.exe"
	
Type "awescript --help" in any path in your terminal.

awescript -R . --srr-dir=~/srrs
"""

#TODO: ask for updated version/what features are requested

# This version always creates a .srr file with the -p option: paths will be stored.

#better handling of srs-dir and srr-dir - i.e. remove meta=DIREECTORY and just os.path.normalize it

#allow rarfix to be srr'd, skip unrar

#allow multiple main_files and loop each (for sfv's with multiple rar sets)
#   will have to delete sfv files after unrar is done for all
# ------ currently works for subs sfv's with multiple rar sets... will screw up if non-scene sfv has 2+ sets that aren't subs

#add option to never unrar compressed subtyp files

#add option to unrar/delete subs

#add error logging to a file

#add sfv check option

#parse existing srs/srr files and see if need to make new ones or use/rename existing!
# srs -l
# - look for .avi .mkv .divx
# srr -l
# - look for .srs .nfo .sfv and main rar sets
# only delete srs in the filelist, bypassing DeleteFiles hardcoded

#need to make sure there's enough space to extract?

#replace unrar lb code with rar header detection code - avoid external programs at all times :)

#if sfv found and no rar - do a recursive check from that dir.

#if unrar runs and is okay, move subs/sample/etc to unrar_dir

#add support to ignore *.1.par2/sfv/rar files that par2 or alt.binz doesn't delete
# - could cause alt.binz to execute before subs/sample downloaded though

#CJ| is gay



if(os.name == "nt"):
    path_to_srs = "srs"
    path_to_srr = "srr"
else:
    path_to_srs = "mono /usr/local/bin/srs.exe"
    path_to_srr = "mono /usr/local/bin/srr.exe"
path_to_unrar = "unrar"

overwrite_existing_subs = 1

overwrite_existing_samples = 1



def get_files(path, cwdsolo):
    
    sfvList = []
    fileList = []
    fileMainList = []
    blackList = []
    sets_in_main = 0
    
    fileList = glob.glob("*.*")
    
    #for file in fileList:
    #    print(file)
    #exit()
    for root,dirs,files in os.walk(path):
        base = os.path.relpath(root) + slash
        if base == "."+slash: base = ""
        for d in dirs:
            fileList += glob.glob(base + d + slash + "*.*")
    fileList.sort()
    
    #move sfv files to top of list
    for file in fileList:
        if re.search("\.sfv$", file, re.IGNORECASE):
            sfvList.append(file)
            fileList.remove(file)
    
    fileList = sfvList + fileList
    
    for file in fileList:
        add = True
        folder = ""
        main_file = ""
        main_files = []
        sfv = ""
        fset = []
        typ = ""
        subtyp = ""
        dest = ""
        sr_dir = "" #dir to store path for srs or srr that was created for fileset
        part_fix = False
        
        (folder,filename) = os.path.split(file)
        if folder: folder += slash
        
        if not re.search("\.(avi|mkv|divx|ogm|mpg|part0?0?1\.rar|00[0-1]|vob|m2ts|sfv|srs|srr)$", filename, re.IGNORECASE):
            if not (re.search("\.rar$", filename, re.IGNORECASE) and not re.search("\.part\d{2,3}\.rar$", filename, re.IGNORECASE)):
                continue
            if re.search("\.part[2-9]\.rar$", filename, re.IGNORECASE):
                basename = filename.split(".rar",1)[0]
                if not os.path.exists(folder + basename + ".r00"):
                    continue
                part_fix = True
        
        #SFV Detection
        if re.search("\.sfv$", filename, re.IGNORECASE):
            sfv = filename
            missingList = []
            for line in fileinput.input([folder+filename]):
                line = line.strip()
                if not len(line) < 10 and not line[0:1] == ";":
                    f = line[:-9]
                    
                    if not os.path.exists(folder + f):
                        if re.search("\.(rar|[rs0-9][0-9][0-9])$", f, re.IGNORECASE):
                            missingList.append(f)
                        continue
                    
                    if re.search("\.part0?0?1\.rar$", f, re.IGNORECASE) or (re.search("\.(rar|00[0-1])$", f, re.IGNORECASE) and not re.search("\.part\d{1,3}\.rar$", f, re.IGNORECASE)):
                        if main_file:
                            blackList.append(f)
                        else:
                            main_file = f
                        main_files.append(f)
                    elif re.search("\.part[2-9]\.rar$", f, re.IGNORECASE):
                        if os.path.exists(folder + f.split(".rar",1)[0] + ".r00"):
                            if main_file:
                                blackList.append(f)
                            else:
                                main_file = f
                            main_files.append(f)
                    if re.search("\.(rar|[rs0-9][0-9][0-9])$", f, re.IGNORECASE):
                        fset.append(f)
            #
            #multi-rar sets subs fix
            #
            #if len(main_files) > 1:
            #    for i in range(len(main_files)-1):
            #        blackList.append(main_files[i])
            #fset.append(sfv)
            if len(missingList) > 0:
                cont = False
                print("Files missing from " + filename + ":\n " + str(missingList)) #str(missingList) +
                for miss in missingList:
                    if re.search("\.(avi|divx|mkv|ogm|mpg)$", miss, re.IGNORECASE):
                        print("SFV contains missing video file.  Skipping instead of quitting.")
                        cont = True
                        break
                    elif re.search("\.(nfo|par2)$", miss, re.IGNORECASE):
                        print("SFV contains MISC files.  Non-Scene SFV.")
                        cont = True
                        break
                    elif re.search("(sub.*|-s)\.rar", miss, re.IGNORECASE) and len(missingList) <= 2:
                        print("Subs files from SFV missing.")
                        cont = True
                        break
                if cont: continue
                if main_file: blackList.append(f)
                return []
            
            if not main_file: continue #sfv was probably corrupt
        
        
        if not main_file:
            main_file = filename
        
        #Look inside RAR and get types (i.e. AVI,MKV,SUBS)
        if re.search("\.(rar|00[0-1])$", main_file, re.IGNORECASE):
            
            if blackList.count(main_file): continue
            if os.path.exists(folder + main_file.split(".001",1)[0] + ".000"):
                continue #split files - not RARs
            
            for i in range(len(fileMainList)):
                if fileMainList[i][1].lower() == main_file.lower():
                    add = False
                    break #RAR file added by SFV, skip
            if not add: continue
            
            if len(fset) == 0: #NO SFV!
                print("no sfv for %s" % main_file)
                fset = glob.glob(wildc(folder, main_file))
                for i in range(len(fset)):
                    fset[i] = fset[i].rsplit(slash)[-1:][0] #remove path, keeping only filename
                #print(fset)
            
            if len(fset) >= 2:
                #print(fset)
                fset.sort() #Fixes when SFV set is out of order (i.e. RAR file at top in .r## set
                if os.path.getsize(folder+fset[len(fset)-1]) == os.path.getsize(folder+fset[len(fset)-2]):
                    print("%s is the same size as %s.  Incomplete set." % (folder+fset[len(fset)-1],folder+fset[len(fset)-2]))
                    #continue
                    return []
                else: #since last 2 aren't same size, we must have last rar to check for missing!
                    numRARs = 0
                    if re.search("\.part(\d{1,3})\.rar$", fset[len(fset)-1], re.IGNORECASE):
                        numRARs = int(re.search("\.part(\d{1,3})\.rar$", fset[len(fset)-1], re.IGNORECASE).groups()[0])
                    elif re.search("\.s(\d{2})$", fset[len(fset)-2], re.IGNORECASE):
                        numRARs = int(re.search("\.s(\d{2})$", fset[len(fset)-2], re.IGNORECASE).groups()[0])
                        numRARs += 101
                    elif re.search("\.r(\d{2})$", fset[len(fset)-2], re.IGNORECASE):
                        numRARs = int(re.search("\.r(\d{2})$", fset[len(fset)-2], re.IGNORECASE).groups()[0])
                        numRARs += 2
                    elif re.search("\.(\d{3})$", fset[len(fset)-1], re.IGNORECASE):
                        numRARs = int(re.search("\.(\d{3})$", fset[len(fset)-1], re.IGNORECASE).groups()[0])
                        if re.search("\.(rar|000)$", main_file, re.IGNORECASE):
                            numRARs += 1
                    #else: return []

                    if numRARs != 0:
                        if len(fset) != numRARs:
                            print("Files missing from RAR set.  Quitting.")
                            return []
                        #else: #check for RARs with wrong size - exit if 2+ have different size.
                        #    fileSize = os.path.getsize(folder+fset[0])
                        #    diffFiles = 0
                        #    for f in fset:
                        #        if os.path.getsize(folder+f) != fileSize:
                        #            diffFiles += 1
                        #        if diffFiles == 2:
                        #            print("2 or more files in the RAR set are a different size.  Set is bad.  Quitting.")
                        #            return []
        
            output = ""
            proc = subprocess.Popen("%s lb \"%s%s\"" % (path_to_unrar,folder,main_file), shell=True, stdout=subprocess.PIPE)
            std = str(proc.communicate()[0]).lstrip("b'").rstrip("'")
            if std:
                if os.name == "nt":
                    output = std.split(r"\r\n")
                else:
                    output = std.split(r"\n")
            elif len(output) == 0 and re.search("\.(avi|divx|mkv|ogm|mpg)\.00[0-1]$", main_file, re.IGNORECASE):
                #if os.path.exists(folder + main_file.split(".001",1)[0] + ".000"):
                #    main_file = main_file.split(".001",1)[0] + ".000"
                print("%s is a joined file." % main_file)
                typ = "Video"
                subtyp = "Joined"
                #wild = glob.glob(wildc(folder,main_file)).sort()
                #continue
            else:
                print("%s could be corrupt?" % main_file)
                continue
            
            if re.search("extra", main_file, re.IGNORECASE):
                subtyp = "Extras"
                if not re.search("extra", cwdsolo, re.IGNORECASE):
                    dest = "Extras" + slash
            
            #
            #need to check if already in a folder and use that
            #
            for s in output: #could be multiple files in the rar
                if not s: continue #for blanks at the end from splitting \r\n or \n
                if re.search("\.(avi|divx|mkv|ogm|mka|dts|ac3|mpg|mp3|ogg)$", s, re.IGNORECASE):
                    typ = "Video"
                    if not folder: sets_in_main += 1 #i.e. not in CD[1-9], so may need to move
                elif re.search("\.(iso|img|nrg|bin|gcm|cdi|dvd|gi)$", s, re.IGNORECASE):
                    typ = "ISO"
                    subtyp = "Compressed"
                else:
                    #print("Unkown files in RAR %s or corrupt." % main_file)
                    continue
                break
            if not typ:
                for s in output: #could be multiple files in the rar
                    if not s: continue #for blanks at the end from splitting \r\n or \n
                    if re.search("\.(srt|sub|idx|rar)$", s, re.IGNORECASE):
                        if re.search("vob.?sub", main_file, re.IGNORECASE):
                            typ = "VobSubs"
                            if not folder:
                                dest = "VobSubs"+slash
                        else:
                            typ = "Subs"
                            if not folder:
                                dest = "Subs"+slash
                        if subtyp == "Extras" and not re.search("extra", cwdsolo, re.IGNORECASE):
                            if not folder: dest = "Extras" + slash + dest
                        break
            if not typ: typ = "Other"
        
        #Check for Video files NOT in RAR files - i.e. samples or previously extracted video        
        elif re.search("\.(avi|mkv|vob|m2ts)$", main_file, re.IGNORECASE):
            
            if re.search("extra", main_file, re.IGNORECASE):
                subtyp = "Extras"
            #check if sample
            if re.search("sample", folder, re.IGNORECASE) or is_sample(folder + main_file):
                if re.search("\.vob$", main_file, re.IGNORECASE):
                    typ = "VobSample"
                    if not folder:
                        dest = "VobSample"+slash
                elif re.search("\.m2ts$", main_file, re.IGNORECASE):
                    typ = "m2tsSample"
                    if not folder:
                        dest = "Sample"+slash
                else:
                    typ = "Sample"
                    if not folder:
                        dest = "Sample"+slash
                if subtyp == "Extras" and not re.search("extra", cwdsolo, re.IGNORECASE):
                    if not folder:
                        dest = "Extras" + slash + dest
            else:
                #not a sample, add as extracted video
                typ = "Video"
                subtyp = "Extracted"
                if not folder: sets_in_main += 1 #i.e. not in CD[1-9], so may need to move
                #continue
        
        elif re.search("\.nfo$", main_file, re.IGNORECASE):
            typ = "Other"
            subtyp = "NFO"
        
        elif re.search("\.srs$", main_file, re.IGNORECASE):
            if re.search("extra", main_file, re.IGNORECASE):
                subtyp = "Extras_SRS"
                if not folder:
                    dest = "Extras"+slash + "Sample"+slash
            else:
                subtyp = "SRS"
                if not folder:
                    dest = "Sample"+slash
            typ = "Sample"
        
        elif re.search("\.srr$", main_file, re.IGNORECASE):
            typ = "Other"
            subtyp = "SRR"
        
        if len(fset) == 0: fset.append(main_file)
        #if dest and options.unrar_dir: dest = options.unrar_dir.rstrip(slash) + slash + dest
        
        fileMainList.append([folder,main_file,sfv,fset,typ,subtyp,dest,sr_dir])
    
    
    #Detect CD folders - skip if folder has TV tags
    if sets_in_main >= 2 and not re.search("([\._\s]s?\d{1,3}[\._\s]?[ex]\d{1,3}|s\d{1,3})", cwdsolo, re.IGNORECASE): #2 or more CDs possible
        fileMainList = get_cds(fileMainList)
    
    
    return fileMainList



def is_sample(video):
    max_size     =  50000000
    if re.search("\.mkv$", video, re.IGNORECASE):
        max_size = 250000000
    
    if re.search("^.*?([\.\-_\w]?sa?mp).*?\.(?:avi|mkv|m2ts|vob)$", video, re.IGNORECASE):
        if os.path.getsize(video) < max_size: return True
    else: #no s?mp in filename - reduce filesize limits manually
        if re.search("\.(avi|mkv|vob|m2ts)$", video, re.IGNORECASE) and os.path.getsize(video) < max_size / 2:
            return True
    
    return False



def only_samples(files):
    sample = False
    for file in files:
        if file[4] == "Video":
            return False
        elif file[4] == "Sample":
            sample = True
    return sample



def get_cds(fileMainList):
    global slash
    #folder,main_file,sfv,fset,typ,dest
    fileList = fileMainList

    fileListNew = []
    position = False
    for i in range(len(fileList)):
        if fileList[i][4] != "Video": continue
        fileListTemp = []
        file = fileList[i][1]
        posTemp = 0
        
        if re.search("(s\d{1,3}[\._]?e\d{1,3})", file, re.IGNORECASE): continue #TV Test (file) - MAKE THIS FOR DIR
        for j in range(len(fileList)):
            if i == j: continue # i <= j ?  since they've already been compared once?
            if fileList[j][4] != "Video": continue
            file2 = fileList[j][1]
            if re.search("(s\d{1,3}[\._]?e\d{1,3})", file2, re.IGNORECASE): continue #TV Test (file2)
            if len(file) == len(file2):
                diff = 0
                for k in range(len(file)):
                    if file[k] != file2[k]:
                        diff += 1
                        if diff > 1: break
                        if posTemp:
                            if k != posTemp:
                                #Can't compute differences for CDs.  Skipping.
                                continue
                        posTemp = k
                        #print(file)
                if diff == 1: fileListTemp.append(j)
        if len(fileListTemp) > len(fileListNew):
            fileListNew = fileListTemp
            fileListNew.append(i)
            position = posTemp
    fileListNew.sort()
    
    if len(fileListNew) <= 1: return fileMainList
    print("CDs: Detected!")

    diff = 99
    
    for i in fileListNew:
        file = fileMainList[i][1]
        char = file[position]
        if re.match("^([1-9])$", char):
            cd = char
        elif re.match("^([A-Fa-f])$", char):
            if char == "a": cd = "1"
            elif char == "b": cd = "2"
            elif char == "c": cd = "3"
            elif char == "d": cd = "4"
            elif char == "e": cd = "5"
            elif char == "f": cd = "6"
        else:
            print(file + " is NOT a cd, subs?")
            continue
        
        #fix for releases with only parts 3/4 but pre as CD1/CD2 (separate release with 1/2)
        if diff == 99:
            if int(cd) == 1:
                diff = 0
            else: #assume it's sorted and just didn't start at 1
                diff = int(cd) - 1
        cd = str(int(cd) - diff)
        print(file + " is CD" + cd)
        
        #get/make directory
        fileMainList[i][6] = "CD" + cd + slash
        if re.search("\.(rar|00[0-1])$", file, re.IGNORECASE):
            fileMainList[i][5] = "CD"
        else:
            fileMainList[i][5] = "Extracted_CD"

    
    return fileMainList



def wildc(folder,file):
    global slash
    if not os.path.exists(folder+file): return False
    
    basename = False
    wildcard = False
    if re.search("\.(part01\.rar)$", file, re.IGNORECASE):
        ext = re.search("\.(part01\.rar)$", file, re.IGNORECASE).groups()[0]
        wildcard = ".[Pp][Aa][Rr][Tt][0-9][0-9].[Rr][Aa][Rr]"
    elif re.search("\.(part001\.rar)$", file, re.IGNORECASE):
        ext = re.search("\.(part001\.rar)$", file, re.IGNORECASE).groups()[0]
        wildcard = ".[Pp][Aa][Rr][Tt][0-9][0-9][0-9].[Rr][Aa][Rr]"
    elif re.search("\.(rar)$", file, re.IGNORECASE):
        if re.search("\.(part1\.rar)$", file, re.IGNORECASE):
            filename = folder + file.split(".rar",1)[0]+".r00".replace("[", "[[]")
            if os.path.exists(filename):
                ext = re.search("\.(part1\.rar)$", file, re.IGNORECASE).groups()[0]
                wildcard = ".[Pp][Aa][Rr][Tt]1.[Rr]??"
            else:
                ext = re.search("\.(part1\.rar)$", file, re.IGNORECASE).groups()[0]
                wildcard = ".[Pp][Aa][Rr][Tt][0-9].[Rr][Aa][Rr]"
        else:
            ext = re.search("\.(rar)$", file, re.IGNORECASE).groups()[0]
            wildcard = ".[Rr]??"
    elif re.search(".(00[0-1])$", file, re.IGNORECASE):
        ext = re.search("\.(00[0-1])$", file, re.IGNORECASE).groups()[0]
        wildcard = ".[0-9][0-9][0-9]"
    else: return False
    
    basename = file.split("."+ext,1)[0].replace("[", "[[]")
    
        
    return folder + basename + wildcard



def move_files(files, options, cwdsolo):
    global slash
    
    if options.move_subs:
        files = move(files, "Subs", "", True, options.debug)
        files = move(files, "VobSubs", "", True, options.debug)
        if options.move_extras:
            files = move(files, "Subs", "Extras", True, options.debug)
            files = move(files, "VobSubs", "Extras", True, options.debug)
    
    if options.move_samples and not (options.delete_samples and options.delete_srs_after_srr):
        if not only_samples(files):
            files = move(files, "Sample", "", True, options.debug)
            if not options.srs_dir:
                files = move(files, "Sample", "SRS", True, options.debug)
            if options.move_extras:
                files = move(files, "Sample", "Extras", True, options.debug)
                if not options.srs_dir:
                    files = move(files, "Sample", "Extras_SRS", True, options.debug)
        else:
            print("Only samples found, not moving.")
    
    if options.move_samples:
        files = move(files, "VobSample", "", True, options.debug)
        files = move(files, "m2tsSample", "", True, options.debug)
        if options.move_extras:
            files = move(files, "VobSample", "Extras", True, options.debug)
            files = move(files, "m2tsSample", "Extras", True, options.debug)
    
    if options.move_cds and not options.delete_rars:
        #print("Moving RAR sets to CD1-N folders.")
        files = move(files, "Video", "CD", True, options.debug)
        if options.move_cds_extracted:
            print("Moving previously extracted video files to CD1-N folders.")
            files = move(files, "Video", "Extracted_CD", True, options.debug)
    
    if options.move_extras:
        files = move(files, "Video", "Extras", True, options.debug)
        files = move(files, "Other", "Extras", True, options.debug)
    
    return files



def move(files, typ, subtyp, overwrite, debug):
    global slash

    for i in range(len(files)):
        if files[i][4] != typ or files[i][5] != subtyp or not files[i][6]: continue
        
        file = files[i]
        ok = True
        fset = file[3]
        dest = file[6]

        if not os.path.isdir(dest):
            if debug:
                print("mkdir %s" % dest)
            else:
                os.makedirs(dest)
            #directory = ""
            #for d in dest.rstrip(slash).split(slash):
            #    directory += d + slash
            #    if not os.path.isdir(directory):
            #        os.mkdir(directory)
        
        if file[2]:#sfv
            fset.append(file[2])
        for f in fset:
            if not os.path.isfile(f): continue
            try:
                if os.path.isfile(dest+f):
                    if overwrite:
                        if debug:
                            print("remove %s%s to overwrite." % (dest,f))
                        else:
                            os.remove(dest+f)
                    else:
                        if os.path.isfile(dest+"copy.of."+f):
                            if debug:
                                print("remove %scopy.of.%s to make new copy." %(dest,f))
                            else:
                                os.remove(dest+"copy.of."+f)
                        if debug:
                            print("rename  %s%s to %scopy.of.%s" (dest,f,dest,f))
                        else:
                            os.rename(dest+f,dest+"copy.of."+f)
                if debug:
                    print("rename %s to %s%s" % (f,dest,f))
                else:
                    os.rename(f, dest+f)
            except OSError:
                ok = False
        
        if ok:
            file[0] = dest #folder = dest
            file[6] = "" #unrar_dir.rstrip(slash) + slash
            files[i] = file
    
    return files



#move full directories post-extraction if unrar_dir set?
def move_dir(file):
    global slash
    
    
    
    return file



def srs_srr(files, options, cwdsolo):
    global slash
    
    code = 0
    
    if options.create_srs:
        code, files = srs(files, options, cwdsolo) #create srs
    
    if options.create_srr: #if srs fails, so be it?
        code, files = srr(files, options, cwdsolo, False) #False to not ignore Extras.  if fail, ignore Extras and try again
    
    if code == 0 and options.create_srr and (options.delete_srs_after_srr and options.include_srs_in_srr):
        if options.debug:
            print("remove *.srs")
        else:
            deleteFiles(["*.srs","*[Ss][Aa][Mm][Pp][Ll][Ee]*/*.srs"], "Re-Sample (SRS)", None, False) #delete *.srs
    
    return code, files



def srs(files, options, cwdsolo):
    global slash, path_to_srs
    
    code = -1
    filesToAdd = []
    onlySamples = only_samples(files)
    
    for i in range(len(files)):
        if files[i][4] != "Sample" or files[i][5] == "SRS" or files[i][5] == "Extras_SRS": continue
        cmd = path_to_srs
        folder = files[i][0]
        file = files[i][1]
        srs_file = file[:-3]+"srs"
        
        if options.srs_namep:
            srs_file = cwdsolo+".srs"
        try:
            cmd += " \"" + folder+file + "\""
            #cmd += opts
            cmd += " -o \""
            if options.srs_dir:
                if os.path.exists(options.srs_dir):
                    folder = options.srs_dir.rstrip(slash) + slash
                else: #create srs_dir
                    if os.makedirs(options.srs_dir):
                        folder = options.srs_dir.rstrip(slash) + slash
                        print("SRS directory %s created." % options.srs_dir)
                    else:
                        print("SRS directory %s could not be created.  SRS will default to release directory." % options.srs_dir)

            if os.path.isfile(folder+srs_file) and os.path.getsize(folder+srs_file) > 0:
                print("SRS file exists, skipping %s" % srs_file)
                code = 0
                continue
            
            cmd += folder+srs_file + "\""
            print(cmd)
            if options.debug:
                code = 0
            else:
                code = os.system(cmd)
            
            if code == 2:
                print("SRS: Sample file \"%s\" is bad." % file)
                code = -1
            elif code == 0:
                files[i][7] = srs_file
                if files[i][5] == "Extras":
                    subtyp = "Extras_SRS"
                else:
                    subtyp = "SRS"
                filesToAdd.append([folder, srs_file, "", [srs_file], "Sample", subtyp, ""])
                if options.delete_samples and not onlySamples:
                    if options.debug:
                        print("delete %s%s" % (folder,file))
                    else:
                        deleteFiles([folder+file], "AVI Sample", None, False)
            else:
                print("Error with SRS.")
                code = -1
        except OSError:
            print("SRS: Error running SRS.")
            return -1, files
    
    files += filesToAdd
    
    return code, files



def srr(files, options, cwdsolo, ignore_extras):
    global slash, path_to_srr

    cmd = path_to_srr
    code = -1
    srrNum = 0
    dest = ""
    srr_file = cwdsolo+".srr"
    joined = False
    extras = False
    
    if options.srr_dir:
        if os.path.exists(options.srr_dir):
            dest = options.srr_dir
        else: #create srr_dir
            if os.makedirs(options.srr_dir):
                dest = options.srr_dir
                print("SRR directory %s created." % options.srr_dir)
            else:
                print("SRR directory %s could not be created.  SRR will default to release directory." % options.srr_dir)
    elif options.unrar_dir:
        if not os.path.exists(options.unrar_dir):
            if options.debug:
                print("mkdir %s" % options.unrar_dir)
                dest = options.unrar_dir
            elif os.makedirs(options.unrar_dir):
                dest = options.unrar_dir
        else:
            dest = options.unrar_dir
    
    for file in files:
        if file[4] != "Video" or file[5] == "Extracted" or file[5] == "Extracted_CD" or file[5] == "Compressed": continue
        if file[5] == "Joined":
            joined = True
            continue
        if file[5] == "Extras":
            extras = True
        #if subtyp and file[5] != subtyp: continue
        folder = file[0]
        if file[2]: file = file[2] #sfv
        elif file[1]: file = file[1] #rar
        else: continue
        cmd += " \"" + folder+file + "\""
        srrNum += 1
    
    if joined and srrNum == 0: return 1, files
    elif srrNum == 0: return 1, files
    
    cmd += " -s" #-s include files below (at least *.nfo)
    
    if options.include_srs_in_srr:
        for file in files:
            if file[4] == "Sample" and (file[5] == "SRS" or file[5] == "Extras_SRS"):
                cmd += " \"%s%s\"" % (file[0],file[1])
    cmd += " *.nfo"
    
    if dest and os.path.isdir(dest):
        cmd += " -o \"%s%s%s\"" % (dest.rstrip(slash),slash,srr_file)
    else:
        cmd += " -o \"%s\"" % srr_file

    # we will always do paths when creating the srr file
    cmd += " -p"

    try:
        print(cmd)
        if options.debug:
            code = 0
        else:
            code = os.system(cmd)
            print(code)
        if code == 3 or code == 768: #3 for windows, 768 for linux ; compressed RARs
            if extras == True and ignore_extras == False:
                print("SRR: RARs are compressed.  Re-Trying without Extras.")
                code, files = srr(files, options, cwdsolo, True)
            else:
                print("SRR: RARs are compressed.  Continuing like normal, ignoring srs deletion")
            return code, files
        elif code != 0:
            print("SRR: Re-Scene failed.  Skipping the rest.")
            return -1, files
        else:
            return 0, files
    except OSError:
        print("SRR: Error running SRR.")
        return -1, files
    
    return -1, files


def unrar(files, options, code):
    global slash, path_to_unrar
    #options.unrar_dir, options.extract_to_main_dir, options.delete_rars, options.delete_sfv
    #[folder,main_file,sfv,fset,typ,subtyp,dest]
    
    if not options.extract_rars or code == -1:
        return code, files
    
    maincmd = "%s x -o+ -p-" % path_to_unrar
    if(os.name == "nt"):
        joincmd = "copy /b"
    else:
        joincmd = "cat"
    
    for fileset in files:
        if (fileset[4] != "Video" and fileset[4] != "ISO") or fileset[5] == "Extracted": continue #typ
        
        folder = fileset[0]
        file = fileset[1] #name.rar
        sfv  = fileset[2]
        fset = fileset[3]
        if folder and (not options.extract_to_main_dir or fileset[5] == "Extras"):
            if options.unrar_dir:
                dest = options.unrar_dir.rstrip(slash) + slash + folder
            else:
                dest = folder
        else:
            if options.unrar_dir:
                dest = options.unrar_dir.rstrip(slash) + slash
            else:
                dest = "."+slash
        
        try:
            #input file
            if fileset[5] != "Joined":
                cmd = maincmd
                cmd += " \"" + folder+file + "\""
            else:
                cmd = joincmd+" "
                for i in range(len(fset)):
                    cmd += "\"%s\"" % fset[i]
                    if i+1 != len(fset):
                        if(os.name == "nt"):
                            cmd += "+"
                        else:
                            cmd += " "
                if(os.name != "nt"):
                    cmd += " >"
                dest = dest+file[:-4]
            
            cmd += " \"" + dest + "\""
            
            print(cmd)
            if options.debug:
                code = 0
            else:
                code = os.system(cmd)
            
            if code != 0:
                print("UnRAR failed.  Skipping the rest.")
                return -1, files
            elif options.delete_rars:
                for f in fset:
                    try:
                        if options.debug:
                            print("remove %s%s" % (folder,f))
                        else:
                            os.remove(folder+f)
                    except OSError:
                        print("Error trying to remove %s%s" % (folder,f))
                print("UnRAR: %s RAR files that were processed have been removed." % folder)
            if options.delete_sfv and sfv:
                try:
                    if options.debug:
                        print("remove %s%s" % (folder,sfv))
                    else:
                        os.remove(folder+sfv)
                        print("UnRAR: %s%s removed." % (folder,sfv))
                except OSError:
                    print("UnRAR: Error trying to remove %s%s" % (folder,sfv))
                    
        except OSError:
            print("Error trying to unrar.")
            return -1, files

        except KeyboardInterrupt:
            print("\nUnRAR was interrupted by user.  Exiting")
            sys.exit()
    
    
    return code, files



def cleanup(files, options, code):
    global slash
    
    if options.delete_par2 and not (code != 0 and options.extract_rars):
        deleteFiles(["*.[Pp][Aa][Rr]2"], "PAR2", None, options.debug)
    deleteFiles(["*.[Nn][Zz][Bb]"], "NZB", None, options.debug)
    
    #need to delete empty folders
    deleteDirectories(["*[Cc][Dd][1-9]*/","*[Ss][Aa][Mm][Pp][Ll][Ee]*/"], options.debug)
    
    
    
    return



def deleteFiles(wildcards, word, ignoreList, debug):
    fileList = []
    for wc in wildcards:
        fileList += glob.glob(wc)
    
    if len(fileList) == 0:
        print("No %s files to delete." % word)
        return 0
    
    for file in fileList:
        cont = True
        if ignoreList:
            for ignore in ignoreList:
                if file == ignore:
                    ignoreList.remove(ignore)
                    cont = False
                    break
        if cont:
            try:
                if debug:
                    print("remove %s" % file)
                else:
                    os.remove(file)
                    print("%s deleted." % file)
            except OSError:
                print("Error trying to remove %s" % file)
                return -1

    return 0



def deleteDirectories(wildcards, debug):
    dirs = []
    for wc in wildcards:
        dirs += glob.glob(wc)
    for directory in dirs:
        if not os.listdir(directory):
            try:
                if debug:
                    print("rmdir %s" % directory)
                else:
                    os.rmdir(directory)
                    print("%s was empty and removed." % directory)
            except OSError:
                print("%s was empty but could not be removed." % directory)
    
    return



def main(options, path):
    global origcwd, cwd, slash

    if options.exit_if_par2_exists: #altbinz mode - fix for altbinz sending lowercase dirname
        for p in glob.glob(os.path.normpath(os.path.join(path, '..'))+slash+"*"):
            if path.lower() == p.lower() or path.lower() == p.lower()[2:]:
                os.chdir(p)
                break
    else:
        os.chdir(path)
    cwd = os.getcwd()
    cwdsolo = os.path.split(cwd)[-1]
    
    if options.exit_if_par2_exists:
        if len(glob.glob("*.par2")) > 0:
            print("PAR2 files exist.  Exiting...")
            sys.exit()
    
    if re.search("(subpack|sub.?fix|subs\.)", cwdsolo, re.IGNORECASE):
        print("SUBS directory detected.  Not processing.")
        return
    elif re.search("(sync.?fix)", cwdsolo, re.IGNORECASE):
        print("SYNCFiX directory detected.  Not processing.")
        return
    elif re.search("(sample.?fix)", cwdsolo, re.IGNORECASE):
        print("SAMPLEFiX directory detected.  Not processing.")
        return
    
    
    print("\nProcessing: %s\n" % cwd)
    
    files = get_files(cwd, cwdsolo)
    if len(files) == 0:
        #print("No files to process.")
        return
    
    #debug
    if options.debug: #or options.verbose
        print("\nFiles:\n[folder, filename, sfv, file_list, type, subtype, destination_dir, rescene_dir]\n")
        for i in range(len(files)):
            print(str(i+1) + ": " + str(files[i]) + "\n")
        print("")
    
    code = 1
    
    files = move_files(files, options, cwdsolo)
    
    code, files = srs_srr(files, options, cwdsolo)
    
    code, files = unrar(files, options, code)
    
    cleanup(files, options, code)
    
    
    return



if __name__ == '__main__':
    usage = "usage: %prog -<option 1> -<option N> <@listdirs...>"
    version = "%prog 0.5b"
    parser = OptionParser(usage=usage, version=version)
    parser.add_option("--altbinz", dest="exit_if_par2_exists", action="store_true", default=False,
                      help="Alt.Binz mode: exit if par2 exists in directory.  Fixes multiple execution issues.")
    
    parser.add_option("-R", dest="recursive", action="store_true", default=False,
                      help="Recursively walk through directories looking for releases and processing each.")
    
    parser.add_option("--no-srr", dest="create_srr", action="store_false", default=True,
                      help="Do not create Re-Scene (SRR) files for RAR sets.")
    parser.add_option("--no-srs", dest="create_srs", action="store_false", default=True,
                      help="Do not create Re-Sample (SRS) files for AVI/MKV Samples.")
    parser.add_option("--separate-srs-srr", dest="include_srs_in_srr", action="store_false", default=True,
                      help="Do not include SRS files in SRR.  This implies --keep-srs.")
    parser.add_option("--keep-srs", dest="delete_srs_after_srr", action="store_false", default=True,
                      help="Do not delete SRS files that are stored in the SRR.")
    parser.add_option("--srs-namep", dest="srs_namep", action="store_true", default=False,
                      help="Rename SRS after release name instead of sample name.")
    parser.add_option("--srs-dir", dest="srs_dir", action="store", default=False,
                      metavar="DIR",
                      help="Directory to move SRS files to in case you keep them all in one directory.")
    parser.add_option("--srr-dir", dest="srr_dir", action="store", default=False,
                      metavar="DIR",
                      help="Directory to move SRR files to in case you keep them all in one directory.")
    
    parser.add_option("-f", "--filter", dest="filters", action="store", default=["xvid","divx","x264","h264"],
                      help="List of filters for input directory.  If it doesn't match it will skip.  DOES NOT CURRENTLY WORK!")
    
    parser.add_option("--ignore-cds", dest="move_cds", action="store_false", default=True,
                      help="Do not move rar sets to CD1-N folders.")
    parser.add_option("--move-extracted-cds", dest="move_cds_extracted", action="store_true", default=False,
                      help="Move already extracted video files to CD1-N folders.")
    parser.add_option("--ignore-extras", dest="move_extras", action="store_false", default=True,
                      help="Do not move EXTRAS to Extras folder.")
    parser.add_option("--ignore-subs", dest="move_subs", action="store_false", default=True,
                      help="Do not move subs to Subs directory.")
    parser.add_option("-i", "--ignore-sample", dest="move_samples", action="store_false", default=True,
                      help="Do not move sample(s) to Sample directory.")
    parser.add_option("-d", "--delete-sample", dest="delete_samples", action="store_true", default=False,
                      help="Delete samples.  Recommended to keep SRS creation enabled (on by default).")
    
    parser.add_option("-e", "--extract", dest="extract_rars", action="store_true", default=False,
                      help="Extract RAR sets.  Specify directory with -u \"dir\" or -m for main directory.")
    parser.add_option("-u", "--unrar-dir", dest="unrar_dir", action="store",
                      help="Directory to UnRAR files.  Will unRAR in place if not specified.", metavar="\"DIRECTORY\"")
    parser.add_option("-m", "--extract-to-main-dir", dest="extract_to_main_dir", action="store_true", default=False,
                      help="UnRAR to input directory if RAR files are in separate folders within (i.e. CD1/CD2).")
    parser.add_option("-r", "--delete-rars", dest="delete_rars", action="store_true", default=False,
                      help="Delete RAR files after successful UnRAR.  You should probably enable SFV deletion with this.")
    
    parser.add_option("-s", "--delete-sfv", dest="delete_sfv", action="store_true", default=False,
                      help="Delete SFV files when done.  Will not delete if UnRAR fails.")
    parser.add_option("-p", "--delete-par2", dest="delete_par2", action="store_true", default=False,
                      help="Delete PAR2 files when done.  Will not delete if UnRAR fails.")
    parser.add_option("-z", "--keep-nzb", dest="delete_nzb", action="store_false", default=True,
                      help="Do not delete NZB files.")
    
    parser.add_option("--debug", dest="debug", action="store_true", default=False,
                      help="Only list what the program would do.  Will not move, unrar, etc.")
    
    (options, args) = parser.parse_args()
    
    if len(args) == 0:
        parser.print_help()
        sys.exit()
    
    if options.extract_to_main_dir and not options.extract_rars: options.extract_rars = True
    if options.unrar_dir: options.unrar_dir = os.path.abspath(options.unrar_dir)
    
    globals()["origcwd"] = os.getcwd()
    sys.path.append(globals()["origcwd"])
    
    if os.name == "nt":
        globals()["slash"] = "\\"
    else: globals()["slash"] = "/"
    
    for path in args:
        #file = open(r"E:\DOWNLOAD\xvid.txt", 'a')
        #file.write(path + '\n')
        #file.write(str(options.unrar_dir) + '\n')
        #file.write('\n')
        #file.close()
        
        os.chdir(globals()["origcwd"])
        
        if not os.path.isdir(path):
            print("Argument %s is not a valid directory." % path)
            continue
        
        if not options.recursive:
            main(options, path)
        else:
            #recursive
            current = "ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ"
            for root,dirs,files in os.walk(path):
                found = False
                if current in root: continue
                for file in files:
                    if re.search("\.(rar|00[0-1]|avi|mkv|ogm|divx|mpg)$", file):
                        found = True
                        break
                if not found:
                    for directory in dirs:
                        if re.match("^cd[1-9]$", directory, re.IGNORECASE):
                            found = True
                            break
                if found:
                    current = root
                    main(options, root)
                    os.chdir(origcwd)
                    
            print("\n\n\nDone with %s directory.\n\n" % path)
    
