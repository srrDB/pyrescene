using System;
using System.IO;
using System.Diagnostics;
using ReSample.Utility;

namespace ReSample.Ebml
{
	public enum EbmlReadMode
	{
		MKV,
		Sample,
		SRS
	}

	public enum EbmlElementType
	{
		Ebml,
		Segment,
		TimecodeScale,
		Cluster,
		Timecode,
		BlockGroup,
		Block,
		AttachmentList,
		Attachment,
		AttachedFileName,
		AttachedFileData,
		ReSample,
		ReSampleFile,
		ReSampleTrack,
		Crc32,
		Unknown
	}

	public enum EbmlLaceType
	{
		None = 0,
		Xiph = 2,
		Fixed = 4,
		Ebml = 6
	}

	public class EbmlElement
	{
		public byte[] RawHeader { get; set; }
		public long ElementStartPos { get; set; }
		public long Length { get; set; }
	}

	public class BlockElement : EbmlElement
	{
		public int TrackNumber { get; set; }
		public int Timecode { get; set; }
		public int[] FrameLengths { get; set; }
		public byte[] RawBlockHeader { get; set; }
	}

	/// <summary>
	/// Implements a simple Reader class that reads through MKV or MKV-SRS files one element at a time.
	/// </summary>
	public class EbmlReader : IDisposable
	{
		private byte[] elementHeader = new byte[12];
		private long fileLength = 0;

		protected Stream ebmlStream;
		protected EbmlReadMode mode;
		protected bool readReady = true;

		protected EbmlElement currentElement;

		public EbmlElementType ElementType { get; protected set; }

		public Stream BaseStream
		{
			get { return ebmlStream; }
		}
		public EbmlElement Element
		{
			get { return currentElement; }
		}
		public BlockElement Block
		{
			get { return currentElement as BlockElement; }
		}


		public EbmlReader(string ebmlPath, EbmlReadMode readMode)
		{
			this.ebmlStream = new FileStream(ebmlPath, FileMode.Open, FileAccess.Read, FileShare.Read);
			fileLength = ebmlStream.Length;
			this.mode = readMode;
		}

		public EbmlReader(Stream riffStream, EbmlReadMode readMode)
		{
			this.ebmlStream = riffStream;
			fileLength = riffStream.Length;
			this.mode = readMode;
		}

