# Fan Control Quick Settings

GNOME 46 control for the supported ASUS Z13. Requires the restricted backend
installed by [Z13 Fan Control](../../../apps/z13-fan-control/README.md).

The manual slider requests 30–100% fan duty for both fans. Manual mode uses a
firmware thermal ramp: full cooling at 85°C, automatic recovery if its client
heartbeat stops. The percentage is requested duty, not a fixed RPM.

For separate fan curves or fan-stop at low temperatures, open **Z13 Fan Control**
from the arrow submenu. Applied custom/Quiet profiles reach full cooling at 95°C;
the slider is inactive while a profile controls the fans. Return to **Automatic
cooling** before using the manual slider. The submenu displays both fan RPMs,
CPU temperature and the active thermal policy.

Manual mode restores automatic cooling on extension disable. Custom profiles
survive closing the app and refreshing Shell. Suspend, power-profile changes or
backend shutdown release custom control. Reboot starts in automatic mode.
Hardware thermal protections remain enabled. See the app guide for power limits,
profile validation, service installation and supported hardware.
