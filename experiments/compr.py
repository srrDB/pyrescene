
import rar
import os
import re
import subprocess
import sys
import pprint
import filecmp

# locating installed unrar
if(os.name == "nt"):
    try:
        unrar = os.environ["ProgramW6432"] + "\WinRAR\UnRAR.exe"
        if not os.path.exists(unrar):
            raise KeyError
    except KeyError:
        try:
            unrar = os.environ["ProgramFiles(x86)"] + "\WinRAR\UnRAR.exe"
            if not os.path.exists(unrar):
                raise KeyError
        except KeyError:
            print("Install WinRAR to use all the functionalities.")
            
    # define your own path to a program to unrar: (uncomment)
    #unrar = "C:\Program Files\7z.exe"
else:
    unrar = "/usr/bin/env unrar"

BEOS, BSD, LINUX, MACOS, WIN32 = list(range(5))

osdir = {
    BEOS: "beos",
    WIN32: "windows",
    BSD: "bsd",
    MACOS: "osx",
    LINUX: "linux" # rar, rar_static
}

versions = {
    "350": {"path": "",
            "win": "",
            "osx": ""},
            
            
            }

def extract_rarexe(source, dest, unrar=unrar):
    source_dir = os.path.join(source, osdir[WIN32])
    for fname in os.listdir(source_dir):
        tag = versiontag(fname)[0]
        if not tag:
            continue
        files = ["Rar.exe", "TechNote.txt", "WhatsNew.txt"]
        args = [unrar, "e", os.path.join(source_dir, fname)] + files + [dest]

        extract = subprocess.Popen(args)
        #extract = custom_popen(args)
        if extract.wait() == 0:
            for efile in files:
                print os.path.join(dest, efile)
                print os.path.join(dest, efile[:-4] + tag + efile[-4:])
                os.rename(os.path.join(dest, efile), 
                          os.path.join(dest, efile[:-4] + tag + efile[-4:]))
        else:
            print "error" + fname
            assert False


def versiontag(file_name):
    """ Returns tuple with:
    - uniquely identifying tag
    - number """
    match = re.match("\w+(?P<x64>-x64-)?"
                     "(?P<large>\d)(?P<small>\d\d)"
                     "(?P<beta>b\d)?.+", file_name)
    if match:
        #x64, large, small, beta = match.group("x64", "large", "small", "beta")
        #print large, small, x64, beta
        return ("".join(filter(None, match.groups())), 
                "".join(match.group("large", "small")))
    return None

#proc = subprocess.Popen("%s lb \"%s%s\"" % (path_to_unrar,folder,main_file), shell=True, stdout=subprocess.PIPE)
#std = str(proc.communicate()[0]).lstrip("b'").rstrip("'")            
#     
def construct_matrix():
    pass

dict_size = {
    64 : "-mda",
    128: "-mdb", 
    256: "-mdc", 
    512: "-mdd",
    1024: "-mde", 
    2048: "-mdf",
    4096: "-mdg",
}

            
def generate_testfiles(rarbindir, raroutdir):
    for rarbin in os.listdir(rarbindir):
        tag = versiontag(rarbin)[0]
        if not tag:
            continue
        rarbin = os.path.join(rarbindir, rarbin)
        files = ["Z:\\rar\\rarextract\\kdewin-installer-gui-latest.exe"]
        for i in range(5):
            # -s: solid archive
            
            rarname = "".join(["m", str(i+1), "testfile", tag, ".rar"])
            rarname = os.path.join(raroutdir, rarname)
            
            args = [rarbin, "a", "-m" + str(i+1), dict_size[4096], rarname] + [files]   
            create = subprocess.Popen(args)
            create.wait()
            #create = custom_popen(args)

def compare(raroutdir):
    # for each compression method dict with all versions
    files = [""] * 5
    for i in range(len(files)):
        files[i] = dict()
        
    for fname in os.listdir(raroutdir):
        tag = versiontag(fname)[1]
        if not tag:
            continue
        #fpath = os.path.join(raroutdir, fname)
        (files[int(fname[1:2])-1])[tag] = fname
    pprint.pprint(files)
    f1 = f2 = 0
    for i in range(len(files)):
#        print sorted(files[i-1].items())
#        continue
        for k, v in sorted(files[i].items()):
            if not f1:
                f1 = v
                continue
            f2 = v
            if _do_cmp(os.path.join(raroutdir, f1), 
                       os.path.join(raroutdir, f2)):
                print "SAME:", k, f1, f2
            else:
                print "DIFF:", k, f1, f2
            f1 = f2

def _do_cmp(f1, f2):
    bufsize = 8*1024
    with open(f1, 'rb') as fp1:
        with open(f2, 'rb') as fp2:
            while True:
                b1 = fp1._read(bufsize)
                b2 = fp2._read(bufsize)
                if b1 != b2:
                    return False
                if not b1:
                    return True
            
# disconnect cmd from parent fds, _read only from stdout
def custom_popen(cmd):
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
    
    
    
#extract_rarexe("Z:\\rar", "Z:\\rar\\rarextract")

#generate_testfiles("Z:\\rar\\rarextract", "Z:\\rar\\rarextract\\testcompression")
compare("Z:\\rar\\rarextract\\testcompression")





#args = ([unrar, "e", "Z://rar//rarextract//wrar400.exe"] +
#             ["Rar.exe", "TechNote.txt", "WhatsNew.txt"] + 
#             ["Z:\\rar\\rarextract"])
#print " ".join(args)
#custom_popen(args)

#subprocess.Popen(args, stdout=subprocess.PIPE)











"""

 Exit values
 ~~~~~~~~~~~

    RAR exits with a zero code (0) in case of successful operation. The exit
    code of non-zero means the operation was cancelled due to an error:

     255   USER BREAK       User stopped the process

       9   CREATE ERROR     Create file error

       8   MEMORY ERROR     Not enough memory for operation

       7   USER ERROR       Command line option error

       6   OPEN ERROR       Open file error

       5   WRITE ERROR      Write to disk error

       4   LOCKED ARCHIVE   Attempt to modify an archive previously locked
                            by the 'k' command

       3   CRC ERROR        A CRC error occurred when unpacking

       2   FATAL ERROR      A fatal error occurred

       1   WARNING          Non fatal error(s) occurred

       0   SUCCESS          Successful operation
"""



