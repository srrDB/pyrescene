--TEST--
RarEntry::getStream() function (bad RAR file)
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
	if ($i++ >= 2)
		break;
	//$e->extract(false, dirname(__FILE__).'/temp.txt');
	//echo "now stream\n";
	$stream = $e->getStream();
	echo $e->getName().": ";
	if ($stream === false) {
		echo "Could not get stream.\n\n";
		continue;
	}
	while (!feof($stream) && $i != 2) {
		echo fread($stream, 8192);
	}
	fclose($stream);
	echo "\n";

}

echo "Done\n";
?>
--EXPECTF--
51 files (will test only the first 4):

: The great battle of Gunprex versus Optiter!!!!!1
Gunprex, Fire!
So long, Optiter!

: 
Done
