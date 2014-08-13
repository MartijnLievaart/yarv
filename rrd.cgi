#!/usr/bin/perl
# -*- mode: perl; -*-

use CGI::Carp qw(fatalsToBrowser);
use CGI qw(:standard);


# FIXME: Let the user choose their timezone!


use Date::Manip;
use HTML::Entities;
use URI::Escape;
use RRDs;
use POSIX; # strftime
use FindBin;
use File::Glob qw/bsd_glob/;

use strict;
use warnings;
no warnings 'redefine';

use constant CONF_FILE => '/projects/yarv/yarv.conf';

my $default_width = 800;
my $default_height = 250;

our %colormap = colornames();
my %modconf = read_yarv_conf();


sub url_param {
        param @_;
}

my $module = url_param('module') || $modconf{'*'}{default_module};
die "Unknown module" unless defined $module and exists $modconf{$module};


my %config = %{$modconf{'*'}} if exists $modconf{'*'};
#use Data::Dumper;
#print Dumper(\%config); exit 0;
%config = (%config, %{$modconf{$module}});
if ($config{geometry}) {
        ($config{width}, $config{height}) = split(/x/, $config{geometry});
}
$config{width} = $default_width unless $config{width};
$config{height} = $default_height unless $config{height};

our $RRD_dir = $config{directory}; # 'Variable will not stay shared...'
`logger RRD_dir=$RRD_dir`;
die 'No RRDdir' unless $RRD_dir and -d $RRD_dir;
my $RRD_glob = $config{glob} || '*.rrd';
$RRD_glob = "$RRD_dir/$RRD_glob";

my $yarv_html = $config{html};
unless ($yarv_html) {
        ($yarv_html = $ENV{SCRIPT_FILENAME}) =~ s!(.*/).*!$1yarv.html!;
}

die "Cannot find $yarv_html" unless -r $yarv_html;

our $js = slurp($yarv_html);
#die '$RRD_dir/rrd.def not found' unless -r "$RRD_dir/rrd.def";
#chomp(our @def = grep !/^\s*(?:#|$)/, slurp("$RRD_dir/rrd.def"));


sub safe_html {
    join('', map(encode_entities($_), @_));
}


if (url_param('s')) {
        # FIXME: uri_unescape?
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
	create_png({start=>$start, end=>$end, rrd=>$rrd, width=>$width, height=>$height})->{image};

    exit;
}


my @RRDs = sort map {m!.*/(.*)\.rrd$!; $1} bsd_glob($RRD_glob);

error("No RRDs found") unless @RRDs;



print
    header,
    start_html('RRD viewer'),
    start_form(-name=>'form1'),
    Dump,
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
    print parse_template($js, { start => $start, end => $end, rrd => $rrd, width => $config{width}, height => $config{height}});
}

print
    end_html;

exit;

# <!-- <img src='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAtklEQVQ4ja3SsWoCQRSF4Q+LpLYNUVD0FZJenyu4261aCZLgg6UWYdUuhUUKC7VwUBBnR3AvDDPcw/xzuHO4VgsLlPgL+0/oJ2uIDTL00EQfeegPqi53sMVHRP8MkHYMsMBXwmGO75hYopsA9LCKiXu8hPPxzoJX/D/r4DcmPjqDWUx85Bd2eKt64TYHDdcc7JxnkSdcXpK4xgFLzPGOIkBGKUhVZQEyrQMyqQMyrgOSPQMpUJwAQnMwXeQXxVYAAAAASUVORK5CYII=' onclick='zoomOut()'> -->

use Data::Dumper;
sub parse_template {
    my ($template, $vars) = @_;
    $vars->{url} = url();
    my $gi = create_png($vars);
#    print STDERR 'gi=', Dumper($gi);
    $vars->{graph_top} = $gi->{graph_top};
    $vars->{graph_left} = $gi->{graph_left};

    print STDERR 'vars=', Dumper($vars);
#    print STDERR 'template=', Dumper($template);

    $template =~ s/\${\s*(\w+)\s*}/exists $vars->{$1}?$vars->{$1}:''/eg;
    return $template;
}

sub error {
    print
        header,
        start_html('RRD viewer'),
        "@_",
        end_html();
    exit;
}

sub slurp {
    my ($fname) = @_;
    open my $fh, '<', $fname or die "Cannot open $fname: $!";
    return <$fh> if wantarray;
    local $/ = undef;
    return <$fh>;
};

sub create_png {
        my ($vars) = @_;
        my ($start, $end, $rrd, $width, $height) = @{$vars}{qw/start end rrd width height/};

        # title is name of rrd without path (if any) ...
        (my $title = $rrd) =~ s!.*/!!;
        # ... together with the date(s)
        my $sd = strftime('%Y-%m-%d', localtime($start));
        my $ed = strftime('%Y-%m-%d', localtime($end));
        $title .= '   ' . (($sd eq $ed) ? $sd : "$sd - $ed");

        $rrd = "$RRD_dir/$rrd.rrd";

        my $info = RRDs::info($rrd);
        my @DS;
        foreach (sort grep /\.index$/, keys %$info) {
                push @DS, $1 if /\[(.*?)\]/;
        }

        my %CF;
        foreach (grep /\.cf$/, keys %$info) {
                $CF{$info->{$_}} = 1;
        }
        my @CF = sort keys %CF;

#    print STDERR Data::Dumper->Dump([\@CF, \@DS],[qw/*CF *DS/]);
        my @colors = map($colormap{lc($_)}, map { qw/black blue red yellow green lime fuchsia gray maroon navy olive orange aqua purple silver teal/ } 1..10);
#    print STDERR Data::Dumper->Dump([\@colors],[qw/*colors/]);
        my (@def, @line);
        for my $ds (@DS) {
                for my $cf (@CF) {
                        my $lcf = lc($cf);
                        $lcf = 'avg' if $lcf eq 'average';
                        push @def, "DEF:$ds-$lcf=$rrd:$ds:$cf";
                        push @line, "LINE:$ds-$lcf#" . pop(@colors) . ":$ds $lcf";
                }
        }

#    print STDERR Data::Dumper->Dump([\@def, \@line],[qw/*def *line/]);

        my $gi = RRDs::graphv('-',
                              "-s", $start,
                              "-e", $end,
                              "-h", $height,
                              "-w", $width,
                              "-t", $title,
                              @def,
                              @line);
        my $ERR=RRDs::error;
        die "ERROR in graph: $ERR\n" if $ERR;

        return $gi;
}

