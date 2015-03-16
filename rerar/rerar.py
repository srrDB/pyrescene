#! /usr/bin/env python3

# Copyright (c) 2011-2012 Martin 'vadmium' Panter
# Copyright (c) 2014 pyReScene
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

# Optimum values possibly depend on speed of Python and cache sizes and
# characteristics
FILE_CRC_BUF = 0x10000

from binascii import crc32
from rar import (
    S_BLK_HDR, S_FILE_HDR, S_SHORT, S_LONG, S_HIGH_SIZE,
    RAR_ID,
    RAR_BLOCK_MAIN, RAR_BLOCK_FILE, RAR_BLOCK_SUB, RAR_BLOCK_ENDARC,
    RAR_BLOCK_OLD_RECOVERY,
    RAR_LONG_BLOCK, RAR_SKIP_IF_UNKNOWN,
    RAR_MAIN_VOLUME, RAR_MAIN_RECOVERY, RAR_MAIN_FIRSTVOLUME, RAR_MAIN_LOCK,
    RAR_MAIN_NEWNUMBERING,
    RAR_FILE_SPLIT_BEFORE, RAR_FILE_SPLIT_AFTER, RAR_FILE_DICTMASK,
    RAR_FILE_LARGE, RAR_FILE_SALT, RAR_FILE_UNICODE, RAR_FILE_EXTTIME,
    RAR_ENDARC_NEXT_VOLUME, RAR_ENDARC_DATACRC, RAR_ENDARC_REVSPACE,
    RAR_ENDARC_VOLNR,
    RAR_OS_WIN32, RAR_OS_UNIX,
    write_main, MAIN_HDR_SIZE,
    write_file, file_hdr_size,
    FILE_PACK_POS, FILE_OS_POS, FILE_VER_POS, FILE_VER_POS, FILE_ATTR_POS,
    DICT_DEFAULT, DICT_MIN, DICT_MAX, DICT_POS,
    filename_encode, time_encode, size_64_encode,
    DOS_2SEC_BIT, DOS_2SEC_BITS, DOS_MIN_BIT, DOS_MIN_BITS,
    DOS_HOUR_BIT, DOS_HOUR_BITS, DOS_DAY_BIT, DOS_DAY_BITS,
    DOS_MONTH_BIT, DOS_MONTH_BITS, DOS_YEAR_BIT, DOS_YEAR_BITS,
    MTIME_INDEX,
    TIME_FLAG_BITS, TIME_VALID_BIT, TIME_ONE_BIT, TIME_SIZE_BIT,
    TIME_SIZE_BITS, TIME_FRAC_DIGITS, TIME_FRAC_BYTES,
    ATTR_ARCHIVE, ATTR_NORMAL,
    write_rr, rr_calc, calc_rr_count, calc_prot_size,
    RR_SECT_SIZE, RR_CRC_SIZE, RR_SUB_NAME, RR_PROTECT_2, RR_PROTECT_3,
    RR_HEADER_SIZE, RR_CRC_INIT,
    write_end, end_size, END_EXTRA,
    HDR_CRC_POS, HDR_DATA_POS, HDR_TYPE_POS, HDR_FLAGS_POS, HDR_SIZE_POS,
)
import sys
import os
import time
import re
import struct
import io
import math

