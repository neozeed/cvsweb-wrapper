#!/usr/bin/perl
use strict;
use warnings;
use Fcntl ':flock';
use File::Path qw(make_path);

# ----------------------------------------------------
# CONFIG
# ----------------------------------------------------
my $orig_script = "/usr/lib/cgi-bin/cvsweb-orig.cgi";
my $cache_dir   = "/var/cache/cvsweb";
my $ttl_seconds = 600;   # 10 minute TTL

make_path($cache_dir) unless -d $cache_dir;

# ----------------------------------------------------
# BUILD CANONICAL CACHE KEY
# ----------------------------------------------------

my $path  = $ENV{'PATH_INFO'}      || '';
my $query = $ENV{'QUERY_STRING'}   || '';

# Prevent infinite path abuse like /i386/i386/i386/...
if ($path =~ m{(\/[^\/]+){20,}}) {
    print "Status: 400 Bad Request\n";
    print "Content-Type: text/plain\n\n";
    print "Path too deep\n";
    exit;
}

# Normalize query string ordering
if ($query) {
    my @params = split(/[;&]/, $query);
    @params = sort @params;
    $query = join("&", @params);
}

my $key = $path . ($query ? "?$query" : "");
$key =~ s/[^A-Za-z0-9]/_/g;

my $cache_file = "$cache_dir/$key.html";
my $lock_file  = "$cache_file.lock";

# ----------------------------------------------------
# SERVE FROM CACHE IF VALID
# ----------------------------------------------------

if (-f $cache_file) {
    my $age = time - (stat($cache_file))[9];
    if ($age < $ttl_seconds) {
        print "Content-Type: text/html\n";
        print "Cache-Control: public, max-age=$ttl_seconds\n";
        print "X-CVS-CACHE: HIT\n\n";

        open(my $fh, '<', $cache_file);
        print while (<$fh>);
        close($fh);
        exit;
    }
}

# ----------------------------------------------------
# LOCK
# ----------------------------------------------------

open(my $lock, '>', $lock_file) or die "Cannot create lock";
flock($lock, LOCK_EX);

# Re-check cache after locking
if (-f $cache_file) {
    my $age = time - (stat($cache_file))[9];
    if ($age < $ttl_seconds) {
        print "Content-Type: text/html\n";
        print "Cache-Control: public, max-age=$ttl_seconds\n";
        print "X-CVS-CACHE: HIT\n\n";

        open(my $fh, '<', $cache_file);
        print while (<$fh>);
        close($fh);
        close($lock);
        exit;
    }
}

# ----------------------------------------------------
# EXECUTE ORIGINAL CGI PROPERLY
# ----------------------------------------------------

# Reconstruct environment for proper CGI execution
$ENV{'SCRIPT_NAME'} = "/cgi-bin/cvsweb.cgi";
$ENV{'PATH_INFO'}   = $path;
$ENV{'QUERY_STRING'}= $query;

# Capture raw CGI output
my $raw_output = `$orig_script`;

# Split headers from body
my ($headers, $body) = split(/\r?\n\r?\n/, $raw_output, 2);

# Fallback safety
$body ||= '';

# ----------------------------------------------------
# CACHE ONLY VALID HTML
# ----------------------------------------------------

if ($body =~ m/<html/i &&
    $body !~ /503 Service Unavailable/i &&
    length($body) > 500)
{
    open(my $fh, '>', $cache_file) or warn "Unable to save cache: $!";
    print $fh $body;
    close($fh);
}

close($lock);

# ----------------------------------------------------
# OUTPUT RESPONSE
# ----------------------------------------------------

print "Content-Type: text/html\n";
print "Cache-Control: public, max-age=$ttl_seconds\n";
print "X-CVS-CACHE: MISS\n\n";
print $body;
