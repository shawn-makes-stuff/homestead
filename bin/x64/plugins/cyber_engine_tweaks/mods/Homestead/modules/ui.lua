-- UI: the workshop menu (the catalog's tree by category and group, the row on screen, the item picked and held),
-- the keys (Keys: the bindings, the game's own actions on them, conflicts), the hints in the game's own list
-- (gameHints), the use prompt on a usable piece, the bench prompt, the menu overlay (syncUI: pushed on change) and
-- the line overlay (Lines: one canvas, one push a frame) with a plant's cage (plantLines).
return function(C)
    local S, catalog, byKey, hashOf, BUDGET, KEYS, Eng = C.S, C.catalog, C.byKey, C.hashOf, C.BUDGET, C.KEYS, C.Eng
    local Gizmo, Life, Q, local2world = C.Gizmo, C.Life, C.Q, C.local2world

    local FINISHES = 8            -- kit pieces offer their first few appearances (brick, plaster, colours) as items
    local FILLER = { ml = 1, int = 1, ext = 1, common = 1, walls = 1, wall = 1, maskset = 1, vdr = 1, sda = 1, lc = 1, jt = 1 }
    -- an appearance name as a short label: words the mesh's own name already has and filler go, three words at most
    -- ("ml_int_common_walls_a_wallpaper_lizzies" on int_common_a_wall -> "Wallpaper Lizzies"; "ap1" -> "Variant 1")
    local function finish(app, mesh)
        local skip, t = {}, {}
        for w in mesh:lower():gmatch("[%a%d]+") do skip[w] = true end
        for w in app:lower():gmatch("[^_%s]+") do
            if w:match("^ap%d+$") then w = "variant " .. w:sub(3) end
            local code = #w <= 2 or (w:find("%d") and not w:find("^variant"))
            if not FILLER[w] and not skip[w] and not code and #t < 3 then t[#t + 1] = (w:gsub("^%l", string.upper)) end
        end
        return #t > 0 and table.concat(t, " ") or app
    end

    -- catalog: the menu tree, as deep as each category needs. tree[cat] is the category's root node; a node is
    -- { name, kids, thumb, count } and its kids are nodes or entries. An item's `group` is its path below the category
    -- ("Large/Straight"). An entry is an item or one of its finishes: { key, app, name, thumb }. Kit pieces a storey up
    -- swap to their `upper` twin by themselves, so the twin (hidden) isn't in the menu.

    local function child(node, name)
        for _, k in ipairs(node.kids) do if not k.key and k.name == name then return k end end
        local k = { name = name, kids = {} }
        table.insert(node.kids, k)
        return k
    end
    local function settle(n)
        n.count = 0
        for _, k in ipairs(n.kids) do
            if k.key then n.count = n.count + 1; n.thumb = n.thumb or k.key
            else settle(k); n.count = n.count + k.count; n.thumb = n.thumb or k.thumb end
        end
    end
    -- Build with Fallout 4's pieces, imported from the player's own install (FO4_IMPORT.md); Cyberpunk's own props, weapons
    -- and some nature are one tab, Night City; its buildings, building kits and roads are out of the menu (catalog
    -- `stashed`: placed ones still load). HS_NATIVE = true shows those too.
    local NATIVE = HS_NATIVE or false                              -- (a plain global: CET sandboxes _G away)
    local function shown(it)
        if it.key == "workbench" or it.hidden then return false end
        if NATIVE == "only" then return not it.fo4 end
        return NATIVE or not it.stashed
    end
    local function makeTree()
      local tree = {}
      for _, it in ipairs(catalog.items) do
        if shown(it) then
            tree[it.cat] = tree[it.cat] or { name = it.cat, kids = {} }
            local node = tree[it.cat]
            for part in it.group:gmatch("[^/]+") do node = child(node, part) end
            table.insert(node.kids, { key = it.key, app = it.apps[1], name = it.name, thumb = it.thumb })
            if it.kind then
                local seen, mesh = {}, it.meshes[1][1]:match("([^\\]+)%.mesh$") or it.key
                for k, a in ipairs(it.apps) do
                    local f = k > 1 and finish(a, mesh)
                    if f and not seen[f:lower()] and #seen < FINISHES - 1 and not a:lower():find("dest") and not a:lower():find("damag") and not a:lower():find("dirt") and a:lower() ~= "off" and not a:lower():find("_off$") then
                        seen[f:lower()] = true
                        seen[#seen + 1] = f
                        table.insert(node.kids, { key = it.key, app = a, name = it.name .. " " .. f, thumb = it.thumb })
                    end
                end
            end
        end
      end
      for _, root in pairs(tree) do settle(root) end
      return tree
    end
    local tree = makeTree()
    local CATS = {}
    for _, c in ipairs(catalog.categories) do if tree[c] then CATS[#CATS + 1] = c end end
    do
        local listed, more = {}, {}
        for _, c in ipairs(CATS) do listed[c] = true end
        for c in pairs(tree) do if not listed[c] then more[#more + 1] = c end end
        table.sort(more)
        for _, c in ipairs(more) do CATS[#CATS + 1] = c end
    end

    -- The line overlay (HomesteadUI.Gizmo, one canvas): its owners (Command mode's dot, a plant's cage, snap points, the gizmo and
    -- its cursor) each say what they show (nil: nothing); one push at the end of the frame, only when one of them said something.
    local Lines = { by = {}, dirty = false, ORDER = { "cmd", "plant", "snap", "gizmo" } }
    function Lines.set(owner, segs, cx, cy)
        if not segs and not Lines.by[owner] then return end
        Lines.by[owner], Lines.dirty = segs and { segs = segs, cx = cx, cy = cy } or nil, true
    end
    function Lines.flush()
        if not Lines.dirty then return end
        Lines.dirty = false
        local all, cx, cy = {}, -1, -1
        for _, k in ipairs(Lines.ORDER) do
            local l = Lines.by[k]
            if l then
                for _, v in ipairs(l.segs) do all[#all + 1] = v end
                if l.cx and l.cx >= 0 then cx, cy = l.cx, l.cy end
            end
        end
        Eng.ui("Gizmo", all, cx, cy, "")
    end

    -- Night City's plants: the game's outline doesn't draw on foliage, so a looked-at one is drawn in lines of its own
    -- shape (catalog `profile`: the mesh in slices, an ellipse each, build_catalog.plant_profile): rings at each slice and
    -- lines between them - a cage the shape of the plant. Without a profile, its box.
    local function plant(p) return p.it.cat == "Night City" and (p.it.group or ""):find("^Nature/") and not p.it.group:find("^Nature/Rocks") end
    local plantLines
    do
    local BOX_EDGES = { { 0, 1 }, { 2, 3 }, { 4, 5 }, { 6, 7 }, { 0, 2 }, { 1, 3 }, { 4, 6 }, { 5, 7 }, { 0, 4 }, { 1, 5 }, { 2, 6 }, { 3, 7 } }
    local RING = 12
    function plantLines(p)
        local it, c, segs = p.it, Gizmo.cam(), {}
        local function seg(a, b) if a and b then for _, x in ipairs({ a[1], a[2], b[1], b[2], 5, 4 }) do segs[#segs + 1] = x end end end
        local function sp(x, y, z) local u, v = Gizmo.project(c, local2world(p.o, p.yaw or 0, x, y, z)) return u and { u, v } end
        local pr = it.profile
        if pr then
            local last
            for _, s in ipairs(pr) do
                local ring = {}
                for k = 0, RING - 1 do
                    local a = 2 * math.pi * k / RING
                    ring[k + 1] = sp(s[2] + math.cos(a) * s[4], s[3] + math.sin(a) * s[5], s[1])
                end
                for k = 1, RING do seg(ring[k], ring[k % RING + 1]) end
                if last then for k = 1, RING, 3 do seg(last[k], ring[k]) end end
                last = ring
            end
            return segs
        end
        local P = {}
        for i = 0, 7 do
            P[i] = sp(i % 2 == 0 and it.min[1] or it.max[1], math.floor(i / 2) % 2 == 0 and it.min[2] or it.max[2], i < 4 and it.min[3] or it.max[3])
        end
        for _, e in ipairs(BOX_EDGES) do seg(P[e[1]], P[e[2]]) end
        return segs
    end
    end


    local function root() return tree[CATS[S.cat]] end
    local function rowNode()
        local n = root()
        for _ = 2, math.max(S.level, 1) do n = n.kids[S.sel[n] or 1] end
        return n
    end
    local function picked() local n = rowNode(); return n.kids[S.sel[n] or 1], n end

    local function holdNew(e)
        Gizmo.off()
        local yaw = S.hold and S.hold.yaw or 0
        if not S.free and not byKey[e.key].fo4 then yaw = Q.square(yaw) end
        S.hold = { kind = "new", key = e.key, app = e.app, yaw = yaw, flip = S.hold and S.hold.flip or false, t = 0 }
        S.slot, S.dist = nil, nil
    end

    local function syncHold()
        if S.hold and S.hold.kind == "move" then return end
        local e = S.level >= 1 and picked()
        if e and e.key then
            if not S.hold or S.hold.key ~= e.key or S.hold.app ~= e.app then holdNew(e) end
        else
            S.hold, S.rot = nil, 0
        end
    end

    local function benchPrompt(pos)
        local b = S.bench
        local near = false
        if b and not Game.GetMountedVehicle(Game.GetPlayer()) then
            local dx, dy = b.at.x - pos.x, b.at.y - pos.y
            local d = math.sqrt(dx * dx + dy * dy)
            local _, f = C.view()
            local fl = math.sqrt(f.x * f.x + f.y * f.y)
            near = d < 3 and math.abs(b.at.z - pos.z) < 2.5 and (d < 1 or fl < 0.2 or (dx * f.x + dy * f.y) / (d * fl) > 0.5)
        end
        S.nearBench = near
    end

    -- Hints are listed bottom first, like the game's own: label, key, label, key, ...

    -- Our hints live in the game's own list (Homestead.Hint): its look, its order, and it moves when the list does (a
    -- weapon drawn). Each key is shown through an input action the game has on it, so it follows the player's bindings
    -- (a hint shows only for an action that is live where V is: F is Choice1_Hold, not Choice1). Outside workshop mode:
    -- hold F for it, E for what the piece under the crosshair does; in it, hints() below. Sent on change only.
    -- the keys (Settings > Mods > Homestead > Keys: BINDS may be rebound; the game's own binds on a key are read through the
    -- plugin, HomesteadImport.GameKeys, for the setting's text and for the hint icons - a hint borrows a game action live on
    -- foot on the same key, so the icon follows the key. The game's key can't be taken from it: a conflict is shown, not fixed)
    local Keys = {}
    Keys.binds = {
        { name = "hold", label = "Workshop mode (hold)", hold = true, desc = "Hold it anywhere in a settlement to build, hold again to leave; a tap at the workbench." },
        { name = "command", label = "Command mode (hold)", hold = true, desc = "Hold it in a settlement to give people jobs, hold again to leave. In Command mode a tap clears the job of the person selected or looked at." },
        { name = "act", label = "Place / Build", desc = "Workshop mode: build the held piece, pick up the piece looked at. Command mode: select a person, assign them, send them." },
        { name = "scrap", label = "Scrap", desc = "Workshop mode: scrap the piece held or looked at." },
        { name = "back", label = "Back", desc = "Workshop mode: back up the menu, put a moved piece back, leave. Command mode: unselect, then leave." },
        { name = "free", label = "Snap / free placement", desc = "Workshop mode: switch between snapping and free placement." },
        { name = "gizmo", label = "Gizmo", desc = "Free placement: the move gizmo on the held piece, or on the piece looked at." },

    }
    for _, b in ipairs(Keys.binds) do b.default = KEYS[b.name] end
    Keys.GAME = {
        Jump = "Jump", ToggleCrouch = "Crouch", Crouch = "Crouch (hold)", Sprint = "Sprint", ToggleSprint = "Sprint", Dodge = "Dodge",
        Choice1 = "Interact", Choice1_Hold = "Interact (hold)", Choice2 = "Interact 2", Reload = "Reload", IconicCyberware = "Cyberware ability",
        QuickMelee = "Quick melee", RangedAttack = "Attack", MeleeAttack = "Attack", CameraAim = "Aim", NextWeapon = "Next weapon", PreviousWeapon = "Previous weapon",
        VisionHold = "Scanner", VisionToggle = "Scanner", VisionPush = "Scanner", PhotoMode = "Photo mode", Phone = "Phone", CallVehicle = "Call vehicle",
        OpenInventory = "Inventory", OpenMap = "Map", OpenJournal = "Journal", OpenHubMenu = "Hub menu", OpenPerks = "Perks", OpenCrafting = "Crafting", OpenPauseMenu = "Pause menu",
        UseConsumable = "Consumable", ThrowGrenade = "Grenade", SwitchItem = "Switch item", WeaponWheel = "Weapon wheel", QuickSave = "Quick save", QuickLoad = "Quick load",
        ToggleWalk = "Walk", Forward = "Move", Back = "Move", Left = "Move", Right = "Move",
    }
    Keys.BLOCKED = {                                             -- what workshop mode's restriction (GameplayRestriction.HomesteadBuild) stops
        IconicCyberware = true, QuickMelee = true, RangedAttack = true, MeleeAttack = true, CameraAim = true, NextWeapon = true, PreviousWeapon = true,
        VisionHold = true, VisionToggle = true, VisionPush = true, PhotoMode = true, Phone = true, CallVehicle = true, OpenInventory = true, OpenMap = true,
        OpenJournal = true, OpenHubMenu = true, OpenPerks = true, OpenCrafting = true, UseConsumable = true, ThrowGrenade = true, WeaponWheel = true,
        Reload = true,
    }
    Keys.DEFACT = { hold = "Choice1_Hold", command = "Choice2", act = "IconicCyberware", scrap = "Choice2", back = "VisionHold", free = "QuickMelee", gizmo = "Dodge" }
    local gameKeys
    function Keys.actions(ik)
        if not gameKeys then
            gameKeys = {}
            local ok, s = pcall(function() return HomesteadImport.GameKeys() end)
            for line in (ok and type(s) == "string" and s or ""):gmatch("[^\n]+") do
                local a, k = line:match("^([^|]+)|(.+)$")
                if a then gameKeys[k] = gameKeys[k] or {}; table.insert(gameKeys[k], a) end
            end
        end
        return gameKeys[ik] or {}
    end
    function Keys.actionFor(name)
        local acts = Keys.actions(KEYS[name])
        for _, a in ipairs(acts) do if Keys.GAME[a] then return a end end
        if acts[1] then return acts[1] end
        for _, b in ipairs(Keys.binds) do if b.name == name and KEYS[name] == b.default then return Keys.DEFACT[name] end end
    end
    function Keys.conflict(name)
        local acts, entry = Keys.actions(KEYS[name]), name == "hold" or name == "command"
        if #acts == 0 then return next(gameKeys or {}) and " The game uses this key for nothing on foot (so no on-screen hint for it)." or "" end
        local seen, red, grey = {}, {}, {}
        for _, a in ipairs(acts) do
            local l = Keys.GAME[a] or a
            if not seen[l] then seen[l] = true; table.insert(Keys.BLOCKED[a] and grey or red, l) end
        end
        local t = ""
        if #red > 0 then t = string.format(" CONFLICT: the game's %s fires on it too%s.", table.concat(red, ", "), entry and "" or " in workshop mode") end
        if #grey > 0 then t = t .. string.format(" Also the game's %s (blocked in workshop mode).", table.concat(grey, ", ")) end
        return t
    end
    function Keys.label(ik) return (ik or ""):gsub("^IK_", ""):upper() end
    function Keys.bind(name, key)
        for _, b in ipairs(Keys.binds) do if b.name == name then KEYS[name] = (key and key ~= "" and key ~= "IK_None") and key or b.default end end
        S.hintSig = nil
        return Keys.conflict(name)
    end

    local gameHints
    do
        local ACTION = { F = "Choice1_Hold", E = "IconicCyberware", R = "Choice2", TAB = "VisionHold", Q = "QuickMelee",
                         DOWN = "down_button", ["LEFT/RIGHT"] = "right_button", ["LMB/RMB"] = "RangedAttack", LMB = "RangedAttack", RMB = "CameraAim",
                         WHEEL = "NextWeapon", CTRL = "Dodge", SHIFT = "ToggleSprint" }
        function gameHints(list, dt)
            S.hintT = (S.hintT or 0) + (dt or 0)
            local key = table.concat(list, "|") .. (S.overlay and "|o" or "") .. ((not S.build and not S.cmd and S.inZone and not S.nearBench) and (Life.walks() and "|zw" or "|z") or "")
            if key == S.hintKey and S.hintSig then
                if S.hintT < 4 then return end                    -- (sent again now and then: one sent while the game
                S.hintT = 0                                       -- was still loading never showed)
                for i, a in ipairs(S.hintOrder) do Eng.hint(a, S.hinted[a], true, S.hintHold[a] or false, i) end
                return
            end
            S.hintKey = key
            local want, order, holdOf = {}, {}, {}
            if not S.overlay then
                if not S.build and not S.cmd then
                    if S.inZone and not S.nearBench then
                        for _, e in ipairs({ { "hold", "Workshop" }, { "command", "Command" } }) do
                            local a = (e[1] ~= "command" or Life.walks()) and Keys.actionFor(e[1])
                            if a and not want[a] then want[a] = e[2]; order[#order + 1] = a; holdOf[a] = true end
                        end
                    end
                else
                    for i = 1, #list, 2 do
                        local k = list[i + 1]
                        local a = ACTION[k] or Keys.actionFor(k)
                        if a and not want[a] then want[a] = list[i]; order[#order + 1] = a; holdOf[a] = (k == "hold" or k == "command") or nil end
                    end
                end
            end
            local labels = {}
            for i, a in ipairs(order) do labels[i] = want[a] end
            local sig = table.concat(order, ",") .. "|" .. table.concat(labels, ",")
            S.hintOrder, S.hintHold = order, holdOf
            if sig == S.hintSig then return end
            S.hintT = 0
            S.hintSig = sig
            for a, label in pairs(S.hinted) do Eng.hint(a, label, false, false, 0) end
            S.hinted = {}
            for i, a in ipairs(order) do
                Eng.hint(a, want[a], true, holdOf[a] or false, i)
                S.hinted[a] = want[a]
            end
        end
    end

    local function usePrompt()
        local p = not S.build and not S.overlay and S.use
        local u, v
        if p then
            local it = p.it
            local lx, ly, lz = it.cx, it.cy, (it.min[3] + it.max[3]) / 2
            local st = it.anim and S.anims[hashOf(p.id)]
            local n, sx, sy, sz = 0, 0, 0, 0
            for k, pb in ipairs(it.anim and it.pcol or {}) do
                local m = it.meshes[it.anim.first + k - 1]
                if pb[1] and m and m[10] then
                    local lo, hi = { math.huge, math.huge, math.huge }, { -math.huge, -math.huge, -math.huge }
                    for _, b in ipairs(pb) do
                        for i = 1, 3 do lo[i], hi[i] = math.min(lo[i], b[i] - b[i + 3]), math.max(hi[i], b[i] + b[i + 3]) end
                    end
                    local cx, cy, cz = (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2, (lo[3] + hi[3]) / 2
                    local now = st and st.lv and st.lv[k]
                    if now then
                        local rest = { i = -m[7], j = -m[8], k = -m[9], r = m[10] }
                        local dx, dy, dz = Q.rot(rest, cx - m[2], cy - m[3], cz - m[4])
                        local nx, ny, nz = Q.rot({ i = now[4], j = now[5], k = now[6], r = now[7] }, dx, dy, dz)
                        cx, cy, cz = now[1] + nx, now[2] + ny, now[3] + nz
                    end
                    n, sx, sy, sz = n + 1, sx + cx, sy + cy, sz + cz
                end
            end
            if n > 0 then lx, ly, lz = sx / n, sy / n, sz / n end
            if it.max[3] - it.min[3] < 1.2 then lz = it.max[3] + 0.15 end   -- (something low, a footlocker: just over it)
            u, v = Gizmo.project(Gizmo.cam(), local2world(p.o, p.yaw, lx, ly, lz))
        end
        if u then Eng.ui("Use", true, u, v, S.useLabel, Keys.label(KEYS.hold)); S.useShown = true
        elseif S.useShown then Eng.ui("Use", false, 0, 0, "", ""); S.useShown = false end
    end

    local function hints()
        if S.cmd then
            local t = { "Done", "back", "Clear job", "command" }
            if S.cmd.who then table.insert(t, "Assign / Wait here") else table.insert(t, "Select") end
            table.insert(t, "act")
            return t
        end
        if not S.build then return {} end
        local h = S.hold
        local place = S.free and "Snap Placement" or "Free Placement"
        local function turn(t)
            if S.gz then
                table.insert(t, "Drag handle"); table.insert(t, "LMB")
                table.insert(t, "Look around"); table.insert(t, "RMB")
                table.insert(t, "Steps"); table.insert(t, "SHIFT")
                table.insert(t, "Gizmo off"); table.insert(t, "gizmo")
                return t
            end
            local it = h and byKey[h.key]
            if it and it.kind == "wall" and not S.free then table.insert(t, "Flip"); table.insert(t, "LMB/RMB")
            else table.insert(t, "Rotate"); table.insert(t, "LMB/RMB") end
            table.insert(t, "Nearer / Further"); table.insert(t, "WHEEL")
            if S.free then table.insert(t, "Gizmo"); table.insert(t, "gizmo") end
            table.insert(t, place); table.insert(t, "free")
            return t
        end
        if h and h.kind == "move" then
            local t = { "Cancel", "back", "Place", "act" }
            if h.key ~= "workbench" then table.insert(t, "Scrap"); table.insert(t, "scrap") end
            return turn(t)
        elseif h then
            local t = turn({ "Back", "back", "Build", "act" })
            table.insert(t, "Item"); table.insert(t, "LEFT/RIGHT")
            return t
        end
        local t = S.level == 0 and { "Exit", "back", "Open", "DOWN", "Category", "LEFT/RIGHT" }
            or { "Back", "back", "Open", "DOWN", "Pick", "LEFT/RIGHT" }
        if S.target then
            table.insert(t, "Move"); table.insert(t, "act")
            if not S.target.bench then table.insert(t, "Scrap"); table.insert(t, "scrap") end
        end
        return t
    end

    local function syncUI()
        local prompt = S.nearBench and not S.build
        local target, sel, n = "", 0, nil
        if S.build then
            n = rowNode()
            sel = (S.sel[n] or 1) - 1
            if not S.hold and S.target then target = S.target.it.name end
            if S.hold and S.hold.kind == "move" then target = byKey[S.hold.key].name end
        elseif S.cmd and S.target then
            target = S.target.it.name
            local j = S.target.it.npc and Life.jobOf(hashOf(S.target.id))
            if j and j:find(",") then target = target .. "  -  standing by"
            elseif j and S.byId[j] then target = target .. "  -  " .. S.byId[j].it.name end
        end
        gameHints(hints(), S.frameDt)
        if target ~= S.targetShown then S.targetShown = target; Eng.ui("Target", target) end
        local sig = table.concat({ tostring(prompt), tostring(S.build), S.level, S.cat, tostring(n), sel, S.cost, S.toast or "", KEYS.hold }, "#")
        if sig == S.menuSig then return end
        S.menuSig = sig
        local names, thumbs, detail, crumb = {}, {}, "", ""
        if n then
            crumb = "Workshop  /  " .. CATS[S.cat]
            local path, m = {}, root()
            for _ = 2, S.level do m = m.kids[S.sel[m] or 1]; path[#path + 1] = m.name end
            if #path > 0 then crumb = crumb .. "  /  " .. table.concat(path, "  /  ") end
            for _, k in ipairs(n.kids) do
                names[#names + 1] = k.name
                thumbs[#thumbs + 1] = k.key and (k.thumb or "") or tostring(k.count)   -- a folder: its count; an item: its
                                                                                          -- thumbnail "atlas|part" (catalog `thumb`)
            end
            local e = n.kids[sel + 1]
            detail = e and not e.key and (e.count .. (e.count == 1 and " item" or " items")) or ""
        end
        Eng.ui("Render", prompt, S.build, S.level, CATS, S.cat - 1, crumb, names, thumbs, sel, detail,   -- (CET: 15 at most)
                           S.cost, BUDGET, Keys.label(KEYS.hold), S.toast or "")
    end

    C.tree, C.CATS, C.root, C.rowNode, C.picked, C.holdNew = tree, CATS, root, rowNode, picked, holdNew
    C.syncHold, C.Lines, C.plant, C.plantLines, C.benchPrompt = syncHold, Lines, plant, plantLines, benchPrompt
    C.Keys, C.gameHints, C.usePrompt, C.hints, C.syncUI = Keys, gameHints, usePrompt, hints, syncUI
end
