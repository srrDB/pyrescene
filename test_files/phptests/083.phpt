--TEST--
RarArchive read_property handler non-int valid dimensions
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php

$f1 = dirname(__FILE__) . "/latest_winrar.rar";
$a = RarArchive::open($f1);

echo "string (\"0\"). {$a['0']}\n";
echo "string (\"1abc\"). {$a['1abc']}\n";
echo "float (0.001). {$a[0.001]}\n";
echo "string (\"0.001\"). {$a['0.001']}\n";

echo "\n";
echo "Done.\n";
--EXPECTF--
string ("0"). RarEntry for file "1.txt" (a0de71c0)

Notice: A non well formed numeric value encountered in %s on line %d
string ("1abc"). RarEntry for file "2.txt" (45a918de)
float (0.001). RarEntry for file "1.txt" (a0de71c0)
string ("0.001"). RarEntry for file "1.txt" (a0de71c0)

Done.
