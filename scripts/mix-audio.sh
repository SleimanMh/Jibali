#!/usr/bin/env bash
# Jibali — add voice, music and sound effects to the finished silent 20 s film.
# Free and local: needs only ffmpeg/ffprobe.
#
# Usage:
#   scripts/mix-audio.sh <silent-20s-video.mp4> <output.mp4>
#
# Inputs, relative to the repository root (any that are missing are skipped,
# with a warning):
#   audio/voice/tagline.wav      spoken tagline (leading/trailing silence is trimmed)
#   audio/music/bed.wav          music bed, at least 20 s
#   audio/sfx/01.wav … 05.wav    sound effects for each scene, starting at the scene start
#
# Timings follow output/brand-film-45/audio-timeline.csv.
# Environment overrides: VOICE_START (default 17.2), VOICE_END_LIMIT (19.8),
# MUSIC_DB (-12), SFX_DB (-6), TARGET_LUFS (-14), AUDIO_DIR (audio/).
set -euo pipefail

VIDEO=${1:?usage: mix-audio.sh <silent-video> <output.mp4>}
OUT=${2:?usage: mix-audio.sh <silent-video> <output.mp4>}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
AUDIO=${AUDIO_DIR:-$ROOT/audio}
DUR=20
VOICE_START=${VOICE_START:-17.2}
VOICE_END_LIMIT=${VOICE_END_LIMIT:-19.8}
MUSIC_DB=${MUSIC_DB:--12}
SFX_DB=${SFX_DB:--6}
TARGET_LUFS=${TARGET_LUFS:--14}

# Scene id, start, end (seconds) — scenes 01–05; scene 06 has no SFX.
SCENES=("01 0 4" "02 4 7" "03 7 10" "04 10 13" "05 13 17")

command -v ffmpeg >/dev/null || { echo "ffmpeg not found" >&2; exit 1; }
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

probe() { ffprobe -v error "$@"; }

# --- Check the picture -------------------------------------------------------
IFS=, read -r W H FPS < <(probe -select_streams v:0 -show_entries stream=width,height,r_frame_rate -of csv=p=0 "$VIDEO")
FRAMES=$(probe -select_streams v:0 -count_packets -show_entries stream=nb_read_packets -of csv=p=0 "$VIDEO")
echo "Video: ${W}x${H} @ ${FPS}, ${FRAMES} frames"
[[ "$W" == 1080 && "$H" == 1920 && "$FPS" == 24/1 && "$FRAMES" == 480 ]] \
  || echo "WARNING: brief requires 1080x1920 @ 24/1 with 480 frames" >&2

INPUTS=(-i "$VIDEO")
FILTERS=()
MIX=()
n=1
FMT="aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo"

# --- Voice -------------------------------------------------------------------
VOICE_IDX=""
if [[ -f "$AUDIO/voice/tagline.wav" ]]; then
  ffmpeg -v error -y -i "$AUDIO/voice/tagline.wav" -af \
    "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse,afade=t=in:d=0.02" \
    -ac 1 -ar 48000 "$TMP/voice.wav"
  VLEN=$(probe -show_entries format=duration -of csv=p=0 "$TMP/voice.wav")
  VEND=$(awk -v s="$VOICE_START" -v l="$VLEN" 'BEGIN{printf "%.2f", s+l}')
  echo "Voice: ${VLEN}s, plays ${VOICE_START}s → ${VEND}s"
  if awk -v e="$VEND" -v lim="$VOICE_END_LIMIT" 'BEGIN{exit !(e>lim)}'; then
    echo "ERROR: voice ends at ${VEND}s, after the ${VOICE_END_LIMIT}s limit. Use a faster take or set VOICE_START earlier." >&2
    exit 1
  fi
  INPUTS+=(-i "$TMP/voice.wav")
  DELAY=$(awk -v s="$VOICE_START" 'BEGIN{printf "%d", s*1000}')
  FILTERS+=("[$n:a]$FMT,adelay=${DELAY}:all=1,asplit=2[voice][vkey]")
  MIX+=("[voice]")
  VOICE_IDX=$n; n=$((n+1))
else
  echo "WARNING: audio/voice/tagline.wav missing — mixing without voice" >&2
fi