def main():
    # srr => Produce rescene file rather than Rar files
    # srr-rr-full => Do not strip Rar recovery records (older SRR file format). Requires srr and one of the rr options.
    # volume => Explicitly specify first, second, etc full volume name. Default is ".partN.rar" for "new" Rar 3 naming scheme, where the number of digits is automatically determined by the total number of volumes; and ".rar", ".r00", ".r01", etc, ".r99", ".s00", etc, ".s99" or ".001", ".002", etc, for the "old" naming scheme.
    # Option to only do the first volume, the first few volumes, or any given set of volumes?
    
    help = False
    file = ""
    intname = None
    vol_max = 15 * 10 ** 6
    timestamp = None
    is_dryrun = False
    is_rr = False
    is_unicode = False
    newline = "\r\n"
    naming_version = None
    is_lock = False
    ref = None
    rls_name = None
    sfvhead = ""
    end_flags = RAR_ENDARC_DATACRC ^ RAR_ENDARC_REVSPACE ^ RAR_ENDARC_VOLNR
    attr = 1 << ATTR_ARCHIVE
    dict = None
    version = 3
    host_os = RAR_OS_WIN32
    lenient = False
    overwrite = False
    base = None
    
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg in {"help", "-h", "--help", "-?", "?"}:
            help = True
            i += 1
        elif "file" == arg:
            file = sys.argv[i + 1]
            i += 2
        elif "time" == arg:
            (timestamp, timestamp_frac) = get_timestamp(sys.argv[i + 1])
            i += 2
        elif "dryrun" == arg:
            is_dryrun = True
            i += 1
        elif "rr" == arg:
            is_rr = True
            i += 1
        elif "unicode" == arg:
            is_unicode = True
            i += 1
        elif "lf" == arg:
            newline = "\n"
            i += 1
        elif "internal" == arg:
            intname = sys.argv[i + 1]
            i += 2
        elif "naming2" == arg:
            naming_version = 2
            i += 1
        elif "naming3" == arg:
            naming_version = 3
            i += 1
        elif "lock" == arg:
            is_lock = True
            i += 1
        elif "ref" == arg:
            ref = sys.argv[i + 1]
            i += 2
        elif "crcrlf" == arg:
            newline = "\r\r\n"
            i += 1
        elif "sfvhead" == arg:
            sfvhead = sys.argv[i + 1]
            if sfvhead and "\n" != sfvhead[-1]:
                sfvhead += "\n"
            i += 2
        elif "nonum" == arg:
            end_flags &= ~RAR_ENDARC_VOLNR
            i += 1
        elif "blankend" == arg:
            end_flags = 0
            i += 1
        elif "normalattr" == arg:
            attr = 1 << ATTR_NORMAL
            i += 1
        elif "dict" == arg:
            dict = int(sys.argv[i + 1])
            if not DICT_MIN <= dict <= DICT_MAX:
                raise SystemExit("Dictionary size {} out of {}-{} range".
                    format(dict, DICT_MIN, DICT_MAX))
            if dict not in (64, 128, 256, 512, 1024, 2048, 4096):
                raise SystemExit("Dictionary size {} not a round binary".
                    format(dict))
            i += 2
        elif "rar2" == arg:
            version = 2
            i += 1
        elif "size" == arg:
            vol_max = int(sys.argv[i + 1])
            i += 2
        elif "unix" == arg:
            host_os = RAR_OS_UNIX
            i += 1
        elif "lenient" == arg:
            lenient = True
            i += 1
        elif "overwrite" == arg:
            overwrite = True
            i += 1
        elif "base" == arg:
            base = sys.argv[i + 1]
            i += 2
        else:
            raise SystemExit('''Bad command line argument: {}
Try "{} help"'''.format(arg, sys.argv[0]))
    
    if help:
        print("""\
Options:
help\tDisplay this help
file <grp-name.avi>
\tSpecify data file. If directory only is specified, append internal name.
ref <grp-name.rar>
\tRead settings from existing Rar file
internal <grp-name.avi>
\tName to be used for the data file inside the Rar set. Defaults to the
\texternal file name, without any directory components (basename).
time "<yyyy>-<mm>-<dd> <hh>:<mm>:<ss>[.<sssssss>]"
\tOverride data file timestamp (Full resolution: +5 bytes per volume)
dryrun\tDisplay file names and sizes but do not create them
rr\tProduce Rar 3 recovery records (~1% of total size)
unicode\tStore data file name in Unicode (~4 bytes per volume)
lf\tUse only LFs at end of text lines in SFV file
crcrlf\tUse CR-CR-LF end-of-line sequence
sfvhead\tSpecify SFV header
naming3\tForce "new" Rar 3 volume naming scheme (".partN.rar"). Default is
\t"old" Rar 2 unless names beyond ".r99" would be needed.
naming2
lock\tSet "lock" bit, indicating the archive is not supposed to be modified
nonum\tDo not include volume number in end block
blankend
\tDo not include any fields in end block
normalattr
\tSet "normal" (instead of usual "archive") file attribute bit
dict <size>
\tSpecify dictionary size (default is 4096 for Rar 3 and 256 for Rar 2)
rar2\t"Old" Rar version 2 format
size <size>
\tRar volume size (default is 15000000)
unix\tSet OS to Unix (instead of Windows)
lenient\tIgnore problems with the reference file
overwrite
\tAllow writing to release directory that already exists
base <grp-name>
\tBase output name, appended with ".sfv", ".partN" and ".rar" as
\tappropriate. Default is the base name of the internal data file name
\twith extension removed.""")
#~ time +/-s.sssssss\tAdjust data file timestamp
#~ M specifies units of 10^6. (TODO: Use scene rules for default.)
        return
    
    if ref is not None:
        if timestamp is not None or is_rr or is_unicode or is_lock:
            raise SystemExit("""\
"Reference" mode not compatible with "timestamp", "rr", "unicode", and
"lock" options.""")
        
        (
            rls_name, version, is_rr, is_lock, naming_version, is_unicode,
            dict, host_os, timestamp, timestamp_frac, attr, intname,
            end_flags,
        errors) = parse_ref(ref)
        
        #~ with "sfv" as sfv:
            #~ get header
            #~ find ref name
        
        print()
        
        if errors and not lenient:
            raise SystemExit()
        if is_dryrun:
            return
    
    if dict is None:
        dict = DICT_DEFAULT[version]
    
    if file is None:
        file = ""
    if not file or os.path.isdir(file):
        if intname is None:
            raise SystemExit("""Data file not specified.
Try "{} help".""".format(sys.argv[0]))
        file = os.path.join(file, intname)
    if intname is None:
        intname = os.path.basename(file)
    name_field = filename_encode(intname, is_unicode)
    
    file_stat = os.stat(file)
    if timestamp is None:
        timestamp = time.localtime(file_stat.st_mtime)
        timestamp_frac = file_stat.st_mtime - int(file_stat.st_mtime)
    
    (dostime, xtime_field) = time_encode(timestamp, timestamp_frac)
    file_size = file_stat.st_size
    
    # Volume up to potential RR
    data_max = vol_max - end_size(version, end_flags)
    
    if is_rr:
        rr_max = calc_rr_count(version, vol_max, vol_max)
        data_max = calc_prot_size(version, data_max, rr_max)
    
    data_max -= len(RAR_ID) + MAIN_HDR_SIZE
    size_64 = size_64_encode(0, file_size)
    data_max -= file_hdr_size(name_field, xtime_field, size_64)
    
    vol_count = quanta(file_size, data_max)
    if base is None:
        base = os.path.splitext(intname)[0]
    vol_digits = 1 + int(math.log10(vol_count - 1))
    sfv_name = "{}.sfv".format(base)
    rls_size = 0
    
    if naming_version is None:
        naming_version = 3 if vol_count > 1 + 100 else 2
    if naming_version >= 3:
        volnum = Numbering3(vol_digits)
    else:
        volnum = Numbering2()
    print("Number of volumes:", vol_count, file=sys.stderr)
    
    if rls_name is None:
        rls_name = ""
    else:
        if not (overwrite and os.path.isdir(rls_name)):
            os.mkdir(rls_name)
    
    Writer = DryRlsWriter if is_dryrun else RlsWriter
    with Writer(file, version, host_os, is_rr, naming_version, newline) as (
    rls):
        start_ellipsis = True
        left = file_size
        while left > 0:
            volname = "{}.{}".format(base, next(volnum))
            
            is_first_vol = volnum.is_first()
            is_last_vol = left <= data_max
            data_size = left if is_last_vol else data_max
            is_interesting = (not is_dryrun or volnum.is_interesting() or
                volnum.num >= vol_count - 2)
            
            if is_interesting:
                print(volname, end=": ", file=sys.stderr)
                sys.stderr.flush()
            elif start_ellipsis:
                print(". . .", file=sys.stderr)
            
            with rls.new_vol(os.path.join(rls_name, volname)) as vol:
                vol.write_id()
                vol.write_main(is_first_vol, is_lock)
                vol.write_file(not is_first_vol, not is_last_vol, name_field,
                    is_unicode, dict, attr, dostime, xtime_field, file_size,
                    data_size)
                
                if is_rr:
                    if is_last_vol or version < 3:
                        rr_count = calc_rr_count(version, vol.size, vol_max)
                    else:
                        rr_count = rr_max
                    vol.write_rr(rr_count)
                
                vol.write_end(end_flags, volnum.num, is_last_vol)
            
            rls.sfv_add(vol, volname)
            rls_size += vol.size
            
            if is_interesting:
                sys.stderr.write("Size: {}".format(fmt_size(vol.size)))
                if not is_dryrun:
                    sys.stderr.write(" CRC: {:08X}".format(vol.crc))
                print(file=sys.stderr)
            
            left -= data_size
            start_ellipsis = is_interesting
        
        rls.sfv_write(os.path.join(rls_name, sfv_name), sfvhead)
        print("{}: Size: {}".format(sfv_name, fmt_size(rls.sfv_size)),
            file=sys.stderr)
        rls_size += rls.sfv_size
    
    print("Total release size: {}".format(fmt_size(rls_size)))

