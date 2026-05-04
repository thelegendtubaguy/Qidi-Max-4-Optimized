# Testing

I would love your help to make this better and test edge cases!  If you want to help me test, here's what you need to know, and what I'll need from you.

> [!CAUTION]
> I refuse to be responsible for your printer.  PLEASE watch prints start ensuring the printer doesn't do something horrible like gouge your bed and be ready to cut power at a moment's notice.

1. Make sure you have the latest slicer GCode found in this repo for the slicer you're using (make sure to grab it from the `dev` branch if following the rest of the instructions)
2. Run this command on your printer to install the latest prerelease (copy and paste it all in one go):
```bash
TLTG_INSTALLER_ARCHIVE_URL=https://github.com/thelegendtubaguy/Qidi-Max-4-Optimized/releases/download/prerelease/tltg-optimized-macros-dev.tar.gz \
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/thelegendtubaguy/Qidi-Max-4-Optimized/dev/installer/release/install-latest.sh)"
```
3. Slice your print how you normally would, but keep track of what settings you used on your machine and filament profiles/selection.
4. Send, print, and watch it go.
5. Report back how it went!

## Report Back
I would like to hear from you even if things went perfectly!  This helps me understand if things are going well for people other than just me.

I would prefer feedback to be collected here on GitHub by having you open issues.  You can also chat about this over on the [TubaMakes Discord](https://l.tubaguy.com/tmdiscord)!
