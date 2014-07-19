--TEST--
RarEntry::getStream() on unicode entry
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php

$rar_file1 = rar_open(dirname(__FILE__).'/rar_unicode.rar');
$entry = rar_entry_get($rar_file1, "file1À۞.txt");
echo $entry."\n";
echo "\n";
$stream = $entry->getStream();
if ($stream !== false)
	while (!feof($stream)) {
		echo fread($stream, 8192);
	}

echo "\n";
	
echo "Done\n";
?>
--EXPECTF--
RarEntry for file "file1À۞.txt" (52b28202)

contents of file 1
Done
