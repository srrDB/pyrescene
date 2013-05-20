from rescene import rar
import optparse
import sys
import os

def main(options, args):
#    print(options)
#    print(args)

    def list_files(rootdir):
        for root, _subFolders, files in os.walk(rootdir):
            for ifile in files:
                if ifile[-4:].lower() == ".srr":
                    fpath = os.path.join(root, ifile)
                    srrhblock = next(rar.RarReader(fpath))
                    #print(ifile[:-4])
                    #print(srrhblock.appname)
                    try:
                        if srrhblock.appname == "":
                            print(ifile)
                    except:
                        print(ifile)
                
            if not options.r: # not recursive
                break
                
    for pdir in args:
        list_files(pdir)
        
if __name__ == '__main__':
    parser = optparse.OptionParser(
    usage="Usage: %prog [options] srr director'\n"
    "This tool will list all the srr files that have no decent file header:\n"
    "No application name in the SRR header or not a SRR file.", 
    version="%prog 0.1") # --help, --version
    
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