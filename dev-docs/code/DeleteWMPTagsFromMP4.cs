/// Source: https://pastebin.com/raw/VJgi20vP
/// https://social.technet.microsoft.com/Forums/windows/en-US/74adc717-7778-45d6-a779-573eaab9cd30/mp4-file-corruption?forum=w7itpromedia#c0314c5b-38cd-4f3b-9d57-b802a0fc6711
/// MemoryError when trying to create .srs with pysrs afterwards

using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.IO;
using System.Diagnostics;
using System.Threading;
using System.Text.RegularExpressions;

class Script
{
    const string usage = "Usage: cscscript DeleteWMPTagsFromMP4.cs INFILE [/COMMIT]\n" +
                         "Removes meta and Xtra tags if present.\n";

    static bool commitFlag = false;

    static public void Main(string[] args)
    {
        if (args.Length == 0 ||
            (args.Length == 1 && (args[0] == "?" || args[0] == "/?" || args[0] == "-?" || args[0].ToLower() == "-help" || args[0].ToLower() == "help")))
        {
            Console.WriteLine(usage);
            return;
        }

        string[] files;
        if (args[0].Contains('*'))
        {
            string dir = Path.GetDirectoryName(args[0]);
            if (dir == "") dir = ".\\";
            string fname = Path.GetFileName(args[0]);
            files = Directory.GetFiles(dir, fname, SearchOption.AllDirectories);
        }
        else
            files = new string[1] { args[0] };

        if (args.Length > 1)
            commitFlag = args[1].Equals("/COMMIT", StringComparison.CurrentCultureIgnoreCase);

        Console.WriteLine("Inputfile:  " + args[0]);
        Console.WriteLine("CommitFlag: " + (commitFlag ? "COMMIT" : "no-commit"));
        Console.WriteLine("");

        foreach (string filename in files)
        {
            if (!File.Exists(filename))
            {
                Console.WriteLine(" Cannot locate file " + filename);
                continue;
            }

            ParseFile(filename);
        }
    }

    static public void ParseFile(string filename)
    {
        int original_filelength = 0;
        int moov_pos = 0, moov_size = 0;
        int udta_pos = 0, udta_size = 0;
        int meta_pos = 0, meta_size = 0;
        int xtra_pos = 0, xtra_size = 0;

        //        Console.WriteLine(string.Format("Parsing [ {0} ]... ", filename));

        using (BinaryReader br = new BinaryReader(File.Open(filename, FileMode.Open, FileAccess.Read)))
        {
            original_filelength = (int)br.BaseStream.Length;

            // check filetype
            br.BaseStream.Seek(4, SeekOrigin.Begin);
            if ("ftypisom" != ASCIIEncoding.ASCII.GetString(br.ReadBytes(8)))
            {
                //Console.WriteLine( " [UNKNOWN FILETYPE]");
                Console.WriteLine(string.Format("[UNKNOWN] [ {0} ]", filename));
                return;
            }

            if (locateTag(br, 0, "moov", ref moov_pos, ref moov_size))
            {
                if (locateTag(br, moov_pos + 8, "udta", ref udta_pos, ref udta_size))
                {
                    locateTag(br, udta_pos + 8, "meta", ref meta_pos, ref meta_size);
                    locateTag(br, udta_pos + 8, "Xtra", ref xtra_pos, ref xtra_size);
                }
            }

            // if file clean, exit
            if ((meta_pos == 0) && (xtra_pos == 0))
            {
                //Console.WriteLine(" [CLEAN]");
                Console.WriteLine(string.Format("[CLEAN]   [ {0} ]", filename));
                return;
            }

            //Console.WriteLine( "[DIRTY!]" );
            Console.WriteLine(string.Format("[DIRTY]   [ {0} ]", filename));
            Console.WriteLine(string.Format(" Tags @ 0x{0:x8}-0x{1:x8}, 0x{2:x8}-0x{3:x8}, 0x{4:x8}-0x{5:x8}",
                                        udta_pos, udta_pos + udta_size,
                                        meta_pos, meta_pos + meta_size,
                                        xtra_pos, xtra_pos + xtra_size
                                        ));

            if (!commitFlag)
                return;

            Console.WriteLine(string.Format(" Fixing file... ", filename));

            try
            {
                byte[] udta_buffer;

                // read udat into memory
                br.BaseStream.Seek(udta_pos, SeekOrigin.Begin);
                udta_buffer = br.ReadBytes((int)udta_size);

                if (BA_FindTag(ref udta_buffer, "meta", ref meta_pos, ref meta_size))
                    CleanUDTA(ref udta_buffer, meta_pos, meta_size);
                if (BA_FindTag(ref udta_buffer, "Xtra", ref xtra_pos, ref xtra_size))
                    CleanUDTA(ref udta_buffer, xtra_pos, xtra_size);
                UpdateUDTASize(ref udta_buffer);

                using (BinaryWriter bw = new BinaryWriter(File.Open(filename + "$TMP", FileMode.Create, FileAccess.Write)))
                {
                    // copy from 0 to UDTA begin
                    br.BaseStream.Seek(0, SeekOrigin.Begin);
                    BufferedBinaryCopy(br, bw, udta_pos);

                    // write new UDTA
                    if (udta_buffer.Length > 8)
                        bw.Write(udta_buffer);

                    // copy from after old UDTA to EOF
                    br.BaseStream.Seek(udta_size, SeekOrigin.Current);
                    BufferedBinaryCopy(br, bw, original_filelength - (udta_pos + udta_size));
                }

                Console.WriteLine(" FIXED!");
            }
            catch
            {
                Console.WriteLine(" --FAILED--");
            }
        }
        File.Replace(filename + "$TMP", filename, filename + ".bak");
    }

