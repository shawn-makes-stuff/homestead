-- The game calls that cost (rays, entities made and deleted, teleports, AI moves, overlay pushes) go through here, counted per
-- frame (GetMod("Homestead").calls: n this frame, last, peak since reset(), total). A tag (by) counts a call a second time under its
-- own name. Frame steps are clocked (timed; GetMod("Homestead").calls.slowlog = true logs the slow frames) and entity lifetime is
-- guarded here. init.lua requires this first; E is C.Eng.
return function(E, C)
    local des, try = C.des, C.try
    local n, last, peak, total = {}, {}, {}, {}
    E.n, E.last, E.peak, E.total = n, last, peak, total

    local function count(k, by)
        n[k] = (n[k] or 0) + 1
        if by then n[by] = (n[by] or 0) + 1 end
    end
    E.count = count

    local guard
    function E.frame()
        for k in pairs(last) do last[k] = nil end
        for k, v in pairs(n) do
            last[k], total[k] = v, (total[k] or 0) + v
            if v > (peak[k] or 0) then peak[k] = v end
            n[k] = nil
        end
        guard()
    end
    function E.reset() for k in pairs(peak) do peak[k] = nil end end

    -- Lifetime guard: delete, teleport or pick-up only once the entity has attached and GUARD frames have passed (a create
    -- and delete a frame apart crashed the game). Attached = onEntity reported it, or the game hands it out (GetEntity) for what
    -- that callback misses (person records, weapons, building objects: created unhooked). Never-attaching ones go after WAIT frames.
    local GUARD, WAIT = 2, 600
    E.GUARD = GUARD
    local now, born, seen, queue, doomed = 0, {}, {}, {}, {}
    local function key(id) return tostring(id.hash) end
    function E.attached(id)
        local h = key(id)
        born[h], seen[h] = nil, now
    end
    local function readyH(h)
        local s = seen[h]
        return not born[h] and (not s or now - s > GUARD)
    end
    function E.ready(id) return readyH(key(id)) end
    E.readyH = readyH
    function E.dying(id) return doomed[key(id)] == true end
    function E.now() return now end
    function E.forget() born, seen, queue, doomed = {}, {}, {}, {} end

    function E.rayHit(a, b, by) count("ray", by) return Homestead.RayHit(a, b) end
    function E.terrain(p, by) count("terrain", by) return Homestead.TerrainBelow(p) end
    function E.create(spec, unhooked, own)                   -- own: an entity of ours in plain values, one that
        count("create")                                      -- may go outside the game's population (modules/world.lua)
        local id = des():CreateEntity(spec, own)
        local h = key(id)
        if not seen[h] then born[h] = { id = id, f = now, unhooked = unhooked } end
        return id
    end
    function E.delete(id)
        local h = key(id)
        if doomed[h] then return end
        doomed[h], queue[#queue + 1] = true, id
    end
    function guard()
        now = now + 1
        for h, b in pairs(born) do
            if b.unhooked and des():GetEntity(b.id) then born[h], seen[h] = nil, now
            elseif now - b.f > WAIT then born[h] = nil end
        end
        for h, f in pairs(seen) do if now - f > GUARD then seen[h] = nil end end
        if #queue == 0 then return end
        local keep = {}
        for _, id in ipairs(queue) do
            if E.ready(id) then count("delete"); doomed[key(id)] = nil; des():DeleteEntity(id) else keep[#keep + 1] = id end
        end
        queue = keep
    end
    -- A settlement in and out of the world by distance (sites.lua): Codeware's EnableEntity / DisableEntity keep the entity's
    -- state (id, tags, save slot) and only its world entity goes and comes. Guarded like a delete: disabled once ready, enabled
    -- once ready again, then treated as new (born).
    function E.enable(id)
        count("enable")
        des():EnableEntity(id)
        born[key(id)] = { id = id, f = now, unhooked = true }
    end
    function E.disable(id)
        count("disable")
        des():DisableEntity(id)
        seen[key(id)] = now
    end
    function E.settling() return next(born) ~= nil end       -- an entity of ours is still attaching
    -- byAI: a person standing free, moved by their AI as well (Homestead.reds MoveNPC) - not one about to be put into a
    -- workspot (what that command does to a workspot just begun isn't known; the facility alone seats people fine)
    function E.teleport(e, at, turn, byAI)                   -- -> false: not yet (a new entity; asked again next frame)
        local ok, id = pcall(function() return e:GetEntityID() end)
        if ok and id and not E.ready(id) then count("teleport.wait") return false end
        count("teleport")
        Game.GetTeleportationFacility():Teleport(e, at, turn)
        if byAI then pcall(function() Homestead.MoveNPC(e, at, turn.yaw) end) end
        return true
    end
    function E.move(npc, cmd) count("move") npc:GetAIControllerComponent():SendCommand(cmd) end
    function E.ui(f, ...) count("ui") return try(f, HomesteadUI[f], ...) end
    function E.hint(...) count("ui") return try("hint", Homestead.Hint, ...) end

    -- os.clock steps a millisecond on Windows: use the performance counter through LuaJIT's ffi where present.
    local clock = os.clock
    do
        local ok, ffi = pcall(require, "ffi")
        if ok and type(ffi) == "table" and ffi.cdef then
            pcall(ffi.cdef, "int QueryPerformanceCounter(int64_t *n); int QueryPerformanceFrequency(int64_t *n);")
            pcall(function()
                local n = ffi.new("int64_t[1]")
                ffi.C.QueryPerformanceFrequency(n)
                local hz = tonumber(n[0])
                if hz and hz > 0 then clock = function() ffi.C.QueryPerformanceCounter(n) return tonumber(n[0]) / hz end end
            end)
        end
    end
    local PROF
    local FRAME = { t = {}, last = -10, lines = 300, depth = 0, inner = {} }
    local SLOW = 6
    function E.timed(name, f, ...)
        local d = FRAME.depth + 1
        FRAME.depth, FRAME.inner[d] = d, 0
        local t0 = clock()
        local a, b, c, e = f(...)
        local ms = (clock() - t0) * 1000
        FRAME.depth = d - 1
        local own = ms - FRAME.inner[d]
        if d > 1 then FRAME.inner[d - 1] = FRAME.inner[d - 1] + ms end
        FRAME.t[name] = (FRAME.t[name] or 0) + own
        if PROF then
            local r = PROF[name] or { n = 0, sum = 0, max = 0 }
            r.n, r.sum, r.max = r.n + 1, r.sum + own, math.max(r.max, own)
            PROF[name] = r
        end
        return a, b, c, e
    end
    function E.slowFrame()
        FRAME.depth = 0
        if not E.slowlog then for k in pairs(FRAME.t) do FRAME.t[k] = nil end return end   -- (off: no table made a frame)
        local total, steps = 0, {}
        for k, v in pairs(FRAME.t) do total = total + v; steps[#steps + 1] = { k, v } end
        FRAME.t = {}
        if total < SLOW or FRAME.lines <= 0 or os.clock() - FRAME.last < 2 then return end
        FRAME.last, FRAME.lines = os.clock(), FRAME.lines - 1
        table.sort(steps, function(x, y) return x[2] > y[2] end)
        local t, c = {}, {}
        for _, s in ipairs(steps) do if s[2] >= 0.05 then t[#t + 1] = string.format("%s %.1f", s[1], s[2]) end end
        for k, v in pairs(last) do c[#c + 1] = k .. " " .. v end
        table.sort(c)
        print(string.format("[Homestead] slow frame: %.1f ms of ours (%s; calls: %s)%s", total, table.concat(t, ", "),
            #c > 0 and table.concat(c, ", ") or "none", C.S.build and " workshop mode" or ""))
    end
    function E.prof(on)
        if on then PROF = {} return end
        local out = {}
        for k, r in pairs(PROF or {}) do out[#out + 1] = string.format("%s avg %.2f max %.2f ms (%d)", k, r.sum / r.n, r.max, r.n) end
        table.sort(out)
        return table.concat(out, " | ")
    end
    C.timed = E.timed
end
