#!/bin/bash

client_id='d9c43c00ff914624a02151e43ab5a16c'
client_secret=''

output="$XDG_RUNTIME_DIR/spotify_status"

token=""
get_token() {
    echo -n 'Bearer '
    if [[ -z "$token" ]]; then
        authorization="$(base64 -w 0 <(echo -n "$client_id:$client_secret"))"
        token="$(curl -s -H "Authorization: Basic $authorization" -d 'grant_type=client_credentials' https://accounts.spotify.com/api/token | jq --join-output --raw-output .access_token)"
    fi
    echo -n "$token"
}

track_data=""
get_track_data() {
    if [[ -z "$track_data" ]]; then
        track_data="$(curl -s -H "Authorization: $(get_token)" "https://api.spotify.com/v1/tracks/$TRACK_ID")"
    fi
    echo -n "$track_data"
}

get_artists() {
    echo "$(get_track_data)" | jq --join-output --raw-output '[.artists[].name] | join(", ")'
}

get_track() {
    echo "$(get_track_data)" | jq --join-output --raw-output '.name'
}

play() {
    echo " $(get_track)" >$output
    echo "$(get_artists) - $(get_track)" >>$output
}

stop() {
    echo " $(get_track)" >$output
    echo "$(get_artists) - $(get_track)" >>$output
}

pause() {
    echo " $(get_track)" >$output
    echo "$(get_artists) - $(get_track)" >>$output
}

case "$PLAYER_EVENT" in
    "start")
        play
        ;;
    "stop")
        pause
        ;;
    "load")
        ;;
    "play")
        play
        ;;
    "pause")
        pause
        ;;
    "preload")
        ;;
    "endoftrack")
        stop
        ;;
    "volumeset")
        ;;
    "change")
        play
        ;;
    *)
        ;; 
esac

