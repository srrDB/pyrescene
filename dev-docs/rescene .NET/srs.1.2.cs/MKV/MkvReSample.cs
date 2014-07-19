using System;
using System.IO;
using System.Text;
using System.Collections.Generic;
using ReScene;
using ReScene.Utility;
using ReSample.Ebml;
using ReSample.Utility;

namespace ReSample
{
	class MkvReSample
	{
		public static int ProfileSample(FileData file, SortedList<int, TrackData> tracks, Dictionary<string, AttachmentData> attachments)
		{
			long otherLength = 0;
			int clustercount = 0;
			int blockcount = 0;
			string currentAttachment = null;
			byte[] elmContent = null;

			file.Crc32 = Crc32.StartValue;
			using (EbmlReader rdr = new EbmlReader(file.Name, EbmlReadMode.Sample))
			{
				while (rdr.Read())
				{
					otherLength += rdr.Element.RawHeader.Length;
					file.Crc32 = Crc32.GetCrc(file.Crc32, rdr.Element.RawHeader);

					switch (rdr.ElementType)
					{
						case EbmlElementType.Segment:
							// segment should be the first thing following the header.  this is a good time to do a check for file size.
							if (rdr.Element.ElementStartPos + rdr.Element.RawHeader.Length + rdr.Element.Length != file.Size)
								Program.ReportError(string.Format("\nWarning: File size does not appear to be correct!\n\t Expected: {0:n0}\n\t Found   : {1:n0}\n", rdr.Element.ElementStartPos + rdr.Element.RawHeader.Length + rdr.Element.Length, file.Size));
							rdr.MoveToChild();
							break;
						case EbmlElementType.Cluster:
							// simple progress indicator since this can take a while (cluster is good because they're about 1mb each)
							Console.Write("\b{0}", Program.spinners[clustercount++ % Program.spinners.Length]);
							rdr.MoveToChild();
							break;
						case EbmlElementType.BlockGroup:
						case EbmlElementType.AttachmentList:
						case EbmlElementType.Attachment:
							// these elements have no useful info of their own, but we want to step into them to examine their children
							rdr.MoveToChild();
							break;
						case EbmlElementType.AttachedFileName:
							elmContent = rdr.ReadContents();
							otherLength += elmContent.Length;
							file.Crc32 = Crc32.GetCrc(file.Crc32, elmContent);
							currentAttachment = Encoding.UTF8.GetString(elmContent);
							if (!attachments.ContainsKey(currentAttachment))
								attachments.Add(currentAttachment, new AttachmentData() { Name = currentAttachment });
							break;
						case EbmlElementType.AttachedFileData:
							elmContent = rdr.ReadContents();
							attachments[currentAttachment].Size = elmContent.Length;
							file.Crc32 = Crc32.GetCrc(file.Crc32, elmContent);
							break;
						case EbmlElementType.Block:
							blockcount++;
							if (!tracks.ContainsKey(rdr.Block.TrackNumber))
								tracks.Add(rdr.Block.TrackNumber, new TrackData() { TrackNumber = (ushort)rdr.Block.TrackNumber });

							TrackData track = tracks[rdr.Block.TrackNumber];
							track.DataLength += rdr.Block.Length;

							otherLength += rdr.Block.RawBlockHeader.Length;
							file.Crc32 = Crc32.GetCrc(file.Crc32, rdr.Block.RawBlockHeader);

							elmContent = rdr.ReadContents();
							file.Crc32 = Crc32.GetCrc(file.Crc32, elmContent);

							// in profile mode, we want to build track signatures
							if (track.SignatureBytes == null || track.SignatureBytes.Length < Program.sigSize)
							{
								// here, we can completely ignore laces, because we know what we're looking for always starts at the beginning
								if (track.SignatureBytes != null)
								{
									byte[] sig = new byte[Math.Min(Program.sigSize, track.SignatureBytes.Length + elmContent.Length)];
									Buffer.BlockCopy(track.SignatureBytes, 0, sig, 0, track.SignatureBytes.Length);
									Buffer.BlockCopy(elmContent, 0, sig, track.SignatureBytes.Length, sig.Length - track.SignatureBytes.Length);
									track.SignatureBytes = sig;
								}
								else
								{
									track.SignatureBytes = new byte[Math.Min(Program.sigSize, elmContent.Length)];
									Buffer.BlockCopy(elmContent, 0, track.SignatureBytes, 0, track.SignatureBytes.Length);
								}
							}
							break;
						default:
							otherLength += rdr.Element.Length;
							file.Crc32 = Crc32.GetCrc(file.Crc32, rdr.ReadContents());
							break;
					}
				}
			}
			Console.Write("\b");

			file.Crc32 = ~file.Crc32;

			long totalSize = otherLength;
			long attachmentSize = 0;

			Console.WriteLine("File Details:   Size           CRC");
			Console.WriteLine("                -------------  --------");
			Console.WriteLine("                {0,13:n0}  {1:X8}\n", file.Size, file.Crc32);

			if (attachments.Count > 0)
			{
				Console.WriteLine("Attachments:    File Name                  Size");
				Console.WriteLine("                -------------------------  ------------");
				foreach (AttachmentData attachment in attachments.Values)
				{
					Console.WriteLine("                {0,-25}  {1,12:n0}", attachment.Name.Substring(0, Math.Min(25, attachment.Name.Length)), attachment.Size);
					totalSize += attachment.Size;
					attachmentSize += attachment.Size;
				}
			}

			Console.WriteLine();
			Console.WriteLine("Track Details:  Track  Length");
			Console.WriteLine("                -----  -------------");
			foreach (TrackData track in tracks.Values)
			{
				Console.WriteLine("                {0,5:n0}  {1,13:n0}", track.TrackNumber, track.DataLength);
				totalSize += track.DataLength;
			}

			Console.WriteLine();
			Console.WriteLine("Parse Details:  Metadata     Attachments   Track Data     Total");
			Console.WriteLine("                -----------  ------------  -------------  -------------");
			Console.WriteLine("                {0,11:n0}  {1,12:n0}  {2,13:n0}  {3,13:n0}\n", otherLength, attachmentSize, totalSize - attachmentSize - otherLength, totalSize);

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
			using (EbmlReader rdr = new EbmlReader(inFile.FullName, EbmlReadMode.MKV))
			{
				while (rdr.Read())
				{
					fsOut.Write(rdr.Element.RawHeader, 0, rdr.Element.RawHeader.Length);

					switch (rdr.ElementType)
					{
						case EbmlElementType.Segment:
							// in store mode, create and write our custom ebml element as the first child of the segment
							byte[] fileElement = file.SerializeAsEbml();
							int elementSize = fileElement.Length;

							byte[][] trackElements = new byte[tracks.Count][];
							for (int i = 0; i < tracks.Count; i++)
							{
								if (bigFile)
									tracks.Values[i].Flags |= TrackData.TrackDataFlags.BigFile;
								trackElements[i] = tracks.Values[i].SerializeAsEbml();
								elementSize += trackElements[i].Length;
							}

							byte[] elementSizeCoded = EbmlHelper.MakeEbmlUInt(elementSize);
							byte[] element = new byte[EbmlElementIDs.ReSample.Length + elementSizeCoded.Length + elementSize];
							fsOut.Write(EbmlElementIDs.ReSample, 0, EbmlElementIDs.ReSample.Length);
							fsOut.Write(elementSizeCoded, 0, elementSizeCoded.Length);
							fsOut.Write(fileElement, 0, fileElement.Length);
							foreach (byte[] trackElement in trackElements)
								fsOut.Write(trackElement, 0, trackElement.Length);

							rdr.MoveToChild();
							break;
						case EbmlElementType.Cluster:
						case EbmlElementType.BlockGroup:
						case EbmlElementType.AttachmentList:
						case EbmlElementType.Attachment:
							// these elements have no useful info of their own, but we want to step into them to examine their children
							rdr.MoveToChild();
							break;
						case EbmlElementType.AttachedFileData:
							// eliminate the data from any attachments
							rdr.SkipContents();
							break;
						case EbmlElementType.Block:
							// copy block header, but eliminate any frame data
							fsOut.Write(rdr.Block.RawBlockHeader, 0, rdr.Block.RawBlockHeader.Length);
							rdr.SkipContents();
							break;
						default:
							// anything not caught above is considered metadata, so we copy it as is
							byte[] buff = rdr.ReadContents();
							fsOut.Write(buff, 0, buff.Length);
							break;
					}
				}
			}
		}

