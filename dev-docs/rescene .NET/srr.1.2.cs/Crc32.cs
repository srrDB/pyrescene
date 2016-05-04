using System;

namespace ReScene.Utility
{
	/// <summary>
	/// Implements a CRC32 calculation using standard primitive polynomial 0xedb88320
	/// </summary>
	public static class Crc32
	{
		private const uint primPoly = 0xedb88320u;
		public  const uint StartValue = 0xffffffffu;

		private static uint[] crcTable;
		static Crc32()
		{
			crcTable = new uint[256];

			for (uint i = 0; i < 256; i++)
			{
				uint c = i;
				for (int j = 0; j < 8; j++)
					c = (c & 1) == 1 ? (c >> 1) ^ primPoly : (c >> 1);
				crcTable[i] = c;
			}
		}

		public unsafe static uint GetCrc(uint startCrc, byte[] data, int offset, int length)
		{
			if (length > 0)
			{
				fixed (byte* dptr = &data[offset])
				fixed (uint* cptr = &crcTable[0])
				{
					for (int i = 0; i < length; i++)
						startCrc = cptr[(byte)(startCrc ^ dptr[i])] ^ (startCrc >> 8);
				}
			}

			return startCrc;
		}

		public static uint GetCrc(uint startCrc, byte[] data)
		{
			return GetCrc(startCrc, data, 0, Buffer.ByteLength(data));
		}

		public static uint GetCrc(byte[] data, int offset, int length)
		{
			return GetCrc(StartValue, data, offset, length);
		}

		public static uint GetCrc(byte[] data)
		{
			return GetCrc(StartValue, data, 0, Buffer.ByteLength(data));
		}
	}
}
