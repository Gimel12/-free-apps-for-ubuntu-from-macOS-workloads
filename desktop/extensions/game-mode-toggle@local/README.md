# Game Mode toggle

Open the top-right system menu beside Wi-Fi and Bluetooth. Turn **Game Mode** on before launching a game, and off after playing.

On holds the Performance power profile and requests Feral GameMode's system optimizations. Off releases this manual request and restores the power profile selected before the hold. Games that independently request GameMode may keep their own optimizations active until they exit. Per-process optimizations for future games can additionally use `gamemoderun %command%` in Steam launch options.

The toggle starts off after a new login. It survives refreshing GNOME Shell during the same login. It does not overclock hardware or change graphics drivers. Performance mode can increase fan noise and battery consumption.

Backend: `~/.config/systemd/user/bizon-game-mode.service`

Terminal controls:

```bash
systemctl --user start bizon-game-mode.service
systemctl --user stop bizon-game-mode.service
```

To remove it, stop the service, disable `game-mode-toggle@local` using GNOME Extensions, remove the extension directory and service file, then run `systemctl --user daemon-reload`.
