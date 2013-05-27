--TEST--
Module info test
--SKIPIF--
<?php if(!extension_loaded("rar")) print "skip"; ?>
--FILE--
<?php

ob_start();
phpinfo(INFO_MODULES);
$phpinfo = ob_get_contents();
ob_end_clean();

$phpinfo = preg_replace('/\r\n?/', "\n", $phpinfo); //normalize line endings

$phpinfo = explode("\n", $phpinfo);

$found = false;
$empty = 0;
foreach ($phpinfo as $line) {
	if (!$found) {
		if ($line == "rar") {
			$found = true;
		}
	}
	else {
		if (empty($line)) {
			$empty++;
		}
		elseif ($empty == 1) {
			echo $line."\n";
		}
	}
}

echo "\n";
echo "Done.\n";
--EXPECTF--
RAR support => enabled
RAR EXT version => %d.%d.%s
Revision => %s
UnRAR version => %d.%d%spatch%d %d-%d-%d
UnRAR API version => %d extension %d

Done.
