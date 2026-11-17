# Sideloading on a real iPhone/iPad from Ubuntu (no Mac, no Xcode)

This gets the CI-built, entirely unsigned `SafariCapture-unsigned.ipa` onto a
physical iPhone or iPad using a free Apple ID. It does not use Xcode, a paid
developer account, TestFlight or a macOS host.

The trade-offs are the normal ones for free provisioning:

- the signature is valid for **7 days**, then the app stops launching until you
  re-sideload;
- a free Apple ID can have a small number of active app IDs (currently 3 apps,
  10 app IDs per week);
- personal-team signing is for your own device, not distribution.

---

## 0. What you need

- Ubuntu 22.04+ (or similar) with a USB port and internet access.
- An iPhone or iPad on **iOS/iPadOS 17+**, a USB cable, and the device passcode.
- A free Apple ID with two-factor authentication enabled.
- The repository and GitHub CLI.
- `usbmuxd` and `libimobiledevice-utils` for USB device access.
- A sideloading UI. This guide uses **Sideloadly** (Windows build under Wine)
  as the primary path and **AltStore/SideStore + AltServer-Linux** as the
  alternative. There is no official Sideloadly Linux binary; using the
  Windows build through Wine is the common Ubuntu workaround. A Windows VM
  also works if Wine misbehaves.

```bash
sudo apt update
sudo apt install -y usbmuxd libimobiledevice-utils unzip curl wine64 wine
sudo systemctl enable --now usbmuxd
```

Install GitHub CLI if needed (`gh`), then authenticate:

```bash
gh auth login
```

---

## 1. Download the CI artifact

From the repository root (the directory containing `SafariCapture/` and
`.github/workflows/`):

```bash
gh workflow run ios-build.yml
# wait for the run to finish, then:
gh run download --name SafariCapture-unsigned -D dist
```

You should now have `dist/SafariCapture-unsigned.ipa`. Verify its shape before
touching the phone:

```bash
unzip -l dist/SafariCapture-unsigned.ipa | grep -E 'Payload/|SafariCaptureExtension'
```

It must contain:

```
Payload/SafariCapture.app/
Payload/SafariCapture.app/PlugIns/SafariCaptureExtension.appex/
```

That embedded `.appex` is the Safari Web Extension. If it is missing, do not
sideload; the CI packaging step is broken.

---

## 2. Pair the device with Ubuntu

1. Connect the iPhone/iPad by USB and unlock it.
2. Tap **Trust** on the device and enter the passcode.
3. On Ubuntu:

```bash
idevicepair pair
ideviceinfo | head -20
```

`ideviceinfo` should print device details. If it says "No device found":

```bash
sudo systemctl restart usbmuxd
idevicepair pair
```

Also try a different cable/port; charge-only cables do not expose data.

If the device asks to trust the computer again, accept it.

---

## 3. Install with Sideloadly (primary path)

1. Download the current Sideloadly Windows installer from the official
   Sideloadly site on your Ubuntu machine.
2. Run the installer under Wine:

   ```bash
   wine SideloadlySetup.exe
   ```

3. Launch it:

   ```bash
   wine "$HOME/.wine/drive_c/Program Files/Sideloadly/Sideloadly.exe"
   ```

   (The exact path/version can vary. On some Wine versions Sideloadly needs
   extra .NET components; if it will not start, use the AltStore route in
   section 4 or a Windows VM.)

4. Drag `dist/SafariCapture-unsigned.ipa` into the Sideloadly window, or use
   the IPA field.
5. Select the connected iPhone/iPad.
6. Enter your **Apple ID** in the Apple account field. Sideloadly will ask for
   the password and a two-factor code. It is signing the app locally with a
   free personal team; the credentials are not sent to this project.
7. Leave the bundle identifier as-is unless it conflicts with an existing
   install. If you must change it, change both the app and the embedded
   extension consistently; changing only one breaks installation.
8. Press **Start**. Wait for "Done" and for the device to re-spring.
9. On the device, open **Settings → General → VPN & Device Management**, tap
   your Apple ID developer entry, and choose **Trust**.
10. On iOS 16+, enable **Settings → Privacy & Security → Developer Mode**,
    restart when prompted, then confirm Developer Mode after the restart.

### Alternative: AltStore / SideStore + AltServer-Linux

If Wine is not workable:

1. Use the community **AltServer-Linux** build to serve AltStore/SideStore to
   the device over USB or the same Wi-Fi network.
2. Install AltStore/SideStore on the device and sign in with the same free
   Apple ID.
