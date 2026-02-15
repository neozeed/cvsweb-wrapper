#!/usr/bin/perl
use strict;
use warnings;
use Fcntl ':flock';

my $cache_dir        = "/var/cache/cvsweb";
my $orig_script      = "/usr/lib/cgi-bin/cvsweb-orig.cgi";
my $max_concurrent   = 3;
my $max_query_length = 300;
my $max_age_seconds  = 86400;

mkdir $cache_dir unless -d $cache_dir;

my $script = $ENV{'SCRIPT_NAME'} // '';
my $qs     = $ENV{'QUERY_STRING'} // '';

if (length($qs) > $max_query_length) {
    print "Status: 400 Bad Request\n";
    print "Content-Type: text/plain\n\n";
    print "Query too long.\n";
    exit;
}

my $uri = $script;
$uri .= "?$qs" if $qs ne '';
$uri =~ s/[^A-Za-z0-9]/_/g;
my $cache_file = "$cache_dir/$uri.html";

if (-f $cache_file) {
    my $age = time - (stat($cache_file))[9];
    if ($age < $max_age_seconds) {
        open(my $fh, "<", $cache_file);
        print "Content-Type: text/html\n\n";
        print while (<$fh>);
        close($fh);
        exit;
    }
}

my $running = `pgrep -fc cvsweb-orig.cgi`;
chomp($running);

if ($running >= $max_concurrent) {
    print "Status: 503 Service Unavailable\n";
    print "Content-Type: text/plain\n\n";
    print "Server busy, try again shortly.\n";
    exit;
}

open(my $lock, ">", "$cache_file.lock") or die;
flock($lock, LOCK_EX);

if (-f $cache_file) {
    my $age = time - (stat($cache_file))[9];
    if ($age < $max_age_seconds) {
        open(my $fh, "<", $cache_file);
        print "Content-Type: text/html\n\n";
        print while (<$fh>);
        close($fh);
        close($lock);
        exit;
    }
}

my $output = qx{/usr/bin/perl -T $orig_script};

# Only cache if it looks valid HTML
if ($output =~ m/<html/i && $output !~ m/503 Service Unavailable/i) {
    open(my $fh, ">", $cache_file);
    print $fh $output;
    close($fh);
}

close($lock);

print $output;

