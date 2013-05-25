--TEST--
RarEntry::getStream() (file level password)
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php
echo "--> should fail (no password):\n";
$rar_file1 = rar_open(dirname(__FILE__).'/encrypted_only_files.rar');
$entries = rar_list($rar_file1);
var_dump(count($entries));
var_dump($entries[0]->getStream());
echo "\n";

echo "--> success (password is the same as the one given on rar_open):\n";
$rar_file2 = rar_open(dirname(__FILE__).'/encrypted_only_files.rar', 'samplepassword');
$entries = rar_list($rar_file2);
echo stream_get_contents($entries[0]->getStream());
echo "\n\n";

echo "--> should give incorrect data (password of 2nd file different from the one given on rar_open):\n";
echo rawurlencode(stream_get_contents($entries[1]->getStream()));
echo "\n\n";

echo "--> should give correct data (password of 2nd file is specified):\n";
echo stream_get_contents($entries[1]->getStream('samplepassword2'));
echo "\n\n";

echo "--> success (password is the same as the one given on rar_open, which shouldn't have been forgotten):\n";
echo stream_get_contents($entries[0]->getStream());
echo "\n\n";

echo "Done\n";
--EXPECTF--
--> should fail (no password):
int(2)

Warning: RarEntry::getStream(): ERAR_MISSING_PASSWORD (password needed but not specified) in %s on line %d
bool(false)

--> success (password is the same as the one given on rar_open):
Encrypted file 1 contents.

--> should give incorrect data (password of 2nd file different from the one given on rar_open):
t%09%A6%2B%0D%1B%F6%815%5E%E7%EC%C0%0BF%5EH%3A%C0%0D%815%5E%E7%EC%C0

--> should give correct data (password of 2nd file is specified):
Encrypted file 1 contents.

--> success (password is the same as the one given on rar_open, which shouldn't have been forgotten):
Encrypted file 1 contents.

Done