def get_timestamp(s):
    frac = re.search(r"(\.\d*)?$", s)
    tm = time.strptime(s[:frac.start()], "%Y-%m-%d %H:%M:%S")
    frac = frac.group()
    if frac in {"", "."}:
        frac = 0
    else:
        frac = float(frac)
    return (tm, frac)

def parse_ref(ref):
    with Parser(ref) as parser:
        rls_name = os.path.basename(os.path.dirname(ref))
        if not rls_name or rls_name.startswith("."):
            rls_name = None
        else:
            parser.out("rls", rls_name)
        version = None
        
        hdr = parser.read(len(RAR_ID))
        if RAR_ID != hdr:
            parser.die(0, "Invalid Rar marker")
        
        (pos, hdr, flags) = parser.expect_block(RAR_BLOCK_MAIN, "Main",
            RAR_MAIN_FIRSTVOLUME ^ RAR_MAIN_RECOVERY ^ RAR_MAIN_LOCK ^
            RAR_MAIN_NEWNUMBERING, RAR_MAIN_VOLUME)
        is_rr = bool(flags & RAR_MAIN_RECOVERY)
        is_lock = bool(flags & RAR_MAIN_LOCK)
        is_first = bool(flags & RAR_MAIN_FIRSTVOLUME)
        if is_rr:
            parser.out("rr")
        if is_lock:
            parser.out("lock")
        
        naming_version = 3 if flags & RAR_MAIN_NEWNUMBERING else 2
        parser.out("naming{}".format(naming_version))
        
        if MAIN_HDR_SIZE != len(hdr):
            parser.error(pos + HDR_SIZE_POS,
                "Expected main block size 0x{:X}".format(MAIN_HDR_SIZE))
        if any(x != 0 for x in hdr[S_BLK_HDR.size:]):
            parser.error(pos + S_BLK_HDR.size,
                "Expected zeroed main block data")
        
        (pos, hdr, flags) = parser.expect_block(RAR_BLOCK_FILE,  "File",
            RAR_FILE_SPLIT_BEFORE ^ RAR_FILE_SPLIT_AFTER ^ RAR_FILE_LARGE ^
            RAR_FILE_UNICODE ^ RAR_FILE_EXTTIME ^ RAR_FILE_DICTMASK,
            RAR_LONG_BLOCK)
        is_unicode = bool(flags & RAR_FILE_UNICODE)
        split_before = bool(flags & RAR_FILE_SPLIT_BEFORE)
        split_after = bool(flags & RAR_FILE_SPLIT_AFTER)
        dict = flags & RAR_FILE_DICTMASK
        
        dict_size = DICT_MIN << (dict >> DICT_POS)
        if dict_size > DICT_MAX:
            parser.error(pos + HDR_FLAGS_POS, "Unexpected dictionary "
                "size in flags: 0x{:02X}".format(dict))
        
        hdr_pos = S_BLK_HDR.size
        
        if is_unicode:
            parser.out("unicode")
        
        (pack_size, data_size, host_os, file_crc, timestamp, rar_ver,
            compress, name_size, attr) = (
            S_FILE_HDR.unpack_from(hdr, hdr_pos))
        
        if RAR_OS_UNIX == host_os:
            parser.out("unix")
        elif RAR_OS_WIN32 != host_os:
            parser.error(pos + hdr_pos + FILE_OS_POS,
                "Expected Windows OS")
        
        timestamp = [
            1980 + (timestamp >> DOS_YEAR_BIT & bitmask(DOS_YEAR_BITS)),
            timestamp >> DOS_MONTH_BIT & bitmask(DOS_MONTH_BITS),
            timestamp >> DOS_DAY_BIT & bitmask(DOS_DAY_BITS),
            timestamp >> DOS_HOUR_BIT & bitmask(DOS_HOUR_BITS),
            timestamp >> DOS_MIN_BIT & bitmask(DOS_MIN_BITS),
            (timestamp >> DOS_2SEC_BIT & bitmask(DOS_2SEC_BITS)) << 1,
        ]
        timestamp_frac = 0
        
        if 20 != rar_ver:
            parser.error(pos + hdr_pos + FILE_VER_POS,
                "Expected Rar version 2.0")
        if ord("0") != compress:
            parser.error(pos + hdr_pos + FILE_METHOD_POS,
                "Compression used")
        if 1 << ATTR_NORMAL == attr:
            parser.out("normalattr")
        elif 1 << ATTR_ARCHIVE != attr:
            parser.error(pos + hdr_pos + FILE_ATTR_POS,
                "Unexpected file attributes: 0x{:08X}".format(attr))
        
        hdr_pos += S_FILE_HDR.size
        
        if flags & RAR_FILE_LARGE:
            (high_pack, high_data) = S_HIGH_SIZE.unpack_from(hdr, hdr_pos)
            hdr_pos += S_HIGH_SIZE.size
            pack_size += high_pack << 32
            data_size += high_data << 32
            parser.error(pos + HDR_FLAGS_POS, "Large file not implemented")
        
        name_field = hdr[hdr_pos:][:name_size]
        
        if not flags & RAR_FILE_UNICODE:
            intname = name_field.decode("latin-1")
        else:
            intname = name_field[:name_field.index(bytes((0,)))].decode(
                "latin-1")
            if encode_filename(intname, True) != name_field:
                parser.error(pos + hdr_pos + len(intname) + 1,
                    "Unexpected filename encoding")
        parser.out("internal", intname)
        hdr_pos += name_size
        
        if flags & RAR_FILE_SALT:
            parser.die(pos + HDR_FLAGS_POS, "Salt not supported")
        
        if flags & RAR_FILE_EXTTIME:
            (xtime_flags,) = S_SHORT.unpack_from(hdr, hdr_pos)
            if (xtime_flags & ~((
                1 << TIME_ONE_BIT ^
                bitmask(TIME_SIZE_BITS) << TIME_SIZE_BIT
            ) << MTIME_INDEX * TIME_FLAG_BITS) !=
            1 << TIME_VALID_BIT << MTIME_INDEX * TIME_FLAG_BITS):
                parser.die(pos + hdr_pos, "Unsupported extended time")
            
            xtime_flags = (xtime_flags >> MTIME_INDEX * TIME_FLAG_BITS &
                bitmask(TIME_FLAG_BITS))
            if not xtime_flags & (
                1 << TIME_ONE_BIT |
                bitmask(TIME_SIZE_BITS) << TIME_SIZE_BIT
            ):
                parser.error(pos + hdr_pos, "Unneeded extended time")
            
            # Seconds field
            timestamp[5] |= xtime_flags >> TIME_ONE_BIT & 1
            
            hdr_pos += 2
            
            size = xtime_flags >> TIME_SIZE_BIT & bitmask(TIME_SIZE_BITS)
            for place in range(TIME_FRAC_BYTES - size, TIME_FRAC_BYTES):
                timestamp_frac |= hdr[hdr_pos] << BYTE_BITS * place
                hdr_pos += 1
            timestamp_frac /= 10 ** TIME_FRAC_DIGITS
        
        timestamp = time.struct_time(tuple(timestamp) + (0, 0, 0))
        parser.out("time", time.strftime("\"%Y-%m-%d %H:%M:%S", timestamp))
        if timestamp_frac:
            print(".{:0{digits}}".format(round(timestamp_frac * 10 **
                TIME_FRAC_DIGITS), digits=TIME_FRAC_DIGITS), end="")
        print("\"", end="")
        
        if hdr_pos != len(hdr):
            parser.error(pos + hdr_pos, "Excess file block header "
                "length: {}".format(len(hdr) - hdr_pos))
        
        print("{}: Size: {}".format(intname, fmt_size(data_size)),
            end="", file=sys.stderr)
        sys.stderr.flush()
        if not split_after:
            left = pack_size
            while left > 0:
                left -= len(parser.read(min(FILE_CRC_BUF, left)))
            
            print(" CRC: {:08X}".format(file_crc), end="",
                file=sys.stderr)
        else:
            calc_crc = file_crc32(parser, pack_size)
            if file_crc != calc_crc:
                parser.error(pos + len(hdr),
                    "CRC mismatch; calculated 0x{:08X}".format(calc_crc))
        print(file=sys.stderr)
        
        if is_rr:
            (pos, hdr, type, flags) = parser.read_block()
            if RAR_BLOCK_OLD_RECOVERY == type:
                version = 2
                parser.expect_flags(pos, "Rar 2 RR", flags, 0,
                    RAR_LONG_BLOCK ^ RAR_SKIP_IF_UNKNOWN)
                hdr_pos = S_BLK_HDR.size
                
                (data_size,) = S_LONG.unpack_from(hdr, hdr_pos)
                hdr_pos += S_LONG.size
                
                if 20 != hdr[hdr_pos]:
                    parser.error(pos + hdr_pos,
                        "Expected Rar version 2.0")
                hdr_pos += 1
                
                (rr_count,) = S_SHORT.unpack_from(hdr, hdr_pos)
                hdr_pos += S_SHORT.size
                
                (prot_sect_count,) = S_LONG.unpack_from(hdr, hdr_pos)
                hdr_pos += S_LONG.size
                
                if RR_PROTECT_2 != hdr[hdr_pos:][:len(RR_PROTECT_2)]:
                    parser.error(pos + hdr_pos,
                        'Expected "{}"'.format(RR_PROTECT_2))
                hdr_pos += len(RR_PROTECT_2)
                
                parser.expect_rr(pos, data_size, rr_count,
                    prot_sect_count, hdr, hdr_pos)
            elif RAR_BLOCK_SUB == type:
                version = 3
                parser.expect_flags(pos, "Sub", flags, 0,
                    RAR_LONG_BLOCK ^ RAR_SKIP_IF_UNKNOWN)
                hdr_pos = S_BLK_HDR.size
                
                (pack_size, data_size, sub_os, file_crc, sub_time,
                    rar_ver, compress, name_size, sub_attr) = (
                    S_FILE_HDR.unpack_from(hdr, hdr_pos))
                
                if 0 != sub_time or 0 != sub_attr:
                    parser.error(pos + hdr_pos, "Expected zero sub-"
                        "block timestamp and file attributes")
                if 29 != rar_ver:
                    parser.error(pos + hdr_pos + FILE_VER_POS,
                        "Expected Rar version 2.9")
                if host_os != sub_os:
                    parser.error(pos + hdr_pos + FILE_OS_POS,
                        "Sub-block ({}) and file ({}) OSes do not match".
                        format(sub_os, host_os))
                if ord("0") != compress:
                    parser.die(pos + hdr_pos + FILE_METHOD_POS,
                        "Compression used")
                if pack_size != data_size:
                    parser.error(pos + hdr_pos + FILE_PACK_POS, "Sub-"
                        "block packed size does not match unpacked size")
                
                hdr_pos += S_FILE_HDR.size
                if RR_SUB_NAME != hdr[hdr_pos:][:name_size]:
                    parser.die(pos + hdr_pos, "Expected RR sub-block")
                hdr_pos += name_size
                
                if RR_PROTECT_3 != hdr[hdr_pos:][:len(RR_PROTECT_3)]:
                    parser.error(pos + hdr_pos,
                        'Expected "{}"'.format(RR_PROTECT_3))
                hdr_pos += len(RR_PROTECT_3)
                
                (rr_count,) = S_LONG.unpack_from(hdr, hdr_pos)
                hdr_pos += S_LONG.size
                
                (prot_sect_count,) = struct.unpack_from("<Q", hdr,
                    hdr_pos)
                hdr_pos += 8
                
                rr_block_crc = parser.expect_rr(pos, data_size, rr_count,
                    prot_sect_count, hdr, hdr_pos)
                
                if file_crc != rr_block_crc:
                    parser.error(parser.file.tell(),
                        "RR block CRC mismatch; calculated 0x{:08X}".
                        format(rr_block_crc))
            else:
                parser.die(pos, "Expected RR block")
        
        vol_crc = parser.vol_crc
        (pos, hdr, type, flags) = parser.read_block()
        this_version = 3 if hdr else 2
        if version is not None and this_version != version:
            parser.error(pos, "Unexpected end block presence for Rar {}".
                format(version))
        else:
            version = this_version
        
        if hdr:
            parser.expect_type(pos, type, RAR_BLOCK_ENDARC, "End")
            parser.expect_flags(pos, "End", flags,
                RAR_ENDARC_NEXT_VOLUME ^ RAR_ENDARC_DATACRC ^
                RAR_ENDARC_REVSPACE ^ RAR_ENDARC_VOLNR,
                RAR_SKIP_IF_UNKNOWN)
            next_volume = bool(flags & RAR_ENDARC_NEXT_VOLUME)
            
            if next_volume != split_after:
                parser.error(pos + HDR_FLAGS_POS, "Split after ({}) and "
                    "next volume ({}) flags to not match".format
                    (split_after, next_volume))
            
            end_flags = flags & (RAR_ENDARC_DATACRC ^
                RAR_ENDARC_REVSPACE ^ RAR_ENDARC_VOLNR)
            if RAR_ENDARC_DATACRC ^ RAR_ENDARC_REVSPACE == end_flags:
                parser.out("nonum")
            elif 0 == end_flags:
                parser.out("blankend")
            elif (RAR_ENDARC_DATACRC ^ RAR_ENDARC_REVSPACE ^
            RAR_ENDARC_VOLNR != end_flags):
                parser.error(pos + HDR_FLAGS_POS,
                    "Unexpected end block flag combination 0x{:01X}".
                    format(end_flags))
            
            hdr_pos = S_BLK_HDR.size
            
            if end_flags & RAR_ENDARC_DATACRC:
                if S_LONG.unpack_from(hdr, hdr_pos) != (vol_crc,):
                    parser.error(pos + hdr_pos, "Volume CRC mismatch; "
                        "calculated 0x{:08X}".format(vol_crc))
                hdr_pos += S_LONG.size
            
            if end_flags & RAR_ENDARC_VOLNR:
                (volnum,) = S_SHORT.unpack_from(hdr, hdr_pos)
                if (0 == volnum) != is_first:
                    parser.error(pos + hdr_pos, "Volume number ({}) and "
                        "first volume flag ({}) do not match".
                        format(volnum, is_first))
                #~ if volnum != Numbering(new_numbering).name(ref):
                    
                hdr_pos += S_SHORT.size
            
            if end_flags & RAR_ENDARC_REVSPACE:
                if any(x != 0 for x in hdr[hdr_pos:][:END_EXTRA]):
                    parser.error(pos + S_BLK_HDR.size,
                        "Expected zeroed end block data")
                hdr_pos += END_EXTRA
            if hdr_pos != len(hdr):
                parser.error(pos + HDR_SIZE_POS,
                    "Unexpected extra end block data")
            
            pos = parser.file.tell()
            if parser.read(1):
                parser.error(pos, "Expected end of file")
        
        else:
            end_flags = None
        
        if 3 != version:
            parser.out("rar{}".format(version))
        if version >= 3 and split_before != (not is_first):
            parser.error(None, "Split before ({}) and first volume ({}) "
                "flags do not correspond".format(split_before, is_first))
        elif version < 3 and is_first:
            parser.error(None,
                "First volume flag set but not Rar 3 format")
        if DICT_DEFAULT[version] != dict:
            parser.out("dict", dict_size)
        
        print("Reference volume size:", fmt_size(pos), file=sys.stderr)
        parser.out("size", pos)
        # print(first volume or volume number {})
    
    if not os.path.basename(ref).startswith(
    os.path.splitext(intname)[0]):
        print("{}: appears to have been renamed".format(ref),
            file=sys.stderr)
        parser.fail = True
    
    # Verify size against rr_count
    # TODO: if not the final volume and RR doesn't introduce ambiguities,
    # show volume size. Verify against specified volume size?
    
    return (
        rls_name, version, is_rr, is_lock, naming_version, is_unicode, dict,
        host_os, timestamp, timestamp_frac, attr, intname, end_flags,
    parser.fail)

