--TEST--
RAR file stream stat
--SKIPIF--
<?php
if(!extension_loaded("rar")) die("skip");
--FILE--
<?php
umask(0);
$stream = fopen("rar://" .
	dirname(__FILE__) . '/latest_winrar.rar' .
	"#1.txt", "r");
print_r(array_slice(fstat($stream), 13));

echo "Done.\n";
--EXPECTF--
Array
(
    [dev] => 0
    [ino] => 0
    [mode] => 33206
    [nlink] => 1
    [uid] => 0
    [gid] => 0
    [rdev] => 0
    [size] => 5
    [atime] => 0
    [mtime] => 1086948439
    [ctime] => 0
    [blksize] => %s
    [blocks] => %s
)
Done.