		public bool Read()
		{
			Debug.Assert(readReady || (mode == EbmlReadMode.SRS && ElementType == EbmlElementType.Block), "Read() is invalid at this time", "MoveToChild(), ReadContents(), or SkipContents() must be called before Read() can be called again");

			long elementStartPos = ebmlStream.Position;
			byte idLengthDescriptor = 0;
			byte dataLengthDescriptor = 0;

			if (elementStartPos + 2 > fileLength)
				return false;

			currentElement = null;
			readReady = false;

			idLengthDescriptor = (byte)ebmlStream.ReadByte();
			elementHeader[0] = idLengthDescriptor;
			idLengthDescriptor = EbmlHelper.GetUIntLength(idLengthDescriptor);
			ebmlStream.Read(elementHeader, 1, idLengthDescriptor - 1);
			dataLengthDescriptor = (byte)ebmlStream.ReadByte();
			elementHeader[idLengthDescriptor] = dataLengthDescriptor;
			dataLengthDescriptor = EbmlHelper.GetUIntLength(dataLengthDescriptor);
			ebmlStream.Read(elementHeader, idLengthDescriptor + 1, dataLengthDescriptor - 1);

			// these comparisons are ordered by the frequency with which they will be encountered to avoid unnecessary processing
			if (ByteArrayComparer.AreEqual(elementHeader, EbmlElementIDs.Block, idLengthDescriptor) || ByteArrayComparer.AreEqual(elementHeader, EbmlElementIDs.SimpleBlock, idLengthDescriptor))
				ElementType = EbmlElementType.Block;
			else if (ByteArrayComparer.AreEqual(elementHeader, EbmlElementIDs.BlockGroup, idLengthDescriptor))
				ElementType = EbmlElementType.BlockGroup;
			else if (ByteArrayComparer.AreEqual(elementHeader, EbmlElementIDs.Cluster, idLengthDescriptor))
				ElementType = EbmlElementType.Cluster;
			else if (ByteArrayComparer.AreEqual(elementHeader, EbmlElementIDs.Timecode, idLengthDescriptor))
				ElementType = EbmlElementType.Timecode;
			else if (ByteArrayComparer.AreEqual(elementHeader, EbmlElementIDs.Segment, idLengthDescriptor))
				ElementType = EbmlElementType.Segment;
			else if (ByteArrayComparer.AreEqual(elementHeader, EbmlElementIDs.TimecodeScale, idLengthDescriptor))
				ElementType = EbmlElementType.TimecodeScale;
			else if (ByteArrayComparer.AreEqual(elementHeader, EbmlElementIDs.Crc32, idLengthDescriptor))
				ElementType = EbmlElementType.Crc32;
			else if (ByteArrayComparer.AreEqual(elementHeader, EbmlElementIDs.AttachmentList, idLengthDescriptor))
				ElementType = EbmlElementType.AttachmentList;
			else if (ByteArrayComparer.AreEqual(elementHeader, EbmlElementIDs.Attachment, idLengthDescriptor))
				ElementType = EbmlElementType.Attachment;
			else if (ByteArrayComparer.AreEqual(elementHeader, EbmlElementIDs.AttachedFileName, idLengthDescriptor))
				ElementType = EbmlElementType.AttachedFileName;
			else if (ByteArrayComparer.AreEqual(elementHeader, EbmlElementIDs.AttachedFileData, idLengthDescriptor))
				ElementType = EbmlElementType.AttachedFileData;
			else if (mode == EbmlReadMode.SRS && ByteArrayComparer.AreEqual(elementHeader, EbmlElementIDs.ReSample, idLengthDescriptor))
				ElementType = EbmlElementType.ReSample;
			else if (mode == EbmlReadMode.SRS && ByteArrayComparer.AreEqual(elementHeader, EbmlElementIDs.ReSampleFile, idLengthDescriptor))
				ElementType = EbmlElementType.ReSampleFile;
			else if (mode == EbmlReadMode.SRS && ByteArrayComparer.AreEqual(elementHeader, EbmlElementIDs.ReSampleTrack, idLengthDescriptor))
				ElementType = EbmlElementType.ReSampleTrack;
			else
				ElementType = EbmlElementType.Unknown;

			long elementLength = EbmlHelper.GetEbmlUInt(elementHeader, idLengthDescriptor, dataLengthDescriptor);

			// sanity check on element length.  skip check on Segment element so we can still report expected size.  this is only applied on samples since a partial movie might still be useful
			long endOffset = elementStartPos + idLengthDescriptor + dataLengthDescriptor + elementLength;
			if (mode == EbmlReadMode.Sample && ElementType != EbmlElementType.Segment && endOffset > fileLength)
				throw new InvalidDataException(string.Format("Invalid element length at 0x{0:x8}", elementStartPos));

			if (ElementType != EbmlElementType.Block)
			{
				byte[] rawHeader = new byte[idLengthDescriptor + dataLengthDescriptor];
				Buffer.BlockCopy(elementHeader, 0, rawHeader, 0, idLengthDescriptor + dataLengthDescriptor);
				currentElement = new EbmlElement() { ElementStartPos = elementStartPos, RawHeader = rawHeader, Length = elementLength };
			}
			else
			{
				// first thing in the block is the track number
				byte trackDescriptor = (byte)ebmlStream.ReadByte();
				byte[] blockHeader = new byte[4];
				blockHeader[0] = trackDescriptor;
				trackDescriptor = EbmlHelper.GetUIntLength(trackDescriptor);

				// incredibly unlikely the track number is > 1 byte, but just to be safe...
				if (trackDescriptor > 1)
				{
					byte[] newBlockHeader = new byte[trackDescriptor + 3];
					newBlockHeader[0] = blockHeader[0];
					ebmlStream.Read(newBlockHeader, 1, trackDescriptor - 1);
					blockHeader = newBlockHeader;
				}

				int trackno = (int)EbmlHelper.GetEbmlUInt(blockHeader, 0, trackDescriptor);

				// read in time code (2 bytes) and flags (1 byte)
				ebmlStream.Read(blockHeader, trackDescriptor, 3);
				short timecode = (short)((blockHeader[blockHeader.Length - 3] << 8) + blockHeader[blockHeader.Length - 2]);

				// need to grab the flags (last byte of the header) to check for lacing
				EbmlLaceType laceType = (EbmlLaceType)(blockHeader[blockHeader.Length - 1] & (byte)EbmlLaceType.Ebml);

				int dataLength = (int)elementLength - blockHeader.Length;
				int bytesConsumed;
				int[] frameSizes = EbmlHelper.GetBlockFrameLengths(laceType, dataLength, ebmlStream, out bytesConsumed);
				if (bytesConsumed > 0)
				{
					byte[] newBlockHeader = new byte[blockHeader.Length + bytesConsumed];
					Buffer.BlockCopy(blockHeader, 0, newBlockHeader, 0, blockHeader.Length);
					ebmlStream.Seek(-bytesConsumed, SeekOrigin.Current);
					ebmlStream.Read(newBlockHeader, blockHeader.Length, bytesConsumed);
					blockHeader = newBlockHeader;
				}

				elementLength -= blockHeader.Length;

				byte[] rawHeader = new byte[idLengthDescriptor + dataLengthDescriptor];
				Buffer.BlockCopy(elementHeader, 0, rawHeader, 0, idLengthDescriptor + dataLengthDescriptor);
				currentElement = new BlockElement() { ElementStartPos = elementStartPos, RawHeader = rawHeader, Length = elementLength, FrameLengths = frameSizes, TrackNumber = trackno, Timecode = timecode, RawBlockHeader = blockHeader };
			}

			// the following line will write mkvinfo-like output from the parser (extremely useful for debugging)
			//Console.WriteLine("{0}: {1} bytes @ {2}", ElementType, elementLength, elementStartPos);

			return true;
		}