class Parser:
    def __init__(self, file):
        self.fail = False
        self.vol_crc = 0
        self.file = open(file, "rb")
    
    def __enter__(self):
        self.file = self.file.__enter__()
        return self
    
    def __exit__(self, *exc):
        self.file.__exit__()
    
    def msg(self, pos, msg):
        if pos is None:
            return "{}: {}".format(self.file.name, msg)
        else:
            return "{}+0x{:X}: {}".format(self.file.name, pos, msg)
    
    def error(self, pos, msg):
        print(self.msg(pos, msg), file=sys.stderr)
        self.fail = True
    
    def die(self, pos, msg):
        raise SystemExit(self.msg(pos, msg))
    
    def expect_rr(self, pos, data_size, rr_count, prot_sect_count, hdr,
    hdr_used):
        expect = quanta(pos, RR_SECT_SIZE)
        if expect != prot_sect_count:
            self.die(pos, "Expected protected sector count: {} not {}".
                format(expect, prot_sect_count))
        
        hdr = len(hdr)
        if hdr_used != hdr:
            self.error(pos + hdr_used,
                "Excess RR header length: {}".format(hdr - hdr_used))
        
        if (data_size !=
        prot_sect_count * RR_CRC_SIZE + rr_count * RR_SECT_SIZE):
            self.die(pos + S_BLOCK_HDR.size, "RR block data size does not "
                "correspond with sector and RR counts")
        
        (rr_crcs, rr_sects) = rr_calc(self.file, rr_count, pos)
        self.file.seek(+hdr, io.SEEK_CUR)
        crc = RR_CRC_INIT
        
        for i in range(prot_sect_count):
            pos = self.file.tell();
            calc_crc = rr_crcs[i * RR_CRC_SIZE:][:RR_CRC_SIZE]
            read_crc = self.read(RR_CRC_SIZE)
            if read_crc != calc_crc:
                self.error(pos, "Sector {} CRC mismatch; calculated "
                    "0x{:04X}".format(i, S_SHORT.unpack(calc_crc)))
            
            crc = crc32(read_crc, crc)
        
        for (i, sect) in enumerate(rr_sects):
            pos = self.file.tell()
            calc_sect = bytes(sect.buffer())
            read_sect = self.read(len(calc_sect))
            if read_sect != calc_sect:
                parser.error(pos, "Recovery sector {}/{} mismatch".
                    format(i, rr_count))
            
            crc = crc32(read_sect, crc)
        
        return crc
    
    def expect_block(self, exp_type, name, ign_flags, exp_flags):
        (pos, hdr, type, flags) = self.read_block()
        self.expect_type(pos, type, exp_type, name)
        self.expect_flags(pos, name, flags, ign_flags, exp_flags)
        return (pos, hdr, flags)
    
    def read_block(self):
        pos = self.file.tell()
        
        hdr = self.read(S_BLK_HDR.size)
        if not hdr:
            return (pos, None, None, None)
        
        (crc, type, flags, size) = S_BLK_HDR.unpack(hdr)
        
        if size < S_BLK_HDR.size:
            self.die(pos + HDR_SIZE_POS,
                "Block size too small: {}".format(size))
        hdr += self.read(size - S_BLK_HDR.size)
        
        calc_crc = crc32(hdr[HDR_DATA_POS:]) & bitmask(16)
        if calc_crc != crc:
            self.die(pos + HDR_CRC_POS,
                "Expected block CRC 0x{:04X}".format(calc_crc))
        return (pos, hdr, type, flags)
    
    def expect_type(self, pos, type, expect, name):
        if expect != type:
            self.die(pos + HDR_TYPE_POS,
                "Expected block type 0x{:02X} ({})".format(expect, name))
        
    def expect_flags(self, pos, block, flags, ignore, expect):
        if flags & ~ignore != expect:
            self.error(pos + HDR_FLAGS_POS, "Unexpected flags: 0x{:04X} "
                "(Block: {})".format(flags, block))
    
    def read(self, size):
        data = self.file.read(size)
        self.vol_crc = crc32(data, self.vol_crc)
        return data
    
    def out(self, *args):
        print("", *args, end="")

