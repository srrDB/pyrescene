--TEST--
RarEntry::getName() function with unicode filenames
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php

$rar_file1 = rar_open(dirname(__FILE__).'/rar_unicode.rar');
$entries = rar_list($rar_file1);
$name = reset($entries)->getName();
var_dump($name);
echo "\n";

echo "Done\n";
?>
--EXPECTF--
string(13) "file1À۞.txt"

Done
