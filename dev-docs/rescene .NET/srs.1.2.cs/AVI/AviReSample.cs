using System;
using System.IO;
using System.Text;
using System.Collections.Generic;
using ReScene;
using ReScene.Utility;
using ReSample.Riff;
using ReSample.Utility;

namespace ReSample
{
	class AviReSample
	{
		public static int ProfileSample(FileData file, SortedList<int, TrackData> tracks)
		{
			long otherLength = 0;
			int blockcount = 0;

			file.Crc32 = Crc32.StartValue;
			using (RiffReader rdr = new RiffReader(file.Name, RiffReadMode.Sample))
			{
				while (rdr.Read())
				{
					otherLength += rdr.Chunk.RawHeader.Length;
					file.Crc32 = Crc32.GetCrc(file.Crc32, rdr.Chunk.RawHeader);

					if (rdr.ChunkType == RiffChunkType.List)
					{
						if (rdr.List.ListType == "RIFF" && rdr.List.ChunkStartPos + rdr.List.RawHeader.Length + rdr.List.Length > file.Size)
							Program.ReportError(string.Format("\nWarning: File size does not appear to be correct!\n\t Expected at least: {0:n0}\n\t Found            : {1:n0}\n", rdr.List.ChunkStartPos + rdr.List.RawHeader.Length + rdr.List.Length, file.Size));

						rdr.MoveToChild();
					}
					else // normal chunk
					{
						if (rdr.ChunkType == RiffChunkType.Movi) // chunk containing stream data (our main focus)
						{
							if (++blockcount % 15 == 0)
								Console.Write("\b{0}", Program.spinners[blockcount % Program.spinners.Length]);

							int trackno = rdr.MoviChunk.StreamNumber;
							if (!tracks.ContainsKey(trackno))
								tracks.Add(trackno, new TrackData());

							TrackData track = tracks[trackno];
							track.TrackNumber = (byte)trackno;
							track.DataLength += rdr.MoviChunk.Length;

							byte[] moviData = rdr.ReadContents();
							file.Crc32 = Crc32.GetCrc(file.Crc32, moviData);

							// in profile mode, we want to build track signatures
							if (track.SignatureBytes == null || track.SignatureBytes.Length < Program.sigSize)
							{
								if (track.SignatureBytes != null)
								{
									byte[] sig = new byte[Math.Min(Program.sigSize, track.SignatureBytes.Length + rdr.MoviChunk.Length)];
									track.SignatureBytes.CopyTo(sig, 0);
									Buffer.BlockCopy(moviData, 0, sig, track.SignatureBytes.Length, sig.Length - track.SignatureBytes.Length);
									track.SignatureBytes = sig;
								}
								else
								{
									track.SignatureBytes = new byte[Math.Min(Program.sigSize, rdr.MoviChunk.Length)];
									Buffer.BlockCopy(moviData, 0, track.SignatureBytes, 0, track.SignatureBytes.Length);
								}
							}
						}
						else
						{
							otherLength += rdr.Chunk.Length;
							file.Crc32 = Crc32.GetCrc(file.Crc32, rdr.ReadContents());
						}

						if (rdr.HasPad)
						{
							otherLength++;
							file.Crc32 = Crc32.GetCrc(file.Crc32, new byte[] {rdr.PadByte});
						}
					}
				}
			}

			Console.Write('\b');

			file.Crc32 = ~file.Crc32;
			long totalSize = otherLength;

			Console.WriteLine("File Details:   Size           CRC");
			Console.WriteLine("                -------------  --------");
			Console.WriteLine("                {0,13:n0}  {1:X8}\n", file.Size, file.Crc32);

			Console.WriteLine();
			Console.WriteLine("Stream Details:  Stream  Length");
			Console.WriteLine("                 ------  -------------");
			foreach (TrackData track in tracks.Values)
			{
				Console.WriteLine("                 {0,6:n0}  {1,13:n0}", track.TrackNumber, track.DataLength);
				totalSize += track.DataLength;
			}

			Console.WriteLine();
			Console.WriteLine("Parse Details:   Metadata     Stream Data    Total");
			Console.WriteLine("                 -----------  -------------  -------------");
			Console.WriteLine("                 {0,11:n0}  {1,13:n0}  {2,13:n0}\n", otherLength, totalSize - otherLength, totalSize);

			if (file.Size != totalSize)
			{
				Program.ReportError("\nError: Parsed size does not equal file size.\n       The sample is likely corrupted or incomplete.\n");
				return 2;
			}

			return 0;
		}

