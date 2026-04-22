#!/bin/bash

# Configuration
THRESHOLD=10
INTERVAL=60 # Seconds

# Prevent multiple notifications for the same event
NOTIFIED=false

while true; do
    # Get battery info from upower (more robust than sysfs)
    BATTERY_PATH="/org/freedesktop/UPower/devices/battery_BAT0"
    
    # Check if battery path exists
    if ! upower -i "$BATTERY_PATH" > /dev/null 2>&1; then
        # Try to find any battery if BAT0 is not found
        BATTERY_PATH=$(upower -e | grep battery | head -n 1)
    fi

    if [ -n "$BATTERY_PATH" ]; then
        INFO=$(upower -i "$BATTERY_PATH")
        PERCENTAGE=$(echo "$INFO" | grep percentage | awk '{print $2}' | tr -dc '0-9.')
        PERCENTAGE=${PERCENTAGE%.*} # Strip decimal if present
        STATUS=$(echo "$INFO" | grep state | awk '{print $2}')

        if [[ "$PERCENTAGE" -le "$THRESHOLD" && "$STATUS" == "discharging" ]]; then
            if [[ "$NOTIFIED" == "false" ]]; then
                notify-send -u critical "Battery Low" "Battery level is at ${PERCENTAGE}%."
                NOTIFIED=true
            fi
        elif [[ "$PERCENTAGE" -gt "$THRESHOLD" || "$STATUS" == "charging" || "$STATUS" == "fully-charged" ]]; then
            # Reset notification flag if battery is above threshold or charging
            NOTIFIED=false
        fi
    fi

    sleep "$INTERVAL"
done
