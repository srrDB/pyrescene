using System;
using System.IO;
using System.Text;
using System.Collections.Generic;
using ReScene;
using ReScene.Utility;
using ReSample.Ebml;
using ReSample.Riff;
using ReSample.Utility;

namespace ReSample
{
	class Program
	{
		public const string appName = "MKV/AVI ReSample 1.2";
		public const int sigSize = 256;
		public readonly static char[] spinners = { '|', '/', '-', '\\' };
		private static Dictionary<string, List<string>> argsDict = new Dictionary<string, List<string>>();

		public enum FileType
		{
			MKV,
			AVI,
			Unknown
		}

		public static FileType GetFileType(FileInfo file)
		{
			byte[] markerMKV = new byte[] { 0x1A, 0x45, 0xDF, 0xA3 };
			byte[] markerAVI = new byte[] { 0x52, 0x49, 0x46, 0x46 };
			byte[] markerRAR = new byte[] { 0x52, 0x61, 0x72, 0x21 };
			
			byte[] fileHeader = new byte[4];
			using (FileStream fs = file.OpenRead())
				fs.Read(fileHeader, 0, 4);

			if (ByteArrayComparer.AreEqual(fileHeader, markerRAR))
			{
				using (RarStream rs = new RarStream(file.FullName))
					rs.Read(fileHeader, 0, 4);
			}

			if (ByteArrayComparer.AreEqual(fileHeader, markerMKV))
				return FileType.MKV;
			else if (ByteArrayComparer.AreEqual(fileHeader, markerAVI))
				return FileType.AVI;
			else
				return FileType.Unknown;
		}

		public static void ReportError(string msg)
		{
			ConsoleColor normalColor = Console.ForegroundColor;
			Console.ForegroundColor = ConsoleColor.Red;
			Console.WriteLine(msg);
			Console.ForegroundColor = normalColor;
		}

		static void DisplayUsage()
		{
			Console.WriteLine(appName);
			Console.WriteLine("\nUsage:  srs <input file> [<input file>] [switches]");
			Console.WriteLine("\tTo create a ReSample file (SRS), pass in the sample MKV or AVI file.\n\t\tex: srs sample.mkv -dd");
			Console.WriteLine("\tTo recreate a sample, pass in the SRS file and the full MKV or AVI\n\t  or the first file of a RAR set containing the MKV or AVI.\n\t\tex: srs sample.srs full.mkv\n\t\tor: srs sample.srs full.rar");
			Console.WriteLine("\nAvailable switches:");
			Console.WriteLine("\t-b: Big file.  Enables support for 'samples' over 2GB.");
			Console.WriteLine("\t-i: Display sample info only.  Does not create .srs file.");
			Console.WriteLine("\t-l: List SRS info only (use only with .srs input file).");
			Console.WriteLine("\t-d: Use sample directory name as basis for generated .srs file name.");
			Console.WriteLine("\t-dd: Use parent directory name as basis for generated .srs file name.");
			Console.WriteLine("\t-ddd: Same as above, but puts the .srs file in the parent directory.");
			Console.WriteLine("\t-o <path>: Specify output file or directory path for .srs file.\n\t    If path is a directory, the -d and -dd flags will work as normal.");
			Console.WriteLine("\t-c <file>: Check sample against given full MKV or AVI file to make sure\n\t    all tracks can be located before saving the .srs file.");
			//Console.WriteLine("\t-k: Keep attachments.");
		}

		static bool CheckOverwrite(string filePath)
		{
			if (File.Exists(filePath))
			{
				Console.WriteLine("Warning: File {0} already exists.  Do you wish to continue? (Y/N)", filePath);
				char res = Console.ReadKey(true).KeyChar;
				if (res != 'y' && res != 'Y')
					return false;
			}

			return true;
		}

