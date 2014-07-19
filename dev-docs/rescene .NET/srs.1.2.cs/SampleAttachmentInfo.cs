using System;
using System.IO;
using System.Text;

namespace ReSample
{
	class AttachmentData
	{
		public string Name = null;
		public long Size = 0;
		public FileStream AttachmentFile = null;
	}
}
