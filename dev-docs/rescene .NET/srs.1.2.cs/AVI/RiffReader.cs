using System;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;
using System.Diagnostics;
using System.Globalization;

namespace ReSample.Riff
{
	public enum RiffReadMode
	{
		AVI,
		Sample,
		SRS
	}

	public enum RiffChunkType
	{
		List,
		Movi,
		SrsFile,
		SrsTrack,
		Unknown
	}

	public class RiffChunk
	{
		public string FourCC { get; set; }
		public uint Length { get; set; }
		public byte[] RawHeader { get; set; }
		public long ChunkStartPos { get; set; }
	}

	public class MoviChunk : RiffChunk
	{
		public int StreamNumber { get; set; }
	}

	public class RiffList : RiffChunk
	{
		public string ListType { get; set; }
	}

	/// <summary>
	/// Implements a simple Reader class that reads through AVI or AVI-SRS files one chunk at a time.
	/// </summary>
	public class RiffReader : IDisposable
	{
		private static Regex fourCCValidator = new Regex("^[ 0-9A-Za-z]{4}$", RegexOptions.Compiled);

		private byte[] chunkHeader = new byte[12];
		private long fileLength = 0;

		protected Stream riffStream;
		protected RiffReadMode mode;
		protected bool readReady = true;

		protected RiffChunk currentChunk;

		public RiffChunkType ChunkType { get; protected set; }
		public bool HasPad { get; protected set; }
		public byte PadByte { get; protected set; }

		public RiffChunk Chunk
		{
			get { return currentChunk; }
		}
		public MoviChunk MoviChunk
		{
			get { return currentChunk as MoviChunk; }
		}
		public RiffList List
		{
			get { return currentChunk as RiffList; }
		}
		public Stream BaseStream
		{
			get { return riffStream; }
		}

		public RiffReader(string riffPath, RiffReadMode readMode)
		{
			this.riffStream = new FileStream(riffPath, FileMode.Open, FileAccess.Read, FileShare.Read);
			fileLength = riffStream.Length;
			this.mode = readMode;
		}

		public RiffReader(Stream riffStream, RiffReadMode readMode)
		{
			this.riffStream = riffStream;
			fileLength = riffStream.Length;
			this.mode = readMode;
		}

		public bool Read()
		{
			Debug.Assert(readReady || (mode == RiffReadMode.SRS && ChunkType == RiffChunkType.Movi), "Read() is invalid at this time", "MoveToChild, ReadContents(), or SkipContents() must be called before Read() can be called again");

			long chunkStartPos = riffStream.Position;
			currentChunk = null;
			readReady = false;

			if (chunkStartPos + 8 > fileLength)
				return false;

			riffStream.Read(chunkHeader, 0, 8);
			// 4 bytes for fourCC, 4 for chunk length
			string fourCC = Encoding.ASCII.GetString(chunkHeader, 0, 4);
			uint chunkLen = BitConverter.ToUInt32(chunkHeader, 4);

			// might not keep this check.  the length check should catch corruption on its own...
			if (!fourCCValidator.IsMatch(fourCC))
				throw new InvalidDataException(string.Format("Invalid FourCC value ({0}) at 0x{1:x8}", fourCC, chunkStartPos));

			// sanity check on chunk length.  skip check on RIFF list so we can still report expected size.    this is only applied on samples since a partial movie might still be useful
			long endOffset = chunkStartPos + 8 + chunkLen;
			if (mode == RiffReadMode.Sample && fourCC != "RIFF" && endOffset > fileLength)
				throw new InvalidDataException(string.Format("Invalid chunk length at 0x{0:x8}", chunkStartPos + 4));

			if (fourCC == "RIFF" || fourCC == "LIST")
			{
				// if the fourCC indicates a list type (RIFF or LIST), there is another fourCC code in the next 4 bytes
				string listType = fourCC;
				riffStream.Read(chunkHeader, 8, 4);
				fourCC = Encoding.ASCII.GetString(chunkHeader, 8, 4);
				chunkLen -= 4;
				byte[] rawHdr = new byte[12];
				Buffer.BlockCopy(chunkHeader, 0, rawHdr, 0, 12);
				ChunkType = RiffChunkType.List;
				currentChunk = new RiffList() { ListType = listType, FourCC = fourCC, Length = chunkLen, RawHeader = rawHdr, ChunkStartPos = chunkStartPos };
			}
			else
			{
				byte[] rawHdr = new byte[8];
				Buffer.BlockCopy(chunkHeader, 0, rawHdr, 0, 8);
				if (char.IsDigit((char)chunkHeader[0]) && char.IsDigit((char)chunkHeader[1]))
				{
					currentChunk = new MoviChunk() { FourCC = fourCC, Length = chunkLen, RawHeader = rawHdr, ChunkStartPos = chunkStartPos, StreamNumber = int.Parse(fourCC.Substring(0, 2), NumberStyles.HexNumber) };
					ChunkType = RiffChunkType.Movi;
				}
				else
				{
					currentChunk = new RiffChunk() { FourCC = fourCC, Length = chunkLen, RawHeader = rawHdr, ChunkStartPos = chunkStartPos };
					ChunkType = RiffChunkType.Unknown;
				}
			}

			HasPad = chunkLen % 2 == 1;

			return true;
		}

		public byte[] ReadContents()
		{
			// if readReady is set, we've already read or skipped it.  back up and read again?
			if (readReady)
				riffStream.Seek(-currentChunk.Length - (HasPad ? 1 : 0), SeekOrigin.Current);

			readReady = true;
			byte[] buff = null;

			if (mode != RiffReadMode.SRS || ChunkType != RiffChunkType.Movi)
			{
				buff = new byte[currentChunk.Length];
				riffStream.Read(buff, 0, buff.Length);
			}

			if (HasPad)
				PadByte = (byte)riffStream.ReadByte();

			return buff;
		}

		public void SkipContents()
		{
			if (!readReady)
			{
				readReady = true;

				if (mode != RiffReadMode.SRS || ChunkType != RiffChunkType.Movi)
					riffStream.Seek(currentChunk.Length, SeekOrigin.Current);

				if (HasPad)
					PadByte = (byte)riffStream.ReadByte();
			}
		}

		public void MoveToChild()
		{
			Debug.Assert(ChunkType == RiffChunkType.List, "MoveToChild() should only be called on a RIFF List");

			readReady = true;
		}

		public void Dispose()
		{
			riffStream.Close();
		}
	}
}
