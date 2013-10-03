using System;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;
using System.Collections.Generic;
using ReScene.Utility;

namespace ReScene
{
	class Program
	{
		private const string appName = "ReScene .NET 1.2";
		private static bool verbose = false;
		private static bool assumeYes = false;

		static void ReportError(string msg)
		{
			ConsoleColor normalColor = Console.ForegroundColor;
			Console.ForegroundColor = ConsoleColor.Red;
			Console.WriteLine(msg);
			Console.ForegroundColor = normalColor;
		}

		static void DisplayUsage()
		{
			Console.WriteLine(appName);
			Console.WriteLine("\nUsage:  srr <input file list> [switches]");
			Console.WriteLine("\tTo create a reconstruction file (SRR), use the release SFV or RAR file.\n\tAll files referenced by the SFV must be in the same folder as the SFV.\n\t\tex: srr example.sfv -s *.nfo -d");
			Console.WriteLine("\tTo reconstruct a release, use the SRR file created from the release.\n\t\tex: srr example.srr");
			Console.WriteLine("\nAvailable switches:");
			Console.WriteLine("\t-l: List SRR file contents only.");
			Console.WriteLine("\t-x: Extract SRR stored files only.");
			Console.WriteLine("\t-d: Use parent directory name as basis for generated .srr file name.");
			Console.WriteLine("\t-p: Store file names with paths (relative to the input base directory)");
			Console.WriteLine("\t-r: Attempt to auto-locate renamed files (must have same extension)");
			Console.WriteLine("\t-u: Disable automatic CRC checking during reconstruction.");
			Console.WriteLine("\t-y: Assume Y(es) for all prompts.");
			Console.WriteLine("\t-v: Enable verbose (technical) output.");
			Console.WriteLine("\t-s <file list>: Store additional files in the SRR (wildcards supported)");
			Console.WriteLine("\t-i <path>: Specify input base directory.");
			Console.WriteLine("\t-o <path>: Specify output file or directory path.");
			Console.WriteLine("\t-h <oldname:newname list>: Specify alternate names for extracted files.\n\t\tex: srr example.srr -h orginal.mkv:renamed.mkv");
		}

		static void ReportUnsupportedFlag()
		{
			ReportError("Warning: Unsupported flag value encountered in SRR file.  This file may use features not supported in this version of the application");
		}

		static bool CheckOverwrite(string filePath)
		{
			if (!assumeYes && File.Exists(filePath))
			{
				Console.WriteLine("Warning: File {0} already exists.  Do you wish to continue? (Y/N)", filePath);
				char res;
				do
					res = Console.ReadKey(true).KeyChar;
				while (res != 'y' && res != 'Y' && res != 'n' && res != 'N');
				if (res != 'y' && res != 'Y')
					return false;
			}

			return true;
		}

		static string FixPathCase(string path)
		{
			if (!File.Exists(path) && !Directory.Exists(path))
				return path;
			
			DirectoryInfo di = new DirectoryInfo(path);
			if (di.Parent != null)
				return Path.Combine(FixPathCase(di.Parent.FullName), di.Parent.GetFileSystemInfos(di.Name)[0].Name);
			else
				return di.Name.ToUpper();
		}

		static string MakePathRelative(string path, string basePath)
		{
			if (!basePath.EndsWith(Path.DirectorySeparatorChar.ToString()))
				basePath += Path.DirectorySeparatorChar;

			path = FixPathCase(path);
			if (path.StartsWith(basePath, StringComparison.OrdinalIgnoreCase))
				return path.Substring(basePath.Length).Replace(Path.DirectorySeparatorChar, '/');
			else
				return path.Substring(path.LastIndexOf(Path.DirectorySeparatorChar) + 1);
		}

