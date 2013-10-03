--TEST--
Stream wrapper with volume find callback
--SKIPIF--
<?php
if(!extension_loaded("rar")) die("skip");
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
$stream = fopen("rar://" .
	dirname(__FILE__) . '/multi_broken.part1.rar' .
	"#file2.txt", "r", false,
	stream_context_create(array('rar'=>array('volume_callback'=>'resolve'))));
$a = stream_get_contents($stream);
echo strlen($a)." bytes, CRC ";
echo int32_to_hex(crc32($a))."\n\n"; //you can confirm they're equal to those given by $e->getCrc()
echo "Done.\n";
--EXPECTF--
17704 bytes, CRC F2C79881

Done.