		public static void CreateSRS(SortedList<int, TrackData> tracks, FileData file, FileInfo inFile, FileInfo srsFile, bool bigFile)
		{
			using (FileStream fsOut = srsFile.Create())
			using (RiffReader rdr = new RiffReader(inFile.FullName, RiffReadMode.AVI))
			{
				while (rdr.Read())
				{
					fsOut.Write(rdr.Chunk.RawHeader, 0, rdr.Chunk.RawHeader.Length);

					if (rdr.ChunkType == RiffChunkType.List)
					{
						// in store mode, create and write our custom chunks as the first child of LIST movi
						// we put them after the avi headers so mediainfo can still read them from the SRS
						if (rdr.List.ListType == "LIST" && rdr.List.FourCC == "movi")
						{
							byte[] fileChunk = file.SerializeAsRiff();
							fsOut.Write(fileChunk, 0, fileChunk.Length);
							if (fileChunk.Length % 2 == 1)
								fsOut.WriteByte(0);

							foreach (TrackData track in tracks.Values)
							{
								if (bigFile)
									track.Flags |= TrackData.TrackDataFlags.BigFile;
								byte[] trackChunk = track.SerializeAsRiff();
								fsOut.Write(trackChunk, 0, trackChunk.Length);
								if (trackChunk.Length % 2 == 1)
									fsOut.WriteByte(0);
							}
						}

						rdr.MoveToChild();
					}
					else
					{
						if (rdr.ChunkType == RiffChunkType.Movi)
							rdr.SkipContents(); // don't copy stream data
						else
							fsOut.Write(rdr.ReadContents(), 0, (int)rdr.Chunk.Length); // do copy everything else

						if (rdr.HasPad)
							fsOut.WriteByte(rdr.PadByte);
					}
				}
			}
		}

		public static void LoadSRS(SortedList<int, TrackData> tracks, ref FileData file, FileInfo inFile)
		{
			using (RiffReader rdr = new RiffReader(inFile.FullName, RiffReadMode.SRS))
			{
				bool done = false;
				while (!done && rdr.Read())
				{
					if (rdr.ChunkType == RiffChunkType.List)
					{
						rdr.MoveToChild();
					}
					else
					{
						if (rdr.Chunk.FourCC == "SRSF") // resample file
						{
							byte[] buff = rdr.ReadContents();
							file = new FileData(buff);
						}
						else if (rdr.Chunk.FourCC == "SRST") // resample track
						{
							byte[] buff = rdr.ReadContents();
							TrackData track = new TrackData(buff);
							tracks.Add(track.TrackNumber, track);
						}
						else if (rdr.ChunkType == RiffChunkType.Movi)
						{
							// if we get here in load mode, we have already got what we need, so bail out
							done = true;
							continue;
						}
						else
						{
							rdr.SkipContents();
						}
					}
				}
			}
		}

