--TEST--
rar_entry_get() and RarEntry::getName() coherence
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php

$rar_file1 = rar_open(dirname(__FILE__).'/rar_unicode.rar');
$entries = rar_list($rar_file1);
$name = reset($entries)->getName();
$entryback = rar_entry_get($rar_file1, $name);
echo "$entryback\n";
echo "\n";

echo "Done\n";
?>
--EXPECTF--
RarEntry for file "file1À۞.txt" (52b28202)

Done
