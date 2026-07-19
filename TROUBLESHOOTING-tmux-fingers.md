# tmux-fingers Troubleshooting

## Problem: "Library not loaded: /opt/homebrew/opt/bdw-gc/lib/libgc.1.dylib"

### Root Cause

The tmux-fingers plugin can be installed in two ways:

1. **"Download binary" (option `b` in install wizard)**: Downloads a statically-linked binary from GitHub releases
   - Size: ~1.7MB
   - Dependencies: None (statically linked)
   - Works immediately after download

2. **"Install with brew" (option `w` in install wizard)**: Installs via Homebrew
   - Size: ~2.6MB  
   - Dependencies: `bdw-gc`, `pcre2`, `libevent`, `libyaml` (dynamically linked)
   - Requires dependencies to be installed

### Why It Failed

If you:
1. Installed tmux-fingers via Homebrew (with dependencies)
2. Later ran `brew autoremove` or `brew cleanup --prune=all`
3. Homebrew removed `bdw-gc` thinking it was unused

The binary would fail with the "Library not loaded" error because Homebrew doesn't track that the TPM-managed plugin depends on these libraries.

### Solution

**Option 1: Auto-fix (recommended)**

The latest optmux now auto-detects and installs missing dependencies. Just run:
```bash
./your-project.optmux.yaml
```

Or manually trigger the plugin update:
```bash
bash ~/.optmux.d/tmux/plugins-update.sh  # or your project's .optmux.d
```

**Option 2: Manual fix**

Install the missing dependencies:
```bash
brew install bdw-gc pcre2 libevent libyaml
```

**Option 3: Reinstall with static binary**

Delete the binary and re-run the install wizard, choosing "Download binary" instead:
```bash
rm -f ~/.optmux.d/tmux/plugins/Morantron/tmux-fingers/bin/tmux-fingers
# Restart tmux session - the wizard will appear
# Choose option (b) "Download binary"
```

### Prevention

The optmux `plugins-update.sh` script now includes a dependency check that:
1. Detects if tmux-fingers binary is dynamically linked (`otool -L` check)
2. Tests if the binary can run
3. Auto-installs missing dependencies via Homebrew

### Configuration

To skip the install wizard on subsequent launches, optmux now sets:
```tmux
set -g @fingers-skip-wizard '1'
```

This is automatically added to the generated `tmux.conf`.

### Verification

Check which binary you have:
```bash
otool -L ~/.optmux.d/tmux/plugins/Morantron/tmux-fingers/bin/tmux-fingers
```

- **Statically linked**: Only shows system libraries (`/usr/lib/*`)
- **Dynamically linked**: Shows Homebrew paths (`/opt/homebrew/opt/bdw-gc/lib/libgc.1.dylib`)

Test if it works:
```bash
~/.optmux.d/tmux/plugins/Morantron/tmux-fingers/bin/tmux-fingers version
```

Should output: `2.7.1` (or current version)
