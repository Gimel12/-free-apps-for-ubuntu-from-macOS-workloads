# Quiet Mode

GNOME 46 Quick Settings toggle for this ASUS ROG Flow Z13.

On: stops the manual Game Mode user service; requests Power Saver; disables CPU
boost; allows 625 MHz idle floor and caps all 32 CPU policies at 2.2 GHz; sets
ASUS sustained/slow/fast power limits to 28/32/45 W (supported firmware minima).
These are limits, not a promise of actual wattage or battery life.

Quiet reading now requests 0% through 70°C, 20% at 80°C, 35% at 85°C,
65% at 90°C and 100% at 95°C. The EC controls actual RPM and retains hardware
protection. No CPU/GPU thermal limit is raised. Edit and apply the Quiet reading
profile in Z13 Fan Control to update the curve used by this toggle.

Off restores the saved boost, CPU min/max clocks, power limits and power profile,
with automatic fan control. Manual fan control also exits Quiet Mode. Selecting
another power profile exits within two seconds without reverting that selection.
Suspend and backend shutdown restore the settings. The mode survives a desktop
Shell refresh; it starts off after a reboot. The privileged service accepts only
root and the installing desktop user and exposes fixed actions, not arbitrary paths or commands.

Backend: /usr/local/lib/bizon-fan-control/{service.py,quiet.py}
Service: bizon-fan-control.service
Transient root-only recovery state: /run/bizon-quiet-mode/restore.json

Verified on September 4, 2026: firmware and all CPU policy writes, restoration,
power profile switching, backend restart recovery, and activation from the UI.
Initial light-use test: both fans reported 0 RPM at CPU temperature 52.75°C.

To turn off from a terminal:

    gdbus call --system --dest com.bizon.FanControl --object-path /com/bizon/FanControl --method com.bizon.FanControl.QuietOff
