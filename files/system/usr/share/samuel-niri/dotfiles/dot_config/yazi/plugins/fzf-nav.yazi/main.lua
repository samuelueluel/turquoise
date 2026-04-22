-- Custom fzf plugin that enables hidden files before revealing dotfiles.

local state = ya.sync(function()
	return cx.active.current.cwd
end)

local function fail(s, ...)
	ya.notify { title = "Fzf", content = string.format(s, ...), timeout = 5, level = "error" }
end

local function entry(_, _args)
	local permit = ui.hide()
	local cwd = state()

	local script = os.getenv("HOME") .. "/.config/yazi/plugins/fzf-nav.yazi/fzf-search"
	local child, err = Command(script):cwd(tostring(cwd)):stdin(Command.INHERIT):stdout(Command.PIPED):spawn()

	if not child then
		if permit then permit:drop() end
		return fail("Spawn failed with error code %s", err)
	end

	local output, err2 = child:wait_with_output()

	if permit then permit:drop() end

	if not output then
		return fail("Cannot read output: %s", err2)
	elseif not output.status.success then
		return
	end

	local target = output.stdout:gsub("\n$", "")
	if target == "" then return end

	local url = Url(cwd:join(target))

	if target:match("^%.") or target:match("/%.") then
		ya.mgr_emit("hidden", { "show" })
	end

	ya.mgr_emit("reveal", { url, raw = true })
end

return { entry = entry }
