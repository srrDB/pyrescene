--TEST--
rar_open()/RarEntry::extract() (headers level password)
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php
$rar_file2 = rar_open(dirname(__FILE__).'/encrypted_headers.rar', 'samplepassword');
$entries = rar_list($rar_file2);

echo "Found " . count($entries) . " files.\n";
$tempfile = dirname(__FILE__).'/temp.txt';
@unlink($tempfile);
var_dump(reset($entries)->extract(false, $tempfile));
echo "Content of first one follows:\n";
echo file_get_contents($tempfile);
$stream = reset($entries)->getStream();
@unlink($tempfile);
echo "\n";

echo "Done\n";
--EXPECTF--
Found 2 files.
bool(true)
Content of first one follows:
Encrypted file 1 contents.
Done
