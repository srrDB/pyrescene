import os, sys, optparse
sys.path.append(os.path.join(os.getcwd(), '..'))
from rescene.rar import RarReader, BlockType

def process(rootdir):
    for root, _, files in os.walk(rootdir):
        for pfile in files:
            if pfile[-4:].lower() == ".srr":
                fpath = os.path.join(root, pfile)
                show_stored_files_flags(fpath)

        if not options.r:  # not recursive
            break

def show_stored_files_flags(srr_file):
    blocks = RarReader(srr_file).read_all()

    for block in blocks:
        if block.rawtype == BlockType.SrrStoredFile:
            print(hex(block.flags))


def main(options, args):
#    print(options)
#    print(args)
    for pdir in args:
        process(pdir)

if __name__ == '__main__':
    parser = optparse.OptionParser(
    usage="Usage: %prog [options] srr director'\n"
    "This tool will list the SRR files that have the wrong flags set.\n",
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
