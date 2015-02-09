--TEST--
RarEntry::getStream() function (broken set fixed with volume callback)
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php
function resolve($vol) {
	if (preg_match('/_broken/', $vol))
		return str_replace('_broken', '', $vol);
	else
		return null;
}
function int32_to_hex($value) { 
  $value &= 0xffffffff; 
  return str_pad(strtoupper(dechex($value)), 8, "0", STR_PAD_LEFT); 
}
$rar_file1 = rar_open(dirname(__FILE__).'/multi_broken.part1.rar', null, 'resolve');
foreach ($rar_file1 as $e) {
	$stream = $e->getStream();
	echo $e->getName().": ";
	$a = "";
	while (is_resource($stream) && !feof($stream)) {
		$a .= fread($stream, 8192);
	}
	echo strlen($a)." bytes, CRC ";
	echo int32_to_hex(crc32($a))."\n\n"; //you can confirm they're equal to those given by $e->getCrc()
}

echo "Done\n";
?>
--EXPECTF--
file1.txt: 18 bytes, CRC 52B28202

file2.txt: 17704 bytes, CRC F2C79881

file3.txt: 18 bytes, CRC BCBCE32E

Done
