--TEST--
rar_list() function
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php

$rar_file1 = rar_open(dirname(__FILE__).'/linux_rar.rar'); 
$list1 = rar_list($rar_file1);
var_dump($list1);

$rar_file2 = rar_open(dirname(__FILE__).'/latest_winrar.rar'); 
$list2 = rar_list($rar_file2);
var_dump($list2);

$rar_file3 = rar_open(dirname(__FILE__).'/no_such_file.rar'); 
$list3 = rar_list($rar_file3);
var_dump($list3);

echo "Done\n";
?>
--EXPECTF--
array(2) {
  [0]=>
  object(RarEntry)#%d (%d) {
    ["rarfile%sprivate%s=>
    object(RarArchive)#%s (%s) {
    }
    ["position%sprivate%s=>
    int(0)
    ["name%sprivate%s=>
    string(9) "plain.txt"
    ["unpacked_size%sprivate%s=>
    int(15)
    ["packed_size%sprivate%s=>
    int(25)
    ["host_os%sprivate%s=>
    int(3)
    ["file_time%sprivate%s=>
    string(19) "2004-06-11 11:01:24"
    ["crc%sprivate%s=>
    string(8) "7728b6fe"
    ["attr%sprivate%s=>
    int(33188)
    ["version%sprivate%s=>
    int(29)
    ["method%sprivate%s=>
    int(51)
    ["flags%sprivate%s=>
    int(32800)
  }
  [1]=>
  object(RarEntry)#%d (%d) {
    ["rarfile%sprivate%s=>
    object(RarArchive)#%d (0) {
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
}
array(2) {
  [0]=>
  object(RarEntry)#%d (%d) {
    ["rarfile%sprivate%s=>
    object(RarArchive)#%d (%d) {
    }
    ["position%sprivate%s=>
    int(0)
    ["name%sprivate%s=>
    string(5) "1.txt"
    ["unpacked_size%sprivate%s=>
    int(5)
    ["packed_size%sprivate%s=>
    int(17)
    ["host_os%sprivate%s=>
    int(2)
    ["file_time%sprivate%s=>
    string(19) "2004-06-11 10:07:18"
    ["crc%sprivate%s=>
    string(8) "a0de71c0"
    ["attr%sprivate%s=>
    int(32)
    ["version%sprivate%s=>
    int(29)
    ["method%sprivate%s=>
    int(53)
    ["flags%sprivate%s=>
    int(36992)
  }
  [1]=>
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
}

Warning: rar_open(): Failed to open %s: ERAR_EOPEN (file open error) in %s on line %d

Warning: rar_list() expects parameter 1 to be RarArchive, boolean given in %s on line %d
NULL
Done