def fmt_size(size):
    s = str(size)
    
    if size >= 1024:
        if size < 1024 << 10:
            pref = "K"
        else:
            for pref in "MGTPEZY":
                size >>= 10
                if size < 1024 << 10: break
        
        s += " ({:.3f} {}iB)".format(size / 1024, pref)
    
    return s

class DryRlsWriter:
    def __init__(self, name, version, host_os, is_rr, naming, newline):
        self.version = version
        self.sfv_size = 0
        self.sfv_newline = newline
    
    def __enter__(self):
        return self
    def __exit__(self, *exc):
        pass
    
    def new_vol(self, name):
        return DryVolWriter(self)
    
    def sfv_add(self, vol, name):
        self.sfv_size += len(name) + 1 + 8 + len(self.sfv_newline)
    
    def sfv_write(self, name, head):
        self.sfv_size += (len(head) +
            head.count("\n") * (len(self.sfv_newline) - 1))

class RlsWriter(DryRlsWriter):
    def __init__(self, file, version, host_os, is_rr, naming, newline):
        DryRlsWriter.__init__(self, file, version, host_os, is_rr, naming,
            newline)
        
        self.data = open(file, "rb")
        self.os = host_os
        self.naming = naming
        self.is_rr = is_rr
        self.file_crc = 0
        self.sfv_entries = dict()
        self.sfv_size = 0
    
    def __enter__(self):
        self.data = self.data.__enter__()
        return self
    
    def __exit__(self, *exc):
        self.data.__exit__()
    
    def new_vol(self, name):
        return VolWriter(self, name)
    
    def sfv_add(self, vol, name):
        self.sfv_entries[name] = vol.crc
        DryRlsWriter.sfv_add(self, vol, name)
    
    def sfv_write(self, name, head):
        with open(name, "wt", encoding="latin-1", newline="") as sfv:
            sfv.write(head.replace("\n", self.sfv_newline))
            for entry in sorted(self.sfv_entries):
                sfv.write("{} {:08x}{}".format(entry,
                    self.sfv_entries[entry], self.sfv_newline))