		public byte[] ReadContents()
		{
			// if readReady is set, we've already read or skipped it.  back up and read again?
			if (readReady)
				ebmlStream.Seek(-currentElement.Length, SeekOrigin.Current);

			readReady = true;
			byte[] buff = null;

			if (mode != EbmlReadMode.SRS || ElementType != EbmlElementType.Block)
			{
				buff = new byte[currentElement.Length];
				ebmlStream.Read(buff, 0, buff.Length);
			}

			return buff;
		}

		public void SkipContents()
		{
			if (!readReady)
			{
				readReady = true;

				if (mode != EbmlReadMode.SRS || ElementType != EbmlElementType.Block)
					ebmlStream.Seek(currentElement.Length, SeekOrigin.Current);
			}
		}

		public void MoveToChild()
		{
			//Debug.Assert(ElementType == RiffChunkType.List, "MoveToChild() should only be called on a RIFF List");

			readReady = true;
		}

		public void Dispose()
		{
			ebmlStream.Close();
		}
	}

	public static class EbmlElementIDs
	{
		public static readonly byte[] Ebml = new byte[] { 0x1A, 0x45, 0xDF, 0xA3 };
		public static readonly byte[] Segment = new byte[] { 0x18, 0x53, 0x80, 0x67 };
		public static readonly byte[] TimecodeScale = new byte[] { 0x2A, 0xD7, 0xB1 };

		public static readonly byte[] Cluster = new byte[] { 0x1F, 0x43, 0xB6, 0x75 };
		public static readonly byte[] Timecode = new byte[] { 0xE7 };
		public static readonly byte[] BlockGroup = new byte[] { 0xA0 };
		public static readonly byte[] Block = new byte[] { 0xA1 };
		public static readonly byte[] SimpleBlock = new byte[] { 0xA3 };

		public static readonly byte[] AttachmentList = new byte[] { 0x19, 0x41, 0xA4, 0x69 };
		public static readonly byte[] Attachment = new byte[] { 0x61, 0xA7 };
		public static readonly byte[] AttachedFileName = new byte[] { 0x46, 0x6E };
		public static readonly byte[] AttachedFileData = new byte[] { 0x46, 0x5C };

		public static readonly byte[] ReSample = new byte[] { 0x1F, 0x69, 0x75, 0x76 };
		public static readonly byte[] ReSampleFile = new byte[] { 0x6A, 0x75 };
		public static readonly byte[] ReSampleTrack = new byte[] { 0x6B, 0x75 };

