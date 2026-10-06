-- The entity system the mod talks to (C.des() is W). People, the game's own objects and work spots go to Codeware's
-- dynamic entity system as before. Our own pieces (homestead\empty*.ent, dressed by entities.lua) go to Codeware's
-- STATIC entity system (the dynamic one only where the game has no static system: an old Codeware). Why (2026-10-06): the
-- dynamic system registers every entity with the game's population system (Codeware DynamicEntitySystem.cpp,
-- SpawnFromEntityState: RegisterEntity, priority 0 = Quest) - the one that budgets crowd and traffic. The user's
-- settlement of 223 entities had no cars; they came back with about 100 of ours left. A static entity is spawned by
-- the runtime spawner: no stub, no population. Seen in game by the user 2026-10-06: the pieces stay, the cars are back.
-- What the static system lacks is done here, under the dynamic system's own names so no caller differs:
--   tags       kept here (IsTagged, GetTaggedIDs, AssignTag; Uid: the "hsu:" tag, as Homestead.Uid reads a dynamic one)
--   out / in   DisableEntity / EnableEntity are Detach / Attach: the entity and its id stay, as the callers expect
--   the save   static entities are not saved. Ours are written to pieces_<rev>.txt and the game's fact hs_world, kept
--              in the save, says which file a save has (as hs_jobs does for jobs.txt). A revision is one stretch of
--              changes between two saves: the first change after a load or a save (Session/BeforeSave -> W.saved)
--              starts a new one, so a file a save points at is never written again. pieces.txt: the highest so far.
--              Files are not deleted: an old save must find its own.
-- A piece a save still has in the dynamic system (made before this) is made again by C.remake (entities.lua), two a frame.
return function(W, C)
    local log = C.log
    local DIR = HS_DIR or ""
    local dyn, sta, noSta
    local st, order = {}, {}                                 -- static pieces: by id hash; in the order made
    local loaded, rev, top, frozen, dirty, dirtyT = false, 0, 0, true, false, 0
    local making
    local mark, marks = nil, 0                               -- this load's own tag on every static entity (live)

    local function dy() dyn = dyn or Game.GetDynamicEntitySystem() return dyn end
    local function stat()
        if sta or noSta then return sta end
        local ok, s = pcall(function() return Game.GetStaticEntitySystem() end)
        if ok and s then sta = s else noSta = true; log("no static entity system (Codeware too old?): pieces stay in the game's population") end
        return sta
    end
    local function key(id) return tostring(id.hash) end
    -- TAGS ARE TEXT here and in every caller. Never read back from the game: in the game a name's text did not come back
    -- (2026-10-06: every tag read the same, every piece "had" every tag, and the Boundary Posts cleanup deleted the
    -- user's settlement). For the dynamic system the game's name is made of the text.
    local cns = {}
    local function cn(t)
        assert(type(t) == "string", "a tag is text")
        local c = cns[t]
        if not c then c = CName.new(t); cns[t] = c end
        return c
    end
    local function fact(v)
        local ok, r = pcall(function()
            local q = Game.GetQuestsSystem()
            if v then q:SetFactStr("hs_world", v) end
            return q:GetFactStr("hs_world")
        end)
        return ok and tonumber(r) or nil
    end

    local function write()
        dirty = false
        local f = io.open(DIR .. "pieces_" .. rev .. ".txt", "w")
        if not f then log("pieces_" .. rev .. ".txt can't be written: this save's pieces are NOT kept") return end
        for _, r in ipairs(order) do
            if r.keep then
                f:write(r.on and "1" or "0", "|", r.path, "|", string.format("%.17g|%.17g|%.17g|%.17g|%.17g|%.17g|%.17g", r.x, r.y, r.z, r.i, r.j, r.k, r.r),
                        "|", table.concat(r.tags, "\t"), "\n")
            end
        end
        f:close()
    end
    local function changed(r)
        if not r.keep then return end
        if frozen or rev == 0 then
            top = top + 1
            rev, frozen = top, false
            local f = io.open(DIR .. "pieces.txt", "w")
            if f then f:write(top, "\n"); f:close() end
            fact(rev)
        end
        dirty, dirtyT = true, 0
    end
    function W.tick(dt)                                      -- (init.lua, every frame: a burst of changes is one write)
        if not dirty then return end
        dirtyT = dirtyT + dt
        if dirtyT > 0.5 then write() end
    end
    function W.saved()                                       -- the game is about to save: what it points at is whole, and closed
        if dirty then write() end
        frozen = true
    end

    local function spawn(r)
        local spec = StaticEntitySpec.new()
        spec.templatePath = ResRef.FromString(r.path)
        spec.position = Vector4.new(r.x, r.y, r.z, 1)
        spec.orientation = Quaternion.new(r.i, r.j, r.k, r.r)
        spec.attached = r.on
        local tags = { CName.new(mark) }
        for _, t in ipairs(r.tags) do tags[#tags + 1] = CName.new(t) end
        spec.tags = tags
        making = r                                           -- (should it initialise inside the call - tools/sim.py's does when
        local id = stat():SpawnEntity(spec)                  -- spawned detached - entities.lua asks its tags before we know its id)
        making = nil
        if not id or tostring(id.hash) == "0" or id.hash == 0 then return nil end
        r.id = id
        st[key(id)], order[#order + 1] = r, r
        return id
    end
    local function load()
        loaded, st, order, dirty, frozen = true, {}, {}, false, true
        marks = marks + 1
        mark = "hsw:" .. os.time() .. ":" .. marks
        rev, top = fact() or 0, 0
        local f = io.open(DIR .. "pieces.txt", "r")
        if f then top = tonumber(f:read("*l")) or 0; f:close() end
        top = math.max(top, rev)
        if rev == 0 or not stat() then return end
        f = io.open(DIR .. "pieces_" .. rev .. ".txt", "r")
        if not f then log("pieces_" .. rev .. ".txt is missing: this save's pieces can't be put back") return end
        local n, bad = 0, 0
        for line in f:lines() do
            local on, path, x, y, z, i, j, k, r, tags = line:match("^([01])|([^|]*)|([^|]*)|([^|]*)|([^|]*)|([^|]*)|([^|]*)|([^|]*)|([^|]*)|(.*)$")
            local rec = on and { on = on == "1", keep = true, path = path, x = tonumber(x), y = tonumber(y), z = tonumber(z),
                                 i = tonumber(i), j = tonumber(j), k = tonumber(k), r = tonumber(r), tags = {}, has = {} }
            if rec and rec.x and rec.y and rec.z and rec.i and rec.j and rec.k and rec.r then
                for t in tags:gmatch("[^\t]+") do rec.tags[#rec.tags + 1] = t; rec.has[t] = true end
                if spawn(rec) then n = n + 1 else bad = bad + 1 end
            elseif line ~= "" then bad = bad + 1 end
        end
        f:close()
        log(string.format("pieces: revision %d of %d, %d put back%s", rev, top, n, bad > 0 and (", " .. bad .. " FAILED") or ""))
    end
    -- are the static entities we know of still in the world? (asked of Codeware by this load's own tag: an id alone
    -- could be another world's)
    local function live()
        local ok, r = pcall(function()
            local s = stat()
            if not s or not s:IsReady() then return false end
            local m = CName.new(mark)
            for _, o in ipairs(order) do if s:IsTagged(o.id, m) then return true end end
            return false
        end)
        return ok and r == true
    end
    -- A session's start or end (init.lua session). The game tells us of one load TWICE, seconds apart, in the same
    -- world (2026-10-06, the game's log: "200 put back" at 19:57:22 and again at 19:57:27; the user: "Two walls, two
    -- doors in the same place"). So only a world that is gone is forgotten: while our entities are still there the
    -- book is kept and nothing is put back again.
    function W.forget()
        dyn, sta, noSta, cns = nil, nil, nil, {}
        if loaded and #order > 0 and live() then return end
        if dirty then write() end
        local old = order
        loaded, st, order, dirty = false, {}, {}, false
        -- (what is kept by id - sounds, animations: W.gone, init.lua - goes with them: the next world's ids may be the same numbers)
        if W.gone then for _, o in ipairs(old) do pcall(W.gone, o.id) end end
    end
    function W.drop() dyn, sta = nil, nil end                -- (a frame: the game is asked for its systems anew)

    function W.static(id) return st[key(id)] ~= nil end
    -- should this catalog item's own entities be static? (people and the game's own objects never)
    function W.wants(it) return not (it.record or it.template) and stat() ~= nil end
    function W.count() return #order end

    function W:IsReady()
        local d = dy()
        if not d or not d:IsReady() then return false end
        if not loaded then
            local s = stat()
            if s and not s:IsReady() then return false end
            load()
        end
        return true
    end
    -- own: an entity of our own that may be static, in plain values { path, x, y, z, i, j, k, r, tags = { text }, keep }
    -- (Eng.create's third argument); spec: the same thing for the dynamic system, used when it is not to be static
    function W:CreateEntity(spec, own)
        if not (own and stat()) then return dy():CreateEntity(spec) end
        local r = { on = true, keep = own.keep == true, path = own.path, x = own.x, y = own.y, z = own.z, i = own.i, j = own.j, k = own.k, r = own.r, tags = {}, has = {} }
        for _, n in ipairs(own.tags) do assert(type(n) == "string", "a tag is text"); r.tags[#r.tags + 1] = n; r.has[n] = true end
        local id = spawn(r)
        if not id then return dy():CreateEntity(spec) end     -- (the static system refused: as before)
        changed(r)
        return id
    end
    function W:DeleteEntity(id)
        local h = key(id)
        local r = st[h]
        if not r then return dy():DeleteEntity(id) end
        stat():DespawnEntity(id)
        st[h] = nil
        for n, o in ipairs(order) do if o == r then table.remove(order, n) break end end
        changed(r)
        return true
    end
    function W:GetEntity(id)
        local r = st[key(id)]
        if not r then return dy():GetEntity(id) end
        return r.on and stat():GetEntity(id) or nil
    end
    function W:DisableEntity(id)
        local r = st[key(id)]
        if not r then return dy():DisableEntity(id) end
        if r.on then r.on = false; stat():DetachEntity(id); changed(r) end
        return true
    end
    function W:EnableEntity(id)
        local r = st[key(id)]
        if not r then return dy():EnableEntity(id) end
        if not r.on then r.on = true; stat():AttachEntity(id); changed(r) end
        return true
    end
    function W:IsTagged(id, tag)
        local r = st[key(id)] or making
        if not r then return dy():IsTagged(id, cn(tag)) end
        return r.has[tag] == true
    end
    function W:AssignTag(id, tag)
        local r = st[key(id)]
        if not r then return dy():AssignTag(id, cn(tag)) end
        local n = tag
        if not r.has[n] then r.has[n] = true; r.tags[#r.tags + 1] = n; changed(r) end
        return true
    end
    function W:GetTaggedIDs(tag)
        local out = dy():GetTaggedIDs(cn(tag))
        if #order == 0 then return out end
        local n, all = tag, {}
        for i, id in ipairs(out or {}) do all[i] = id end
        for _, r in ipairs(order) do if r.has[n] then all[#all + 1] = r.id end end
        return all
    end
    function W:GetTaggedID(tag)
        local n = tag
        for _, r in ipairs(order) do if r.has[n] then return r.id end end
        return dy():GetTaggedID(cn(tag))
    end
    function W:IsPopulated(tag)
        local n = tag
        for _, r in ipairs(order) do if r.has[n] then return true end end
        return dy():IsPopulated(cn(tag))
    end
    function W:Uid(id)                                       -- "" none; a dynamic one's: Homestead.reds Uid
        local r = st[key(id)]
        if not r then return Homestead.Uid(id) end
        for _, t in ipairs(r.tags) do if t:sub(1, 4) == "hsu:" then return t:sub(5) end end
        return ""
    end
end
