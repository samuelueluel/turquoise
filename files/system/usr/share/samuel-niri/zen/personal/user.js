// Zen Browser — Samuel's personal profile preferences
// This file is read on every startup and overrides prefs.js.
// Only user-modified preferences are listed here.
// Generated from qa89d0nt.personal/prefs.js — excludes timestamps, UUIDs, and auto-managed state.

// ── Fonts ─────────────────────────────────────────────────────────────────────
user_pref("font.name.monospace.x-western", "JetBrainsMono Nerd Font Mono");
user_pref("font.name.sans-serif.x-western", "IBM Plex Sans");
user_pref("font.name.serif.x-western", "IBM Plex Sans");

// ── Color scheme (0 = dark) ───────────────────────────────────────────────────
user_pref("layout.css.prefers-color-scheme.content-override", 0);

// ── Accessibility ─────────────────────────────────────────────────────────────
user_pref("accessibility.typeaheadfind.flashBar", 0);

// ── Network — disable speculative/prefetch ────────────────────────────────────
user_pref("network.dns.disablePrefetch", true);
user_pref("network.http.speculative-parallel-limit", 0);
user_pref("network.prefetch-next", false);

// ── DNS over HTTPS ────────────────────────────────────────────────────────────
user_pref("doh-rollout.mode", 2);
user_pref("doh-rollout.self-enabled", true);
user_pref("doh-rollout.uri", "https://mozilla.cloudflare-dns.com/dns-query");

// ── Privacy ───────────────────────────────────────────────────────────────────
user_pref("privacy.clearOnShutdown_v2.formdata", true);
user_pref("signon.rememberSignons", false);

// ── URL bar suggestions ───────────────────────────────────────────────────────
user_pref("browser.urlbar.suggest.bookmark", false);
user_pref("browser.urlbar.suggest.clipboard", false);
user_pref("browser.urlbar.suggest.engines", false);
user_pref("browser.urlbar.suggest.history", false);
user_pref("browser.urlbar.suggest.openpage", false);
user_pref("browser.urlbar.suggest.recentsearches", false);

// ── Browser behavior ──────────────────────────────────────────────────────────
user_pref("browser.contentblocking.category", "standard");
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("browser.tabs.insertRelatedAfterCurrent", false);
user_pref("browser.preferences.experimental.hidden", true);

// ── UI ────────────────────────────────────────────────────────────────────────
user_pref("ui.key.menuAccessKeyFocuses", false);
// Toolbar layout (extension buttons require uBlock0 and the sidebar extension)
user_pref("browser.uiCustomization.state", "{\"placements\":{\"widget-overflow-fixed-list\":[],\"unified-extensions-area\":[],\"nav-bar\":[\"back-button\",\"forward-button\",\"stop-reload-button\",\"customizableui-special-spring1\",\"vertical-spacer\",\"urlbar-container\",\"customizableui-special-spring2\",\"unified-extensions-button\",\"ublock0_raymondhill_net-browser-action\",\"_446900e4-71c2-419f-a6a7-df9c091e268b_-browser-action\"],\"toolbar-menubar\":[\"menubar-items\"],\"TabsToolbar\":[\"tabbrowser-tabs\"],\"vertical-tabs\":[],\"PersonalToolbar\":[\"import-button\",\"personal-bookmarks\"],\"zen-sidebar-top-buttons\":[\"zen-toggle-compact-mode\"],\"zen-sidebar-foot-buttons\":[\"downloads-button\",\"zen-workspaces-button\",\"zen-create-new-button\"]},\"seen\":[\"developer-button\",\"screenshot-button\",\"ublock0_raymondhill_net-browser-action\",\"_446900e4-71c2-419f-a6a7-df9c091e268b_-browser-action\"],\"dirtyAreaCache\":[\"nav-bar\",\"vertical-tabs\",\"zen-sidebar-foot-buttons\",\"PersonalToolbar\",\"unified-extensions-area\",\"toolbar-menubar\",\"TabsToolbar\",\"zen-sidebar-top-buttons\"],\"currentVersion\":23,\"newElementCount\":2}");

// ── Sidebar ───────────────────────────────────────────────────────────────────
user_pref("sidebar.visibility", "hide-sidebar");
user_pref("sidebar.main.tools", "{446900e4-71c2-419f-a6a7-df9c091e268b}");

// ── Form autofill ─────────────────────────────────────────────────────────────
user_pref("dom.forms.autocomplete.formautofill", true);
user_pref("extensions.formautofill.addresses.enabled", false);
user_pref("extensions.formautofill.creditCards.enabled", false);

// ── Extensions — allow unsigned ───────────────────────────────────────────────
user_pref("xpinstall.signatures.required", false);
user_pref("xpinstall.whitelist.required", false);

// ── Nimbus (disable experiments/rollouts) ─────────────────────────────────────
user_pref("nimbus.rollouts.enabled", false);

// ── Zen settings ──────────────────────────────────────────────────────────────
user_pref("zen.glance.enabled", false);
user_pref("zen.tabs.ctrl-tab.ignore-pending-tabs", true);
user_pref("zen.theme.content-element-separation", 6);
user_pref("zen.view.compact.enable-at-startup", true);
user_pref("zen.view.experimental-no-window-controls", true);
user_pref("zen.view.show-newtab-button-top", false);
user_pref("zen.view.window.scheme", 0);
user_pref("zen.welcome-screen.seen", true);
user_pref("zen.workspaces.show-workspace-indicator", true);

// ── Zen theme mod settings ────────────────────────────────────────────────────
user_pref("mod.ivaon.urlbar.hide_results", "0");
user_pref("mod.superpins.essentials.grid-count", "1");
user_pref("mod.superpins.pins.grid-count", "1");
user_pref("theme-better_find_bar-enable_custom_background", false);
user_pref("theme.better_find_bar.custom_background", "#112233");
user_pref("theme.better_find_bar.hide_find_status", false);
user_pref("theme.better_find_bar.hide_found_matches", false);
user_pref("theme.better_find_bar.hide_highlight", "not_hide");
user_pref("theme.better_find_bar.hide_match_case", "not_hide");
user_pref("theme.better_find_bar.hide_match_diacritics", "not_hide");
user_pref("theme.better_find_bar.hide_whole_words", "not_hide");
user_pref("theme.better_find_bar.horizontal_position", "default");
user_pref("theme.better_find_bar.instant_animations", false);
user_pref("theme.better_find_bar.textbox_width", "800");
user_pref("theme.better_find_bar.transparent_background", true);
user_pref("theme.better_find_bar.vertical_position", "default");

// ── SuperPins / UC mod settings ───────────────────────────────────────────────
user_pref("uc.essentials.gap", "Normal");
user_pref("uc.essentials.transition-speed", "100ms");
user_pref("uc.essentials.width", "Normal");
user_pref("uc.pins.auto-grow", true);
user_pref("uc.pins.legacy-layout", false);
user_pref("uc.pins.stay-at-top", true);
user_pref("uc.pins.transition-speed", "100ms");
user_pref("uc.tabs.strikethrough-on-pending", true);
