--TEST--
RarEntry::getStream() function (good RAR file, several volumes)
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php

$rar_file1 = rar_open(dirname(__FILE__).'/multi.part1.rar');
$entries = rar_list($rar_file1);
echo count($entries)." files:\n\n";
//var_dump($entries);
function int32_to_hex($value) { 
  $value &= 0xffffffff; 
  return str_pad(strtoupper(dechex($value)), 8, "0", STR_PAD_LEFT); 
}
foreach ($entries as $e) {
	$stream = $e->getStream();
	if ($stream === false) {
		die("Failed to get stream.\n");
		break;
	}
	echo $e->getName().": ";
	$a = "";
	while (!feof($stream)) {
		$a .= fread($stream, 8192);
	}
	echo strlen($a)." bytes, CRC ";
	echo int32_to_hex(crc32($a))."\n\n"; //you can confirm they're equal to those given by $e->getCrc()
}

echo "Done\n";
?>
--EXPECTF--
3 files:

file1.txt: 18 bytes, CRC 52B28202

file2.txt: 17704 bytes, CRC F2C79881

file3.txt: 18 bytes, CRC BCBCE32E

Done