    static public bool BufferedBinaryCopy(BinaryReader source, BinaryWriter destination, int length)
    {
        const int IOBUFFER_SIZE = 32 * 1024 * 1024;
        byte[] buffer;

        int bytes_left = length;
        int bytes_to_read = 0;

        while (bytes_left > 0)
        {
            bytes_to_read = Math.Min(IOBUFFER_SIZE, bytes_left);
            buffer = source.ReadBytes(bytes_to_read);
            bytes_left -= buffer.Length;

            destination.Write(buffer);
        }
        return true;
    }

    static public bool locateTag(BinaryReader br, int offset, string tag, ref int pos, ref int size)
    {
        Byte[] tagdata;
        try
        {
            br.BaseStream.Seek(offset, SeekOrigin.Begin);

            while (br.BaseStream.Position < br.BaseStream.Length - 8)
            {
                tagdata = br.ReadBytes(4);
                Array.Reverse(tagdata);
                int tagsize = (int)BitConverter.ToUInt32(tagdata, 0);
                if (tagsize == 1)
                {
                    byte[] exdata = br.ReadBytes(4);
                    Array.Reverse(exdata);
                    tagsize = (tagsize << 32) + (int)BitConverter.ToUInt32(exdata, 0);
                }

                tagdata = br.ReadBytes(4);
                string tagname = ASCIIEncoding.ASCII.GetString(tagdata);

                if (tagname == tag)
                {
                    pos = (int)br.BaseStream.Position - 8;
                    size = tagsize;
                    return true;
                }
                if (tagsize == 0)
                    return false;
                br.BaseStream.Seek(tagsize - 8, SeekOrigin.Current);
            }

        }
        catch
        {
        }
        return false;
    }

    static public void CleanUDTA(ref byte[] buffer, int pos, int size)
    {
        List<byte> lb = buffer.ToList();
        lb.RemoveRange(pos, size);
        buffer = lb.ToArray();
    }

    static public void UpdateUDTASize(ref byte[] buffer)
    {
        int buffer_length = buffer.Length;
        byte[] tagsize = BitConverter.GetBytes(buffer_length);
        Array.Reverse(tagsize);

        List<byte> lb = buffer.ToList();
        lb.RemoveRange(0, 4);
        lb.InsertRange(0, tagsize);
        buffer = lb.ToArray();
    }

    static public bool RewriteFile(ref BinaryReader input, long udta_pos, long udta_size, long meta_pos, long meta_size, long xtra_pos, long xtra_size)
    {
        string tempname = string.Format(@"{0}.txt", Guid.NewGuid());
        using (BinaryWriter b = new BinaryWriter(File.Open("tempname", FileMode.Create, FileAccess.Read)))
        {



        }
        return true;
    }

    static public bool BA_FindTag(ref byte[] bb, string tag, ref int tag_pos, ref int tag_size)
    {
        byte[] pattern = Encoding.UTF8.GetBytes(tag);
        int byte_index = BA_IndexOf(bb, pattern);
        if (byte_index >= 0)
        {
            tag_pos = byte_index - 4;
            tag_size = (bb[byte_index - 4] << 24) | (bb[byte_index - 3] << 16) | (bb[byte_index - 2] << 8) | bb[byte_index - 1];
            return true;
        }

        return false;
    }

    static public int BA_IndexOf(byte[] data, byte[] pattern)
    {
        if (pattern.Length > data.Length)
            return -1;

        for (int i = 0; i < data.Length - pattern.Length; i++)
        {
            bool found = true;
            for (int j = 0; j < pattern.Length; j++)
            {
                if (data[i + j] != pattern[j])
                {
                    found = false;
                    break;
                }
            }
            if (found)
            {
                return i;
            }
        }
        return -1;
    }
}