		public static void LoadSRS(SortedList<int, TrackData> tracks, ref FileData file, FileInfo inFile)
		{
			using (EbmlReader rdr = new EbmlReader(inFile.FullName, EbmlReadMode.SRS))
			{
				bool done = false;
				while (!done && rdr.Read())
				{
					switch (rdr.ElementType)
					{
						case EbmlElementType.Segment:
						case EbmlElementType.ReSample:
							rdr.MoveToChild();
							break;
						case EbmlElementType.ReSampleFile:
							byte[] buff = rdr.ReadContents();
							file = new FileData(buff);
							break;
						case EbmlElementType.ReSampleTrack:
							buff = rdr.ReadContents();
							TrackData track = new TrackData(buff);
							tracks.Add(track.TrackNumber, track);
							break;
						case EbmlElementType.Cluster:
						case EbmlElementType.AttachmentList:
							// if we get to either of these elements, we've passed the interesting part of the file, so bail out
							rdr.SkipContents();
							done = true;
							break;
						default:
							rdr.SkipContents();
							break;
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

			using (EbmlReader rdr = new EbmlReader(fs, EbmlReadMode.MKV))
			{
				int clustercount = 0;
				bool done = false;
				while (rdr.Read() && !done)
				{
					switch (rdr.ElementType)
					{
						case EbmlElementType.Segment:
						case EbmlElementType.BlockGroup:
							rdr.MoveToChild();
							break;
						case EbmlElementType.Cluster:
							// simple progress indicator since this can take a while (cluster is good because they're about 1mb each)
							Console.Write("\b{0}", Program.spinners[clustercount++ % Program.spinners.Length]);
							rdr.MoveToChild();
							break;
						case EbmlElementType.Block:
							if (!tracks.ContainsKey(rdr.Block.TrackNumber))
								tracks.Add(rdr.Block.TrackNumber, new TrackData() { TrackNumber = (ushort)rdr.Block.TrackNumber });

							TrackData track = tracks[rdr.Block.TrackNumber];

							// it's possible the sample didn't require or contain data for all tracks in the main file
							//  if that happens, we obviously don't want to try to match the data
							if (track.SignatureBytes != null && (track.MatchOffset == 0 || track.CheckBytes.Length < track.SignatureBytes.Length))
							{
								// here, the data we're looking for might not start in the first frame (lace) of the block, so we need to check them all
								byte[] buff = rdr.ReadContents();
								int offset = 0;
								for (int i = 0; i < rdr.Block.FrameLengths.Length; i++)
								{
									if (track.CheckBytes != null && track.CheckBytes.Length < track.SignatureBytes.Length)
									{
										byte[] checkBytes = new byte[Math.Min(track.SignatureBytes.Length, rdr.Block.FrameLengths[i] + track.CheckBytes.Length)];
										Buffer.BlockCopy(track.CheckBytes, 0, checkBytes, 0, track.CheckBytes.Length);
										Buffer.BlockCopy(buff, offset, checkBytes, track.CheckBytes.Length, checkBytes.Length - track.CheckBytes.Length);

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
									//  to see if it's the start of a new match (rare problem, but it can happen with subtitles especially)
									if (track.CheckBytes == null)
									{
										byte[] checkBytes = new byte[Math.Min(track.SignatureBytes.Length, rdr.Block.FrameLengths[i])];
										Buffer.BlockCopy(buff, offset, checkBytes, 0, checkBytes.Length);

										if (ByteArrayComparer.AreEqual(track.SignatureBytes, checkBytes, checkBytes.Length))
										{
											track.CheckBytes = checkBytes;
											track.MatchOffset = rdr.Block.ElementStartPos + rdr.Block.RawHeader.Length + rdr.Block.RawBlockHeader.Length + offset;
											track.MatchLength = Math.Min(track.DataLength, rdr.Block.FrameLengths[i]);
										}
									}
									else
									{
										track.MatchLength += Math.Min(track.DataLength - track.MatchLength, rdr.Block.FrameLengths[i]);
									}

									offset += rdr.Block.FrameLengths[i];
								}
							}
							else if (track.MatchLength < track.DataLength)
							{
								track.MatchLength += Math.Min(track.DataLength - track.MatchLength, rdr.Element.Length);
								rdr.SkipContents();

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
							else
							{
								rdr.SkipContents();
							}
							break;
						default:
							rdr.SkipContents();
							break;
					}
				}
			}

			Console.Write('\b');
		}

		public static void ExtractSampleStreams(SortedList<int, TrackData> tracks, Dictionary<string, AttachmentData> attachments, FileData file, FileInfo inFile, DirectoryInfo outDir)
		{
			Stream fs;
			if (RarFileNameComparer.IsRarFile(inFile.Name))
				fs = new RarStream(inFile.FullName);
			else
				fs = inFile.OpenRead();

			using (EbmlReader rdr = new EbmlReader(fs, EbmlReadMode.MKV))
			{
				long startOffset = long.MaxValue;
				foreach (TrackData track in tracks.Values)
					if (track.MatchOffset > 0)
						startOffset = Math.Min(track.MatchOffset, startOffset);

				string currentAttachment = null;
				int clustercount = 0;
				bool done = false;
				while (rdr.Read() && !done)
				{
					switch (rdr.ElementType)
					{
						case EbmlElementType.Segment:
						case EbmlElementType.AttachmentList:
						case EbmlElementType.Attachment:
						case EbmlElementType.BlockGroup:
							rdr.MoveToChild();
							break;
						case EbmlElementType.Cluster:
							// simple progress indicator since this can take a while (cluster is good because they're about 1mb each)
							Console.Write("\b{0}", Program.spinners[clustercount++ % Program.spinners.Length]);

							// in extract mode, we know the first data offset we're looking for, so skip any clusters before that
							if (rdr.Element.ElementStartPos + rdr.Element.RawHeader.Length + rdr.Element.Length < startOffset)
								rdr.SkipContents();
							else
								rdr.MoveToChild();
							break;
						case EbmlElementType.AttachedFileName:
							currentAttachment = Encoding.UTF8.GetString(rdr.ReadContents());
							if (!attachments.ContainsKey(currentAttachment))
								attachments.Add(currentAttachment, new AttachmentData() { Name = currentAttachment });
							break;
						case EbmlElementType.AttachedFileData:
							AttachmentData attachment = attachments[currentAttachment];
							attachment.Size = rdr.Element.Length;

							// in extract mode, extract all attachments in case we need them later
							if (attachment.AttachmentFile == null)
								attachment.AttachmentFile = new FileStream(Path.Combine(outDir.FullName, attachment.Name), FileMode.Create, FileAccess.ReadWrite, FileShare.Read, 0x10000, FileOptions.DeleteOnClose);

							byte[] buff = rdr.ReadContents();
							attachment.AttachmentFile.Write(buff, 0, buff.Length);
							attachment.AttachmentFile.Seek(0, SeekOrigin.Begin);
							break;
						case EbmlElementType.Block:
							TrackData track = tracks[rdr.Block.TrackNumber];

							if (rdr.Block.ElementStartPos + rdr.Block.RawHeader.Length + rdr.Block.RawBlockHeader.Length + rdr.Block.Length > track.MatchOffset)
							{
								if (track.TrackFile == null)
									track.TrackFile = new FileStream(Path.Combine(outDir.FullName, inFile.Name + "." + track.TrackNumber.ToString("d3")), FileMode.Create, FileAccess.ReadWrite, FileShare.Read, 0x10000, FileOptions.DeleteOnClose);

								buff = rdr.ReadContents();
								int offset = 0;
								for (int i = 0; i < rdr.Block.FrameLengths.Length; i++)
								{
									if (rdr.Block.ElementStartPos + rdr.Block.RawHeader.Length + rdr.Block.RawBlockHeader.Length + offset >= track.MatchOffset && track.TrackFile.Position < track.DataLength)
										track.TrackFile.Write(buff, offset, rdr.Block.FrameLengths[i]);

									offset += rdr.Block.FrameLengths[i];
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
							else
							{
								rdr.SkipContents();
							}
							break;
						default:
							rdr.SkipContents();
							break;
					}
				}
			}

			Console.Write('\b');
		}

		public static FileData RebuildSample(FileData file, SortedList<int, TrackData> tracks, Dictionary<string, AttachmentData> attachments, FileInfo srsFile, DirectoryInfo outDir)
		{
			uint crc = Crc32.StartValue;

			using (EbmlReader rdr = new EbmlReader(srsFile.FullName, EbmlReadMode.SRS))
			using (FileStream fsOut = new FileStream(Path.Combine(outDir.FullName, file.Name), FileMode.Create))
			{
				string currentAttachment = null;
				int clustercount = 0;
				while (rdr.Read())
				{
					// the ReSample element is the only part of the SRS file we don't want copied into the new sample.
					if (rdr.ElementType == EbmlElementType.ReSample)
					{
						rdr.SkipContents();
						continue;
					}

					fsOut.Write(rdr.Element.RawHeader, 0, rdr.Element.RawHeader.Length);
					crc = Crc32.GetCrc(crc, rdr.Element.RawHeader);

					switch (rdr.ElementType)
					{
						case EbmlElementType.Segment:
						case EbmlElementType.BlockGroup:
						case EbmlElementType.AttachmentList:
						case EbmlElementType.Attachment:
							// these elements have no useful info of their own, but we want to step into them to examine their children
							rdr.MoveToChild();
							break;
						case EbmlElementType.Cluster:
							// simple progress indicator since this can take a while (cluster is good because they're about 1mb each)
							Console.Write("\b{0}", Program.spinners[clustercount++ % Program.spinners.Length]);
							rdr.MoveToChild();
							break;
						case EbmlElementType.AttachedFileName:
							byte[] buff = rdr.ReadContents();
							fsOut.Write(buff, 0, buff.Length);
							crc = Crc32.GetCrc(crc, buff);
							currentAttachment = Encoding.UTF8.GetString(buff);
							break;
						case EbmlElementType.AttachedFileData:
							AttachmentData attachment = attachments[currentAttachment];
							// restore data from extracted attachments
							buff = new byte[rdr.Element.Length];
							attachment.AttachmentFile.Read(buff, 0, buff.Length);
							fsOut.Write(buff, 0, buff.Length);
							crc = Crc32.GetCrc(crc, buff);
							if ((file.Flags & FileData.FileDataFlags.AttachmentsRemoved) != 0)
								rdr.MoveToChild();  // really means do nothing in this case
							else
								rdr.SkipContents();
							break;
						case EbmlElementType.Block:
							TrackData track = tracks[rdr.Block.TrackNumber];
							// restore data from extracted tracks
							buff = new byte[rdr.Block.Length];
							track.TrackFile.Read(buff, 0, buff.Length);
							fsOut.Write(rdr.Block.RawBlockHeader, 0, rdr.Block.RawBlockHeader.Length);
							crc = Crc32.GetCrc(crc, rdr.Block.RawBlockHeader);
							fsOut.Write(buff, 0, buff.Length);
							crc = Crc32.GetCrc(crc, buff);
							rdr.MoveToChild();  // really means do nothing in this case
							break;
						default:
							// anything not caught above is considered metadata, so we copy it as is
							buff = rdr.ReadContents();
							fsOut.Write(buff, 0, buff.Length);
							crc = Crc32.GetCrc(crc, buff);
							break;
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
