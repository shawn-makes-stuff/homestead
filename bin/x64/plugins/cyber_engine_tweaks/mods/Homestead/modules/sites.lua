-- Sites: the settlements - V's founded ones, each its workbench whose tags carry where it is (known again after a
-- reload, its bench streamed in or not); Sites.nearest is the one V is at. found / abandon (CET hotkeys), map pins.
return function(C)
    local S, byKey, atan2, des, v4, hashOf, say, log = C.S, C.byKey, C.atan2, C.des, C.v4, C.hashOf, C.say, C.log
    local NOWHERE, RADIUS, originFromAnchor, groundZ = C.NOWHERE, C.RADIUS, C.originFromAnchor, C.groundZ
    local removePiece, refresh = C.removePiece, C.refresh

    -- Home plus every settlement V founded (hotkey "Found a settlement here"). A founded one is its workbench, whose tags carry
    -- the centre in bits, like the key hash (CET can't read a tag's text back): known after a reload even while the bench isn't streamed in.
    -- A piece belongs to the nearest settlement, inside its circle or not. Settlements stand Sites.gap apart (circles never overlap).
    local Sites = { gap = 300, list = {} }
    do
        local AX = { { "x", 16384, 17 }, { "y", 16384, 17 }, { "z", 1024, 14 } }      -- (0.25 m steps)
        local cache = {}
        function Sites.tags(c)
            local t = { CName.new("hssite") }
            for _, a in ipairs(AX) do
                local n = math.floor((c[a[1]] + a[2]) * 4 + 0.5)
                for b = 0, a[3] - 1 do if math.floor(n / 2 ^ b) % 2 == 1 then t[#t + 1] = CName.new("hss" .. a[1] .. b) end end
            end
            return t
        end
        function Sites.make(x, y, z)
            local c = { x = math.floor(x * 4 + 0.5) / 4, y = math.floor(y * 4 + 0.5) / 4, z = math.floor(z * 4 + 0.5) / 4, site = true }
            c.key, c.tags = string.format("%.2f:%.2f", c.x, c.y), Sites.tags(c)
            return c
        end
        local function decode(id)
            local h = hashOf(id)
            if cache[h] == nil then
                cache[h] = false
                if des():IsTagged(id, CName.new("hssite")) then
                    local v = {}
                    for _, a in ipairs(AX) do
                        local n = 0
                        for b = 0, a[3] - 1 do if des():IsTagged(id, CName.new("hss" .. a[1] .. b)) then n = n + 2 ^ b end end
                        v[a[1]] = n / 4 - a[2]
                    end
                    cache[h] = Sites.make(v.x, v.y, v.z)
                end
            end
            return cache[h]
        end
        function Sites.scan()
            local list, known = {}, {}
            for _, s in ipairs(Sites.list) do known[s.key] = s end
            local seen = {}
            for _, id in ipairs(des():GetTaggedIDs(CName.new("Homestead.bench")) or {}) do
                local s = decode(id)
                if s and not seen[s.key] then seen[s.key] = true; list[#list + 1] = known[s.key] or s end
            end
            local h = S.hold
            if h and h.key == "workbench" and S.zone ~= NOWHERE and not seen[S.zone.key] then list[#list + 1] = S.zone end
            Sites.list = list
        end
        function Sites.forget() cache = {} end
        function Sites.nearest(p)
            local best, bd
            for _, s in ipairs(Sites.list) do
                local d = (p.x - s.x) ^ 2 + (p.y - s.y) ^ 2
                if not bd or d < bd then best, bd = s, d end
            end
            return best, bd and math.sqrt(bd)
        end
    end


    local function pin(s)
        local ok, id = pcall(function()
            local data = MappinData.new()
            data.mappinType = TweakDBID.new("Mappins.DefaultStaticMappin")
            data.variant = gamedataMappinVariant.ApartmentVariant
            data.active = true
            data.visibleThroughWalls = true
            return Game.GetMappinSystem():RegisterMappin(data, v4(s.x, s.y, s.z + 2))
        end)
        S.pins[s.key] = ok and id or false
        if not ok then print("[Homestead] map pin failed") end
    end

    -- a new settlement where V stands: its workbench 3 m ahead, facing V, the plot the circle (RADIUS) round a point
    -- 12 m ahead; refused within Sites.gap of another one
    local function found()
        local pos = C.playerPos()
        if not pos or S.build then return false end
        local near, d = Sites.nearest(pos)
        if near and d < Sites.gap then
            say(string.format("Too close to another settlement (%.0f m): settlements stand %d m apart", d, Sites.gap))
            return false
        end
        local f = Game.GetCameraSystem():GetActiveCameraForward()
        local l = math.max(1e-6, math.sqrt(f.x * f.x + f.y * f.y))
        local fx, fy = f.x / l, f.y / l
        local cx, cy = pos.x + fx * 12, pos.y + fy * 12
        local s = Sites.make(cx, cy, groundZ(cx, cy, pos.z + 40))
        table.insert(Sites.list, s)
        C.setZone(s)
        local yaw = math.deg(atan2(-fx, fy)) % 360
        local bx, by = pos.x + fx * 3, pos.y + fy * 3
        C.spawnPiece("workbench", "default", originFromAnchor(byKey.workbench, { x = bx, y = by, z = groundZ(bx, by, pos.z + 40) }, yaw), yaw, false)
        C.index()
        log(string.format("settlement founded at %.1f, %.1f, %.1f", s.x, s.y, s.z))
        say("Settlement founded: hold F to build here")
        S.toastT = 6
        return true
    end
    registerHotkey("homestead_found", "Found a settlement here", function() found() end)

    local function abandon()
        if not S.zone.site then say("Not in a settlement") return false end
        C.exitBuild()
        refresh()
        for _, p in ipairs(S.pieces) do removePiece(p) end
        local key = S.zone.key
        for i, s in ipairs(Sites.list) do if s.key == key then table.remove(Sites.list, i) break end end
        if S.pins[key] then pcall(function() Game.GetMappinSystem():UnregisterMappin(S.pins[key]) end) end
        S.pins[key] = nil
        local pos = C.playerPos()
        C.setZone(pos and Sites.nearest(pos))
        log("settlement abandoned: " .. key)
        say("Settlement abandoned")
        return true
    end
    registerHotkey("homestead_abandon", "Abandon this settlement", function() abandon() end)

    -- Loading by distance: a settlement comes in when V is within S.loadDist (Settings > Building) of its area (circle plus its
    -- pieces' reach) and goes once V is past S.loadDist + MORE (the gap is hysteresis). Via Codeware's DisableEntity / EnableEntity
    -- (Eng.disable / enable), which keep the entity's state: id (jobs.txt, LiveNav, S.info), tags, place in the save. Never out: the zone V builds or commands in.
    local MORE, BUDGET, DESPAWN, SCAN, YOUNG = 100, 100, 10, 2, 30
    local TAGS, POSTS                                         -- (made at first use: no game types while the mod loads)
    local CHUNK, Eng, Anim = C.CHUNK, C.Eng, C.Anim
    -- at: entity hash -> { x, y } where it stands (pieces never move; people: where put). ups / downs: queued ins and outs.
    -- In: nearest V first, BUDGET components a frame (see units; one bigger than that goes alone). Out: DESPAWN a frame. Each once Eng.readyH allows.
    local at, ups, downs, news = {}, {}, {}, nil
    local scanT, young, scanned = 0, YOUNG, nil
    -- S.unloaded: entity hash -> true while out. LiveNav: its objects go out at once with one Rebuild (Life.navUnload) and come back
    -- in one batch once all have attached (Life.navLoad; livenav waits while Sites.loading). People come and go with it, jobs kept, their day paused.
    Sites.loading = false

    -- Boundary Posts (an old adjustable border, no longer in the catalog): a save's are deleted, each once it is in the world
    -- (one saved out: when its settlement comes in), through the lifetime guard's queue. Found by their tag.
    local function posts()
        POSTS = POSTS or CName.new("hs:boundary")
        local n = 0
        for _, id in ipairs(des():GetTaggedIDs(POSTS) or {}) do
            if des():GetEntity(id) and not Eng.dying(id) then C.del(id); n = n + 1 end
        end
        if n > 0 then log(string.format("removed %d Boundary Posts from the save: a settlement is the %d m circle round its centre now; what was built outside it stays", n, RADIUS)) end
    end
    -- Who belongs: by where each stands (the nearest settlement) - S.info's place, else the entity's, kept in `at`. One saved out has
    -- no entity to ask, so going out tags each with hsin<key> (AssignTag, kept in the save) and coming in asks for those too.
    local function scan()
        for _, s in ipairs(Sites.list) do
            s.ids, s.hs = {}, {}
            s.x0, s.y0, s.x1, s.y1 = s.x - RADIUS, s.y - RADIUS, s.x + RADIUS, s.y + RADIUS
        end
        posts()
        TAGS = TAGS or { CName.new("Homestead"), CName.new("Homestead.part") }
        for _, tag in ipairs(TAGS) do
            for _, id in ipairs(des():GetTaggedIDs(tag) or {}) do
                local h = hashOf(id)
                local a, info = at[h], S.info[h] or S.pending[h]
                if not a then
                    local o = info and info.o
                    if not o then local e = des():GetEntity(id) o = e and e:GetWorldPosition() end
                    if o and (o.x ~= 0 or o.y ~= 0) then a = { x = o.x, y = o.y }; at[h] = a end
                end
                local s = a and not Eng.dying(id) and Sites.nearest(a)
                if s then
                    local it = info and byKey[info.key]
                    local r = it and math.max(-it.min[1], it.max[1], -it.min[2], it.max[2]) or 0
                    s.ids[#s.ids + 1], s.hs[#s.hs + 1] = id, h
                    s.x0, s.y0 = math.min(s.x0, a.x - r), math.min(s.y0, a.y - r)
                    s.x1, s.y1 = math.max(s.x1, a.x + r), math.max(s.y1, a.y + r)
                end
            end
        end
    end
    local function edge(s, p)
        local dx, dy = math.max(s.x0 - p.x, 0, p.x - s.x1), math.max(s.y0 - p.y, 0, p.y - s.y1)
        return math.sqrt(dx * dx + dy * dy)
    end
    -- An entity's share of a frame coming in: the components onEntity makes for it (meshes and collider boxes, each a handful of
    -- game calls) plus 1 for itself; a person or game object costs ENT_COST's 10.
    local function units(h)
        local info = S.info[h] or S.pending[h]
        local it = info and byKey[info.key]
        if not it or it.record or it.template then return 10 end
        local c = info.chunk or 1
        return math.max(0, math.min(CHUNK, it.nmesh - (c - 1) * CHUNK)) + math.ceil(#(it.cboxes or it.boxes) / it.chunks) + 1
    end

    local function out(s)
        local hs = {}
        for i, id in ipairs(s.ids or {}) do
            local h = s.hs[i]
            if not S.unloaded[h] then S.unloaded[h] = true; downs[#downs + 1] = { id = id, h = h, s = s }; hs[#hs + 1] = h end
        end
        if #hs > 0 then C.Life.navUnload(hs) end
        return #hs
    end
    local function goOut(s, d)
        local n = out(s)
        if s == S.zone then
            C.Life.reset()
            S.pieces, S.byId, S.world = {}, {}, S.world + 1
            C.index()
        end
        log(string.format("settlement %s out: %d entities (V %.0f m off its edge)", s.key, n, d))
    end
    local function goIn(s, p, d)
        local mine, n = {}, 0
        local function add(id, h, saved)
            if mine[h] then return end
            mine[h] = true
            if S.unloaded[h] or (saved and not des():GetEntity(id)) then
                local a = at[h]
                ups[#ups + 1] = { id = id, h = h, s = s, d = a and (a.x - p.x) ^ 2 + (a.y - p.y) ^ 2 or math.huge }
                n = n + 1
            end
        end
        for i, id in ipairs(s.ids or {}) do add(id, s.hs[i], false) end
        for _, id in ipairs(des():GetTaggedIDs(s.tag) or {}) do add(id, hashOf(id), true) end
        table.sort(ups, function(a, b) return a.d < b.d end)
        if n == 0 then return end
        news = news or { keys = {}, n = 0, t = 0 }
        news.keys[#news.keys + 1] = s.key
        log(string.format("settlement %s in: %d entities to come (V %.0f m off its edge)", s.key, n, d))
    end

    -- A queue's entries run in order while the frame's cap lasts: step(e, what's left) -> its cost (done), nil (not yet, or too big
    -- for what's left: kept, in order) or false (stale: its settlement turned back, dropped). In place: no table a frame.
    local function drain(q, step, cap)
        local spent, j = 0, 0
        for i = 1, #q do
            local e, c = q[i], nil
            if spent < cap then c = step(e, cap - spent, cap) end
            if c == nil then j = j + 1; q[j] = e elseif c then spent = spent + c end
        end
        for i = #q, j + 1, -1 do q[i] = nil end
    end
    local function stepIn(e, left, cap)
        if e.s.loaded ~= true then return false end
        local u = units(e.h)
        if not Eng.readyH(e.h) or (u > left and left < cap) then return nil end
        S.unloaded[e.h] = nil
        Eng.enable(e.id)
        if news then news.n = news.n + 1 end
        return u
    end
    local function stepOut(e)
        if e.s.loaded ~= false then return false end
        if not Eng.readyH(e.h) then return nil end
        des():AssignTag(e.id, e.s.tag)
        C.killFx(e.h)
        Anim.forget(e.id)
        Eng.disable(e.id)
        return 1
    end

    -- Every frame (init.lua update): who belongs where - a look at every id of ours, so only while a session's entities attach (YOUNG s)
    -- and when the zone's pieces changed (S.world; not in workshop mode), at most every SCAN s and at every turn in or out;
    -- then in or out by V's distance to each; then the queues' share of the frame.
    function Sites.stream(dt, p)
        scanT, young = scanT - dt, young - dt
        local fresh = scanT <= 0 and not S.build and (young > 0 or scanned ~= S.world)
        for _, s in ipairs(Sites.list) do fresh = fresh or not s.x0 end
        if fresh then
            scanT, scanned = SCAN, S.world
            scan()
            for _, s in ipairs(Sites.list) do if s.loaded == false then out(s) end end
        end
        for _, s in ipairs(Sites.list) do
            s.tag = s.tag or CName.new("hsin" .. s.key)
            local d, want = edge(s, p), nil
            if d < S.loadDist or (s == S.zone and (S.build or S.cmd)) then want = true
            elseif d > S.loadDist + MORE then want = false end
            if want ~= nil and want ~= s.loaded then
                if not fresh then fresh = true; scan() end
                s.loaded = want
                if want then goIn(s, p, d) else goOut(s, d) end
            end
        end
        if #downs > 0 then drain(downs, stepOut, DESPAWN) end
        if #ups > 0 then drain(ups, stepIn, BUDGET) end
        if news then news.t = news.t + dt end
        Sites.loading = news ~= nil
        -- All in and attached: refresh's full look (the cheap one would list none of them: same ids as before), LiveNav's batch, the log.
        if news and #ups == 0 and not Eng.settling() then
            log(string.format("settlement %s in the world: %d entities, all attached after %.1f s", table.concat(news.keys, ", "), news.n, news.t))
            news, Sites.loading, S.world = nil, false, S.world + 1
            C.Life.navLoad()
        end
    end
    Sites.edge = edge
    function Sites.reset()
        at, ups, downs, news, scanT, young, scanned, Sites.loading = {}, {}, {}, nil, 0, YOUNG, nil, false
        for _, s in ipairs(Sites.list) do s.loaded = nil end
    end

    C.Sites, C.pin, C.found, C.abandon = Sites, pin, found, abandon
end
