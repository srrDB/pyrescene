--TEST--
RarEntry::extract() (file level password)
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--CLEAN--
@unlink(dirname(__FILE__).'/extract_temp');
--FILE--
<?php
$dest = dirname(__FILE__).'/extract_temp';

echo "--> should fail (no password):\n";
$rar_file1 = rar_open(dirname(__FILE__).'/encrypted_only_files.rar');
$entries = rar_list($rar_file1);
var_dump(count($entries));
var_dump($entries[0]->extract(false, $dest));
echo "\n";

echo "--> success (password is the same as the one given on rar_open):\n";
$rar_file2 = rar_open(dirname(__FILE__).'/encrypted_only_files.rar', 'samplepassword');
$entries = rar_list($rar_file2);
var_dump($entries[0]->extract(false, $dest));
echo file_get_contents($dest);
unlink($dest);
echo "\n\n";

echo "--> should fail (password of 2nd file different from the one given on rar_open):\n";
var_dump($entries[1]->extract(false, $dest));
echo "\n\n";

echo "--> should give correct data (password of 2nd file is specified):\n";
var_dump($entries[1]->extract(false, $dest, 'samplepassword2'));
echo file_get_contents($dest);
unlink($dest);
echo "\n\n";

echo "Done\n";
--EXPECTF--
--> should fail (no password):
int(2)

Warning: RarEntry::extract(): ERAR_MISSING_PASSWORD (password needed but not specified) in %s on line %d
bool(false)

--> success (password is the same as the one given on rar_open):
bool(true)
Encrypted file 1 contents.

--> should fail (password of 2nd file different from the one given on rar_open):

Warning: RarEntry::extract(): ERAR_BAD_DATA in %s on line %d
bool(false)


--> should give correct data (password of 2nd file is specified):
bool(true)
Encrypted file 1 contents.

Done
