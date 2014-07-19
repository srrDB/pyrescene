using System;
using System.Collections.Generic;
using System.Text;
using System.IO;
using System.Text.RegularExpressions;
using System.Globalization;

namespace ReScene
{
	public class SfvEntry
	{
		public string FileName { get; set; }
		public uint Crc32 { get; set; }
	}

	/// <summary>
	/// Implements a simple Reader class that reads through SFV files one line (entry) at a time.
	/// </summary>
	public class SfvReader : IDisposable
	{
		protected StreamReader reader;

		public SfvReader(string sfvPath)
		{
			reader = new StreamReader(sfvPath, Encoding.ASCII);
		}

		public SfvReader(Stream sfvStream)
		{
			reader = new StreamReader(sfvStream, Encoding.ASCII);
		}

		public SfvEntry Read()
		{
			// comment lines in sfv start with ';', so skip those.  also skip any lines that are too short to have both a file name and CRC
			string line;
			do
				line = reader.ReadLine();
			while (line != null && (line.Trim().Length < 10 || line.StartsWith(";")));

			if (line == null)
				return null;

			uint i;
			if (uint.TryParse(line.Substring(line.Length - 8), NumberStyles.HexNumber, null, out i))
				return new SfvEntry()
				{
					FileName = line.Substring(0, line.Length - 9).Trim(),
					Crc32 = i
				};
			else
				return null;
		}

		public void Dispose()
		{
			reader.Close();
		}
	}
}