class DryVolWriter:
    def __init__(self, rls):
        self.rls = rls
        self.size = 0
    
    def __enter__(self): return self
    def __exit__(self, *exc): pass
    
    def write_id(self):
        self.size += len(RAR_ID)
    
    def write_main(self, is_first, is_lock):
        self.size += MAIN_HDR_SIZE
        
    def write_file(self, split_before, split_after, name, is_unicode, dict,
    attr, dostime, xtime, file_size, data_size):
        size_64 = size_64_encode(data_size, file_size)
        self.size += file_hdr_size(name, xtime, size_64)
        self.size += data_size
    
    def write_rr(self, count):
        self.size += (RR_HEADER_SIZE[self.rls.version] +
            quanta(self.size, RR_SECT_SIZE) * RR_CRC_SIZE +
            count * RR_SECT_SIZE)
    
    def write_end(self, flags, volnum, is_last):
        self.size += end_size(self.rls.version, flags)

class VolWriter(DryVolWriter):
    def __init__(self, rls, name):
        self.file = open(name, "w+b")
        DryVolWriter.__init__(self, rls)
    
    def __enter__(self):
        self.file = self.file.__enter__()
        return self
    
    def __exit__(self, *exc):
        self.file.__exit__(*exc)
    
    def write_id(self):
        self.file.write(RAR_ID)
        DryVolWriter.write_id(self)
    
    def write_main(self, is_first, is_lock):
        write_main(self.file, self.rls.version, self.rls.is_rr, is_first,
            self.rls.naming, is_lock)
        DryVolWriter.write_main(self, is_first, is_lock)
    
    def write_file(self, split_before, split_after, name, is_unicode, dict,
    attr, dostime, xtime, file_size, data_size):
        self.rls.file_crc = write_file(self.file, self.rls.data,
            split_before, split_after, name, is_unicode, dict, self.rls.os,
            attr, self.rls.file_crc, dostime, xtime, file_size, data_size)
        DryVolWriter.write_file(self, split_before, split_after, name,
            is_unicode, dict, attr, dostime, xtime, file_size, data_size)
    
    def write_rr(self, count):
        write_rr(self.rls.version, self.rls.os, self.file, count)
        DryVolWriter.write_rr(self, count)
    
    def write_end(self, flags, volnum, is_last):
        size = self.file.tell()
        self.crc = write_end(self.file, self.rls.version, flags, volnum,
            is_last)
        DryVolWriter.write_end(self, flags, volnum, is_last)
        size = self.file.tell() - size
        
        self.file.seek(-size, io.SEEK_CUR)
        self.crc = crc32(self.file.read(size), self.crc)

