--TEST--
RarEntry::extract() method (corrupt RAR file)
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php
$rar_file1 = rar_open(dirname(__FILE__).'/corrupted.rar');
$entries = rar_list($rar_file1);
echo count($entries)." files (will test only the first 4):\n\n";
//var_dump($entries);
$i = 0;
foreach ($entries as $e) {
	if ($i++ >= 4)
		break;
	echo "Extraction of file #$i:\n";
	$ret = $e->extract(false, dirname(__FILE__).'/temp.txt');
	if ($ret)
		echo "\tSUCCESS\n";
	else
		echo "\tFAILED\n";
	
	echo "\n";
}

@unlink(dirname(__FILE__).'/temp.txt');

echo "Done\n";
?>
--EXPECTF--
51 files (will test only the first 4):

Extraction of file #1:
	SUCCESS

Extraction of file #2:

Warning: RarEntry::extract(): ERAR_BAD_DATA in %s on line %d
	FAILED

Extraction of file #3:

Warning: RarEntry::extract(): ERAR_BAD_DATA in %s on line %d
	FAILED

Extraction of file #4:

Warning: RarEntry::extract(): ERAR_BAD_DATA in %s on line %d
	FAILED

Done
