--TEST--
RarEntry::extract() function (broken set fixed with volume callback)
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
echo "Fail:\n";
$rar_file1 = rar_open(dirname(__FILE__).'/multi_broken.part1.rar');
$entry = $rar_file1->getEntry('file2.txt');

echo "\nSuccess:\n";
$rar_file1 = rar_open(dirname(__FILE__).'/multi_broken.part1.rar', null, 'resolve');
$entry = $rar_file1->getEntry('file2.txt');
$entry->extract(null, dirname(__FILE__) . "/temp_file2.txt");
echo int32_to_hex(crc32(file_get_contents(dirname(__FILE__) . "/temp_file2.txt")));
echo "\n";
echo "Done\n";
?>
--CLEAN--
<?php
@unlink(dirname(__FILE__) . "/temp_file2.txt");
--EXPECTF--
Fail:

Warning: RarArchive::getEntry(): Volume %smulti_broken.part2.rar was not found in %s on line %d

Warning: RarArchive::getEntry(): ERAR_EOPEN (file open error) in %s on line %d

Success:
F2C79881
Done
