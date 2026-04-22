#!/usr/bin/env python3
import json
import subprocess
import sys

def run_cmd(cmd):
    return json.loads(subprocess.check_output(cmd, shell=True))

def snap_pct(pct):
    # Snap to common preset percentages to avoid width drift over multiple swaps
    targets = [25.0, 33.3333, 50.0, 66.6667, 75.0]
    for t in targets:
        if abs(pct - t) < 3.0:
            return t
    return pct

def main():
    try:
        windows = run_cmd("niri msg -j windows")
        workspaces = run_cmd("niri msg -j workspaces")
        outputs = run_cmd("niri msg -j outputs")
    except Exception as e:
        print(f"Error communicating with niri: {e}", file=sys.stderr)
        sys.exit(1)

    active_ws = next((w for w in workspaces if w["is_focused"]), None)
    if not active_ws:
        print("No active workspace found.", file=sys.stderr)
        sys.exit(1)

    out_name = active_ws["output"]
    out_width = outputs[out_name]["logical"]["width"]

    ws_windows = [w for w in windows if w["workspace_id"] == active_ws["id"]]
    ws_windows.sort(key=lambda w: w["layout"]["pos_in_scrolling_layout"][0])

    focused = next((w for w in ws_windows if w["is_focused"]), None)
    if not focused:
        print("No focused window found.", file=sys.stderr)
        sys.exit(1)

    f_idx = ws_windows.index(focused)

    best_partner = None
    best_diff = float('inf')

    # Look at adjacent columns to find the one that, together with the focused 
    # column, best fits the monitor width (isolating the visible pair from C).
    for i in [f_idx - 1, f_idx + 1]:
        if 0 <= i < len(ws_windows):
            partner = ws_windows[i]
            sum_w = focused["layout"]["tile_size"][0] + partner["layout"]["tile_size"][0]
            diff = abs(out_width - sum_w)
            if diff < best_diff:
                best_diff = diff
                best_partner = partner

    if not best_partner:
        print("No partner window found to swap with.", file=sys.stderr)
        sys.exit(1)

    # Determine spatial relationships
    if ws_windows.index(best_partner) < f_idx:
        left_win = best_partner
        right_win = focused
    else:
        left_win = focused
        right_win = best_partner

    w_L = left_win["layout"]["tile_size"][0]
    w_R = right_win["layout"]["tile_size"][0]

    # Calculate percentages of the pair footprint and snap to bounds
    total_w = w_L + w_R
    pct_L = snap_pct((w_L / total_w) * 100)
    pct_R = snap_pct((w_R / total_w) * 100)

    commands = []

    # Sequence actions to execute the swap and re-bind widths while keeping focus
    if focused == left_win:
        commands.append("niri msg action swap-window-right")
        commands.append(f"niri msg action set-column-width {pct_R}%")
        commands.append("niri msg action focus-column-left")
        commands.append(f"niri msg action set-column-width {pct_L}%")
        commands.append("niri msg action focus-column-right")
    else:
        commands.append("niri msg action swap-window-left")
        commands.append(f"niri msg action set-column-width {pct_L}%")
        commands.append("niri msg action focus-column-right")
        commands.append(f"niri msg action set-column-width {pct_R}%")
        commands.append("niri msg action focus-column-left")

    # Dispatch sequence
    for cmd in commands:
        subprocess.run(cmd, shell=True, check=True)

if __name__ == "__main__":
    main()
