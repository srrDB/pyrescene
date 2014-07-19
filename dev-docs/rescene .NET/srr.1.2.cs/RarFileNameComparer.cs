using System;
using System.IO;
using System.Collections.Generic;
using System.Text.RegularExpressions;

namespace ReScene.Utility
{
	public class RarFileNameComparer : IComparer<string>
	{
		private static Regex rarNameExpression = new Regex(@"\.((rar)|([r-v]\d{2})|(\d{3}))$", RegexOptions.IgnoreCase);

		public static bool IsRarFile(string fileName)
		{
			return rarNameExpression.IsMatch(fileName);
		}

		public static int Compare(string fileName1, string fileName2)
		{
			string e1 = Path.GetExtension(fileName1.ToLower());
			string e2 = Path.GetExtension(fileName2.ToLower());

			if (e1 != e2 && e1 == ".rar")
				return -1;
			else if (e1 != e2 && e2 == ".rar")
				return 1;
			else
				return fileName1.CompareTo(fileName2);
		}

		int IComparer<string>.Compare(string fileName1, string fileName2)
		{
			return Compare(fileName1, fileName2);
		}
	}
}
