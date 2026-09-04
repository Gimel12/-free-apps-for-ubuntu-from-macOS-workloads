# Adaptive Touch Controls

For GNOME 46 on this ASUS Z13. Touchscreen input activates touch controls;
switching to a mouse or touchpad restores normal pointer interaction.

- Hides the mouse pointer during touch input.
- Allows GNOME's native screen keyboard without requiring the firmware tablet switch.
- Enlarges Quick Settings touch targets while using fingers.
- Shows a tablet indicator and subtle blue touch feedback in the shell.
- Preserves the separate Screen Keyboard button's manual override.
- Does not consume or convert app input, change global scaling, change sessions,
  or interfere with app-specific scrolling and pinch gestures.

App support still matters. This does not convert desktop apps into tablet apps
or make every app support one-finger scrolling. GNOME's existing touchscreen
gestures remain available, including three-finger workspace/overview gestures.

Disable in Extensions, or run:

```sh
gnome-extensions disable adaptive-touch@local
```
# Touch window grip (September 4, 2026)

Touch mode displays a blue grip at the top center of the focused normal window.
Hold and drag the grip with one finger to use Mutter's native window move operation.
The native operation supports restoring maximized windows and edge tiling.
This is an explicit drag target; it does not turn pinch gestures inside app content
into window movement. Application scrolling and zooming retain their own behavior.
The grip hides for mouse/keyboard use, fullscreen windows, and the overview.

The clock-top-left extension also now allocates unused center-panel space to the
right tray and slightly reduces button spacing in portrait orientation. This keeps
the battery percentage and Quick Settings visible on the internal portrait display.