		static int CreateReconstructionFile(List<FileInfo> inFiles, DirectoryInfo inFolder, List<string> storeFiles, string srrName, bool savePaths)
		{
			using (FileStream srrfs = new FileStream(srrName, FileMode.Create))
			{
				BinaryWriter bw = new BinaryWriter(srrfs, Encoding.ASCII);
				bw.Write(new SrrHeaderBlock(appName).RawData);

				// we store copies of any files included in the storeFiles list in the .srr using a "store block".  any SFV files used are also included.
				foreach (FileInfo fi in inFiles)
					if (fi.Extension.ToLower() == ".sfv")
						storeFiles.Add(fi.FullName);

				SrrStoredFileBlock storeBlock = null;
				foreach (string fileName in storeFiles)
				{
					string searchName = fileName;
					if (!Path.IsPathRooted(searchName))
						searchName = Path.Combine(inFolder.FullName, fileName);

					DirectoryInfo searchDir = new DirectoryInfo(Path.GetDirectoryName(searchName));
					if (searchDir.Exists)
					foreach (FileInfo storeFile in searchDir.GetFiles(Path.GetFileName(searchName)))
					{
						string fName = savePaths ? MakePathRelative(storeFile.FullName, inFolder.FullName) : storeFile.Name;
						Console.WriteLine("Storing file: {0}", fName);
						storeBlock = new SrrStoredFileBlock(fName, (int)storeFile.Length);
						if (savePaths)
							storeBlock.Flags |= (ushort)SrrStoredFileBlock.FlagValues.PathsSaved;
						using (FileStream storefs = storeFile.OpenRead())
							storefs.Read(storeBlock.RawData, storeBlock.FileOffset, (int)storeFile.Length);

						bw.Write(storeBlock.RawData);
					}
				}

				List<string> rarFiles = new List<string>();
				foreach (FileInfo inFile in inFiles)
				{
					if (inFile.Extension.ToLower() == ".sfv")
					{
						using (SfvReader sfvReader = new SfvReader(inFile.FullName))
						{
							List<string> sfvRarFiles = new List<string>();
							SfvEntry sfvEntry;
							while ((sfvEntry = sfvReader.Read()) != null)
							{
								if (RarFileNameComparer.IsRarFile(sfvEntry.FileName))
								{
									sfvRarFiles.Add(Path.Combine(inFile.DirectoryName, sfvEntry.FileName));
								}
								else
								{
									ReportError(string.Format("Warning: Non-RAR file referenced in SFV: {0}\n\tThis file cannot be recreated unless it is stored using -s", sfvEntry.FileName));
									continue;
								}
							}

							sfvRarFiles.Sort(new RarFileNameComparer());
							rarFiles.AddRange(sfvRarFiles);
						}
					}
					else
					{
						bool oldNameFormat = false;
						RarBlock block = null;
						using (RarReader rdr = new RarReader(inFile.FullName, RarReadMode.RAR))
						while ((block = rdr.Read()) != null)
						{
							if (block is RarVolumeHeaderBlock && ((block.Flags & (ushort)RarVolumeHeaderBlock.FlagValues.Volume) != 0))
							{
								if ((block.Flags & (ushort)RarVolumeHeaderBlock.FlagValues.FirstVolume) == 0)
									throw new InvalidDataException("You must start with the first volume from a RAR set");

								oldNameFormat = (block.Flags & (ushort)RarVolumeHeaderBlock.FlagValues.NewNumbering) == 0;
							}
						}

						string nextFileName = inFile.FullName;
						while (File.Exists(nextFileName))
						{
							rarFiles.Add(Path.Combine(inFile.DirectoryName, nextFileName));
							nextFileName = RarFileNameFinder.FindNextFileName(nextFileName, oldNameFormat);
						}
					}
				}

				foreach (string fileName in rarFiles)
				{
					if (!File.Exists(fileName))
					{
						ReportError(string.Format("Referenced file not found: {0}", fileName));
						srrfs.Close();
						File.Delete(srrName);
						return 2;
					}

					string fName = savePaths ? MakePathRelative(fileName, inFolder.FullName) : Path.GetFileName(fileName);
					Console.WriteLine("Processing file: {0}", fName);

					SrrRarFileBlock rarBlock = new SrrRarFileBlock(fName);
					if (savePaths)
						rarBlock.Flags |= (ushort)SrrRarFileBlock.FlagValues.PathsSaved;

					bw.Write(rarBlock.RawData);
					using (RarReader rarReader = new RarReader(fileName, RarReadMode.RAR))
					{
						RarBlock block;
						while ((block = rarReader.Read()) != null)
						{
							if (verbose)
							{
								Console.WriteLine("\tBlock Type: 0x{0:x2}", block.RawType);
								Console.WriteLine("\tBlock Size: {0}", block.RawData.Length);
							}

							if (block is RarPackedFileBlock)
							{
								RarPackedFileBlock fileData = (RarPackedFileBlock)block;

								if (verbose)
								{
									Console.WriteLine("\t\tCompression Type: 0x{0:x2}", fileData.CompressionMethod);
									Console.WriteLine("\t\tPacked Data Size: {0:n0}", fileData.PackedSize);
									Console.WriteLine("\t\tFile Size: {0:n0}", fileData.UnpackedSize);
									Console.WriteLine("\t\tFile Name: {0}", fileData.FileName);
								}

								if (fileData.CompressionMethod != 0x30)
								{
									ReportError(string.Format("Archive uses unsupported compression method: {0}", fileName));
									srrfs.Close();
									File.Delete(srrName);
									return 3;
								}
							}
							else if (block is RarRecoveryBlock)
							{
								RarRecoveryBlock subData = (RarRecoveryBlock)block;

								if (verbose & subData.RecoverySectors > 0)
								{
									Console.WriteLine("\t\tRecovery Record Size: {0:n0}", subData.PackedSize);
									Console.WriteLine("\t\tRecovery Sectors: {0:n0}", subData.RecoverySectors);
									Console.WriteLine("\t\tProtected Sectors: {0:n0}", subData.DataSectors);
								}
							}

							// store the raw data for any blocks found
							bw.Write(block.RawData);
						}
					}
				}
			}

			Console.WriteLine("\nReconstruction file successfully created: {0}", srrName);

			return 0;
		}

