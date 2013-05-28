using System;
using System.IO;

namespace ReScene.Utility
{
	public static class RarFileNameFinder
	{
		private static void incrementNumericExtension(char[] ext)
		{
			int i = ext.Length - 1;
			while (++ext[i] == '9' + 1)
			{
				ext[i] = '0';
				i--;
			}
		}

		public static string FindNextFileName(string fileName, bool oldNameFormat)
		{
			if (oldNameFormat) // .rar .r00 ... or .001 .002 ... format
			{
				char[] ext = Path.GetExtension(fileName).ToCharArray();

				// if last 2 chars of extension are not numeric (e.g. .rar), make last 2 chars 00 (e.g. .r00)
				if (!char.IsDigit(ext[2]) && !char.IsDigit(ext[3]))
				{
					ext[2] = '0';
					ext[3] = '0';
				}
				else
				{
					incrementNumericExtension(ext);
				}

				return Path.ChangeExtension(fileName, new string(ext));
			}
			else // part*.rar format
			{
				// remove the .rar at the end and focus on the .part* part
				string partName = Path.ChangeExtension(fileName, null);
				char[] ext = Path.GetExtension(partName).ToCharArray();

				if (ext.Length == 0 || !char.IsDigit(ext[ext.Length - 1]))
				{
					// there is no .part* part, so this was the only rar
					return null;
				}
				else
				{
					incrementNumericExtension(ext);
					return Path.ChangeExtension(partName, new string(ext)) + Path.GetExtension(fileName);
				}
			}
		}
	}
}
