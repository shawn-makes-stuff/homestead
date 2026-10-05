-- Homestead's settings: the game's Settings > Mods > Homestead (Native Settings UI, required - Nexus 3518), on the main
-- menu and the pause menu alike. Rows: Fallout 4 import, People, Building, Keys.
-- The import starts from the main menu only, through the RED4ext plugin (HomesteadImport; CET can't start programs). It builds
-- there and installs as the game closes (its archives are locked while it runs).
-- A switch's value reaches the mod through C.applied (init.lua). The importer reports in import_status.txt ("key=value" lines:
-- state, step, fo4, fo4version, drives, work, started, finished, minutes, message); our choices are settings.txt next to it.
-- init.lua requires this; Settings is C.Settings.
return function(Settings, C)
    local inGame, applied = C.inGame, C.applied
    local DIR = HS_DIR or ""                                 -- (CET: paths are this mod's folder's; tools/sim.py sets it)
    local NS, status, conf, readT, force, note, noteT = nil, {}, nil, 0, false, nil, 0
    local T, IMP = "/homestead", "/homestead/import"
    local opt, shownSig = {}, nil
    local DEFAULTS = { peopleWalk = true, peopleFurniture = true, peopleTalk = true, peopleNav = true, borderLine = true, snapPoints = false,
                       keepImportFiles = false, loadDistance = 800, buildLimit = true, radius = 50 }

    local function readKV(file)
        local t, f = {}, io.open(DIR .. file, "r")
        if not f then return t end
        for line in f:lines() do
            local k, v = line:match("^([%w_]+)=(.*)$")
            if k then t[k] = v end
        end
        f:close()
        return t
    end
    local function conf_() conf = conf or readKV("settings.txt") return conf end
    function Settings.get(k) return conf_()[k] end
    function Settings.set(k, v)
        conf_()[k] = v
        local f = io.open(DIR .. "settings.txt", "w")
        if not f then return false end
        for key, val in pairs(conf) do f:write(key, "=", val, "\n") end
        f:close()
        return true
    end
    function Settings.on(k)
        local v = Settings.get(k)
        if v == nil then return DEFAULTS[k] end
        return v == "1"
    end
    function Settings.num(k) return tonumber(Settings.get(k)) or DEFAULTS[k] end

    -- The mod was updated since the last import: build.txt (tools/release.py) differs from the one imported.txt recorded.
    function Settings.stale()
        local b = readKV("build.txt").build
        return b ~= nil and readKV("import_status.txt").state == "done" and readKV("imported.txt").build ~= b
    end

    local function plugin(fn, ...)
        local ok, r = pcall(HomesteadImport[fn], ...)
        if ok then return r end
    end
    local BUSY = { running = true, checking = true, waiting = true }
    local function busy() return BUSY[status.state] and plugin("Running") end
    local function statusLine()
        if note then return note end
        local st = status.state
        if not st then return plugin("Path") == "" and "Importer not found: install Homestead again" or "No import yet" end
        -- A running state with no process: it was killed or the PC went off, and nothing told us.
        if BUSY[st] and plugin("Running") == false then return "Stopped before it finished - import again" end
        if st == "cancelled" then return "Cancelled - import again to finish it" end
        if st == "checking" then return "Looking for the games..." end
        if st == "running" then
            local pct, eta = tonumber(status.pct), tonumber(status.eta)
            local left = not eta and "" or eta < 60 and "  -  under a minute left" or ("  -  about " .. math.floor(eta / 60 + 0.5) .. " min left")
            return "Importing: " .. (status.step or "") .. (pct and ("  -  " .. pct .. "%") or "") .. left
        end
        if st == "waiting" then return "Built - quit Cyberpunk to install it" end
        if st == "found" then return "Games found - ready to import" end
        if st == "done" and Settings.stale() then return "Homestead was updated - import again (only what changed is redone)" end
        if st == "done" then return "Imported " .. (status.finished or "") .. "  (" .. (status.minutes or "?") .. " min)" end
        if st == "failed" then return "Failed: " .. (status.message or "?") end
        return st
    end
    local function defaultDir()
        local exe = plugin("Path")
        if exe and exe ~= "" then return (exe:gsub("[\\/]importer[\\/][^\\/]+$", "\\import")) end
        return "this mod's import folder"
    end
    local function folders()
        local dflt = defaultDir()
        local names, paths = { "Default: " .. (dflt:match("([\\/]mods[\\/].+)$") and ("..." .. dflt:match("([\\/]mods[\\/].+)$")) or dflt) }, { "" }
        for d in (status.drives or ""):gmatch("[^;]+") do
            local letter, free = d:match("^(%a:)|(%d+)$")
            if letter and letter:upper() ~= dflt:sub(1, 2):upper() then
                names[#names + 1] = letter .. "\\Homestead\\import  (" .. free .. " GB free)"
                paths[#paths + 1] = letter .. "\\Homestead\\import"
            end
        end
        local cur, sel = Settings.get("importDir") or "", 1
        for i, p in ipairs(paths) do if p:lower() == cur:lower() then sel = i end end
        return names, paths, sel, dflt
    end

    local function say()
        local f = io.open(DIR .. "import_status.txt", "w")
        if f then for k, v in pairs(status) do f:write(k, "=", v, "\n") end f:close() end
    end
    local function cancel()
        if plugin("Stop") then status.state, status.message = "cancelled", ""; say() end
        Settings.tick(0, true)
    end

    local function run(mode)
        note, noteT = nil, os.time() + 8
        if mode ~= 2 and inGame() then note = "Quit to the main menu to import"
        elseif plugin("Running") then note = "The importer is already running"
        elseif not plugin("Path") or plugin("Path") == "" then note = "The importer isn't there: install Homestead again"
        elseif plugin("Start", mode) then
            status.state, status.step, status.started = mode == 2 and "checking" or "running", "starting", tostring(os.time())
            say()
            if mode == 1 and opt.overwrite then force = false; pcall(NS.setOption, opt.overwrite, false) end
        else note = "The importer didn't start" end
        Settings.tick(0, true)
    end

    local function liveRows()
        local fo4 = status.fo4 and ("Fallout 4: " .. status.fo4 .. (status.fo4version and ("  (version " .. status.fo4version .. ")") or ""))
            or "Fallout 4: not looked for yet"
        local names, paths, sel, dflt = folders()
        local sig = statusLine() .. (busy() and "#c#" or "#i#") .. fo4 .. "#" .. table.concat(names, "|") .. sel
        if sig == shownSig then return end
        shownSig = sig
        for _, k in ipairs({ "status", "fo4", "folder" }) do if opt[k] then pcall(NS.removeOption, opt[k]) end end
        opt.status = NS.addButton(IMP, statusLine(),
            "Makes Homestead's pieces from your own Fallout 4 (about 15 minutes the first time). From the main menu; it installs as you quit Cyberpunk. Cancel stops it: import again to finish.",
            busy() and "Cancel" or "Import", 40, function() if busy() then cancel() else run(force and 1 or 0) end end, 1)
        opt.fo4 = NS.addButton(IMP, fo4, "Where Homestead found Fallout 4 (Steam, GOG, Epic, Game Pass or Bethesda's launcher).",
            "Look again", 40, function() run(2) end, 2)
        opt.folder = NS.addSelectorString(IMP, "Import data folder",
            "Where the import works: about 20 GB while it runs, then about 0.5 GB (9 GB with Keep import files). Import again after changing it. Default: " .. dflt,
            names, sel, 1, function(i) Settings.set("importDir", paths[i] or ""); shownSig = nil end, 3)
    end

    -- Every frame, the main menu too. Reads the importer's news only while an import runs or where the settings can be seen
    -- (main menu, a menu open); not while playing.
    function Settings.tick(dt, now)
        if not NS then return end
        readT = readT - dt
        if readT > 0 and not now then return end
        readT = BUSY[status.state] and 1 or 2
        if not (now or BUSY[status.state] or not inGame() or Homestead.InMenu()) then return end
        if note and os.time() > noteT then note = nil end
        status = readKV("import_status.txt")
        liveRows()
    end

    Settings.apply = applied
    function Settings.init()
        for _, k in ipairs(C.Keys.binds) do local v = Settings.get("key." .. k.name) if v then C.Keys.bind(k.name, v) end end
        NS = GetMod("nativeSettings")
        if not NS then
            print("[Homestead] Native Settings UI is missing (Nexus mod 3518): Homestead's settings and its import need it")
            applied() return
        end
        NS.addTab(T, "Homestead")
        NS.addSubcategory(IMP, "Fallout 4 import")
        Settings.tick(0, true)
        opt.overwrite = NS.addSwitch(IMP, "Overwrite already imported items",
            "Make every piece again, for clean data (if something broke). Off again after the import.", false, false,
            function(v) force = v end)
        NS.addSwitch(IMP, "Keep import files", "Keep the import's working files (about 9 GB): re-imports take ~2 minutes instead of ~7.",
            Settings.on("keepImportFiles"), false, function(v) Settings.set("keepImportFiles", v and "1" or "0") end)
        local function switch(path, label, desc, k)
            NS.addSwitch(path, label, desc, Settings.on(k), DEFAULTS[k], function(v) Settings.set(k, v and "1" or "0"); applied() end)
        end
        local P, B = T .. "/people", T .. "/building"
        -- LiveNav not set up: no People rows at all (placed people are props). Navigation off: its switch alone.
        -- Hidden rows keep their value in settings.txt, unused.
        local nav = C.Life.livenav.present()
        local walks = nav and Settings.on("peopleNav")
        if nav then NS.addSubcategory(P, "People") end
        if walks then
            switch(P, "People walk around", "Placed people wander and go to look at things. Off: they stay where you put them.", "peopleWalk")
            switch(P, "People use furniture", "Placed people sit, sleep, lean and work at the furniture.", "peopleFurniture")
            switch(P, "People talk to each other", "Placed people meet up and chat.", "peopleTalk")
        end
        if nav then switch(P, "Navigation", "People walk on the game's navmesh, which LiveNav makes hold your pieces: to furniture, to each other, where Command mode sends them. Off: placed people are props - they stand where you put them, no furniture, no talking, no Command mode. Takes effect at the next load (the rows above come and go with it).", "peopleNav") end
        NS.addSubcategory(B, "Building")
        switch(B, "Settlement border", "The holographic wall round a settlement in workshop mode.", "borderLine")
        switch(B, "Build limit", "The settlement's size limit (Fallout's size bar). Off: build as much as you like - your frame rate is the limit.", "buildLimit")
        NS.addRangeInt(B, "Settlement size", "A settlement's radius (m). Takes effect when the mods are reloaded or the game restarts.",
            50, 120, 10, Settings.num("radius"), DEFAULTS.radius, function(v) Settings.set("radius", tostring(v)); applied() end)
        NS.addRangeInt(B, "Settlement load distance", "How close (m, to its edge) a settlement comes into the world - its pieces and people - and goes again 100 m further out. Nearer saves memory; too near and you may see a settlement appear when you drive up to it.",
            200, 2000, 50, Settings.num("loadDistance"), DEFAULTS.loadDistance, function(v) Settings.set("loadDistance", tostring(v)); applied() end)
        local K = T .. "/keys"
        NS.addSubcategory(K, "Keys")
        for _, k in ipairs(C.Keys.binds) do
            if k.name ~= "command" or walks then
            NS.addKeyBinding(K, k.label, k.desc .. C.Keys.conflict(k.name), Settings.get("key." .. k.name) or k.default, k.default, k.hold or false,
                function(v) Settings.set("key." .. k.name, v); C.Keys.bind(k.name, v) end) end
        end
        switch(B, "Show snap points", "Snap placement: the snap points of built pieces near the held piece (cyan; the one it snaps to yellow) and the held piece's own (green). Through walls too.", "snapPoints")
        applied()
    end
end