		//TODO check for dupe files
		static int AddStoredFiles(FileInfo srrFileInfo, DirectoryInfo inFolder, List<string> storeFiles, bool savePaths)
		{
			FileInfo newFileInfo = new FileInfo(srrFileInfo.FullName + ".tmp");

			using (FileStream fsOut = newFileInfo.Create())
			using (BinaryWriter bw = new BinaryWriter(fsOut))
			{
				bool filesAdded = false;
				using (RarReader rarReader = new RarReader(srrFileInfo.FullName, RarReadMode.SRR))
				{
					RarBlock block;
					while ((block = rarReader.Read()) != null)
					{
						if (block is SrrRarFileBlock && !filesAdded)
						{
							foreach (string fileName in storeFiles)
							{
								string searchName = fileName;
								if (!Path.IsPathRooted(searchName))
									searchName = Path.Combine(inFolder.FullName, fileName);

								DirectoryInfo searchDir = new DirectoryInfo(Path.GetDirectoryName(searchName));
								if (searchDir.Exists)
								foreach (FileInfo storeFile in new DirectoryInfo(Path.GetDirectoryName(searchName)).GetFiles(Path.GetFileName(searchName)))
								{
									string fName = savePaths ? MakePathRelative(storeFile.FullName, inFolder.FullName) : storeFile.Name;
									Console.WriteLine("Storing file: {0}", fName);
									SrrStoredFileBlock storeBlock = new SrrStoredFileBlock(fName, (int)storeFile.Length);
									if (savePaths)
										storeBlock.Flags |= (ushort)SrrStoredFileBlock.FlagValues.PathsSaved;
									using (FileStream storefs = storeFile.OpenRead())
										storefs.Read(storeBlock.RawData, storeBlock.FileOffset, (int)storeFile.Length);

									bw.Write(storeBlock.RawData);
								}
							}

							filesAdded = true;
						}

						bw.Write(block.RawData);
					}
				}
			}

			srrFileInfo.Delete();
			newFileInfo.MoveTo(srrFileInfo.FullName);

			return 0;
		}

