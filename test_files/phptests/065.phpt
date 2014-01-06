--TEST--
Directory streams compatibility with RecursiveDirectoryIterator
--SKIPIF--
<?php
if(!extension_loaded("rar")) die("skip");
--FILE--
<?php

$a = "rar://" . dirname(__FILE__) . '/dirs_and_extra_headers.rar#';
$it = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($a),
	RecursiveIteratorIterator::LEAVES_ONLY);

$it->rewind();
while($it->valid()) {
	if (!$it->isDot()) {
		echo 'SubPathName: ' . rawurldecode($it->getSubPathName()) . "\n";
		echo 'SubPath:     ' . rawurldecode($it->getSubPath()) . "\n";
		echo 'Key:         ' . $it->key() . "\n\n";
	}
	$it->next();
}

echo "Done.\n";
--EXPECTF--
SubPathName: file1.txt
SubPath:     
Key:         rar://%s/dirs_and_extra_headers.rar#%sfile1.txt

SubPathName: file2_אּ.txt
SubPath:     
Key:         rar://%s/dirs_and_extra_headers.rar#%sfile2_%EF%AC%B0.txt

SubPathName: with_streams.txt
SubPath:     
Key:         rar://%s/dirs_and_extra_headers.rar#%swith_streams.txt

SubPathName: אּ%s%2Fempty%2E%sfile7.txt
SubPath:     אּ%s%2Fempty%2E
Key:         rar://%s/dirs_and_extra_headers.rar#%s%EF%AC%B0%s%252Fempty%252E%sfile7.txt

SubPathName: אּ%sfile3.txt
SubPath:     אּ
Key:         rar://%s/dirs_and_extra_headers.rar#%s%EF%AC%B0%sfile3.txt

SubPathName: אּ%sfile4_אּ.txt
SubPath:     אּ
Key:         rar://%s/dirs_and_extra_headers.rar#%s%EF%AC%B0%sfile4_%EF%AC%B0.txt

SubPathName: אּ%sאּ_2%sfile5.txt
SubPath:     אּ%sאּ_2
Key:         rar://%s/dirs_and_extra_headers.rar#%s%EF%AC%B0%s%EF%AC%B0_2%sfile5.txt

SubPathName: אּ%sאּ_2%sfile6_אּ.txt
SubPath:     אּ%sאּ_2
Key:         rar://%s/dirs_and_extra_headers.rar#%s%EF%AC%B0%s%EF%AC%B0_2%sfile6_%EF%AC%B0.txt

Done.
