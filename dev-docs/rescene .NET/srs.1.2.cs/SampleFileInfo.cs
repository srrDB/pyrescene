using System;
using System.IO;
using System.Text;
using ReSample.Ebml;

namespace ReSample
{
	class FileData
	{
		[Flags()]
		public enum FileDataFlags : ushort
		{
			None = 0,
			SimpleBlockFix = 0x1,
			AttachmentsRemoved = 0x2//,
			//BigFile = 0x4
		}

		public string Name;
		public FileDataFlags Flags = FileDataFlags.SimpleBlockFix | FileDataFlags.AttachmentsRemoved; //default to using new features
		public long Size;
		public uint Crc32;
		public string AppName;

		public FileData()
		{
		}

		public FileData(byte[] buff)
		{
			using (BinaryReader br = new BinaryReader(new MemoryStream(buff), Encoding.UTF8))
			{
				Flags = (FileDataFlags)br.ReadUInt16();
				AppName = new string(br.ReadChars(br.ReadUInt16()));
				Name = new string(br.ReadChars(br.ReadUInt16()));
				Size = br.ReadInt64();
				Crc32 = br.ReadUInt32();
			}
		}

		public FileData(string fileName)
		{
			FileInfo fi = new FileInfo(fileName);

			Name = fi.FullName;
			Size = fi.Length;
			/*
			uint crc = ReScene.Utility.Crc32.StartValue;
			using (FileStream fs = fi.OpenRead())
			{
				int blockcount = 0;
				byte[] buff = new byte[0x40000];
				while (fs.Position < fi.Length)
				{
					Console.Write("\b{0}", Program.spinners[++blockcount % Program.spinners.Length]);
					int bytesRead = fs.Read(buff, 0, buff.Length);
					crc = ReScene.Utility.Crc32.GetCrc(crc, buff, 0, bytesRead);
				}
				Console.Write("\b");
			}
			Crc32 = ~crc;
			*/
		}

		public byte[] Serialize()
		{
			byte[] appNameBytes = Encoding.UTF8.GetBytes(Program.appName);
			byte[] fileNameBytes = Encoding.UTF8.GetBytes(Path.GetFileName(Name));
			int dataLength = sizeof(ushort) + sizeof(ushort) + appNameBytes.Length + sizeof(ushort) + fileNameBytes.Length + sizeof(long) + sizeof(uint);
			byte[] buff = new byte[dataLength];
			using (BinaryWriter bw = new BinaryWriter(new MemoryStream(buff)))
			{
				bw.Write((ushort)Flags);
				bw.Write((ushort)Program.appName.Length);
				bw.Write(appNameBytes);
				bw.Write((ushort)Path.GetFileName(Name).Length);
				bw.Write(fileNameBytes);
				bw.Write(Size);
				bw.Write(Crc32);
			}

			return buff;
		}

		public byte[] SerializeAsEbml()
		{
			byte[] data = Serialize();
			byte[] elementLengthCoded = EbmlHelper.MakeEbmlUInt(data.Length);
			byte[] element = new byte[EbmlElementIDs.ReSampleFile.Length + elementLengthCoded.Length + data.Length];
			using (BinaryWriter bw = new BinaryWriter(new MemoryStream(element)))
			{
				bw.Write(EbmlElementIDs.ReSampleFile);
				bw.Write(elementLengthCoded);
				bw.Write(data);
			}

			return element;
		}

		public byte[] SerializeAsRiff()
		{
			byte[] data = Serialize();
			byte[] chunk = new byte[data.Length + 8];
			using (BinaryWriter bw = new BinaryWriter(new MemoryStream(chunk)))
			{
				bw.Write(Encoding.ASCII.GetBytes("SRSF"));
				bw.Write((uint)data.Length);
				bw.Write(data);
			}

			return chunk;
		}
	}
}
