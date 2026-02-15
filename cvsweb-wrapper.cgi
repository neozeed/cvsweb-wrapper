#!/usr/bin/perl
use strict;
use warnings;
use Fcntl ':flock';


my $cache_dir = "/var/cache/cvsweb";
my $key = $ENV{'REQUEST_URI'};
$key =~ s/[^A-Za-z0-9]/_/g;

my $cache_file = "$cache_dir/$key.html";

if (-f $cache_file) {
    open(my $fh, "<", $cache_file);
    print "Content-Type: text/html\n\n";
    print while(<$fh>);
    close($fh);
    exit;
}

open(my $lock, ">", "$cache_file.lock") or die;
flock($lock, LOCK_EX);

# After lock, re-check cache exists
if (-f $cache_file) {
    open(my $fh, "<", $cache_file);
    print "Content-Type: text/html\n\n";
    print while(<$fh>);
    close($fh);
    close($lock);
    exit;
}

# run real cvsweb
my $output = `/usr/lib/cgi-bin/cvsweb-orig.cgi`;

open(my $fh, ">", $cache_file);
print $fh $output;
close($fh);

print $output;
