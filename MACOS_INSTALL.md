# Opening PhysicsAnalysis on Mac (first time)

This app isn't signed with an Apple Developer certificate, so macOS
will warn you the first time you open it. This is normal for
small/independent tools — it doesn't mean anything is wrong with the
app. You only need to do this once.

## Steps

1. Unzip the download and drag **PhysicsAnalysis.app** into your
   **Applications** folder.
2. **Don't double-click it the first time.** Instead, **right-click**
   (or Control-click) the app and choose **Open**.
3. A dialog will warn that the developer can't be verified. Click
   **Open** anyway.
4. That's it — from now on, double-clicking it normally will work.

## If that doesn't work

Open **Terminal** and run:

```bash
xattr -cr /Applications/PhysicsAnalysis.app
```

Then double-click the app normally.

## Why this happens

Apple requires a paid Developer account ($99/year) to sign and notarize
apps for smooth, warning-free distribution. This is a personal/lab
tool, not something distributed through the App Store, so that step is
skipped — the trade-off is this one-time manual approval instead.
