--TEST--
rar_close() liberates resource (PECL bug #9649)
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php
copy(dirname(__FILE__).'/latest_winrar.rar', dirname(__FILE__).'/temp.rar');
$rar_file1 = rar_open(dirname(__FILE__).'/temp.rar');
echo $rar_file1."\n";
$entries = rar_list($rar_file1);
$entry1 = reset($entries);
unset($entries);
echo $entry1."\n";
echo "\n";

rar_close($rar_file1);
echo $rar_file1."\n";
$entry1->extract(".");
unlink(dirname(__FILE__).'/temp.rar');
	
echo "Done\n";
?>
--EXPECTF--
RAR Archive "%s"
RarEntry for file "1.txt" (a0de71c0)

RAR Archive "%s" (closed)

Warning: RarEntry::extract(): The archive is already closed in %s on line %d
Done
