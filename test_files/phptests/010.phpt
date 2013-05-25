--TEST--
RarEntry::getStream() function (good RAR file, one volume)
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php

$rar_file1 = rar_open(dirname(__FILE__).'/latest_winrar.rar');
$entries = rar_list($rar_file1);
echo count($entries)." files:\n\n";
//var_dump($entries);
foreach ($entries as $e) {
	$stream = $e->getStream();
	echo $e->getName().":\n";
	while (!feof($stream)) {
		echo fread($stream, 8192);
	}
	echo "\n\n";
}

echo "Done\n";
?>
--EXPECTF--
2 files:

1.txt:
11111

2.txt:
22222

Done
