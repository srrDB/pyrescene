--TEST--
RarEntry::extract() method
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php

$rar_file1 = rar_open(dirname(__FILE__).'/linux_rar.rar'); 
$entry1 = rar_entry_get($rar_file1, 'test file with whitespaces.txt');

$entry1->extract(dirname(__FILE__));
$contents11 = file_get_contents(dirname(__FILE__).'/test file with whitespaces.txt');
echo $contents11."\n";
@unlink(dirname(__FILE__).'/test file with whitespaces.txt');

$entry1->extract(false,dirname(__FILE__).'/1.txt');
$contents12 = file_get_contents(dirname(__FILE__).'/1.txt');
echo $contents12."\n";
@unlink(dirname(__FILE__).'/1.txt');

$rar_file2 = rar_open(dirname(__FILE__).'/latest_winrar.rar'); 
$entry2 = rar_entry_get($rar_file2, '2.txt');

$entry2->extract(dirname(__FILE__));
$contents21 = file_get_contents(dirname(__FILE__).'/2.txt');
echo $contents21."\n";
@unlink(dirname(__FILE__).'/2.txt');

$entry2->extract(false,dirname(__FILE__).'/some.txt');
$contents22 = file_get_contents(dirname(__FILE__).'/some.txt');
echo $contents22."\n";
@unlink(dirname(__FILE__).'/some.txt');

$entry2->extract(dirname(__FILE__));
var_dump(file_get_contents(dirname(__FILE__).'/2.txt'));
@unlink(dirname(__FILE__).'/2.txt');

$oldcwd = getcwd();
chdir(dirname(__FILE__));

var_dump($entry2);
var_dump($entry2->extract("",""));

@unlink('2.txt');

chdir($oldcwd);

echo "Done\n"; 
?>
--EXPECTF--
blah-blah-blah
blah-blah-blah
22222
22222
string(5) "22222"
object(RarEntry)#%d (%d) {
  ["rarfile%sprivate%s=>
  object(RarArchive)#3 (0) {
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
bool(true)
Done