		static int Reconstruct(FileInfo srrFileInfo, DirectoryInfo inFolder, DirectoryInfo outFolder, bool savePaths, Dictionary<string, string> hints, bool skipRarCrc, bool autoLocateRenamed)
		{
			string rarName = null, srcName = null;
			FileStream rarfs = null, srcfs = null;
			bool rebuildRecovery = false;
			byte[] copyBuff = new byte[0x10000];
			uint runningCrc = 0;

			using (RarReader rarReader = new RarReader(srrFileInfo.FullName, RarReadMode.SRR))
			{
				RarBlock block;
				 while ((block = rarReader.Read()) != null)
				{
					if (verbose)
					{
						Console.WriteLine("\tBlock Type: 0x{0:x2}", block.RawType);
						Console.WriteLine("\tBlock Size: {0}", block.RawData.Length);
					}

					if (block is SrrHeaderBlock)
					{
						// file header block.  the only thing here so far is the name of the app that created the SRR file
						if ((block.Flags & ~SrrHeaderBlock.SupportedFlagMask) != 0)
							ReportUnsupportedFlag();

						SrrHeaderBlock headBlock = (SrrHeaderBlock)block;

						if (verbose)
							Console.WriteLine("SRR file created with {0}", headBlock.AppName);
					}
					else if (block is SrrStoredFileBlock)
					{
						// There is a file stored within the .srr.  extract it.
						if ((block.Flags & ~SrrStoredFileBlock.SupportedFlagMask) != 0)
							ReportUnsupportedFlag();

						SrrStoredFileBlock sb = (SrrStoredFileBlock)block;
						string fileName = savePaths ? sb.FileName : sb.FileName.Substring(sb.FileName.LastIndexOf('/') + 1);
						FileInfo fileInfo = new FileInfo(Path.Combine(outFolder.FullName, fileName));
						if (CheckOverwrite(fileInfo.FullName))
						{
							Console.WriteLine("Re-creating stored file: {0}", fileName);
							fileInfo.Directory.Create();
							using (FileStream sffs = fileInfo.Create())
								sffs.Write(block.RawData, sb.FileOffset, (int)sb.FileLength);
						}
						else
						{
							ReportError("Operation aborted.");
							return -1;
						}
					}
					else if (block is SrrRarFileBlock)
					{
						// for each SRR block, we need to create a RAR file.  get the stored name and create it.
						if ((block.Flags & ~SrrRarFileBlock.SupportedFlagMask) != 0)
							ReportUnsupportedFlag();

						SrrRarFileBlock srrBlock = (SrrRarFileBlock)block;

						if (rarName != srrBlock.FileName)
						{
							// we use flag 0x1 to mark files that have recovery records removed.  all other flags are currently undefined.
							rebuildRecovery = (block.Flags & (ushort)SrrRarFileBlock.FlagValues.RecoveryBlocksRemoved) != 0;

							rarName = srrBlock.FileName;
							if (rarfs != null)
								rarfs.Close();

							string fileName = savePaths ? srrBlock.FileName : srrBlock.FileName.Substring(srrBlock.FileName.LastIndexOf('/') + 1);
							FileInfo fileInfo = new FileInfo(Path.Combine(outFolder.FullName, fileName));
							if (CheckOverwrite(fileInfo.FullName))
							{
								Console.WriteLine("Re-creating RAR file: {0}", fileName);
								fileInfo.Directory.Create();
								rarfs = fileInfo.Create();
							}
							else
							{
								ReportError("Operation aborted.");
								return -1;
							}
						}
					}
					else if (block is RarRecoveryBlock || block is RarOldRecoveryBlock)
					{
						// either the recovery block or the newsub block is used for recovery record data.  it consists of two parts: crc's and recovery sectors.
						//  all file data preceding the recovery record block is protected by the recovery record.  that data is broken into sectors of 512 bytes.
						//  the crc portion of the recovery block is the 2 low-order bytes of the crc32 value for each sector (2 bytes * protected sector count)
						//  the recovery sectors are created by breaking the data into slices based on the recovery sector count. (512 bytes * recovery sector count)
						//  each slice will get one parity sector created by xor-ing the corresponding bytes from all other sectors in the slice.
						uint recoverySectors = 0;
						ulong protectedSectors = 0;

						if (block is RarRecoveryBlock)
						{
							RarRecoveryBlock subData = (RarRecoveryBlock)block;
							recoverySectors = subData.RecoverySectors;
							protectedSectors = subData.DataSectors;
						}
						else
						{
							RarOldRecoveryBlock recData = (RarOldRecoveryBlock)block;
							recoverySectors = recData.RecoverySectors;
							protectedSectors = recData.DataSectors;
						}

						if (recoverySectors > 0 && rebuildRecovery)
						{
							if (verbose)
							{
								Console.WriteLine("\t\tCRC entries to rebuild: {0:n0}", protectedSectors);
								Console.WriteLine("\t\tRecovery sectors to rebuild: {0:n0}", recoverySectors);
							}

							byte[] crc = new byte[protectedSectors * 2];
							byte[][] rr = new byte[recoverySectors][];
							for (int i = 0; i < recoverySectors; i++)
								rr[i] = new byte[512];

							int rrSlice = 0;
							long currentSector = 0;
							long rarPos = rarfs.Position;

							byte[] sector = new byte[512];
							rarfs.Position = 0;
							while (rarfs.Position < rarPos)
							{
								// read data 1 sector at a time.  pad the last sector with 0's
								if (rarPos - rarfs.Position >= 512)
									rarfs.Read(sector, 0, 512);
								else
								{
									long pos = rarfs.Position;
									rarfs.Read(sector, 0, (int)(rarPos - pos));
									for (int i = (int)(rarPos - pos); i < 512; i++)
										sector[i] = 0;
								}

								// calculate the crc32 for the sector and store the 2 low-order bytes
								ushort sectorCrc = (ushort)(Crc32.GetCrc(sector) & 0xffff);
								crc[currentSector * 2] = (byte)(sectorCrc & 0xff);
								crc[currentSector * 2 + 1] = (byte)((sectorCrc >> 8) & 0xff);
								currentSector++;

								// update the recovery sector parity data for this slice
								for (int i = 0; i < 512; i++)
									rr[rrSlice][i] ^= sector[i];

								if (++rrSlice % recoverySectors == 0)
									rrSlice = 0;
							}

							// write the backed-up block header, crc data, and recovery sectors
							rarfs.Write(block.RawData, 0, block.RawData.Length);
							rarfs.Write(crc, 0, crc.Length);
							foreach (byte[] ba in rr)
								rarfs.Write(ba, 0, ba.Length);
						}
						else
						{
							// block is from a previous ReScene version or is not a recovery record.  just copy it
							rarfs.Write(block.RawData, 0, block.RawData.Length);
						}
					}
					else if (block is RarPackedFileBlock)
					{
						// this is the main RAR block we treat differently.  We removed the data when storing it, so we need to get the data back from the extracted file
						RarPackedFileBlock fileData = (RarPackedFileBlock)block;

						if (verbose)
						{
							Console.WriteLine("\t\tPacked Data Size: {0:n0}", fileData.PackedSize);
							Console.WriteLine("\t\tFile Name: {0}", fileData.FileName);
						}

						// write the block contents from the .srr file
						rarfs.Write(block.RawData, 0, block.RawData.Length);

						if (fileData.PackedSize > 0)
						{
							// make sure we have the correct extracted file open.  if not, attempt to locate and open it
							if (srcName != fileData.FileName)
							{
								srcName = fileData.FileName;
								runningCrc = Crc32.StartValue;
								if (srcfs != null)
									srcfs.Close();

								FileInfo srcInfo = new FileInfo(Path.Combine(inFolder.FullName, srcName));
								if (hints.ContainsKey(srcName.ToLower()))
									srcInfo = new FileInfo(Path.Combine(inFolder.FullName, hints[srcName.ToLower()]));

								if (!srcInfo.Exists)
								{
									ReportError(string.Format("Could not locate data file: {0}", srcInfo.FullName));

									if (autoLocateRenamed)
									{
										foreach (FileInfo altInfo in inFolder.GetFiles(string.Format("*{0}", Path.GetExtension(fileData.FileName))))
										{
											if ((ulong)altInfo.Length == fileData.UnpackedSize)
											{
												ReportError(string.Format("Attempting to substitute file: {0}", altInfo.FullName));
												srcInfo = altInfo;
												break;
											}
										}
									}
									
									if (!srcInfo.Exists)
										return 4;
								}
								if ((ulong)srcInfo.Length != fileData.UnpackedSize)
								{
									ReportError(string.Format("Data file is not the correct size: {0}\n\tFound: {1:n0}\n\tExpected: {2:n0}", srcInfo.FullName, srcInfo.Length, fileData.UnpackedSize));
									return 5;
								}

								srcfs = srcInfo.OpenRead();
							}

							// then grab the correct amount of data from the extracted file
							int bytesCopied = 0;
							uint fileCrc = Crc32.StartValue;
							while (bytesCopied < (int)fileData.PackedSize)
							{
								int bytesToCopy = (int)fileData.PackedSize - bytesCopied;
								if (bytesToCopy > copyBuff.Length)
									bytesToCopy = copyBuff.Length;

								int bytesRead = srcfs.Read(copyBuff, 0, bytesToCopy);
								rarfs.Write(copyBuff, 0, bytesRead);

								if (!skipRarCrc)
								{
									runningCrc = Crc32.GetCrc(runningCrc, copyBuff, 0, bytesRead);
									fileCrc = Crc32.GetCrc(fileCrc, copyBuff, 0, bytesRead);
								}

								// if the file didn't have as many bytes as we needed, this file record was padded.  add null bytes to correct length
								if (bytesRead != bytesToCopy)
								{
									Array.Clear(copyBuff, 0, copyBuff.Length);
									rarfs.Write(copyBuff, 0, bytesToCopy - bytesRead);
								}

								bytesCopied += bytesToCopy;
							}

							if (!skipRarCrc)
							{
								if ((fileData.Flags & (ushort)RarPackedFileBlock.FlagValues.SplitAfter) != 0 && fileData.FileCrc != ~fileCrc)
									ReportError(string.Format("CRC mismatch in file: {0}", rarName));
								else if ((fileData.Flags & (ushort)RarPackedFileBlock.FlagValues.SplitAfter) == 0 && fileData.FileCrc != ~runningCrc)
									ReportError(string.Format("CRC mismatch in file: {0}", fileData.FileName));
							}
						}
					}
					else if (block.RawType >= (byte)RarBlockType.RarMin && block.RawType <= (byte)RarBlockType.RarMax || block.RawType == 0x00)
					{
						// -> P0W4 cleared RAR archive end block: almost all zeros except for the header length field
						// copy any other rar blocks to the destination unmodified
						rarfs.Write(block.RawData, 0, block.RawData.Length);
					}
					else
					{
						ReportError(string.Format("Warning: Unknown block type ({0:X2}) encountered in SRR file, consisting of {1:n0} bytes.  This block will be skipped.", block.RawType, block.RawData.Length));
					}
				}
			}

			if (rarfs != null)
				rarfs.Close();

			Console.WriteLine("\nRelease successfully reconstructed.  Please re-check files against the SFV to verify before using.");

			return 0;
		}

