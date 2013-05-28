using System;
using System.Collections.Generic;
using System.Text;
using System.IO;

namespace ReScene
{
	public enum RarBlockType : byte
	{
		// not all block types are consumed. this type is for ones we don't know/care about
		Unknown = 0,
		// these are the only rar block types we do anything with
		RarVolumeHeader = 0x73,
		RarPackedFile = 0x74,
		RarOldRecovery = 0x78, // old-style RR.  new-style is in RarNewSub
		RarNewSub = 0x7A,
		// block types 0x72 to 0x7B are defined by the RAR spec.  these values let us identify them
		RarMin = 0x72,
		RarMax = 0x7B,
		// we use the range just below that (0x69 to 0x71) for SRR
		SrrHeader = 0x69,
		SrrStoredFile = 0x6A,
		SrrRarFile = 0x71
	}

	public class RarBlock
	{
		[Flags()]
		public enum FlagValues : ushort
		{
			LongBlock = 0x8000
		}

		protected BinaryReader reader;
		protected BinaryWriter writer;
		protected Encoding encoding = Encoding.UTF8;

		public ushort Crc { get; set; }
		public byte RawType { get; set; }
		public ushort Flags { get; set; }
		public byte[] RawData { get; set; }
		public long BlockPosition { get; set; }

		public RarBlock() { }
		public RarBlock(byte[] blockBytes, long filePos)
		{
			RawData = blockBytes;
			// BinaryReader and MemoryStream both implement IDisposable, but neither has a Finalize.
			//  since there are no destructors, I'm ok with leaving them both here and open for the lifetime of the instance
			reader = new BinaryReader(new MemoryStream(RawData), encoding);

			Crc = reader.ReadUInt16();
			RawType = reader.ReadByte();
			Flags = reader.ReadUInt16();
			reader.BaseStream.Seek(2, SeekOrigin.Current); // block size (which we already know)
			BlockPosition = filePos;
		}

		// all RAR and SRR blocks share the same 7 byte header
		public const ushort HeaderLength = sizeof(ushort) + sizeof(byte) + sizeof(ushort) + sizeof(ushort);

		public void WriteHeader(ushort length, int addlLength)
		{
			writer = new BinaryWriter(new MemoryStream(RawData = new byte[length + addlLength]), encoding);

			writer.Write(Crc);
			writer.Write(RawType);
			writer.Write(Flags);
			writer.Write(length);
		}
	}

	public class SrrHeaderBlock : RarBlock // 0x69
	{
		[Flags()]
		public new enum FlagValues : ushort
		{
			AppNamePresent = 0x1
		}

		public static ushort SupportedFlagMask = (ushort)FlagValues.AppNamePresent;

		public string AppName { get; set; }

		public SrrHeaderBlock(byte[] blockBytes, long filePos) : base(blockBytes, filePos)
		{
			// if AppNamePresent flag is set, header contains 2 bytes for app name length, then the name
			if ((base.Flags & (ushort)FlagValues.AppNamePresent) != 0)
				AppName = new string(reader.ReadChars(reader.ReadUInt16()));
			else
				AppName = "Unknown";
		}

		// SRR blocks are based on RAR block format.  Header block type is 0x69.  We don't use crc for blocks (as of now), so crc value is set to 0x6969
		//  Flag 0x1 indicates the header contains appName. Length of the block is 7 (header length) + 2 bytes for appName length + the length of the appName.
		//  See http://datacompression.info/ArchiveFormats/RAR202.txt for more details on RAR file format
		public SrrHeaderBlock(string appName)
		{
			Crc = 0x6969;
			RawType = 0x69;
			Flags = (ushort)FlagValues.AppNamePresent;

			int length = HeaderLength + sizeof(ushort) + encoding.GetByteCount(appName);
			AppName = appName;

			WriteHeader((ushort)length, 0);
			writer.Write((ushort)encoding.GetByteCount(appName));
			writer.Write(appName.ToCharArray());
		}
	}

	public class SrrStoredFileBlock : RarBlock // 0x6A
	{
		[Flags()]
		public new enum FlagValues : ushort
		{
			PathsSaved = 0x2,
			LongBlock = 0x8000
		}

		public static ushort SupportedFlagMask = (ushort)(FlagValues.PathsSaved | FlagValues.LongBlock);

		public string FileName { get; set; }
		public ushort FileOffset { get; set; }
		public uint FileLength { get; set; }

		//public SrrStoredFileBlock() { }
		public SrrStoredFileBlock(byte[] blockBytes, long filePos) : base(blockBytes, filePos)
		{
			// 4 bytes for file length
			FileLength = reader.ReadUInt32();

			// 2 bytes for name length, then the name
			FileName = new string(reader.ReadChars(reader.ReadUInt16()));
			FileOffset = (ushort)reader.BaseStream.Position;
		}

		// store block (type 0x6A) has the 0x8000 flag set to indicate there is additional data following the block.
		// format is 7 byte header followed by 4 byte file size, 2 byte file name length, and file name
		public SrrStoredFileBlock(string fileName, int fileLength)
		{
		// editing the flag value after it is constructed doesn't do anything!!
		// TODO: bug!
		
		
		
			Crc = 0x6A6A;
			RawType = 0x6A;
			Flags = (ushort)FlagValues.LongBlock;

			int length = HeaderLength + sizeof(uint) + sizeof(ushort) + encoding.GetByteCount(fileName);
			FileName = fileName;
			FileLength = (uint)fileLength;
			FileOffset = (ushort)length;

			WriteHeader(FileOffset, fileLength);
			writer.Write(FileLength);
			writer.Write((ushort)encoding.GetByteCount(fileName));
			writer.Write(fileName.ToCharArray());
		}
	}

