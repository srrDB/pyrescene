--TEST--
RarEntry::extract() with unicode files
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php
$rar_file1 = rar_open(dirname(__FILE__).'/rar_unicode.rar');
$entries = rar_list($rar_file1);
$e = reset($entries);

$e->extract(false, dirname(__FILE__).'/temp.txt');

echo file_get_contents(dirname(__FILE__).'/temp.txt');
echo "\n";

@unlink(dirname(__FILE__).'/temp.txt');

echo "Done\n";
?>
--EXPECTF--
contents of file 1
Done
