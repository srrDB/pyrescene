using System;
using System.IO;

namespace ReScene
{
	public enum RarReadMode
	{
		RAR,
		SRR
	}

	/// <summary>
	/// Implements a simple Reader class that reads through RAR or SRR files one block at a time.
	/// </summary>
	public class RarReader : IDisposable
	{
		private const int headerLength = 7;

		private Stream rarStream;
		private RarReadMode mode;

		private long rarLength;
		private byte[] headerBuff = new byte[headerLength];

		public RarReader(string rarPath, RarReadMode readMode)
		{
			rarStream = new FileStream(rarPath, FileMode.Open, FileAccess.Read, FileShare.Read);
			rarLength = rarStream.Length;
			mode = readMode;
		}

		public RarReader(Stream rarStream, RarReadMode readMode)
		{
			this.rarStream = rarStream;
			rarLength = rarStream.Length;
			mode = readMode;
		}

		public RarBlock Read()
		{
			long blockStartPos = rarStream.Position;

			// make sure we can at least read the basic block header
			if (blockStartPos + headerLength > rarLength)
				return null;

			// block header is always 7 bytes.  2 for crc, 1 for block type, 2 for flags, and 2 for block length
			rarStream.Read(headerBuff, 0, headerLength);
			//ushort crc = BitConverter.ToUInt16(headerBuff, 0); // not used for now
			RarBlockType blockType = Enum.IsDefined(typeof(RarBlockType), headerBuff[2]) ? (RarBlockType)headerBuff[2] : RarBlockType.Unknown;
			ushort flags = BitConverter.ToUInt16(headerBuff, 3);
			ushort length = BitConverter.ToUInt16(headerBuff, 5);

			// one more sanity check on the length before continuing
			if (length < headerLength || blockStartPos + length > rarLength)
				throw new InvalidDataException(string.Format("Invalid RAR block length at offset 0x{1:X}", rarStream.Position - 2));

			byte[] blockBuff = new byte[length];
			Buffer.BlockCopy(headerBuff, 0, blockBuff, 0, headerLength);

			if (length == headerLength)
				return new RarBlock(blockBuff, blockStartPos);

			// read in the rest of the block.  we already have the header
			rarStream.Read(blockBuff, headerLength, length - headerLength);

			// if RAR LONG_BLOCK flag is set or if this is a File or NewSub block, next 4 bytes are additional data size
			uint addlLength = (flags & (ushort)RarBlock.FlagValues.LongBlock) != 0 || blockType == RarBlockType.RarPackedFile || blockType == RarBlockType.RarNewSub ? BitConverter.ToUInt32(blockBuff, 7) : 0;

			// next, check to see if this is a recovery record.  Old-style recovery records are stored in block type 0x78.
			//  New-style recovery records are stored in the RAR NEWSUB block type (0x7A)
			//   and have file name length of 2 (bytes 27 and 28) and a file name of RR (bytes 33 and 34)
			bool isRecovery = blockType == RarBlockType.RarOldRecovery || (blockType == RarBlockType.RarNewSub
								&& length > 34 && BitConverter.ToUInt16(blockBuff, 26) == 2 && blockBuff[32] == 'R' && blockBuff[33] == 'R');

			// if there is additional data in the block, decide whether we want to include include it in the RarBlock we return
			//  we don't return the additional data for file blocks or recovery records.  we do for anything else
			if (blockType != RarBlockType.RarPackedFile && !isRecovery && addlLength > 0)
			{
				byte[] oldbuff = blockBuff;
				blockBuff = new byte[length + addlLength];

				Buffer.BlockCopy(oldbuff, 0 , blockBuff, 0, length);
				rarStream.Read(blockBuff, length, (int)addlLength);
			}
			//  if we're not returning the data, skip over it, but only for RAR mode.  the data isn't there in the SRR, so need need to skip
			else if (mode == RarReadMode.RAR && addlLength > 0)
			{
				rarStream.Seek(addlLength, SeekOrigin.Current);
			}

			switch (blockType)
			{
				case RarBlockType.SrrHeader:
					return new SrrHeaderBlock(blockBuff, blockStartPos);
				case RarBlockType.SrrStoredFile:
					return new SrrStoredFileBlock(blockBuff, blockStartPos);
				case RarBlockType.SrrRarFile:
					return new SrrRarFileBlock(blockBuff, blockStartPos);
				case RarBlockType.RarVolumeHeader:
					return new RarVolumeHeaderBlock(blockBuff, blockStartPos);
				case RarBlockType.RarPackedFile:
					return new RarPackedFileBlock(blockBuff, blockStartPos);
				case RarBlockType.RarOldRecovery:
					return new RarOldRecoveryBlock(blockBuff, blockStartPos);
				case RarBlockType.RarNewSub:
					return isRecovery ? new RarRecoveryBlock(blockBuff, blockStartPos) : new RarBlock(blockBuff, blockStartPos);
				default:
					return new RarBlock(blockBuff, blockStartPos);
			}
		}

		public void Dispose()
		{
			rarStream.Close();
		}
	}
}
