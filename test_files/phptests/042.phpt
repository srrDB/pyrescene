--TEST--
rar_open() with volume find callback basic test
--SKIPIF--
<?php
if(!extension_loaded("rar")) die("skip");
--FILE--
<?php
chdir(dirname(__FILE__));
function volume_callback($vol) {
	if (preg_match('/_fail/', $vol))
		$ret = basename(str_replace('_fail', '', $vol));
	elseif (preg_match('/_broken/', $vol))
		$ret = basename(str_replace('_broken', '_fail', $vol));
	else
		$ret = null;
	echo "Not found:\n\t$vol\nReplacing with:\n\t$ret\n";
	return $ret;
}
$fn = dirname(__FILE__) . '/multi_broken.part1.rar';
$rar = RarArchive::open($fn, null, 'volume_callback');
foreach ($rar as $e) {
	echo "Entry: $e.\n";
}
echo "Done.\n";
--EXPECTF--
Not found:
	%smulti_broken.part2.rar
Replacing with:
	multi_fail.part2.rar
Not found:
	%smulti_fail.part2.rar
Replacing with:
	multi.part2.rar
Entry: RarEntry for file "file1.txt" (52b28202).
Entry: RarEntry for file "file2.txt" (f2c79881).
Entry: RarEntry for file "file3.txt" (bcbce32e).
Done.