# --- Music (ducked under the voice) ------------------------------------------
if [[ -f "$AUDIO/music/bed.wav" ]]; then
  INPUTS+=(-i "$AUDIO/music/bed.wav")
  FILTERS+=("[$n:a]$FMT,atrim=0:$DUR,asetpts=N/SR/TB,afade=t=in:d=1.5,afade=t=out:st=$((DUR-1)):d=1,volume=${MUSIC_DB}dB[music_raw]")
  if [[ -n "$VOICE_IDX" ]]; then
    FILTERS+=("[music_raw][vkey]sidechaincompress=threshold=0.015:ratio=6:attack=30:release=500[music]")
  else
    FILTERS+=("[music_raw]anull[music]")
  fi
  MIX+=("[music]"); n=$((n+1))
else
  echo "WARNING: audio/music/bed.wav missing — mixing without music" >&2
  [[ -n "$VOICE_IDX" ]] && FILTERS+=("[vkey]anullsink")
fi

# --- Sound effects, one per scene --------------------------------------------
for scene in "${SCENES[@]}"; do
  read -r id start end <<<"$scene"
  f="$AUDIO/sfx/$id.wav"
  if [[ -f "$f" ]]; then
    len=$((end-start))
    INPUTS+=(-i "$f")
    FILTERS+=("[$n:a]$FMT,atrim=0:$len,asetpts=N/SR/TB,afade=t=in:d=0.05,afade=t=out:st=$(awk -v l=$len 'BEGIN{print l-0.15}'):d=0.15,volume=${SFX_DB}dB,adelay=$((start*1000)):all=1[sfx$id]")
    MIX+=("[sfx$id]"); n=$((n+1))
  else
    echo "WARNING: audio/sfx/$id.wav missing — scene $id has no sound effects" >&2
  fi
done

(( ${#MIX[@]} > 0 )) || { echo "No audio inputs found — nothing to mix" >&2; exit 1; }

PRE="$(IFS=';'; echo "${FILTERS[*]}");$(IFS=''; echo "${MIX[*]}")amix=inputs=${#MIX[@]}:normalize=0:duration=longest,apad,atrim=0:$DUR"

# --- Two-pass loudness normalisation ----------------------------------------
echo "Measuring loudness…"
MEAS=$(ffmpeg -hide_banner -nostats "${INPUTS[@]}" -filter_complex \
  "$PRE,loudnorm=I=$TARGET_LUFS:TP=-1.5:LRA=11:print_format=json[a]" -map "[a]" -f null - 2>&1 \
  | sed -n '/^{/,/^}/p')
get() { echo "$MEAS" | sed -n "s/.*\"$1\" : \"\(.*\)\".*/\1/p"; }
LN="loudnorm=I=$TARGET_LUFS:TP=-1.5:LRA=11:measured_I=$(get input_i):measured_TP=$(get input_tp):measured_LRA=$(get input_lra):measured_thresh=$(get input_thresh):offset=$(get target_offset):linear=true"

echo "Mixing → $OUT"
ffmpeg -hide_banner -v error -y "${INPUTS[@]}" -filter_complex \
  "$PRE,$LN,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,atrim=0:$DUR[a]" \
  -map 0:v:0 -c:v copy -map "[a]" -c:a aac -b:a 192k -ar 48000 -ac 2 \
  -t $DUR -movflags +faststart "$OUT"

# --- Verify ------------------------------------------------------------------
echo "--- Verification ---"
NA=$(probe -select_streams a -show_entries stream=index -of csv=p=0 "$OUT" | wc -l)
NV=$(probe -select_streams v -show_entries stream=index -of csv=p=0 "$OUT" | wc -l)
AD=$(probe -select_streams a:0 -show_entries stream=sample_rate,channels,duration -of csv=p=0 "$OUT")
OF=$(probe -select_streams v:0 -count_packets -show_entries stream=nb_read_packets -of csv=p=0 "$OUT")
LUFS=$(ffmpeg -hide_banner -nostats -i "$OUT" -map 0:a -af ebur128=peak=true -f null - 2>&1 | sed -n 's/^ *I: *\(.*\) LUFS/\1/p' | tail -1)
echo "Video streams: $NV, frames: $OF"
echo "Audio streams: $NA (sample rate, channels, duration: $AD)"
echo "Integrated loudness: ${LUFS} LUFS (target $TARGET_LUFS)"
[[ "$NV" == 1 && "$NA" == 1 && "$OF" == "$FRAMES" ]] || { echo "VERIFICATION FAILED" >&2; exit 1; }
echo "OK"
