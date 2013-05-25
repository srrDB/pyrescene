using System;

namespace ReSample.Utility
{
	public static class ByteArrayComparer
	{
		public unsafe static bool AreEqual(byte[] a1, byte[] a2, int a1StartOffset, int a2StartOffset, int compareLength)
		{
			if (compareLength == 0)
				return true;

			if (Buffer.ByteLength(a1) - a1StartOffset < compareLength || Buffer.ByteLength(a2) - a2StartOffset < compareLength)
				return false;

			bool match = true;
			fixed (byte* pa1 = &a1[a1StartOffset], pa2 = &a2[a2StartOffset])
			{
				for (int i = 0; i < compareLength; i++)
				{
					if (pa1[i] != pa2[i])
					{
						match = false;
						break;
					}
				}
			}
			return match;
		}

		public static bool AreEqual(byte[] a1, byte[] a2, int compareLength)
		{
			return AreEqual(a1, a2, 0, 0, compareLength);
		}

		public static bool AreEqual(byte[] a1, byte[] a2)
		{
			if (Buffer.ByteLength(a1) != Buffer.ByteLength(a2))
				return false;

			return AreEqual(a1, a2, 0, 0, Buffer.ByteLength(a1));
		}
	}
}
