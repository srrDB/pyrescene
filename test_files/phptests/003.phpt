--TEST--
rar_entry_get() function
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php

$rar_file1 = rar_open(dirname(__FILE__).'/linux_rar.rar'); 
$entry1 = rar_entry_get($rar_file1, 'test file with whitespaces.txt');
var_dump($entry1);

$rar_file2 = rar_open(dirname(__FILE__).'/latest_winrar.rar'); 
$entry2 = rar_entry_get($rar_file2, '2.txt');
var_dump($entry2);

$rar_file3 = rar_open(dirname(__FILE__).'/no_such_file.rar'); 
$entry3 = rar_entry_get($rar_file3, '2.txt');
var_dump($entry3);

echo "Done\n";
?>
--EXPECTF--
object(RarEntry)#%d (%d) {
  ["rarfile%sprivate%s=>
  object(RarArchive)#%d (%d) {
  }
  ["position%sprivate%s=>
  int(1)
  ["name%sprivate%s=>
  string(30) "test file with whitespaces.txt"
  ["unpacked_size%sprivate%s=>
  int(14)
  ["packed_size%sprivate%s=>
  int(20)
  ["host_os%sprivate%s=>
  int(3)
  ["file_time%sprivate%s=>
  string(19) "2004-06-11 11:01:32"
  ["crc%sprivate%s=>
  string(8) "21890dd9"
  ["attr%sprivate%s=>
  int(33188)
  ["version%sprivate%s=>
  int(29)
  ["method%sprivate%s=>
  int(51)
  ["flags%sprivate%s=>
  int(32800)
}
object(RarEntry)#%d (%d) {
  ["rarfile%sprivate%s=>
  object(RarArchive)#%d (%d) {
  }
  ["position%sprivate%s=>
  int(1)
  ["name%sprivate%s=>
  string(5) "2.txt"
  ["unpacked_size%sprivate%s=>
  int(5)
  ["packed_size%sprivate%s=>
  int(16)
  ["host_os%sprivate%s=>
  int(2)
  ["file_time%sprivate%s=>
  string(19) "2004-06-11 10:07:26"
  ["crc%sprivate%s=>
  string(8) "45a918de"
  ["attr%sprivate%s=>
  int(32)
  ["version%sprivate%s=>
  int(29)
  ["method%sprivate%s=>
  int(53)
  ["flags%sprivate%s=>
  int(37008)
}

Warning: rar_open(): Failed to open %s: ERAR_EOPEN (file open error) in %s on line %d

Warning: rar_entry_get() expects parameter 1 to be RarArchive, boolean given in %s on line %d
NULL
Done
