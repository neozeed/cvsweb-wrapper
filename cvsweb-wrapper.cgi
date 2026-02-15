#!/usr/bin/perl
use strict;
use warnings;
use Fcntl ':flock';

# ------------------------------
# CONFIGURATION
# ------------------------------

# Cache directory
my $cache_dir        = "/var/cache/cvsweb";

# Path to original CVSWeb script
my $orig_script      = "/usr/lib/cgi-bin/cvsweb-orig.cgi";

# Max concurrent dynamic generator processes
my $max_concurrent   = 6;

# Max accepted length of query string
my $max_query_length = 300;

# Max age before refresh (in seconds)
my $max_age_seconds  = 86400;   # 24h

# Max allowed directory depth (slashes)
my $max_path_depth   = 15;

# ------------------------------
# INITIAL SETUP
# ------------------------------

# Ensure cache dir exists
unless (-d $cache_dir) {
    mkdir $cache_dir or die "Unable to create cache dir: $!";
}

# Grab request components
my $script_name = $ENV{'SCRIPT_NAME'} // '';
my $query       = $ENV{'QUERY_STRING'} // '';
my $request_uri = $ENV{'REQUEST_URI'} // '';

# ------------------------------
# VALIDATION / SAFETY CHECKS
# ------------------------------

# Reject pathological query strings
if (length($query) > $max_query_length) {
    print "Status: 400 Bad Request\n";
    print "Content-Type: text/plain\n\n";
    print "Query string too long.\n";
    exit;
}

# Limit absurd path depth (protect against infinite recursion abuse)
{
    my $depth = () = $request_uri =~ /\//g;
    if ($depth > $max_path_depth) {
        print "Status: 400 Bad Request\n";
        print "Content-Type: text/plain\n\n";
        print "Path depth exceeds safe limits.\n";
        exit;
    }
}

# ------------------------------
# FORM CACHE KEY
# ------------------------------

# Build a cache key based on exact path + query
# Replace non-alphanumeric with underscores
(my $key = $request_uri) =~ s/[^A-Za-z0-9]/_/g;
my $cache_file = "$cache_dir/$key.html";

# ------------------------------
# SERVE FROM CACHE (if valid)
# ------------------------------

if (-f $cache_file) {
    my $age = time - (stat($cache_file))[9];
    if ($age < $max_age_seconds) {
        open(my $fh, '<', $cache_file) or last;
	print "Content-Type: text/html\n";
	print "Cache-Control: public, max-age=600\n";
	print "X-CVS-CACHE: HIT\n";
	print "Vary: Accept-Encoding\n\n";
        print while (<$fh>);
        close $fh;
        exit;
    }
}

# ------------------------------
# GLOBAL CONCURRENCY LIMIT
# ------------------------------

# Count currently running instances of original script
my $running = `pgrep -fc cvsweb-orig.cgi`;
chomp $running;

if ($running >= $max_concurrent) {
    print "Status: 503 Service Unavailable\n";
    print "Content-Type: text/plain\n\n";
    print "Server busy, try again shortly.\n";
    exit;
}

# ------------------------------
# FILE-LEVEL LOCKING (prevent races)
# ------------------------------

open(my $lock, '>', "$cache_file.lock") or die "Unable to lock: $!";
flock($lock, LOCK_EX);

# Re-check cache now that we hold the lock
if (-f $cache_file) {
    my $age = time - (stat($cache_file))[9];
    if ($age < $max_age_seconds) {
        open(my $fh, '<', $cache_file) or last;
	print "Content-Type: text/html\n";
        print while (<$fh>);
        close $fh;
        close $lock;
        exit;
    }
}

# ------------------------------
# GENERATE FRESH OUTPUT
# ------------------------------

# Run the original script directly without extra shell spawning
# my $output = qx{/usr/bin/perl -T $orig_script};
my $raw = `/usr/lib/cgi-bin/cvsweb-orig.cgi`;

# Split headers and body
my ($headers, $body) = split(/\r?\n\r?\n/, $raw, 2);

# Only cache body
if (defined $body && $body =~ m/<html/i && $body !~ /503 Service Unavailable/i) {
    open(my $fh, '>', $cache_file) or warn "Unable to save cache: $!";
    print $fh $body;
    close $fh;
}


# ------------------------------
# CACHE ONLY VALID HTML
# ------------------------------

if (defined $output && $output =~ m/<html/i && $output !~ /503 Service Unavailable/i) {
    open(my $fh, '>', $cache_file) or warn "Unable to save cache: $!";
    print $fh $output;
    close $fh;
}

close $lock;

# ------------------------------
# SEND RESPONSE
# ------------------------------

print $output;
exit;

