# Updating fazif.yazi

This plugin is tracked manually via Chezmoi (as a frozen copy) rather than Yazi's built-in package manager (`ya`). This is because the plugin requires our custom `folder_search` script to be placed directly inside its directory, which breaks `ya`'s integrity checks.

If you ever need to update this plugin to a newer version from the upstream repository, follow these steps:

1. Clone the latest version into a temporary directory:
   ```bash
   git clone https://github.com/Shallow-Seek/fazif.yazi.git /tmp/fazif.yazi
   ```

2. Copy the updated core files over to your config directory. **Do not copy the entire folder directly or use `ya`, as it will overwrite/delete your custom `folder_search` script.**
   ```bash
   cp /tmp/fazif.yazi/init.lua ~/.config/yazi/plugins/fazif.yazi/
   cp /tmp/fazif.yazi/main.lua ~/.config/yazi/plugins/fazif.yazi/
   ```

3. Update the tracked files in Chezmoi:
   ```bash
   chezmoi add ~/.config/yazi/plugins/fazif.yazi/
   ```

4. Clean up the temporary folder:
   ```bash
   rm -rf /tmp/fazif.yazi
   ```