		static int Main(string[] args)
		{
			try
			{
				DirectoryInfo workingDir = new DirectoryInfo(".");
				if (workingDir.Parent != null)
					workingDir = workingDir.Parent.GetDirectories(workingDir.Name)[0]; // fix workingDir case

				argsDict = ArgParser.GetArgsDictionary(args);

				List<string> files = new List<string>();
				if (argsDict.ContainsKey("infile"))
					files.AddRange(argsDict["infile"]);
				if (argsDict.ContainsKey("c"))
					files.AddRange(argsDict["c"]);
				foreach (string inFileName in files)
				{
					FileInfo inInfo = new FileInfo(inFileName);
					if (!inInfo.Exists || GetFileType(inInfo) == FileType.Unknown)
					{
						if (!inInfo.Exists)
							ReportError(string.Format("Input file not found: {0}\n", inFileName));
						else
							ReportError(string.Format("Could not locate MKV or AVI data in file: {0}\n", inFileName));
						DisplayUsage();
						return 1;
					}
				}

				DateTime start = DateTime.Now;
				SortedList<int, TrackData> tracks = new SortedList<int, TrackData>();
				Dictionary<string, AttachmentData> attachments = new Dictionary<string, AttachmentData>();

				if (argsDict["infile"].Count == 1 && !argsDict["infile"][0].ToLower().EndsWith(".srs"))
				{
					FileInfo sampleInfo = new FileInfo(argsDict["infile"][0]);
					FileType sampleType = GetFileType(sampleInfo);
					bool bigFile = argsDict.ContainsKey("b");

					if (sampleInfo.Length >= 0x80000000 && !bigFile)
					{
						ReportError("Samples over 2GB are not supported without the -b switch.  Are you sure it's a sample?");
						return 1;
					}

					DirectoryInfo outFolder = workingDir;
					string srsName = null;
					if (argsDict.ContainsKey("o") && argsDict["o"].Count == 1)
						if (Path.GetExtension(argsDict["o"][0]).ToLower() == ".srs")
							srsName = argsDict["o"][0];
						else
							outFolder = new DirectoryInfo(argsDict["o"][0]);
					else if (argsDict.ContainsKey("ddd"))
						outFolder = sampleInfo.Directory.Parent;

					if (srsName == null)
					{
						if (argsDict.ContainsKey("d"))
							srsName = Path.Combine(outFolder.FullName, sampleInfo.Directory.Name + ".srs");
						else if (argsDict.ContainsKey("dd") || argsDict.ContainsKey("ddd") && sampleInfo.Directory.Parent != null)
							srsName = Path.Combine(outFolder.FullName, sampleInfo.Directory.Parent.Name + ".srs");
						else
							srsName = Path.Combine(outFolder.FullName, Path.ChangeExtension(sampleInfo.Name, ".srs"));
					}

					if (!outFolder.Exists)
					{
						ReportError(string.Format("Output directory does not exist: {0}", outFolder.FullName));
						return 1;
					}
					if (Path.GetDirectoryName(srsName).Length > 0 && !Directory.Exists(Path.GetDirectoryName(srsName)))
					{
						ReportError(string.Format("Output directory does not exist: {0}", Path.GetDirectoryName(srsName)));
						return 1;
					}

					FileData file = new FileData(sampleInfo.FullName);

					if (sampleType == FileType.MKV)
					{
						if (MkvReSample.ProfileSample(file, tracks, attachments) != 0)
							return 2;
					}
					else
					{
						if (AviReSample.ProfileSample(file, tracks) != 0)
							return 2;
					}

					if (tracks.Count == 0)
					{
						ReportError("No A/V data was found.  The sample is likely corrupted.");
						return 2;
					}

					// check for info only mode
					if (argsDict.ContainsKey("i"))
						return 0;

					if (argsDict.ContainsKey("c") && argsDict["c"].Count == 1)
					{
						Console.WriteLine("Checking that sample exists in the specified full file...");

						FileInfo movieInfo = new FileInfo(argsDict["c"][0]);
						FileType moviType = GetFileType(movieInfo);
						FileData srsData = new FileData();

						if (moviType == FileType.MKV)
							MkvReSample.FindSampleStreams(tracks, movieInfo);
						else
							AviReSample.FindSampleStreams(tracks, movieInfo);

						for (int i = tracks.Count; i > 0; i--)
						{
							if (tracks.Values[i - 1].SignatureBytes != null && tracks.Values[i - 1].MatchOffset == 0)
							{
								ReportError(string.Format("\nUnable to locate track signature for track {0}.  Aborting.", tracks.Values[i - 1].TrackNumber));
								return 3;
							}
							else if (tracks.Values[i - 1].SignatureBytes == null)
							{
								tracks.RemoveAt(i - 1);
							}
						}

						Console.WriteLine("Check Complete.  All tracks located.");
					}

					if (!CheckOverwrite(srsName))
					{
						Program.ReportError("\nOperation aborted");
						return 0;
					}

					if (sampleType == FileType.MKV)
						MkvReSample.CreateSRS(tracks, file, sampleInfo, new FileInfo(srsName), bigFile);
					else
						AviReSample.CreateSRS(tracks, file, sampleInfo, new FileInfo(srsName), bigFile);

					Console.WriteLine("Successfully created SRS file: {0}", srsName);
				}
				else if (argsDict["infile"].Count == 1 && argsDict["infile"][0].ToLower().EndsWith(".srs") && argsDict.ContainsKey("l"))
				{
					FileInfo srsInfo = new FileInfo(argsDict["infile"][0]);
					FileType srsType = GetFileType(srsInfo);
					FileData srsData = new FileData();

					if (srsType == FileType.MKV)
						MkvReSample.LoadSRS(tracks, ref srsData, srsInfo);
					else
						AviReSample.LoadSRS(tracks, ref srsData, srsInfo);

					Console.WriteLine("SRS Type   : {0}", srsType);
					Console.WriteLine("SRS App    : {0}", srsData.AppName);
					Console.WriteLine("Sample Name: {0}", srsData.Name);
					Console.WriteLine("Sample Size: {0:n0}", srsData.Size);
					Console.WriteLine("Sample CRC : {0:X8}", srsData.Crc32);
				}
				else if (argsDict["infile"].Count == 2 && argsDict["infile"][0].ToLower().EndsWith(".srs"))
				{
					FileInfo srsInfo = new FileInfo(argsDict["infile"][0]);
					FileInfo movieInfo = new FileInfo(argsDict["infile"][1]);
					FileType srsType = GetFileType(srsInfo);
					FileType moviType = GetFileType(movieInfo);
					FileData srsData = new FileData();

					DirectoryInfo outFolder = workingDir;
					if (argsDict.ContainsKey("o") && argsDict["o"].Count == 1)
						outFolder = new DirectoryInfo(argsDict["o"][0]);

					if (!outFolder.Exists)
						outFolder.Create();

					if (srsType == FileType.MKV)
						MkvReSample.LoadSRS(tracks, ref srsData, srsInfo);
					else
						AviReSample.LoadSRS(tracks, ref srsData, srsInfo);

					Console.WriteLine("SRS Load Complete...          Elapsed Time: {0:f2}s", (DateTime.Now - start).TotalMilliseconds / 1000);

					bool skipLocation = true;
					foreach (TrackData track in tracks.Values)
					{
						if (track.MatchOffset == 0)
						{
							skipLocation = false;
							break;
						}
					}

					if (!skipLocation)
					{
						if (moviType == FileType.MKV)
							MkvReSample.FindSampleStreams(tracks, movieInfo);
						else
							AviReSample.FindSampleStreams(tracks, movieInfo);

						Console.WriteLine("Track Location Complete...    Elapsed Time: {0:f2}s", (DateTime.Now - start).TotalMilliseconds / 1000);

						foreach (TrackData track in tracks.Values)
						{
							//Console.WriteLine("{0} {1} {2}", track.TrackNumber, track.DataLength, track.MatchOffset);
							if (track.SignatureBytes != null && track.MatchOffset == 0)
							{
								ReportError(string.Format("\nUnable to locate track signature for track {0}.  Aborting.", track.TrackNumber));
								return 3;
							}
						}
					}

					if (moviType == FileType.MKV)
						MkvReSample.ExtractSampleStreams(tracks, attachments, srsData, movieInfo, outFolder);
					else
						AviReSample.ExtractSampleStreams(tracks, srsData, movieInfo, outFolder);

					Console.WriteLine("Track Extraction Complete...  Elapsed Time: {0:f2}s", (DateTime.Now - start).TotalMilliseconds / 1000);

					foreach (TrackData track in tracks.Values)
					{
						track.TrackFile.Position = 0;
						if (track.SignatureBytes != null && (track.TrackFile == null || track.TrackFile.Length < track.DataLength))
						{
							ReportError(string.Format("\nUnable to extract correct amount of data for track {0}.  Aborting.", track.TrackNumber));
							return 4;
						}
					}

					if (!CheckOverwrite(Path.Combine(outFolder.FullName, srsData.Name)))
					{
						ReportError("\nOperation aborted");
						return 0;
					}

					FileData file = null;
					if (srsType == FileType.MKV)
						file = MkvReSample.RebuildSample(srsData, tracks, attachments, srsInfo, outFolder);
					else
						file = AviReSample.RebuildSample(srsData, tracks, srsInfo, outFolder);

					Console.WriteLine("Rebuild Complete...           Elapsed Time: {0:f2}s", (DateTime.Now - start).TotalMilliseconds / 1000);

					foreach (TrackData track in tracks.Values)
						track.TrackFile.Close();
					foreach (AttachmentData attachment in attachments.Values)
						attachment.AttachmentFile.Close();

					//Console.WriteLine("Verify Complete...            Elapsed Time: {0:f2}s", (DateTime.Now - start).TotalMilliseconds / 1000);

					Console.WriteLine("\nFile Details:   Size           CRC");
					Console.WriteLine("                -------------  --------");
					Console.WriteLine("Expected    :   {0,13:n0}  {1:X8}", srsData.Size, srsData.Crc32);
					Console.WriteLine("Actual      :   {0,13:n0}  {1:X8}\n", file.Size, file.Crc32);

					if (file.Crc32 == srsData.Crc32)
						Console.WriteLine("\nSuccessfully rebuilt sample: {0}", srsData.Name);
					else
					{
						ReportError(string.Format("\nRebuild failed for sample: {0}", srsData.Name));
						return 5;
					}
				}
				else
				{
					DisplayUsage();
				}

				return 0;
			}
			catch (InvalidDataException ex)
			{
				ReportError(string.Format("Corruption detected: {0}.  Aborting.", ex.Message));
				return 2;
			}
			catch (Exception ex)
			{
				ReportError(string.Format("Unexpected Error:\n{0}", ex.ToString()));
				return 99;
			}
		}
	}
}
