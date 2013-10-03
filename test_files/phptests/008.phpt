--TEST--
rar_entry_get() function
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php

$rar_file1 = rar_open(dirname(__FILE__).'/multi.part1.rar');
$entry = rar_entry_get($rar_file1, "file1.txt");
echo "$entry\n";
$entry = rar_entry_get($rar_file1, "nonexistent_file.txt");
var_dump($entry);
echo "\n";

$rar_file2 = rar_open(dirname(__FILE__).'/nonexistent.rar'); 
$entry = rar_entry_get($rar_file2, "file1.txt");
var_dump($entry);
echo "\n";

echo "Done\n";
?>
--EXPECTF--
RarEntry for file "file1.txt" (52b28202)

Warning: rar_entry_get(): cannot find file "nonexistent_file.txt" in Rar archive "%s" in %s on line %d
bool(false)


Warning: rar_open(): Failed to open %s: ERAR_EOPEN (file open error) in %s on line %d

Warning: rar_entry_get() expects parameter 1 to be RarArchive, boolean given in %s on line %d
NULL

Done
