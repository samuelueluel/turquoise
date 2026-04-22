--- @sync entry
return {
  entry = function()
    local h = cx.active.current.hovered
    if h and h.cha.is_dir then
      ya.mgr_emit("enter", {})
    else
      ya.mgr_emit("open", {})
      if os.getenv("YAZI_FLOAT") == "1" then
        ya.mgr_emit("quit", {})
      end
    end
  end,
}
