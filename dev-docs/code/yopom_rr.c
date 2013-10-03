#include	<stdio.h>
#include	<stdlib.h>
#include	<mem.h>

extern void far _calc_CRC32(unsigned long far *CRC, const void far *buff, const unsigned int buff_count);

#define _subData_DataSectors 		28423
//#define _subData_RecoverySectors 	763
#define _subData_RecoverySectors 	2


char *rr[_subData_RecoverySectors];
char onesector[512];
int rrSlice = 0;

FILE *InpFile;
FILE *OutFile;
FILE *TmpFile;

unsigned long RawData_Len = 14552348Ul;
unsigned long currentSector = 0;
unsigned long RawD_Pos;

int killME = 0;

unsigned long crc32_on_sector_buff(void) {
   unsigned long running_CRC32 = ~0;    // precondition to -1
  _calc_CRC32(&running_CRC32, onesector, 512);
   running_CRC32 = ~running_CRC32;

killME++;
if (killME < 5) {
printf("ADJ CRC is %08lx\n", running_CRC32);
printf("Bytes in sector are %02x %02x %02x %02x\n", onesector[0], onesector[1], onesector[2], onesector[3]);
}
  return ( running_CRC32);

//  return ( ~running_CRC32);
}


void init_rr_array(void) {
   int i;
   char *tmpP;
   for (i = 0; (i < _subData_RecoverySectors); i++) {
printf("Alloc %d of %d blocks\n", i, _subData_RecoverySectors);


      tmpP = (char *) malloc(512);
      if (tmpP == NULL) {
	printf("\n\nError: Not enough memory for rr array\n");
	exit(0);
      }
      memset(tmpP, 0, 512);
      rr[i] = tmpP;
   }
printf("Recovery Block Arr Init Complete\n");

}



int gen_new_recovery_block(void) {
   int i, rcount;
   int rrSlice = 0;
   long tMPpos;
   unsigned this_CRC16;

   RawD_Pos = 0;

   while (RawD_Pos < RawData_Len) {   //read data 1 sector at a time.  pad the last sector with 0's
      if ( (RawData_Len - RawD_Pos) >= 512) {
	 rcount = fread (onesector,1,512,InpFile);
	 RawD_Pos += 512;
      }
      else   {
	tMPpos = RawD_Pos;
	rcount = fread (onesector,1,(int)(RawData_Len - tMPpos),InpFile);
	//rarfs.Read(sector, 0, (int)(RawData_Len - tMPpos));
	RawD_Pos = RawData_Len;
	for (i = (int)(RawData_Len - RawD_Pos); i < 512; i++)
	   onesector[i] = 0;
      }


      if (rcount == 0)
	 return(1);

       // calculate the crc32 for the sector and store the 2 low-order bytes
	 ///  ushort sectorCrc = (ushort)(UpdateCrc(0xffffffff, sector, 0, sector.Length) & 0xffff);
      this_CRC16 = (unsigned) ( crc32_on_sector_buff() & 0xffffffffUL);

if (this_CRC16 == 0x42e4) {
printf("Found correct crc\n");
if getchar();
}


      fwrite( &this_CRC16, sizeof ( this_CRC16), 1, TmpFile);
		// update the recovery sector parity data for this slice
      for (i = 0; i < 512; i++)
	 * (rr[rrSlice] + i) ^= onesector[i];
      if (++rrSlice % _subData_RecoverySectors == 0)
	 rrSlice = 0;
   } // end while

printf("Writing %d RecoveryDataSectors to output file\n", _subData_RecoverySectors);
   for (i = 0; (i < _subData_RecoverySectors); i++)
      fwrite(rr[i], 512, 1, OutFile);
   return(0);
}



// Input file is named rawd
// Output file is named chkrec


int main(void) {
   int status;

   if  ((InpFile = fopen("rawd","rb")) == NULL) {
      printf("Error on input file open\n");
      return(1);
   }
   if ((OutFile = fopen("chkrec","wb")) == NULL) {
      printf("Error on output file create\n");
      return(2);
   }
   if ((TmpFile = fopen("$$$zz$","wb")) == NULL) {
      printf("Error on TEMP file create\n");
      return(3);
   }

   init_rr_array();
   status = gen_new_recovery_block();

   if (status)
      printf("Error on reading data\n");


   fclose(InpFile);
   fclose(OutFile);
   fclose(TmpFile);
   return(0);
}


