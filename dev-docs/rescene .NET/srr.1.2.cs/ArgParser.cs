using System;
using System.Collections.Generic;

namespace ReScene.Utility
{
	public static class ArgParser
	{
		public static Dictionary<string, List<string>> GetArgsDictionary(string[] args)
		{
			Dictionary<string, List<string>> dict = new Dictionary<string, List<string>>();
			string cmdSwitch = "infile";
			List<string> switchParams = new List<string>();

			for (int i = 0; i < args.Length; i++)
			{
				if (args[i].StartsWith("-"))
				{
					dict.Add(cmdSwitch, switchParams);

					cmdSwitch = args[i].Substring(1).ToLower();
					switchParams = new List<string>();
				}
				else
				{
					switchParams.Add(args[i]);
				}
			}
			dict.Add(cmdSwitch, switchParams);

			return dict;
		}
	}
}
