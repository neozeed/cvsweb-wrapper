#!/usr/bin/perl
use strict;
use warnings;
use Fcntl ':flock';

# -----------------------------
# CONFIG
# -----------------------------
my $cache_dir        = "/var/cache/cvsweb";
my $orig_script      = "/usr/lib/cgi-bin/cvsweb-orig.cgi";
my $max_concurrent   = 3;        # max dynamic generators
my $max_query_length = 150;      # reject pathological bots
my $max_age_seconds  = 86400;    # 24h cache expiry
# -----------------------------

# Ensure cache dir exists
mkdir $cache_dir unless -d $cache_dir;

# Get request info
my $script = $ENV{'SCRIPT_NAME'} // '';
my $qs     = $ENV{'QUERY_STRING'} // '';

# Reject pathological query strings
if (length($qs) > $max_query_length) {
    print "Status: 400 Bad Request\n";
    print "Content-Type: text/plain\n\n";
    print "Query too long.\n";
    exit;
}

## Normalize noisy parameters (collapse bot permutations)
#$qs =~ s/(annotate|sortby|f|only_with_tag)=[^&]+//g;
#$qs =~ s/&&/&/g;
#$qs =~ s/^&//;
#$qs =~ s/&$//;

# Build normalized cache key
#my $key = $script;
#$key .= "?$qs" if $qs ne '';
#$key =~ s/[^A-Za-z0-9]/_/g;
my $uri = $ENV{'REQUEST_URI'} // '';
exit if length($uri) > 300;  # sanity cap

my $key = $uri;
$key =~ s/[^A-Za-z0-9]/_/g;


my $cache_file = "$cache_dir/$key.html";

# -----------------------------
# Serve cached if fresh
# -----------------------------
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

# -----------------------------
# Global concurrency limit
# -----------------------------
my $running = `pgrep -fc cvsweb-orig.cgi`;
chomp $running;

if ($running >= $max_concurrent) {
    print "Status: 503 Service Unavailable\n";
    print "Content-Type: text/plain\n\n";
    print "Server busy, try again shortly.\n";
    exit;
}

# -----------------------------
# Lock per cache file
# -----------------------------
open(my $lock, ">", "$cache_file.lock") or die;
flock($lock, LOCK_EX);

# Re-check cache after acquiring lock
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

# -----------------------------
# Generate fresh output
# -----------------------------
my $output = qx{/usr/bin/perl -T $orig_script};

# Save to cache safely
if ($output && length($output) > 0) {
    open(my $fh, ">", $cache_file);
    print $fh $output;
    close($fh);
}

close($lock);

# Return response
print $output;