sub read_yarv_conf {
        my $conffile = CONF_FILE;
        my %conf;
        my $section = '*';
        open my $c, '<', $conffile or die "Cannot open $conffile: $!";
        while (<$c>) {
                chomp;
                /^\s*(?:\#|$)/ and next;
                if (/^\[(.*)\]\s*$/) {
                        $section = $1;
                        next;
                }
                my ($key, $val) = split(/\s*=\s*/);
                die "Syntax error at $conffile($.): '$_'" unless defined $val;
                $conf{$section}{$key} = $val;
        }
        return %conf;
}

sub colornames {
        return map lc($_), qw/
AliceBlue  F0F8FF
AntiqueWhite  FAEBD7
Aqua  00FFFF
Aquamarine  7FFFD4
Azure  F0FFFF
Beige  F5F5DC
Bisque  FFE4C4
Black  000000
BlanchedAlmond  FFEBCD
Blue  0000FF
BlueViolet  8A2BE2
Brown  A52A2A
BurlyWood  DEB887
CadetBlue  5F9EA0
Chartreuse  7FFF00
Chocolate  D2691E
Coral  FF7F50
CornflowerBlue  6495ED
Cornsilk  FFF8DC
Crimson  DC143C
Cyan  00FFFF
DarkBlue  00008B
DarkCyan  008B8B
DarkGoldenRod  B8860B
DarkGray  A9A9A9
DarkGreen  006400
DarkKhaki  BDB76B
DarkMagenta  8B008B
DarkOliveGreen  556B2F
DarkOrange  FF8C00
DarkOrchid  9932CC
DarkRed  8B0000
DarkSalmon  E9967A
DarkSeaGreen  8FBC8F
DarkSlateBlue  483D8B
DarkSlateGray  2F4F4F
DarkTurquoise  00CED1
DarkViolet  9400D3
DeepPink  FF1493
DeepSkyBlue  00BFFF
DimGray  696969
DodgerBlue  1E90FF
FireBrick  B22222
FloralWhite  FFFAF0
ForestGreen  228B22
Fuchsia  FF00FF
Gainsboro  DCDCDC
GhostWhite  F8F8FF
Gold  FFD700
GoldenRod  DAA520
Gray  808080
Green  008000
GreenYellow  ADFF2F
HoneyDew  F0FFF0
HotPink  FF69B4
IndianRed   CD5C5C
Indigo   4B0082
Ivory  FFFFF0
Khaki  F0E68C
Lavender  E6E6FA
LavenderBlush  FFF0F5
LawnGreen  7CFC00
LemonChiffon  FFFACD
LightBlue  ADD8E6
LightCoral  F08080
LightCyan  E0FFFF
LightGoldenRodYellow  FAFAD2
LightGray  D3D3D3
LightGreen  90EE90
LightPink  FFB6C1
LightSalmon  FFA07A
LightSeaGreen  20B2AA
LightSkyBlue  87CEFA
LightSlateGray  778899
LightSteelBlue  B0C4DE
LightYellow  FFFFE0
Lime  00FF00
LimeGreen  32CD32
Linen  FAF0E6
Magenta  FF00FF
Maroon  800000
MediumAquaMarine  66CDAA
MediumBlue  0000CD
MediumOrchid  BA55D3
MediumPurple  9370DB
MediumSeaGreen  3CB371
MediumSlateBlue  7B68EE
MediumSpringGreen  00FA9A
MediumTurquoise  48D1CC
MediumVioletRed  C71585
MidnightBlue  191970
MintCream  F5FFFA
MistyRose  FFE4E1
Moccasin  FFE4B5
NavajoWhite  FFDEAD
Navy  000080
OldLace  FDF5E6
Olive  808000
OliveDrab  6B8E23
Orange  FFA500
OrangeRed  FF4500
Orchid  DA70D6
PaleGoldenRod  EEE8AA
PaleGreen  98FB98
PaleTurquoise  AFEEEE
PaleVioletRed  DB7093
PapayaWhip  FFEFD5
PeachPuff  FFDAB9
Peru  CD853F
Pink  FFC0CB
Plum  DDA0DD
PowderBlue  B0E0E6
Purple  800080
Red  FF0000
RosyBrown  BC8F8F
RoyalBlue  4169E1
SaddleBrown  8B4513
Salmon  FA8072
SandyBrown  F4A460
SeaGreen  2E8B57
SeaShell  FFF5EE
Sienna  A0522D
Silver  C0C0C0
SkyBlue  87CEEB
SlateBlue  6A5ACD
SlateGray  708090
Snow  FFFAFA
SpringGreen  00FF7F
SteelBlue  4682B4
Tan  D2B48C
Teal  008080
Thistle  D8BFD8
Tomato  FF6347
Turquoise  40E0D0
Violet  EE82EE
Wheat  F5DEB3
White  FFFFFF
WhiteSmoke  F5F5F5
Yellow  FFFF00
YellowGreen  9ACD32
/;
}