		static int DisplayInfo(FileInfo srrFileInfo)
		{
			List<string> storeFiles = new List<string>();
			List<string> rarFiles = new List<string>();
			List<string> archiveFiles = new List<string>();
			string appName = string.Empty;

			using (RarReader rarReader = new RarReader(srrFileInfo.FullName, RarReadMode.SRR))
			{
				RarBlock block;
				while ((block = rarReader.Read()) != null)
				{
					if (block is SrrHeaderBlock)
					{
						appName = ((SrrHeaderBlock)block).AppName;
					}
					else if (block is SrrStoredFileBlock)
					{
						SrrStoredFileBlock sb = (SrrStoredFileBlock)block;
						storeFiles.Add(sb.FileName);
					}
					else if (block is SrrRarFileBlock)
					{
						SrrRarFileBlock srrBlock = (SrrRarFileBlock)block;
						rarFiles.Add(srrBlock.FileName);
					}
					else if (block is RarPackedFileBlock && !(block is RarRecoveryBlock))
					{
						RarPackedFileBlock fileBlock = (RarPackedFileBlock)block;
						if (!archiveFiles.Contains(fileBlock.FileName))
							archiveFiles.Add(fileBlock.FileName);
					}
				}
			}

			Console.WriteLine("Creating Application:");
			Console.WriteLine("\t{0}\n", string.IsNullOrEmpty(appName) ? "Unknown" : appName);

			if (storeFiles.Count > 0)
			{
				Console.WriteLine("Stored Files:");
				foreach (string file in storeFiles)
					Console.WriteLine("\t{0}", file);
				Console.WriteLine();
			}
			if (rarFiles.Count > 0)
			{
				Console.WriteLine("RAR Files:");
				foreach (string file in rarFiles)
					Console.WriteLine("\t{0}", file);
				Console.WriteLine();
			}
			if (archiveFiles.Count > 0)
			{
				Console.WriteLine("Archived Files:");
				foreach (string file in archiveFiles)
					Console.WriteLine("\t{0}", file);
				Console.WriteLine();
			}

			return 0;
		}

