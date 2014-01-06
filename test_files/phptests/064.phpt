--TEST--
RAR directory-aware traversal with directory streams
--SKIPIF--
<?php
if(!extension_loaded("rar")) die("skip");
--FILE--
<?php
$a = "rar://" . dirname(__FILE__) . '/dirs_and_extra_headers.rar';
$stack = array();
$dh = opendir($a);
if ($dh) {
	array_push($stack, array("", $dh));
}
$indent = 0;
while (!empty($stack)) {
	$arr = array_pop($stack);
	$prefix = $arr[0];
	$cd = $arr[1];
	while (($file = readdir($cd)) !== false) {
		$u = $a . "#" . $prefix . "/" . $file;
		$isdir = is_dir($u);
		echo str_repeat("    ", $indent) .
			"- ".rawurldecode($file)." ". ($isdir?"(dir)":""). "\n";
		if ($isdir) {
			if (($dh = opendir($u)) === false)
				die("could not open $u");
			$indent++;
			array_push($stack, array($prefix, $cd));
			$cd = $dh;
			$prefix = $prefix . "/" . $file;
		}
	}
	$indent--;
}

echo "Done.\n";
--EXPECTF--
- allow_everyone_ni (dir)
- file1.txt 
- file2_אּ.txt 
- with_streams.txt 
- אּ (dir)
    - %2Fempty%2E (dir)
        - file7.txt 
    - empty (dir)
    - file3.txt 
    - file4_אּ.txt 
    - אּ_2 (dir)
        - file5.txt 
        - file6_אּ.txt 
Done.
