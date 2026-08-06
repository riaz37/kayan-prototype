#!/usr/bin/env bash
# A local PBX to develop the voice channel against.
#
# Kayan has no phone system yet, and the voice engine is a SIP *endpoint* —
# it registers as an extension somewhere, it is not itself a switch. So
# testing needs something to register to. FreeSWITCH is bottled in Homebrew
# and runs natively on macOS, which keeps everything on one machine: no
# Docker, and therefore no NAT between the engine and the PBX. SIP puts IP
# addresses inside its payloads, so NAT is exactly what you do not want in
# a test rig.
#
#   ./scripts/freeswitch_dev.sh setup     patch config for LAN-only use
#   ./scripts/freeswitch_dev.sh start     start it
#   ./scripts/freeswitch_dev.sh status    is it up, who is registered
#   ./scripts/freeswitch_dev.sh stop      stop it
#   ./scripts/freeswitch_dev.sh calls     show live channels
#
# Extensions come from FreeSWITCH's stock config: 1000-1019, password 1234.
# The convention used here:
#
#   1001   the Kayan voice engine (what SIP_USERNAME registers as)
#   1000   you, on a softphone — dial 1001 to reach the agent
#   1002   the "human agent" the bot transfers to (SIP_TRANSFER_TARGET)
#
set -euo pipefail

FS_ETC="${FS_ETC:-/opt/homebrew/etc/freeswitch}"
FS_LOG="${FS_LOG:-/opt/homebrew/var/log/freeswitch/freeswitch.log}"
VARS="$FS_ETC/vars.xml"

lan_ip() {
  ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo 127.0.0.1
}

cmd_setup() {
  if [ ! -f "$VARS" ]; then
    echo "FreeSWITCH config not found at $FS_ETC — is it installed? (brew install freeswitch)" >&2
    exit 1
  fi
  # Homebrew symlinks the config into the Cellar; sed -i cannot edit a
  # symlink in place, so follow it to the real file.
  VARS="$(python3 -c "import os,sys;print(os.path.realpath(sys.argv[1]))" "$VARS")"
  # Stock vars.xml resolves external_rtp_ip / external_sip_ip over STUN, so
  # FreeSWITCH advertises this machine's PUBLIC address in SDP. On a rig
  # where every leg is on the LAN that sends RTP out to the internet and
  # the call connects with no audio — the single most confusing failure
  # mode here. Pin both to the local address instead.
  if grep -q 'stun-set" data="external_rtp_ip' "$VARS"; then
    cp "$VARS" "$VARS.kayan-backup"
    sed -i '' \
      -e 's|<X-PRE-PROCESS cmd="stun-set" data="external_rtp_ip=stun:stun.freeswitch.org"/>|<X-PRE-PROCESS cmd="set" data="external_rtp_ip=$${local_ip_v4}"/>|' \
      -e 's|<X-PRE-PROCESS cmd="stun-set" data="external_sip_ip=stun:stun.freeswitch.org"/>|<X-PRE-PROCESS cmd="set" data="external_sip_ip=$${local_ip_v4}"/>|' \
      "$VARS"
    echo "patched $VARS (backup at $VARS.kayan-backup)"
  else
    echo "already patched: external_rtp_ip/external_sip_ip are local"
  fi
  echo
  echo "Point the engine at it — in kayan-prototype/.env:"
  echo "  SIP_SERVER=$(lan_ip)"
  echo "  SIP_USERNAME=1001"
  echo "  SIP_PASSWORD=1234"
  echo "  SIP_TRANSFER_TARGET=1002"
}

cmd_start() {
  if pgrep -f "[f]reeswitch -nc" >/dev/null; then
    echo "already running (pid $(pgrep -f '[f]reeswitch -nc'))"
  else
    # -nc  no console (background)   -nonat  don't probe for NAT
    # -nosql  skip the core db, faster boot and we keep no state
    freeswitch -nc -nonat -nosql
    echo -n "starting"
    for _ in $(seq 1 30); do
      sleep 1; echo -n "."
      if fs_cli -x status >/dev/null 2>&1; then echo " up"; break; fi
    done
  fi
  cmd_status
}

cmd_stop() {
  fs_cli -x "fsctl shutdown" >/dev/null 2>&1 || true
  for _ in $(seq 1 10); do
    pgrep -f "[f]reeswitch -nc" >/dev/null || break
    sleep 1
  done
  pkill -f "[f]reeswitch -nc" 2>/dev/null || true
  sleep 1
  echo "stopped"
}

cmd_status() {
  if ! fs_cli -x status >/dev/null 2>&1; then
    echo "FreeSWITCH is not responding — start it with: $0 start"
    exit 1
  fi
  echo "--- profile ---"
  fs_cli -x "sofia status profile internal" 2>/dev/null \
    | grep -E "^(SIP-IP|Ext-SIP-IP|RTP-IP|Ext-RTP-IP|BIND-URL)" || true
  echo "--- registrations ---"
  fs_cli -x "sofia status profile internal reg" 2>/dev/null \
    | grep -E "^(Call-ID|User|Contact|Status)" | head -40 || true
  echo "(none listed means nothing has registered yet)"
}

cmd_calls() {
  fs_cli -x "show channels" 2>/dev/null || true
}

cmd_log() {
  tail -f "$FS_LOG"
}

case "${1:-status}" in
  setup)  cmd_setup ;;
  start)  cmd_start ;;
  stop)   cmd_stop ;;
  status) cmd_status ;;
  calls)  cmd_calls ;;
  log)    cmd_log ;;
  *) echo "usage: $0 {setup|start|stop|status|calls|log}" >&2; exit 2 ;;
esac
