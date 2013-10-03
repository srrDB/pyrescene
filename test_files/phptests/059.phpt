--TEST--
url stat test
--SKIPIF--
<?php
if(!extension_loaded("rar")) die("skip");
--FILE--
<?php
umask(0);
$inex_rar = "rar://" .
	dirname(__FILE__) . '/not_found.rar' .
	"#emptydir";

echo "RAR not found:\n";
var_dump(stat($inex_rar));

$inex_entry = "rar://" .
	dirname(__FILE__) . '/dirlink_unix.rar' .
	"#inexistent entry";

echo "\nRAR entry not found:\n";
var_dump(stat($inex_entry));
	
$root1 = "rar://" .
	dirname(__FILE__) . '/dirlink_unix.rar';

echo "\nRAR root:\n";
$statr1 = stat($root1);
print_r(array_slice($statr1, 13));
echo "\nRAR root is dir:\n";
var_dump(is_dir($root1));
	
$root2 = "rar://" .
	dirname(__FILE__) . '/dirlink_unix.rar#';

echo "\nRAR root variant 2 matches:\n";
var_dump(stat($root2) == $statr1);
	
$root3 = "rar://" .
	dirname(__FILE__) . '/dirlink_unix.rar#/';
echo "\nRAR root variant 3 matches:\n";
var_dump(stat($root3) == $statr1);

$file = "rar://" .
	dirname(__FILE__) . '/dirlink_unix.rar' .
	"#file";

echo "\nRegular file:\n";
print_r(array_slice(stat($file), 13));
	
$dir = "rar://" .
	dirname(__FILE__) . '/dirlink_unix.rar' .
	"#emptydir";
echo "\nRegular file:\n";
print_r(array_slice(stat($dir), 13));

echo "Done.\n";
--EXPECTF--
RAR not found:

Warning: stat(): Failed to open %snot_found.rar: ERAR_EOPEN (file open error) in %s on line %d

Warning: stat(): stat failed for rar://%s/not_found.rar#emptydir in %s on line %d
bool(false)

RAR entry not found:

Warning: stat(): Found no entry inexistent entry in archive %sdirlink_unix.rar in %s on line %d

Warning: stat(): stat failed for rar://%s/dirlink_unix.rar#inexistent entry in %s on line %d
bool(false)

RAR root:
Array
(
    [dev] => 0
    [ino] => 0
    [mode] => 16895
    [nlink] => 1
    [uid] => 0
    [gid] => 0
    [rdev] => 0
    [size] => 0
    [atime] => 0
    [mtime] => 312768000
    [ctime] => 0
    [blksize] => %s
    [blocks] => %s
)

RAR root is dir:
bool(true)

RAR root variant 2 matches:
bool(true)

RAR root variant 3 matches:
bool(true)

Regular file:
Array
(
    [dev] => 0
    [ino] => 0
    [mode] => 33188
    [nlink] => 1
    [uid] => 0
    [gid] => 0
    [rdev] => 0
    [size] => 8
    [atime] => 0
    [mtime] => 1259625512
    [ctime] => 0
    [blksize] => %s
    [blocks] => %s
)

Regular file:
Array
(
    [dev] => 0
    [ino] => 0
    [mode] => 16877
    [nlink] => 1
    [uid] => 0
    [gid] => 0
    [rdev] => 0
    [size] => 0
    [atime] => 0
    [mtime] => 1259625807
    [ctime] => 0
    [blksize] => %s
    [blocks] => %s
)
Done.