		static int ExtractFiles(FileInfo srrFileInfo, DirectoryInfo outFolder, bool savePaths)
		{
			using (RarReader rarReader = new RarReader(srrFileInfo.FullName, RarReadMode.SRR))
			{
				RarBlock block;
				while ((block = rarReader.Read()) != null)
				{
					if (block is SrrStoredFileBlock)
					{
						SrrStoredFileBlock sb = (SrrStoredFileBlock)block;
						string fileName = savePaths ? sb.FileName : sb.FileName.Substring(sb.FileName.LastIndexOf('/') + 1);
						FileInfo fileInfo = new FileInfo(Path.Combine(outFolder.FullName, fileName));
						if (CheckOverwrite(fileInfo.FullName))
						{
							Console.WriteLine("Re-creating stored file: {0}", fileName);
							fileInfo.Directory.Create();
							using (FileStream sffs = fileInfo.Create())
							{
								sffs.Write(block.RawData, sb.FileOffset, (int)sb.FileLength);
							}
						}
						else
						{
							ReportError("Operation aborted.");
							return -1;
						}
					}
				}
			}

			return 0;
		}

		static int Main(string[] args)
		{
			try
			{
				Dictionary<string, List<string> > argDict = ArgParser.GetArgsDictionary(args);
				if (args.Length == 0 || argDict.ContainsKey("?"))
				{
					DisplayUsage();
					return -1;
				}

				verbose = argDict.ContainsKey("v");
				assumeYes = argDict.ContainsKey("y");
				bool savePaths = argDict.ContainsKey("p");

				DirectoryInfo workingDir = new DirectoryInfo(FixPathCase(Directory.GetCurrentDirectory()));

				List<FileInfo> inFiles = new List<FileInfo>(); 
				foreach (string inFile in argDict["infile"])
				{
					FileInfo fi = new FileInfo(inFile);
					inFiles.Add(fi);
					if (!fi.Exists)
					{
						ReportError(string.Format("Input file not found: {0}\n", fi.FullName));
						DisplayUsage();
						return 1;
					}
					else if (fi.Extension.ToLower() != ".srr" && fi.Extension.ToLower() != ".sfv" && fi.Extension.ToLower() != ".rar")
					{
						ReportError(string.Format("Input file type not recognized: {0}\n", fi.FullName));
						DisplayUsage();
						return -1;
					}
				}

				if (inFiles.Count == 0)
				{
					ReportError("No input file(s) specified.");
					DisplayUsage();
					return 1;
				}

				DirectoryInfo inFolder = workingDir;
				if (argDict.ContainsKey("i") && argDict["i"].Count == 1)
					inFolder = new DirectoryInfo(argDict["i"][0]);

				if (inFiles[0].Extension.ToLower() == ".srr")
				{
					DirectoryInfo outFolder = workingDir;
					if (argDict.ContainsKey("o") && argDict["o"].Count == 1)
						outFolder = new DirectoryInfo(argDict["o"][0]);

					if (argDict.ContainsKey("l"))
						return DisplayInfo(inFiles[0]);
					else if (argDict.ContainsKey("x"))
						return ExtractFiles(inFiles[0], outFolder, savePaths);
					else if (argDict.ContainsKey("s"))
						return AddStoredFiles(inFiles[0], inFolder, argDict["s"], savePaths);
					else
					{
						Dictionary<string, string> hints = new Dictionary<string, string>();
						if (argDict.ContainsKey("h"))
						{
							foreach (string hint in argDict["h"])
							{
								string[] pair = hint.Split(new char[] { ':' });
								if (pair.Length != 2)
								{
									ReportError(string.Format("Invalid hint (-h) value: {0}\n", hint));
									DisplayUsage();
									return 1;
								}
								else
									hints.Add(pair[0].ToLower(), pair[1]);
							}
						}

						return Reconstruct(inFiles[0], inFolder, outFolder, savePaths, hints, argDict.ContainsKey("u"), argDict.ContainsKey("r"));
					}
				}
				else
				{
					List<string> storeFiles = argDict.ContainsKey("s") ? argDict["s"] : new List<string>();

					string srrName = null;
					DirectoryInfo outFolder = workingDir; ;
					if (argDict.ContainsKey("o") && argDict["o"].Count == 1)
						if (Path.GetExtension(argDict["o"][0]).ToLower() == ".srr")
							srrName = argDict["o"][0];
						else
							outFolder = new DirectoryInfo(argDict["o"][0]);

					if (srrName == null)
					{
						if (argDict.ContainsKey("d"))
							srrName = Path.Combine(outFolder.FullName, inFolder.Name + ".srr");
						else
							srrName = Path.Combine(outFolder.FullName, Path.ChangeExtension(inFiles[0].Name, ".srr"));
					}

					return CreateReconstructionFile(inFiles, inFolder, storeFiles, srrName, savePaths);
				}
			}
			catch (Exception ex)
			{
				ReportError(string.Format("Unexpected Error:\n{0}", ex.ToString()));
				return 99;
			}
		}
	}
}
