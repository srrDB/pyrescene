--TEST--
RarEntry::getStream() with directory
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php
$rar_file1 = rar_open(dirname(__FILE__).'/directories.rar');
$e = rar_entry_get($rar_file1, "emptydir");
$stream = $e->getStream();
var_dump($stream);
var_dump(feof($stream));
var_dump(fread($stream, 200));
var_dump(feof($stream));

echo "Done\n";
--EXPECTF--
resource(%d) of type (stream)
bool(false)
string(0) ""
bool(true)
Done
