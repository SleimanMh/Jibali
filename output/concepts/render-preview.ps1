# SUPERSEDED historical 20-second / 25fps slideshow. Not the active 24fps production.
throw 'Historical preview renderer disabled. Use output/brand-film-45/production.json; generation approval is pending.'
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Join-Path $PSScriptRoot '..\..')
$starts = @(7, 449, 893, 1335)
for ($shot = 0; $shot -lt 4; $shot++) {
    $filter = "crop=432:872:$($starts[$shot]):7,scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,zoompan=z='1+0.00045*on':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=125:s=720x1280:fps=25,setsar=1,fade=t=in:st=0:d=0.3,fade=t=out:st=4.7:d=0.3"
    & ffmpeg -y -hide_banner -loglevel error -i 'output/concepts/jibali-rashaya-saj-storyboard-v2.png' -vf $filter -frames:v 125 -an -c:v libx264 -preset fast -crf 20 -pix_fmt yuv420p "output/concepts/jibali-shot-$shot.mp4"
    if ($LASTEXITCODE -ne 0) { throw "Shot $shot failed" }
}
$list = (0..3 | ForEach-Object { "file 'jibali-shot-$_.mp4'" }) -join "`n"
[IO.File]::WriteAllText((Join-Path  'jibali-shots.txt'), $list, [Text.UTF8Encoding]::new($false))
& ffmpeg -y -hide_banner -loglevel error -f concat -safe 0 -i 'output/concepts/jibali-shots.txt' -vf 'drawbox=x=0:y=1000:w=iw:h=220:color=0x073e33@0.78:t=fill,ass=output/concepts/jibali-titles.ass' -an -c:v libx264 -preset fast -crf 20 -pix_fmt yuv420p -movflags +faststart 'output/concepts/jibali-rashaya-preview.mp4'
if ($LASTEXITCODE -ne 0) { throw 'Final render failed' }