		public static void FindSampleStreams(SortedList<int, TrackData> tracks, FileInfo inFile)
		{
			Stream fs;
			if (RarFileNameComparer.IsRarFile(inFile.Name))
				fs = new RarStream(inFile.FullName);
			else
				fs = inFile.OpenRead();

			using (RiffReader rdr = new RiffReader(fs, RiffReadMode.AVI))
			{
				int blockcount = 0;
				bool done = false;
				while (rdr.Read() && !done)
				{
					if (rdr.ChunkType == RiffChunkType.List)
					{
						rdr.MoveToChild();
					}
					else // normal chunk
					{
						if (rdr.ChunkType == RiffChunkType.Movi)
						{
							if (++blockcount % 15 == 0)
								Console.Write("\b{0}", Program.spinners[blockcount % Program.spinners.Length]);

							int trackno = rdr.MoviChunk.StreamNumber;
							if (!tracks.ContainsKey(trackno))
								tracks.Add(trackno, new TrackData());

							TrackData track = tracks[trackno];
							track.TrackNumber = (byte)trackno;

							if (track.MatchOffset == 0 || track.CheckBytes.Length < track.SignatureBytes.Length)
							{
								// it's possible the sample didn't require or contain data for all tracks in the main file
								//  if that happens, we obviously don't want to try to match the data
								if (track.SignatureBytes != null)
								{
									if (track.CheckBytes != null && track.CheckBytes.Length < track.SignatureBytes.Length)
									{
										byte[] checkBytes = new byte[Math.Min(track.SignatureBytes.Length, rdr.MoviChunk.Length + track.CheckBytes.Length)];
										track.CheckBytes.CopyTo(checkBytes, 0);
										Buffer.BlockCopy(rdr.ReadContents(), 0, checkBytes, track.CheckBytes.Length, checkBytes.Length - track.CheckBytes.Length);

										if (ByteArrayComparer.AreEqual(track.SignatureBytes, checkBytes, checkBytes.Length))
										{
											track.CheckBytes = checkBytes;
										}
										else
										{
											// it was only a partial match.  start over
											track.CheckBytes = null;
											track.MatchOffset = 0;
											track.MatchLength = 0;
										}
									}

									// this is a bit weird, but if we had a false positive match going and discovered it above, we check this frame again
									//  to see if it's the start of a new match (probably will never happen with AVI, but it does in MKV, so just in case...)
									if (track.CheckBytes == null)
									{
										byte[] chunkBytes = rdr.ReadContents();

										byte searchByte = track.SignatureBytes[0];
										int foundPos = -1;
										while ((foundPos = Array.IndexOf<byte>(chunkBytes, searchByte, foundPos + 1)) > -1)
										{
											byte[] checkBytes = new byte[Math.Min(track.SignatureBytes.Length, chunkBytes.Length - foundPos)];
											Buffer.BlockCopy(chunkBytes, foundPos, checkBytes, 0, checkBytes.Length);

											if (ByteArrayComparer.AreEqual(track.SignatureBytes, checkBytes, checkBytes.Length))
											{
												track.CheckBytes = checkBytes;
												track.MatchOffset = rdr.Chunk.ChunkStartPos + rdr.Chunk.RawHeader.Length + foundPos;
												track.MatchLength = Math.Min(track.DataLength, chunkBytes.Length - foundPos);
												break;
											}
										}
									}
									else
									{
										track.MatchLength += Math.Min(track.DataLength - track.MatchLength, rdr.MoviChunk.Length);
									}
								}
							}
							else if (track.MatchLength < track.DataLength)
							{
								track.MatchLength += Math.Min(track.DataLength - track.MatchLength, rdr.MoviChunk.Length);

								bool tracksDone = true;
								foreach (TrackData t in tracks.Values)
								{
									if (t.MatchLength < t.DataLength)
									{
										tracksDone = false;
										break;
									}
								}
								done = tracksDone;
							}

							rdr.SkipContents();
						}
						else
						{
							rdr.SkipContents();
						}
					}
				}
			}

			Console.Write('\b');
		}