3. In AltStore/SideStore use **My Apps → +** and choose
   `SafariCapture-unsigned.ipa` (copy it to the device via Files/AirDrop or
   AltStore's file picker).
4. Trust the developer entry in **Settings → General → VPN & Device Management**
   and enable Developer Mode if prompted.

AltServer-Linux is a community tool rather than an Apple-supported path; if a
release stops working after an iOS update, Sideloadly under Wine or a Windows
VM is the fallback.

---

## 4. Enable the Safari extension

Installing the app is not enough; Safari extensions are opt-in.

1. Open **SafariCapture** once from the Home Screen so iOS registers the
   containing app and its extension.
2. Open **Settings → Safari → Extensions → Capture the Domain**.
   On some iOS 17 builds the path is **Settings → Apps → Safari → Extensions**.
3. Toggle **Capture the Domain** on.
4. Tap **All Websites** (or the per-site permission) and choose **Allow** for
   the sites you want to capture. If you prefer, allow only the demo host.
5. Open Safari, tap the **Aa** / extensions button in the address bar, and
   confirm **Capture the Domain** is listed.

If the extension is missing, delete and reinstall the app (or re-sideload),
open the containing app once, and check Settings again.

---

## 5. Point the popup at your Ubuntu receiver

Start the stub on the Ubuntu machine:

```bash
node stub/server.js 8787
```

It binds `0.0.0.0`, so the phone can reach it if both devices are on the same
Wi-Fi/LAN and the firewall allows the port.

Find the Ubuntu machine's LAN address:

```bash
hostname -I
# example: 192.168.1.20
```

In the Safari extension popup enter:

| Field | Value |
|---|---|
| Sync endpoint | `http://192.168.1.20:8787/api/capture` |
| Bearer token | `demo` |

Do **not** use `localhost` here: on the phone, `localhost` is the phone.
Press **Save**, allow the iOS **Local Network** prompt if it appears, then:

1. Open `http://192.168.1.20:8787/demo` in Safari.
2. Arm the extension.
3. Reload or click Chapter 2.
4. Watch the stub print `201 <host> <bytes>` and write
   `captures/<host>/<content_hash>.md` on the Ubuntu machine.

If Safari refuses the plain-HTTP LAN endpoint, put the receiver behind an
HTTPS reverse proxy (Caddy/nginx with a local certificate) or use HTTPS
tunnelling. The extension accepts any `http(s)` endpoint typed at runtime.

---

## 6. The 7-day re-sideload cycle

A free Apple ID provisioning profile expires after 7 days. Symptoms:

- the app icon remains but tapping it says the developer is no longer trusted
  or the app cannot be launched;
- the Safari extension disappears from Settings.

To refresh:

1. Keep the same Apple ID and the same bundle identifier.
2. Re-run the `iOS build` workflow (or reuse the downloaded IPA).
3. Re-sideload over the existing app with Sideloadly/AltStore. Do **not**
   delete the app first if you want to keep endpoint, token, log and queue
   state; a normal re-sign/overwrite usually preserves app data.
4. Trust the developer entry again if iOS asks.
5. Confirm the extension is still enabled in Settings → Safari → Extensions.

If you had to delete the app, re-enter endpoint, token and arm the extension
again. The queue and log live in Safari extension storage, so uninstalling the
containing app removes them.

AltStore/SideStore can refresh in the background when the device is on the
same network as AltServer and the 7-day window is near; that is a convenience,
not a replacement for the initial signing.

---

## 7. Troubleshooting

| Problem | Fix |
|---|---|
| `idevicepair` cannot find the device | Unlock, trust the computer, try another cable/port, `sudo systemctl restart usbmuxd`. |
| Sideloadly under Wine crashes | Use a Windows VM, or the AltStore/SideStore path. |
| "Maximum number of apps for free development profiles" | Remove an unused sideloaded app or wait for the weekly app-ID reset. |
| "Untrusted Developer" | Settings → General → VPN & Device Management → trust the Apple ID entry. |
| App installs but will not launch | Developer Mode off (iOS 16+), expired 7-day certificate, or the app was signed for another device. Re-sideload. |
| Extension not in Settings | Open the containing app once; re-sideload; on iOS 17 check both Settings → Safari → Extensions and Settings → Apps → Safari → Extensions. |
| Popup endpoint unreachable | Phone and Ubuntu on the same LAN; use the LAN IP, not `localhost`; open the firewall port; allow the Local Network prompt. |
| Uploads fail with 401 | The popup token must match the stub token. The stub's default is `demo`; override with the second CLI argument or `CAPTURE_TOKEN`. |
| HTTP LAN endpoint blocked | Put the stub behind HTTPS; do not weaken TLS settings on the device. |
| Extension stops after a week | Free provisioning expired. Re-sideload; see section 6. |
