using System;
using System.IO;
using System.Text;
using ReSample.Ebml;

namespace ReSample
{
	class TrackData
	{
		[Flags()]
		public enum TrackDataFlags : ushort
		{
			None = 0,
			BigFile = 0x4
		}

		public ushort TrackNumber = 0;
		public TrackDataFlags Flags = TrackDataFlags.None;
		public long DataLength = 0;
		public long MatchLength = 0;
		public long MatchOffset = 0;
		public byte[] SignatureBytes = null;
		public byte[] CheckBytes = null;
		public FileStream TrackFile = null;

		public TrackData()
		{
		}

		public TrackData(byte[] buff)
		{
			using (BinaryReader br = new BinaryReader(new MemoryStream(buff), Encoding.UTF8))
			{
				Flags = (TrackDataFlags)br.ReadUInt16();
				TrackNumber = br.ReadUInt16();
				DataLength = (Flags & TrackDataFlags.BigFile) != 0 ? br.ReadInt64() : br.ReadInt32();
				MatchOffset = br.ReadInt64();
				SignatureBytes = new byte[br.ReadUInt16()];
				br.Read(SignatureBytes, 0, SignatureBytes.Length);
			}
		}

		public byte[] Serialize()
		{
			bool bigFile = (Flags & TrackDataFlags.BigFile) != 0;
			int dataLength = sizeof(ushort) + sizeof(ushort) + (bigFile ? sizeof(long) : sizeof(int)) + sizeof(long) + sizeof(ushort) + SignatureBytes.Length;
			byte[] buff = new byte[dataLength];
			using (BinaryWriter bw = new BinaryWriter(new MemoryStream(buff)))
			{
				bw.Write((ushort)Flags);
				bw.Write(TrackNumber);
				if (bigFile)
					bw.Write(DataLength);
				else
					bw.Write((int)DataLength);
				bw.Write(MatchOffset);
				bw.Write((ushort)SignatureBytes.Length);
				bw.Write(SignatureBytes);
			}

			return buff;
		}

		public byte[] SerializeAsEbml()
		{
			byte[] data = Serialize();
			byte[] elementLengthCoded = EbmlHelper.MakeEbmlUInt(data.Length);
			byte[] element = new byte[EbmlElementIDs.ReSampleTrack.Length + elementLengthCoded.Length + data.Length];
			using (BinaryWriter bw = new BinaryWriter(new MemoryStream(element)))
			{
				bw.Write(EbmlElementIDs.ReSampleTrack);
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
				bw.Write(Encoding.ASCII.GetBytes("SRST"));
				bw.Write((uint)data.Length);
				bw.Write(data);
			}

			return chunk;
		}
	}
}
