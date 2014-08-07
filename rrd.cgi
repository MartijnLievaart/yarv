#!/usr/bin/perl
# -*- mode: perl; -*-

use CGI::Carp qw(fatalsToBrowser);
use CGI qw(:standard);

# FireFox warning:
# A form was submitted in the windows-1252 encoding which cannot encode all Unicode characters, so user input may get corrupted. To avoid this problem, the page should be changed so that the form is submitted in the UTF-8 encoding either by changing the encoding of the page itself to UTF-8 or by specifying accept-charset=utf-8 on the form element.

use Date::Manip;
use HTML::Entities;
use URI::Escape;
use RRDs;
use POSIX; # strftime
use FindBin;

use strict;
use warnings;
no warnings 'redefine';

my $default_width = 800;
my $default_height = 250;

our $RRDdir = `grep RRDdir /etc/ping2rrd`;
$RRDdir =~ s/.*=\s*(.*?)\s*$/$1/;
die 'No RRDdir' unless $RRDdir and -d $RRDdir;

=pod

print
    header,
    start_html('RRD viewer'),
    "<table>";

print map { "<tr><td>$_</td><td>$ENV{$_}</td></tr>" } sort keys %ENV;

print
    "</table>",
    end_html();

exit;

=cut

(my $yarv_html = $ENV{SCRIPT_FILENAME}) =~ s!(.*/).*!$1yarv.html!;
die "Cannot find $yarv_html" unless -r $yarv_html;

sub slurp {
    my ($fname) = @_;
    open my $fh, '<', $fname or die "Cannot open $fname: $!";
    return <$fh> if wantarray;
    local $/ = undef;
    return <$fh>;
};

our $js = slurp($yarv_html);
die '$RRDdir/rrd.def not found' unless -r "$RRDdir/rrd.def";
chomp(our @def = grep !/^\s*(?:#|$)/, slurp("$RRDdir/rrd.def"));


sub safe_html {
    join('', map(encode_entities($_), @_));
}


if (url_param('s')) {
    my $start = param('s');
    die "Illegal start: $start " unless $start =~ /^\d+$/;
    my $end = param('e');
    die "Illegal end: $end" unless $end =~ /^\d+$/;
    my $rrd = uri_unescape(param('r'));
    die "Illegal filename" if $rrd =~ /\.\./;
    my $width = param('w') || $default_width;
    die "Illegal width: $width" unless $width =~ /^\d+$/;
    my $height = param('h') || $default_height;
    die "Illegal height: $height" unless $height =~ /^\d+$/;
    print
	header({type=>'image/png'}),
	create_png($start, $end, $rrd, $width, $height)->{image};

    exit;
}

sub create_png {
    my ($start, $end, $rrd, $width, $height) = @_;

    # title is name of rrd without path (if any) ...
    (my $title = $rrd) =~ s!.*/!!;
    # ... together with the date(s)
    my $sd = strftime('%Y-%m-%d', localtime($start));
    my $ed = strftime('%Y-%m-%d', localtime($end));
    $title .= '   ' . (($sd eq $ed) ? $sd : "$sd - $ed");

    $rrd = "$RRDdir/$rrd.rrd";
    s/(\$\w+)/$1/eeg for @def;

    my $gi = RRDs::graphv('-',
			  "-s", $start,
			  "-e", $end,
			  "-h", $height,
			  "-w", $width,
			  "-t", $title,
			  @def);
    my $ERR=RRDs::error;
    die "ERROR in graph: $ERR\n" if $ERR;

    return $gi;
}


my @RRDs = sort map {m!.*/(.*)\.rrd$!; $1} glob("$RRDdir/*.rrd");
unless(@RRDs) {
    print
	header,
	start_html('RRD viewer'),
	"No RRDs found",
	end_html();
    exit;
}



print
    header,
    start_html('RRD viewer'),
    start_form(-name=>'form1'),
    popup_menu('RRD', \@RRDs),
    "Start:",
    textfield('start'),
    "End:",
    textfield('end'),
    submit,
    br,
    end_form, "\n";

my $start = uri_unescape(param('start'));
my $end = uri_unescape(param('end'));
my $rrd = uri_unescape(param('RRD')) || $RRDs[0];
my $d;
my @err;

if ($start or $end) {
    if ($start) {
	if (!($d = ParseDate($start))) {
	    push @err, "Invalid date '$start'";
	} else {
	    $start = UnixDate($d,"%s");
	}
    } else {
	push @err, "Missing start date";
    }
    if ($end) {
	if (!($d = ParseDate($end))) {
	    push @err, "Invalid date '$end'";
	} else {
	    $end = UnixDate($d,"%s");
#		$end = $d->secs_since_1970_GMT();
	}
    } else {
	$end = time;
	#push @err, "Missing end date";
    }
} else {
    $end = time;
    $start = time - 3600;
}
unless ($rrd) { push @err, "Missing rrd? Strange!"; }

if (!@err) {
    push @err, "Start must be before end" if $start >= $end;
}

if (@err) {
    print br, map { (strong(safe_html($_)), br) } @err;
} else {
    print xx($start, $end, $rrd, $default_width, $default_height);
}



print
    end_html;

exit;

# <!-- <img src='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAtklEQVQ4ja3SsWoCQRSF4Q+LpLYNUVD0FZJenyu4261aCZLgg6UWYdUuhUUKC7VwUBBnR3AvDDPcw/xzuHO4VgsLlPgL+0/oJ2uIDTL00EQfeegPqi53sMVHRP8MkHYMsMBXwmGO75hYopsA9LCKiXu8hPPxzoJX/D/r4DcmPjqDWUx85Bd2eKt64TYHDdcc7JxnkSdcXpK4xgFLzPGOIkBGKUhVZQEyrQMyqQMyrgOSPQMpUJwAQnMwXeQXxVYAAAAASUVORK5CYII=' onclick='zoomOut()'> -->


sub xx {
    my ($start, $end, $rrd, $width, $height) = @_;
    my $url = url();
    my $gi = create_png($start, $end, $rrd, $width, $height);
    my $graph_top = $gi->{graph_top};
    my $graph_left = $gi->{graph_left};
    my $t = $js;
    $t =~ s/(\$\w+)/$1/eeg;
    return $t;
}