	public class SrrRarFileBlock : RarBlock // 0x71
	{
		[Flags()]
		public new enum FlagValues : ushort
		{
			RecoveryBlocksRemoved = 0x1,
			PathsSaved = 0x2
		}

		public static ushort SupportedFlagMask = (ushort)(FlagValues.RecoveryBlocksRemoved | FlagValues.PathsSaved);

		public string FileName { get; set; }

		//public SrrRarFileBlock() { }
		public SrrRarFileBlock(byte[] blockBytes, long filePos) : base(blockBytes, filePos)
		{
			// 2 bytes for name length, then the name
			FileName = new string(reader.ReadChars(reader.ReadUInt16()));
		}

		// we create one SRR block (type 0x71) for each RAR file.
		//  it has 7 byte header, 2 bytes for file name length, then file name
		//  flag 0x1 means recovery records have been removed if present
		public SrrRarFileBlock(string fileName)
		{
			Crc = 0x7171;
			RawType = 0x71;
			Flags = (ushort)FlagValues.RecoveryBlocksRemoved;

			int length = HeaderLength + sizeof(ushort) + encoding.GetByteCount(fileName);
			FileName = fileName;

			WriteHeader((ushort)length, 0);
			writer.Write((ushort)encoding.GetByteCount(fileName));
			writer.Write(fileName.ToCharArray());
		}
	}

	public class RarVolumeHeaderBlock : RarBlock // 0x73
	{
		[Flags()]
		public new enum FlagValues : ushort
		{
			Volume = 0x1,
			NewNumbering = 0x10,
			Protected = 0x40,
			Encrypted = 0x80,
			FirstVolume = 0x100
		}

		public RarVolumeHeaderBlock(byte[] blockBytes, long filePos) : base(blockBytes, filePos) { }
	}

	public class RarPackedFileBlock : RarBlock // 0x74
	{
		[Flags()]
		public new enum FlagValues : ushort
		{
			SplitBefore = 0x1,
			SplitAfter = 0x2,
			Directory = 0xe0,
			LargeFile = 0x100,
			Utf8FileName = 0x200
		}

		public byte CompressionMethod { get; protected set; }
		public ulong PackedSize { get; protected set; }
		public ulong UnpackedSize { get; protected set; }
		public uint FileCrc { get; protected set; }
		public string FileName { get; protected set; }

		public RarPackedFileBlock(byte[] blockBytes, long filePos) : base(blockBytes, filePos)
		{
			// 4 bytes for packed size, 4 for unpacked
			PackedSize = reader.ReadUInt32();
			UnpackedSize = reader.ReadUInt32();

			// skip 1 byte for OS
			reader.BaseStream.Seek(1, SeekOrigin.Current);

			// 4 bytes for crc
			FileCrc = reader.ReadUInt32();

			// skip 4 bytes for file date/time, 1 for required RAR version
			reader.BaseStream.Seek(5, SeekOrigin.Current);

			// 1 byte for compression method, then 2 for filename length
			CompressionMethod = reader.ReadByte();
			ushort nameLength = reader.ReadUInt16();

			// skip 4 bytes for file attributes
			reader.BaseStream.Seek(4, SeekOrigin.Current);

			// if large file flag is set, next are 4 bytes each for high order bits of file sizes
			if ((base.Flags & (ushort)FlagValues.LargeFile) != 0)
			{
				PackedSize += reader.ReadUInt32() * 0x100000000ul;
				UnpackedSize += reader.ReadUInt32() * 0x100000000ul;
			}

			// and finally, the file name.
			FileName = new string(reader.ReadChars(nameLength));

			// the file name can be null-terminated, especially in the case of utf-encoded ones.  cut it off if necessary
			if (FileName.IndexOf('\0') >= 0)
				FileName = FileName.Substring(0, FileName.IndexOf('\0'));
		}
	}

	public class RarRecoveryBlock : RarPackedFileBlock // 0x7A (FILE and NEWSUB share the same structure)
	{
		public uint RecoverySectors { get; protected set; }
		public ulong DataSectors { get; protected set; }

		public RarRecoveryBlock(byte[] blockBytes, long filePos) : base(blockBytes, filePos)
		{
			// skip 8 bytes for 'Protect+'
			reader.BaseStream.Seek(8, SeekOrigin.Current);

			// 4 bytes for recovery sector count, 8 bytes for data sector count
			RecoverySectors = reader.ReadUInt32();
			DataSectors = reader.ReadUInt64();
		}
	}

	public class RarOldRecoveryBlock : RarBlock // 0x78
	{
		public uint PackedSize { get; protected set; }
		public ushort RecoverySectors { get; protected set; }
		public uint DataSectors { get; protected set; }

		public RarOldRecoveryBlock(byte[] blockBytes, long filePos)
			: base(blockBytes, filePos)
		{
			PackedSize = reader.ReadUInt32();

			// skip 1 byte for RAR version
			reader.BaseStream.Seek(1, SeekOrigin.Current);

			// 2 bytes for recovery sector count, 4 bytes for data sector count
			RecoverySectors = reader.ReadUInt16();
			DataSectors = reader.ReadUInt32();

			// 8 bytes for 'Protect!'
			//reader.BaseStream.Seek(8, SeekOrigin.Current);
		}
	}
}