		public static void ExtractSampleStreams(SortedList<int, TrackData> tracks, FileData file, FileInfo inFile, DirectoryInfo outDir)
		{
			Stream fs;
			if (RarFileNameComparer.IsRarFile(inFile.Name))
				fs = new RarStream(inFile.FullName);
			else
				fs = inFile.OpenRead();

			using (RiffReader rdr = new RiffReader(fs, RiffReadMode.AVI))
			{
				long startOffset = long.MaxValue;
				foreach (TrackData track in tracks.Values)
					if (track.MatchOffset > 0)
						startOffset = Math.Min(track.MatchOffset, startOffset);

				int blockcount = 0;
				bool done = false;
				while (rdr.Read() && !done)
				{
					if (rdr.ChunkType == RiffChunkType.List)
					{
						rdr.MoveToChild();
					}
					else // normal chunk
					{
						if (rdr.ChunkType == RiffChunkType.Movi)
						{
							if (++blockcount % 15 == 0)
								Console.Write("\b{0}", Program.spinners[blockcount % Program.spinners.Length]);

							if (!tracks.ContainsKey(rdr.MoviChunk.StreamNumber))
								tracks.Add(rdr.MoviChunk.StreamNumber, new TrackData());

							TrackData track = tracks[rdr.MoviChunk.StreamNumber];

							if (rdr.MoviChunk.ChunkStartPos + rdr.MoviChunk.RawHeader.Length + rdr.MoviChunk.Length > track.MatchOffset)
							{
								if (track.TrackFile == null)
									track.TrackFile = new FileStream(Path.Combine(outDir.FullName, inFile.Name + "." + track.TrackNumber.ToString("d3")), FileMode.Create, FileAccess.ReadWrite, FileShare.Read, 0x10000, FileOptions.DeleteOnClose);

								if (track.TrackFile.Position < track.DataLength)
								{
									if (rdr.MoviChunk.ChunkStartPos + rdr.MoviChunk.RawHeader.Length >= track.MatchOffset)
									{
										track.TrackFile.Write(rdr.ReadContents(), 0, (int)rdr.MoviChunk.Length);
									}
									else
									{
										int chunkOffset = (int)(track.MatchOffset - (rdr.MoviChunk.ChunkStartPos + rdr.MoviChunk.RawHeader.Length));
										track.TrackFile.Write(rdr.ReadContents(), chunkOffset, (int)rdr.MoviChunk.Length - chunkOffset);
									}
								}

								bool tracksDone = true;
								foreach (TrackData t in tracks.Values)
								{
									if (t.TrackFile == null || t.TrackFile.Length < t.DataLength)
									{
										tracksDone = false;
										break;
									}
								}
								done = tracksDone;
							}

							rdr.SkipContents();
						}
						else
						{
							rdr.SkipContents();
						}
					}
				}
			}

			Console.Write('\b');
		}

		public static FileData RebuildSample(FileData file, SortedList<int, TrackData> tracks, FileInfo srsFile, DirectoryInfo outDir)
		{
			uint crc = Crc32.StartValue;

			using (RiffReader rdr = new RiffReader(srsFile.FullName, RiffReadMode.SRS))
			using (FileStream fsOut = new FileStream(Path.Combine(outDir.FullName, file.Name), FileMode.Create))
			{
				int blockcount = 0;
				while (rdr.Read())
				{
					// skip over our custom chunks in rebuild mode (only read it in load mode)
					if (rdr.Chunk.FourCC == "SRSF" || rdr.Chunk.FourCC == "SRST")
					{
						rdr.SkipContents();
						continue;
					}

					fsOut.Write(rdr.Chunk.RawHeader, 0, rdr.Chunk.RawHeader.Length);
					crc = Crc32.GetCrc(crc, rdr.Chunk.RawHeader);

					if (rdr.ChunkType == RiffChunkType.List)
					{
						rdr.MoveToChild();
					}
					else
					{
						if (rdr.ChunkType == RiffChunkType.Movi)
						{
							if (++blockcount % 15 == 0)
								Console.Write("\b{0}", Program.spinners[blockcount % Program.spinners.Length]);

							TrackData track = tracks[rdr.MoviChunk.StreamNumber];
							byte[] buff = new byte[rdr.MoviChunk.Length];
							track.TrackFile.Read(buff, 0, buff.Length);
							fsOut.Write(buff, 0, buff.Length);
							crc = Crc32.GetCrc(crc, buff);
							rdr.SkipContents();
						}
						else
						{
							byte[] buff = rdr.ReadContents();
							fsOut.Write(buff, 0, buff.Length);
							crc = Crc32.GetCrc(crc, buff);
						}

						if (rdr.HasPad)
						{
							fsOut.WriteByte(rdr.PadByte);
							crc = Crc32.GetCrc(crc, new byte[] {rdr.PadByte});
						}
					}
				}
			}
			Console.Write('\b');

			FileData newFile = new FileData(Path.Combine(outDir.FullName, file.Name));
			newFile.Crc32 = ~crc;

			return newFile;
		}
	}
}