class VolNumbering:
    def __init__(self):
        self.next = 0
    
    def __iter__(self): return self
    
    def __next__(self):
        self.num = self.next
        self.next = self.next + 1
        return self.num
    
    def is_first(self):
        return not self.num
    
    def is_interesting(self):
        return self.is_first()

class Numbering3(VolNumbering):
    def __init__(self, digits):
        VolNumbering.__init__(self)
        self.digits = digits
    
    def __next__(self):
        return "part{:0{digits}}.rar".format(1 + VolNumbering.__next__(self),
            digits=self.digits)

class Numbering2(VolNumbering):
    def __next__(self):
        num = VolNumbering.__next__(self)
        if num < 1:
            return "rar"
        num -= 1
        if num < 100:
            return "r{:02}".format(num)
        num -= 100
        return "s{:02}".format(num)
    
    def is_interesting(self):
        return (VolNumbering.is_interesting(self) or
            self.num - 1 <= 200 and (self.num - 1) % 100 in {0, 99})

def file_crc32(file, size):
    crc = 0
    while size > 0:
        chunk = file.read(min(FILE_CRC_BUF, size))
        if not chunk:
            raise EOFError()
        size -= len(chunk)
        crc = crc32(chunk, crc)
    return crc

def bitmask(size): return ~(~0 << size)
BYTE_BITS = 8
def quanta(total, quantum): return (total - 1) // quantum + 1

if "__main__" == __name__: main()
