using System;
using System.Collections.Generic;
using System.Text;
using System.IO;
using ReScene.Utility;

namespace ReScene
{
	/// <summary>
	/// Implements a read-only Stream that can read a packed file from a RAR archive set.  Only store-mode (m0) RAR sets are supported.
	/// </summary>
	public class RarStream : Stream
	{
		class RarVolume
		{
			public string FilePath { get; set; }
			public long PackedFileOffset { get; set; }
			public long PackedFileRangeStart { get; set; }
			public long PackedFileRangeEnd { get; set; }
			public FileStream FStream { get; set; }
		}

		List<RarVolume> rarVolumes = new List<RarVolume>();
		RarVolume currentVol = null;
		long packedFileLength = 0;
		long currentPos = 0;

		public RarStream(string rarPath)
		{
			bool oldNameFormat = true;
			RarBlock block = null;

			using (RarReader rdr = new RarReader(rarPath, RarReadMode.RAR))
			while ((block = rdr.Read()) != null)
			{
				if (block is RarVolumeHeaderBlock && ((block.Flags & (ushort)RarVolumeHeaderBlock.FlagValues.Volume) != 0))
				{
					oldNameFormat = (block.Flags & (ushort)RarVolumeHeaderBlock.FlagValues.NewNumbering) == 0;
				}
				else if (block is RarPackedFileBlock)
				{
					if ((block.Flags & (ushort)RarPackedFileBlock.FlagValues.SplitBefore) != 0)
						throw new InvalidDataException("You must start with the first volume from a RAR set");

					break;
				}
			}

			// this constructor implementation picks the first packed file encountered in the archive and sets up to read it
			//  an alternate constructor might have a parameter to specify the packed file to read.
			string packedFileName = null;
			string nextFileName = rarPath;
			while (File.Exists(nextFileName))
			{
				using (RarReader rdr = new RarReader(nextFileName, RarReadMode.RAR))
				while ((block = rdr.Read()) != null)
				{
					RarPackedFileBlock fblock = block as RarPackedFileBlock;
					if (fblock != null)
					{
						if (string.IsNullOrEmpty(packedFileName))
							packedFileName = fblock.FileName;

						if (packedFileName == fblock.FileName)
						{
							if (fblock.CompressionMethod != 0x30)
								throw new InvalidDataException("Compressed RARs are not supported");

							currentVol = new RarVolume();
							currentVol.FilePath = nextFileName;
							currentVol.PackedFileRangeStart = packedFileLength;
							currentVol.PackedFileRangeEnd = packedFileLength + (long)fblock.PackedSize - 1;
							currentVol.PackedFileOffset = fblock.BlockPosition + fblock.RawData.LongLength;

							rarVolumes.Add(currentVol);

							packedFileLength += (long)fblock.PackedSize;
						}
					}
				}

				nextFileName = RarFileNameFinder.FindNextFileName(nextFileName, oldNameFormat);
			}

			currentVol = rarVolumes[0];
		}

		public override long Length
		{
			get { return packedFileLength; }
		}

		public override long Position
		{
			get
			{
				return currentPos;
			}
			set
			{
				if (value < 0L)
					throw new ArgumentOutOfRangeException();

				Seek(value, SeekOrigin.Begin);
			}
		}

		public override long Seek(long offset, SeekOrigin origin)
		{
			long destination = 0;

			switch (origin)
			{
				case SeekOrigin.Begin:
					destination = offset;
					break;
				case SeekOrigin.Current:
					destination = currentPos + offset;
					break;
				case SeekOrigin.End:
					destination = packedFileLength - 1 + offset;
					break;
			}

			if (destination < 0L)
				throw new ArgumentOutOfRangeException();

			currentPos = destination;

			if (currentVol == null || currentPos < currentVol.PackedFileRangeStart || currentPos > currentVol.PackedFileRangeEnd)
			{
				currentVol = null;
				foreach (RarVolume vol in rarVolumes)
				{
					if (currentPos >= vol.PackedFileRangeStart && currentPos <= vol.PackedFileRangeEnd)
					{
						currentVol = vol;
						break;
					}
				}
			}

			return currentPos;
		}

		public override int Read(byte[] buffer, int offset, int count)
		{
			if (count < 0 || offset + count > buffer.Length)
				throw new ArgumentOutOfRangeException();

			if (currentVol == null)
				return 0;

			int fileBytesRead = 0;
			int totalBytesRead = 0;
			do
			{
				if (currentVol.FStream == null)
					currentVol.FStream = new FileStream(currentVol.FilePath, FileMode.Open, FileAccess.Read, FileShare.Read);

				currentVol.FStream.Seek(currentVol.PackedFileOffset + (currentPos - currentVol.PackedFileRangeStart), SeekOrigin.Begin);
				fileBytesRead = currentVol.FStream.Read(buffer, offset, Math.Min((int)(currentVol.PackedFileRangeEnd - currentPos) + 1, count));
				Seek(fileBytesRead, SeekOrigin.Current);
				totalBytesRead += fileBytesRead;
				offset += fileBytesRead;
				count -= fileBytesRead;
			} while (fileBytesRead > 0 && count > 0 && currentPos < packedFileLength);

			return totalBytesRead;
		}

		public override bool CanRead
		{
			get { return true; }
		}

		public override bool CanSeek
		{
			get { return true; }
		}

		public override bool CanWrite
		{
			get { return false; }
		}

		public override void Flush()
		{
		}

		public override void SetLength(long value)
		{
			throw new NotSupportedException();
		}

		public override void Write(byte[] buffer, int offset, int count)
		{
			throw new NotSupportedException();
		}

		public override void Close()
		{
			foreach (RarVolume vol in rarVolumes)
			{
				if (vol.FStream != null)
					vol.FStream.Close();
			}

			base.Close();
		}
	}
}
