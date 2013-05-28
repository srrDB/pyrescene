--TEST--
rar_list()/rar_entry_get() with not first volume
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php
$rar_file1 = rar_open(dirname(__FILE__).'/multi.part2.rar');
$entries = rar_list($rar_file1);
echo "Number of entries: " . count($entries) . "\n";
echo reset($entries)."\n";
$e = rar_entry_get($rar_file1, "file2.txt");
var_dump($e);
$e = rar_entry_get($rar_file1, "file3.txt");
echo $e."\n";

echo "Done\n";
--EXPECTF--
Number of entries: 1
RarEntry for file "file3.txt" (bcbce32e)

Warning: rar_entry_get(): cannot find file "file2.txt" in Rar archive "%s in %s on line %d
bool(false)
RarEntry for file "file3.txt" (bcbce32e)
Done