		public static readonly byte[] Crc32 = new byte[] { 0xBF };
	}

	public static class EbmlHelper
	{
		public static byte GetUIntLength(byte lengthDescriptor)
		{
			int length = 0;
			for (int i = 0; i < 8; i++)
				if ((lengthDescriptor & (0x80 >> i)) != 0)
				{
					length = i + 1;
					break;
				}

			return (byte)length;
		}

		public static byte[] GetEbmlElementID(Stream stm)
		{
			byte firstByte = (byte)stm.ReadByte();
			int length = GetUIntLength(firstByte);

			byte[] elementID = new byte[length];
			elementID[0] = firstByte;
			stm.Read(elementID, 1, length - 1);

			return elementID;
		}

		public unsafe static long GetEbmlUInt(byte[] buff, int offset, int count)
		{
			long value = buff[offset] & (0xFF >> count);
			fixed (byte* ptr = &buff[offset])
			{
				for (int i = 1; i < count; i++)
					value = (value << 8) + ptr[i];
			}

			return value;
		}

		public static long GetEbmlUInt(Stream stm, out int bytesConsumed)
		{
			byte firstByte = (byte)stm.ReadByte();
			int length = GetUIntLength(firstByte);

			long dataSize = firstByte & (0xFF >> length);
			for (int i = 1; i < length; i++)
				dataSize = (dataSize << 8) + (byte)stm.ReadByte();

			bytesConsumed = length;

			return dataSize;
		}

		public static byte[] MakeEbmlUInt(long n)
		{
			int lengthDescriptor = 0;
			long lengthMask = 0;

			for (int i = 1; i < 8; i++)
			{
				lengthMask = 1L << (i * 8 - i);
				if (n < lengthMask)
				{
					lengthDescriptor = i;
					n |= lengthMask;
					break;
				}
			}

			byte[] data = new byte[lengthDescriptor];
			for (int i = 0; i < lengthDescriptor; i++)
				data[i] = (byte)((n >> ((lengthDescriptor - (i + 1)) * 8)) & 0xFF);

			return data;
		}

		public static int[] GetBlockFrameLengths(EbmlLaceType laceType, int dataLength, Stream stm, out int bytesConsumed)
		{
			// Matroska uses 'lacing' to store more than one frame of data in a single block, thereby saving the overhead of a full block per frame
			//  this method determines the length of each frame so they can be re-separated and searched.  See the Matroska specs for details...
			bytesConsumed = 0;
			int laceFrameCount = 1;
			if (laceType != EbmlLaceType.None)
			{
				laceFrameCount = stm.ReadByte() + 1;
				bytesConsumed++;
			}

			int[] frameSizes = new int[laceFrameCount];
			for (int i = 0; i < laceFrameCount; i++)
			{
				if (laceType == EbmlLaceType.None)
					frameSizes[i] = dataLength;
				else if (laceType == EbmlLaceType.Fixed)
					frameSizes[i] = dataLength / laceFrameCount;
				else if (laceType == EbmlLaceType.Xiph)
				{
					if (i < laceFrameCount - 1)
					{
						int nextByte;
						do
						{
							nextByte = stm.ReadByte();
							bytesConsumed++;
							frameSizes[i] += nextByte;
						} while (nextByte == 0xFF);
					}
					else
					{
						frameSizes[i] = dataLength - bytesConsumed;
						for (int j = 0; j < i; j++)
							frameSizes[i] -= frameSizes[j];
					}
				}
				else // EbmlLaceType.Ebml
				{
					int bc = 0;

					if (i == 0)
					{
						frameSizes[i] = (int)GetEbmlUInt(stm, out bc);
					}
					else if (i < laceFrameCount - 1)
					{
						// convert UInt to SInt then add to previous
						int len = (int)GetEbmlUInt(stm, out bc);
						len -= ((1 << (bc * 8 - (bc + 1))) - 1);
						frameSizes[i] = frameSizes[i - 1] + len;
					}
					else
					{
						frameSizes[i] = dataLength - bytesConsumed;
						for (int j = 0; j < i; j++)
							frameSizes[i] -= frameSizes[j];
					}

					bytesConsumed += bc;
				}
			}

			return frameSizes;
		}
	}
}
