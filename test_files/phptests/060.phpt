--TEST--
RAR directory stream basic test
--SKIPIF--
<?php
if(!extension_loaded("rar")) die("skip");
--FILE--
<?php

echo "Root entries unencoded:\n";
$u = "rar://" .
	dirname(__FILE__) . '/dirs_and_extra_headers.rar*';

$d = dir($u);
while (false !== ($entry = $d->read())) {
   echo $entry."\n";
}
$d->close();
	
echo "\nRoot entries encoded:\n";
$u = "rar://" .
	dirname(__FILE__) . '/dirs_and_extra_headers.rar';

$d = dir($u);
while (false !== ($entry = $d->read())) {
   echo $entry."\n";
}
$d->close();
	
echo "\nSub-root directory entries unencoded:\n";
$u = "rar://" .
	dirname(__FILE__) . '/dirs_and_extra_headers.rar*#%EF%AC%B0';

$d = dir($u);
while (false !== ($entry = $d->read())) {
   echo $entry."\n";
}

echo "\nDone.\n";
--EXPECTF--
Root entries unencoded:
allow_everyone_ni
file1.txt
file2_אּ.txt
with_streams.txt
אּ

Root entries encoded:
allow_everyone_ni
file1.txt
file2_%EF%AC%B0.txt
with_streams.txt
%EF%AC%B0

Sub-root directory entries unencoded:
%2Fempty%2E
empty
file3.txt
file4_אּ.txt
אּ_2

Done.
