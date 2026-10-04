-- The LiveNav navigation backend (navigation.lua's contract). LiveNav is a separate, optional addon that rebuilds the engine's own
-- navmesh round objects it is given, so the game's NPC systems path on our pieces. Found by asking it (LiveNav.Status); without it, or
-- with Settings > People > Navigation off, nothing here calls LiveNav or the navigation system.
-- World edits (Life sends them whichever backend walks; switching navigation off restores the vanilla navmesh): each committed piece
-- is one navmesh object "hs:<entity hash>" of its static collider boxes (cboxes, else boxes; a door leaf is pcol and stays out, so a
-- shut doorway stays walkable). Pieces over 200 boxes go from the import's box file (AddBoxesFile). Each box is solid on its own, so
-- floors, roofs and lintels keep their gaps. Box tops are walkable (walkTop) for pieces the catalog marks `walk` (Fallout walks them:
-- the guard tower, a cage floor), with a stair ramp, or in Structures / Structure / Roads / Buildings; anything else only cuts.
return function(C)
    local S, Q, hashOf, log = C.S, C.Q, C.hashOf, C.log
    local B = {}
    local WALK = { Structures = true, Structure = true, Roads = true, Buildings = true }
    local PREFIX, SETTLE, LOAD_CAP, DOOR = "hs:", 0.3, 5, "hs:door:"
    local WALKS, STILL = { walk = true }, { walk = false }

    local available, was
    local idOf, sent, sigs, lifted, flat = {}, {}, {}, {}, {}
    local doors, traffic, nearest = {}, nil, nil
    local dirty, last, loading, loadT, clock, seen = false, 0, false, 0, 0, nil

    local function call(f)
        local ok, r = pcall(f)
        if not ok then log("LiveNav: " .. tostring(r)) end
        return ok and r
    end
    local function detect()
        local ok, s = pcall(function() return LiveNav.Status() end)
        local now = ok and type(s) == "string"
        if now ~= available then log(now and "LiveNav found: people's navmesh holds the pieces" or "LiveNav not installed: navigation off") end
        available, traffic, nearest = now, nil, nil
        return now
    end
    local function active()
        if available == nil then detect() end
        return available and C.Life.allow.nav ~= false
    end

    local function static(it) return it.cboxes or it.boxes or {} end
    local function floats(key, list)                    -- 10 floats a box (cx, cy, cz, hx, hy, hz, qi, qj, qk, qr), by key
        local f = flat[key]
        if f then return f end
        f = {}
        for _, b in ipairs(list) do
            local n = #f
            for k = 1, 6 do f[n + k] = b[k] end
            f[n + 7], f[n + 8], f[n + 9], f[n + 10] = b[7] or 0, b[8] or 0, b[9] or 0, b[10] or 1
        end
        flat[key] = f
        return f
    end
    local function transform(p)
        local t = WorldTransform.new()
        t:SetPosition(Vector4.new(p.o.x, p.o.y, p.o.z, 1))
        t:SetOrientation(Q.toQuat(p.q, p.yaw))
        return t
    end
    local function sig(p)
        local q = p.q or {}
        return string.format("%s %.3f %.3f %.3f %.2f %.4f %.4f %.4f", p.key, p.o.x, p.o.y, p.o.z, p.yaw or 0, q.i or 0, q.j or 0, q.k or 0)
    end
    local function edit() dirty, last = true, clock end
    local function add(id, p)
        local it = p.it
        local t, walk = transform(p), it.walk or WALK[it.cat] or false
        if not (it.navfile and call(function() return LiveNav.AddBoxesFile(id, it.navfile, t, walk) end)) then
            call(function() return LiveNav.AddBoxes(id, floats(it.key, static(it)), t, walk) end)
        end
    end
    local function leaves(it)
        local l = {}
        for _, pb in ipairs(it.pcol or {}) do for _, b in ipairs(pb) do l[#l + 1] = b end end
        return l
    end
    -- A shut door's leaves (catalog pcol, at rest) go as traffic boxes "hs:door:<entity hash>" (LiveNav.AddTrafficBoxes): cars and
    -- pavement walkers stop at them, the navmesh never sees them, so people still path through. Sent when shut (commit, load, anim.lua ->
    -- Life.navDoor -> B.door), removed as it starts to open, at a scrap or a pick-up. Never a Rebuild. Skipped (logged once) on a LiveNav without the call.
    local function shut(p, now)
        local h = hashOf(p.id)
        if now == (doors[h] or false) then return end
        if not now then call(function() return LiveNav.RemoveObject(DOOR .. h) end); doors[h] = nil return end
        if traffic == nil then
            traffic = pcall(function() assert(LiveNav.AddTrafficBoxes) end)
            if not traffic then log("LiveNav has no AddTrafficBoxes (older than 11356b3): shut doors don't stop traffic") end
        end
        local f = traffic and floats(p.it.key .. "/door", leaves(p.it))
        if f and #f > 0 then doors[h] = call(function() return LiveNav.AddTrafficBoxes(DOOR .. h, f, transform(p)) end) or nil end
    end

    local function sweep()
        for _, p in ipairs(S.pieces) do
            local h = hashOf(p.id)
            local id = idOf[h]
            if not id and not p.it.npc and (p.o.x ~= 0 or p.o.y ~= 0) and #static(p.it) > 0 then
                for i, l in ipairs(lifted) do
                    if l.moving and l.key == p.key then id = l.id; table.remove(lifted, i) break end
                end
                id = id or PREFIX .. h
                idOf[h] = id
            end
            if id and sent[id] ~= p then
                local s = sig(p)
                if sigs[id] ~= s then
                    add(id, p)
                    sigs[id] = s
                    edit()
                end
                sent[id] = p
            end
            if not doors[h] and (p.o.x ~= 0 or p.o.y ~= 0) and C.Anim.shut(p) then shut(p, true) end
        end
    end
    local function drop()
        for _, l in ipairs(lifted) do
            call(function() return LiveNav.RemoveObject(l.id) end)
            sent[l.id], sigs[l.id] = nil, nil
            edit()
        end
        lifted = {}
    end
    local function rebuild()
        dirty = false
        if call(function() return LiveNav.Rebuild() end) == -1 then
            available = false
            log("LiveNav's hooks aren't installed (Rebuild -1): navigation off")
        end
    end
    local function forget() idOf, sent, sigs, lifted, doors, seen = {}, {}, {}, {}, {}, nil end
    local function wipe() call(function() return LiveNav.RemovePrefix(PREFIX) end); edit() end

    local step
    function B.frame(dt) C.timed("navsync", step, dt) end
    function step(dt)
        clock = clock + dt
        local on = active()
        if on ~= was then
            if was and available then forget(); wipe(); rebuild() end
            was, seen = on, nil
        end
        if not on then return end
        if S.hold and S.hold.kind == "move" then
            for _, l in ipairs(lifted) do l.moving = true end
            return
        end
        if C.Sites.loading then return end
        if loading then
            if S.settled == nil or (#(S.waitIds or {}) > 0 and clock - loadT < LOAD_CAP) then return end
            loading, seen = false, S.world
            sweep(); drop()
            if dirty then rebuild() end
            return
        end
        if seen ~= S.world then seen = S.world; sweep() end
        drop()
        if dirty and clock - last >= SETTLE then rebuild() end
    end
    function B.pieceRemoved(p)
        shut(p, false)
        local h = hashOf(p.id)
        local id = idOf[h]
        if not id then return end
        idOf[h] = nil
        lifted[#lifted + 1] = { id = id, key = p.key }
        if active() then call(function() return LiveNav.Release(id) end) end
    end
    function B.clear(load)
        forget()
        loading, loadT = load or false, clock
        if load or available == nil then detect() end
        if active() then wipe() end
    end
    function B.zone()
        if loading or not active() then return end
        drop()
        if dirty then rebuild() end
    end
    function B.present() if available == nil then detect() end return available end
    function B.door(p, now) if active() then shut(p, now) end end
    -- A settlement out by distance (sites.lua -> Life.navUnload): remove each piece's object and shut doors' traffic boxes (by the id it
    -- has: a moved piece keeps an older one), one Rebuild. Back in (B.load, once all have attached): as a load without the wipe - nothing sent
    -- while Sites.loading, then every listed piece in one frame and one Rebuild.
    function B.unload(hs)
        if not active() then return end
        local n = 0
        for _, h in ipairs(hs) do
            local id = idOf[h]
            if id then call(function() return LiveNav.RemoveObject(id) end); idOf[h], sent[id], sigs[id], n = nil, nil, nil, n + 1 end
            if doors[h] then call(function() return LiveNav.RemoveObject(DOOR .. h) end); doors[h] = nil end
        end
        if n > 0 then rebuild() end
    end
    function B.load() if active() then loading, loadT = true, clock end end

    local function natives() return Homestead and Homestead.NavPoint and Homestead.NavPath end
    function B.caps() return (active() and natives()) and WALKS or STILL end
    -- The navmesh point nearest (x, y, z) within `within` m each way, or nil: LiveNav.Nearest (the poly its Probe starts and ends on);
    -- on an older LiveNav, Homestead.NavPoint (the game's FindPointInSphereOnlyHumanNavmesh).
    function B.near(x, y, z, within)
        if not B.caps().walk then return nil end
        within = within or 1.5
        if nearest == nil then
            nearest = pcall(function() assert(LiveNav.Nearest) end)
            if not nearest then log("LiveNav has no Nearest (older than 591731a): spots from the game's navmesh query") end
        end
        local ok, v
        if nearest then ok, v = pcall(function() return LiveNav.Nearest(Vector4.new(x, y, z, 1), Vector4.new(within, within, within, 0)) end)
        else ok, v = pcall(Homestead.NavPoint, x, y, z, within) end
        if ok and v and v.w == 1 then return { x = v.x, y = v.y, z = v.z } end
    end
    function B.free(x, y, z) if not B.caps().walk then return true end return B.near(x, y, z, 0.2) ~= nil end
    -- Why `to` can't be reached from `from`, or nil; and the probe's length (LiveNav.Probe: Detour on the live Human navmesh). -1: an end
    -- is off the navmesh ("no way there"); another negative: the best path ends short, on another region ("no way up there", e.g. a foundation
    -- top reached only by a ladder: LiveNav makes no ladder links, as in Fallout). An older LiveNav can't be asked: nil, as reachable.
    function B.reach(from, to)
        local ok, d = pcall(function() return LiveNav.Probe(Vector4.new(from.x, from.y, from.z, 1), Vector4.new(to.x, to.y, to.z, 1)) end)
        if not ok or type(d) ~= "number" or d >= 0 then return nil, ok and d or nil end
        return d == -1 and "no way there" or "no way up there", d
    end
    local function cancel(npc, st)
        if st.cmd and npc then pcall(function() npc:GetAIControllerComponent():CancelCommand(st.cmd) end) end
        st.cmd = nil
    end
    -- One move, on the navmesh (never ignoreNavigation), cancelling the one before. It doesn't end where they get to: it holds them there
    -- till Life plays what they came for (B.stop right before the workspot) or sends them on. Ended by itself, it left a person with neither
    -- command nor workspot while the spot's device came, and one placed from a record T-posed.
    local function walk(npc, st, to, close)
        cancel(npc, st)
        local pos = WorldPosition.new()
        pos:SetVector4(Vector4.new(to.x, to.y, to.z, 1))
        local spec = AIPositionSpec.new()
        spec:SetWorldPosition(pos)
        local cmd = AIMoveToCommand.new()
        cmd.movementTarget = spec
        cmd.rotateEntityTowardsFacingTarget = false
        cmd.ignoreNavigation = false
        cmd.desiredDistanceFromTarget = close and 0.1 or 0.3
        cmd.movementType = moveMovementType.Walk
        cmd.finishWhenDestinationReached = false
        C.Eng.move(npc, cmd)
        st.cmd, st.to, st.lost = cmd, to, nil
    end
    -- A move cancelled by LiveNav's removal hand-off (the floor under them scrapped or picked up) is sent again once they stand on the navmesh
    -- (Probe(at, at) >= 0): the walk on to its goal, or the hold back at its spot. Lost = the command says it ended (AICommandState 3 Cancelled,
    -- 4 Interrupted, 6 Failure; never 5 Success, which a hold doesn't reach), or a held one is over 1 m off the spot (state unreadable).
    local LOST = { [3] = true, [4] = true, [6] = true }
    function B.keep(npc, st)
        if not st.cmd then return end
        local at = npc:GetWorldPosition()
        if not st.lost then
            local ok, s = pcall(function() return EnumInt(st.cmd.state) end)
            st.lost = ok and LOST[s] or (not st.goal and (at.x - st.to.x) ^ 2 + (at.y - st.to.y) ^ 2 > 1) or nil
            if not st.lost then return end
            log(string.format("navigation: %s's move cancelled (handed off?), sent again once on the navmesh", tostring(st.rec):match("[^.]+$") or "?"))
        end
        local ok, d = pcall(function() local v = Vector4.new(at.x, at.y, at.z, 1) return LiveNav.Probe(v, v) end)
        if not (ok and type(d) == "number" and d >= 0) then return end
        st.lost = nil
        walk(npc, st, (st.goal or not B.reach(at, st.to)) and st.to or at, st.close)
        st.best, st.stuck = math.huge, 0
    end
    function B.moveTo(npc, st, to, close)
        if not B.caps().walk then return false end
        local at = npc:GetWorldPosition()
        local why = B.reach(at, to)
        if why then return false, why end
        local ok, path = pcall(Homestead.NavPath, Vector4.new(at.x, at.y, at.z, 1), Vector4.new(to.x, to.y, to.z, 1))
        local e = ok and path and path[#path]
        if not e or (e.x - to.x) ^ 2 + (e.y - to.y) ^ 2 > 0.09 or math.abs(e.z - to.z) > 0.6 then return false end
        st.goal, st.close, st.best, st.stuck, st.resent = to, close, math.huge, 0, false
        walk(npc, st, to, close)
        return true
    end
    function B.stop(npc, st) cancel(npc, st); st.goal = nil end
    function B.update(npc, st, dt)
        if not st.goal then return true end
        local at = npc:GetWorldPosition()
        local d = math.sqrt((at.x - st.goal.x) ^ 2 + (at.y - st.goal.y) ^ 2)
        if d < 0.4 then st.goal = nil return true end
        if d < st.best - 0.1 then st.best, st.stuck = d, 0 else st.stuck = st.stuck + dt end
        if st.stuck > 6 then
            if st.resent then B.stop(npc, st) return false end
            st.resent, st.stuck = true, 0
            walk(npc, st, st.goal, st.close)
        end
    end

    return B
end
