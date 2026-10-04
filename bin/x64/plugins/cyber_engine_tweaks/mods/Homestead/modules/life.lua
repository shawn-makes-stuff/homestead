-- People living in a settlement. Each has a day of their own (a personality: how much they like to sit, work, talk, look about),
-- doing one thing at a time: sit, work a bench, look at something, stop to talk, stand about, sleep at night. Seats and work spots are
-- Fallout's furniture markers (catalog `seats` [x, y, z, yaw, kind, top] in the piece's space, tools/fo4/furniture.py), used through
-- Cyberpunk's own workspots via a device: an empty entity at the marker carrying the workspot (Life.onEntity), deleted when left. Its
-- height is the seat's: Cyberpunk's animations sit at Cyberpunk's seat heights (SEAT), Fallout's seat tops come from its meshes (`top`).
-- Movement is the navigation backend's (navigation.lua); without navigation people are props. Their day isn't saved; Command mode's
-- jobs are (jobs.txt). init.lua requires this once everything it uses exists; Life is C.Life.
return function(Life, C)
    local S, des, hashOf, local2world, Anim, eng = C.S, C.des, C.hashOf, C.local2world, C.Anim, C.Eng
    Life.allow = { walk = true, furniture = true, talk = true, nav = true }
    local NAV = require("modules/navigation")(C)
    local LN = NAV.livenav
    local B = NAV.null

    local W = "homestead\\workspots\\"                     -- (Cyberpunk's own, copied looping: tools/make_workspots.py -
                                                              -- the game's play once and get up)
    local WS = {
        chair = { "chair\\generic__sit_chair__sit_around__01", "chair\\generic__sit_chair_lean_back__sit_around__01",
                  "chair\\generic__sit_chair_lean_front__sit_around__01", "chair\\generic__sit_chair_can__drink__01",
                  "chair\\generic__sit_chair_cellphone__check__01", "chair\\generic__sit_chair_lean_back__think__01" },
        couch = { "couch\\generic__sit_couch__sit_around__01" },
        table = { "chair\\generic__sit_chair_lean_front__sit_around__01", "chair\\generic__sit_chair_asian_takeout__eat__01",
                  "chair\\generic__sit_chair_lean_front_glass__drink__01", "chair\\generic__sit_chair_can__drink__01" },
        stool = { "barstool\\generic__sit_barstool__sit_around__01", "bar\\generic__sit_barstool_cigarette__smoke__01" },
        bed = { "bed\\generic__lie_bed_lean_left__lie_around__01" },
        floorbed = { "ground\\generic__lie_ground_lean_left__lie_around__01" },
        guard = { "ground\\generic__stand_ground__guard__01", "ground\\generic__stand_ground__guard__02" },
        counter = { "bar\\generic__stand_bar_lean_front__stand_around__01", "bar\\generic__stand_bar_lean_front_pen__work__01" },
        work = { "table\\generic__stand_table_lean_front_tool__fix__01", "table\\generic__stand_table_lean_front__search__01" },
        kneel = { "ground\\generic__kneel_ground_tool__fix__01" },
        look = { "ground\\generic__stand_ground__look_at_products__01", "ground\\generic__stand_ground__look_at_products__02",
                 "ground\\generic__stand_ground__look_at_products__03", "ground\\generic__stand_ground_arms_crossed__stand_around__02" },
        chat = { "ground\\generic__stand_ground__stand_around__01", "ground\\generic__stand_ground__stand_around__02",
                 "ground\\generic__stand_ground__stand_around__03", "ground\\generic__stand_ground_arms_crossed__stand_around__03",
                 "ground\\generic__stand_ground__wait__01" },
        idle = { "ground\\generic__stand_ground__stand_around__04", "ground\\generic__stand_ground__stand_around__05",
                 "ground\\generic__stand_ground__stand_around__06", "ground\\generic__stand_ground__stand_around__07",
                 "ground\\generic__stand_ground__wait__02", "ground\\generic__stand_ground_cellphone__check_phone__01",
                 "ground\\generic__stand_ground_cigarette__smoke__01" },
    }
    local BODY = {                                            -- bodies the generic ones don't fit (a big man in a
        generic = WS,                                         -- generic bed: a T-pose): their own, where there are any
        big = { chair = { "chair\\big__sit_chair_lean_back__sit_around__01", "chair\\big__sit_chair_can__drink__01" },
                table = { "chair\\big__sit_chair_lean_front_burger__eat__01" },
                counter = { "bar\\big__stand_bar_lean_front__stand_around__01" },
                kneel = { "ground\\big__kneel_ground__kneel_around__01" },
                look = { "ground\\big__stand_ground__stand_around__01" }, chat = { "ground\\big__stand__stand_around__01" },
                idle = { "ground\\big__stand_ground__stand_around__01" } },
        fat = { chair = { "chair\\fat__sit_chair_cigarette__sit_around__01" },
                table = { "chair_table\\fat__sit_chair_table_lean_front_cigar__smoke__01" },
                look = { "ground\\fat__stand_ground__stand_around__01" }, chat = { "ground\\fat__stand_ground__stand_around__01" },
                idle = { "ground\\fat__stand_ground_cigarette__stand_around__01" } },
        child = { chair = { "chair\\child__sit_chair_lean_front__play__01" },
                  table = { "chair_table\\child__sit_chair_table_lean_front__sit_around__01" },
                  look = { "ground\\child__stand__stand_around__01" }, chat = { "ground\\child__stand__stand_around__01" },
                  idle = { "ground\\child__stand__stand_around__01" } },
        cat = { sit = { "@animals\\cat\\cat__sit__01" }, lie = { "@animals\\cat\\cat__lie__01" },   -- (@: under workspots,
                sleep = { "@animals\\cat\\cat__sleep__01", "@animals\\cat\\cat__sleep__02" },          -- not common)
                clean = { "@animals\\cat\\cat__sit_ground__clean_self__01" }, scratch = { "@animals\\cat\\cat__scratching__01" } },
    }
    local GROUP = { ManAverage = "generic", WomanAverage = "generic", ManBig = "big", ManMassive = "big", ManFat = "fat",
                    WomanFat = "fat", Child = "child", ChildMale = "child", ChildFemale = "child" }
    -- what they do, the spots each uses, and for how long (seconds; a bed: till morning)
    local ACT = { relax = { "chair", "couch", "table", "stool" }, work = { "work", "counter", "kneel", "guard" },
                  sleep = { "bed", "floorbed" } }
    local LONG = { relax = { 240, 600 }, work = { 180, 420 }, look = { 25, 70 }, chat = { 60, 180 }, idle = { 30, 90 },
 }
    local ACTS = { "sleep", "relax", "work", "chat", "look", "idle", "wander" }
    local USE = {}
    for act, kinds in pairs(ACT) do for _, k in ipairs(kinds) do USE[k] = act end end
    local IDLE, REACH, TALK = { 2, 6 }, 30, 20
    local FROM = { bed = 1.2, chair = 0.6, couch = 0.6, stool = 0.6 }
    local SEAT = { chair = 0.444, table = 0.444, couch = 0.463, stool = 0.834, bed = 0.403, floorbed = 0 }   -- (hips
                                                              -- less 0.085 sitting, 0.146 lying: the chair one matches)
    -- FWD: m forward (+: the way the sitter faces) of the seat top's middle (Fallout's mesh: seats[7], tools/fo4/furniture.py seat_mid),
    -- else of Fallout's marker. Cyberpunk's sit further back than Fallout's, so they are nudged forward; a kneel reaches into a fire, a lean over a bench into it.
    local FWD = { chair = 0.2, table = 0.2, stool = 0.2, couch = 0.3, kneel = -0.3, work = -0.2 }
    local LIE = {
        [W .. "bed\\generic__lie_bed_lean_left__lie_around__01.workspot"] = { 0, -0.05, -0.72 },
        [W .. "ground\\generic__lie_ground_lean_left__lie_around__01.workspot"] = { 80, -0.08, -0.08 },
    }
    local SIDE = { bed = true, floorbed = true }
    local STAND = { look = true, chat = true, idle = true, sit = true, lie = true, sleep = true, clean = true, scratch = true }
    -- a cat: mostly sits about, lies down, naps (longer at night); now and then washes, scratches, wanders
    local CAT = { { "sit", 30, { 60, 180 } }, { "lie", 25, { 120, 300 } }, { "sleep", 15, { 300, 600 } },
                  { "clean", 10, { 20, 45 } }, { "scratch", 5, { 10, 20 } }, { "wander", 15 } }
    local NIGHT = { [22] = true, [23] = true, [0] = true, [1] = true, [2] = true, [3] = true, [4] = true, [5] = true }

    local PATHS = {}
    for _, set in pairs(BODY) do for _, l in pairs(set) do for i, w in ipairs(l) do
        PATHS[#PATHS + 1] = (w:sub(1, 1) == "@" and "base\\workspots\\" .. w:sub(2) or W .. w) .. ".workspot"; l[i] = #PATHS
    end end end
    local who = {}
    local order
    local function sorted()
        if not order then
            order = {}
            for h in pairs(who) do order[#order + 1] = h end
            table.sort(order)
        end
        return order
    end
    local function people()
        local o, i = sorted(), 0
        return function()
            repeat i = i + 1 until not o[i] or who[o[i]]
            if o[i] then return o[i], who[o[i]] end
        end
    end
    local taken = {}
    -- Jobs (Command mode): person hash -> the hash of the piece they're assigned to, or a spot "x,y,z" they were sent to. They go to it and
    -- use it for good until cleared; kept in jobs.txt (entity ids survive a save: persistSpawn), checked against the pieces there are when they come up.
    local JOBS = (HS_DIR or "") .. "jobs.txt"
    local jobs = {}
    do
        local f = io.open(JOBS, "r")
        if f then for line in f:lines() do local a, b = line:match("^(%w+)=([%w%.,%-]+)$") if a then jobs[a] = b end end f:close() end
    end
    local function saveJobs()
        local f = io.open(JOBS, "w")
        if not f then return end
        for h, j in pairs(jobs) do f:write(h, "=", j, "\n") end
        f:close()
    end
    -- Once a session, once refresh has read our entities (S.seenIds: every settlement's, Life.sync): a job whose person or piece is none of
    -- ours any more is dropped. Never at a save: a piece placed since the last refresh isn't in S.seenIds yet.
    local pruned = false
    local function prune()
        if pruned or S.settled == nil then return end
        pruned = true
        local ours, n = {}, 0
        for _, h in ipairs(S.seenIds or {}) do ours[tostring(h)] = true end
        for h, j in pairs(jobs) do
            if not ours[h] or not (j:find(",", 1, true) or ours[j]) then jobs[h], n = nil, n + 1 end
        end
        if n > 0 then saveJobs(); C.log(string.format("jobs: %d dropped (their person or piece is gone)", n)) end
    end

    local function span(r) return r[1] + math.random() * (r[2] - r[1]) end
    local function dist2(a, b) return (a.x - b.x) ^ 2 + (a.y - b.y) ^ 2 + (a.z - b.z) ^ 2 end

    local function seats()
        local out = {}
        for _, p in ipairs(S.pieces) do
            for i, s in ipairs(p.it.seats or {}) do
                local f, r = (FWD[s[5]] or 0) + (s[7] or 0), math.rad(s[4])
                local w = local2world(p.o, p.yaw, s[1] - math.sin(r) * f, s[2] + math.cos(r) * f,
                    s[3] + ((s[6] and SEAT[s[5]]) and s[6] - SEAT[s[5]] or 0))
                w.yaw, w.kind, w.key, w.piece = (p.yaw or 0) + s[4], s[5], hashOf(p.id) .. ":" .. i, p
                out[#out + 1] = w
            end
        end
        return out
    end

    local function front(s, d)
        local r = math.rad(s.yaw)
        return { x = s.x - math.sin(r) * d, y = s.y + math.cos(r) * d, z = s.z }
    end

    local function side(s, lx, ly)
        local r = math.rad(s.yaw)
        local fx, fy = -math.sin(r), math.cos(r)
        return { x = s.x + lx * fy + ly * fx, y = s.y - lx * fx + ly * fy, z = s.z }
    end
    local function approaches(s)
        if STAND[s.kind] then return { s } end
        if SIDE[s.kind] then return { side(s, 0.9, 0), side(s, -0.9, 0) } end
        local d = FROM[s.kind] or -0.6
        return { front(s, d), side(s, 0.6, 0), side(s, -0.6, 0), front(s, -d) }
    end
    local function facing(a, b) return math.deg(math.atan2(-(b.x - a.x), b.y - a.y)) end

    -- a piece's own colliders off for a moment while someone gets on or off it: Cyberpunk's animations are made for
    -- its furniture, and stepping through ours the body stood up on it (a picnic bench) - through it, they step off
    local ghosts = {}
    local function solid(p, on)
        local e = p and des():GetEntity(p.id)
        if not e then return end
        for first = 1, math.max(#(p.it.cboxes or p.it.boxes or {}), 1), 64 do
            local c = e:FindComponentByName(CName.new("hs_collider" .. first))
            if c then pcall(function() c:Toggle(on) end) end
        end
    end
    local function ghost(p, t) if p then if not ghosts[p] then solid(p, false) end ghosts[p] = t end end

    -- lying: straight into it - its own way in sat on a bed's end. Entry 1 is the workspot's root sequence (its way
    -- in included), entry 2 the lie loop: jumped to entry 1 a woman lay diagonally across a bed. Set onto the device
    -- first (where the loop starts from), so the jump doesn't blend in from wherever the walk ended
    local LIE_LOOP = 2
    local function play(dev, npc, st)
        local lie = SIDE[st.seat.kind]
        if lie then
            pcall(function() eng.teleport(npc, dev:GetWorldPosition(), EulerAngles.new(0, 0, st.devYaw or st.seat.yaw)) end)
        end
        local ok = pcall(function() Game.GetWorkspotSystem():PlayInDeviceSimple(dev, npc, false, CName.new("hs_ws"),
            CName.new("None"), CName.new("None"), 0.5, 1) end)
        if ok and lie then pcall(function() Game.GetWorkspotSystem():SendJumpCommandEnt(npc, LIE_LOOP, true) end)
        elseif ok then ghost(st.seat.piece, 3) end
        return ok
    end

    local function device(s, n)
        local a, yaw, at = LIE[PATHS[n]], s.yaw, s
        if a then
            yaw = s.yaw - a[1]
            local d = side({ x = 0, y = 0, z = 0, yaw = yaw }, a[2], a[3])
            at = { x = s.x - d.x, y = s.y - d.y, z = s.z }
        end
        local spec = DynamicEntitySpec.new()
        spec.templatePath = ResRef.FromString("homestead\\empty.ent")
        spec.position = Vector4.new(at.x, at.y, at.z, 1)
        spec.orientation = EulerAngles.new(0, 0, yaw):ToQuat()
        spec.persistSpawn = false
        spec.alwaysSpawned = true
        spec.tags = { CName.new("Homestead.ws"), CName.new("hsws" .. n) }
        return eng.create(spec), yaw
    end

    local drops = {}
    local function free(st)
        if st.seat and st.seat.key then taken[st.seat.key] = nil end
        if st.dev then drops[#drops + 1] = { id = st.dev, t = 6 } end
        st.seat, st.dev = nil, nil
    end

    local function rise(npc, st)
        if npc and st.set == "cat" then
            pcall(function() Game.GetWorkspotSystem():SendSlowExitSignal(npc) end)
            npc = nil
        end
        if npc then
            local s, dir = st.seat, nil
            if s then
                local fwd = (FROM[s.kind] or -1) > 0 and 1 or -1
                local order = SIDE[s.kind] and { { 1, 0 }, { -1, 0 }, { 0, -1 }, { 0, 1 } } or { { 0, fwd }, { 0, -fwd }, { 1, 0 }, { -1, 0 } }
                for _, d in ipairs(order) do
                    local w = side(s, d[1] * 0.8, d[2] * 0.8)
                    if B.free(w.x, w.y, s.z) then
                        local r = math.rad(st.devYaw or s.yaw)
                        local gx, gy, wx, wy = -math.sin(r), math.cos(r), w.x - s.x, w.y - s.y
                        dir = { (wx * gy - wy * gx) / 0.8, (wx * gx + wy * gy) / 0.8 }
                        break
                    end
                end
            end
            local now = s and SIDE[s.kind]
            if s and not now then ghost(s.piece, 3.5) end
            pcall(function()
                if dir then Game.GetWorkspotSystem():SendFastExitSignal(npc, Vector3.new(dir[1], dir[2], 0), false, true, now or false, true)
                else Game.GetWorkspotSystem():SendFastExitSignal(npc) end
            end)
        end
        local o = st.partner and who[st.partner]
        if o and o.partner == st.h then o.partner = nil; o.t = math.min(o.t, 1 + math.random() * 3) end
        st.partner = nil
        free(st)
        st.mode, st.t = "idle", span(IDLE)
    end

    local function body(npc, st)
        if st.set == nil then
            local ok, b = pcall(function() return npc:GetBodyType().value end)
            local rec = (st.rec or ""):lower()
            st.set = (ok and GROUP[b]) or (rec:find("cat") and "cat") or false
        end
        return st.set and BODY[st.set]
    end

    local function crowded(st, s)
        for h, o in people() do
            if h ~= st.h and o.partner ~= st.h then
                local e = des():GetEntity(o.id)
                local a = e and e:GetWorldPosition()
                if a and (a.x - s.x) ^ 2 + (a.y - s.y) ^ 2 < 0.49 and math.abs(a.z - s.z) < 1.5 then return true end
                local g = o.seat
                if g and g ~= s and (g.x - s.x) ^ 2 + (g.y - s.y) ^ 2 < 0.49 and math.abs(g.z - s.z) < 1.5 then return true end
            end
        end
        return false
    end

    local cut, now = {}, 0
    local function assign(npc, st, s, act, dur)
        if not s.key and crowded(st, s) then return false end
        local ok = false
        for _, a in ipairs(approaches(s)) do ok = B.moveTo(npc, st, a); if ok then break end end
        if Life.trace then Life.trace("assign", st, s, ok) end
        if not ok then return false end
        if s.key then taken[s.key] = st.h end
        st.mode, st.seat, st.act, st.dur = "walk", s, act, dur
        return true
    end

    local function like(st)
        if not st.like then
            local h = 0
            for c in tostring(st.h):gmatch("%d") do h = (h * 31 + tonumber(c)) % 1000003 end
            local function r(k) return ((h * (k * 7919 + 13)) % 1000) / 1000 end
            st.like = { relax = 0.8 + r(1) * 1.6, work = 0.2 + r(2) * 1.4, look = 0.4 + r(3) * 0.8, chat = 0.4 + r(4) * 1.2,
                        idle = 0.5, wander = 0.2 + r(5) * 0.5 }
        end
        return st.like
    end

    local function free_to_talk(o)
        return o.set and o.set ~= "cat" and not o.partner and not jobs[o.h]
            and (o.mode == "idle" or (o.mode == "use" and o.seat and (o.seat.kind == "idle" or o.seat.kind == "look")))
    end

    local function lookSpot(at)
        local things = {}
        for _, p in ipairs(S.pieces) do
            local sz = p.it.size
            if not p.it.npc and sz and sz[3] > 0.3 and sz[3] < 3.5 and math.max(sz[1], sz[2]) < 4
               and (p.o.x - at.x) ^ 2 + (p.o.y - at.y) ^ 2 < 20 * 20 then things[#things + 1] = p end
        end
        if #things == 0 then return nil end
        local p = things[math.random(#things)]
        local c = local2world(p.o, p.yaw, p.it.cx, p.it.cy, 0)
        local r = math.max(p.it.size[1], p.it.size[2]) / 2 + 0.7
        local a = math.random() * 2 * math.pi
        local f = B.near(c.x + math.cos(a) * r, c.y + math.sin(a) * r, p.o.z, 1.5)
        if not f then return nil end
        return { x = f.x, y = f.y, z = f.z, yaw = facing(f, c), kind = "look" }
    end

    local function wanderSpot(at)
        for _ = 1, 6 do
            local a, d = math.random() * 2 * math.pi, 4 + math.random() * 10
            local x, y = at.x + math.cos(a) * d, at.y + math.sin(a) * d
            if C.inZone(x, y) then
                local f = B.near(x, y, at.z, 1.5)
                if f then return { x = f.x, y = f.y, z = f.z, yaw = math.random() * 360, kind = "idle" } end
            end
        end
    end

    local function chat(npc, st, at)
        local best, bd
        for h, o in people() do
            if h ~= st.h and free_to_talk(o) then
                local e = des():GetEntity(o.id)
                local b = e and e:GetWorldPosition()
                local d = b and (b.x - at.x) ^ 2 + (b.y - at.y) ^ 2
                if d and d < TALK * TALK and (not bd or d < bd) then best, bd = { o = o, e = e, b = b }, d end
            end
        end
        if not best then return false end
        local m = B.near((at.x + best.b.x) / 2, (at.y + best.b.y) / 2, at.z, 2)
        if not m then return false end
        local dx, dy = best.b.x - at.x, best.b.y - at.y
        local l = math.max(math.sqrt(dx * dx + dy * dy), 1e-3)
        dx, dy = dx / l * 0.55, dy / l * 0.55
        local a = B.near(m.x - dx, m.y - dy, m.z, 0.8)
        local b = B.near(m.x + dx, m.y + dy, m.z, 0.8)
        if not (a and b) then return false end
        local dur = span(LONG.chat)
        local o = best.o
        if o.mode == "use" then rise(best.e, o) end
        st.partner, o.partner = o.h, st.h
        local ok = assign(best.e, o, { x = b.x, y = b.y, z = b.z, yaw = facing(b, a), kind = "chat" }, "chat", dur)
        if not ok then st.partner, o.partner = nil, nil return ok end
        ok = assign(npc, st, { x = a.x, y = a.y, z = a.z, yaw = facing(a, b), kind = "chat" }, "chat", dur)
        if not ok then st.partner, o.partner = nil, nil; free(o); o.mode, o.t = "idle", span(IDLE) return ok end
        return true
    end

    local function pick(npc, st, at)
        local set = body(npc, st)
        if not set then st.t = 1e9 return end
        if set.lie then
            local night = NIGHT[Game.GetTimeSystem():GetGameTime():Hours()]
            local sum = 0
            for _, k in ipairs(CAT) do sum = sum + k[2] * (night and k[1] == "sleep" and 4 or 1) end
            local r, pick_ = math.random() * sum, CAT[1]
            for _, k in ipairs(CAT) do r = r - k[2] * (night and k[1] == "sleep" and 4 or 1); if r <= 0 then pick_ = k break end end
            local s
            if pick_[1] == "wander" and not Life.allow.walk then pick_ = CAT[1] end
            if pick_[1] == "wander" then
                s = wanderSpot(at); if s then s.kind = "sit" end
                pick_ = CAT[1]
            else
                local f = B.near(at.x, at.y, at.z, 2)
                local ok, yaw = pcall(function() return npc:GetWorldYaw() end)
                s = f and { x = f.x, y = f.y, z = f.z, yaw = ok and yaw or math.random() * 360, kind = pick_[1] }
            end
            local ok = s and assign(npc, st, s, "cat", span(pick_[3]))
            if ok then return end
            st.t = span(IDLE) return
        end
        local job = jobs[st.h]
        local x, y, z = (job or ""):match("^(.-),(.-),(.-)$")
        if x then
            local f = B.near(tonumber(x), tonumber(y), tonumber(z), 1.5)
            local ok = f and assign(npc, st, { x = f.x, y = f.y, z = f.z, yaw = facing(at, f), kind = "idle", spot = job }, "idle", 1e9)
            if ok then st.last = "job" return end
            st.mode, st.t = "idle", 3 return
        elseif job then
            local mine, there = {}, false
            for _, s in ipairs(seats()) do
                if hashOf(s.piece.id) == job then
                    there = true
                    if set[s.kind] and USE[s.kind] and (not taken[s.key] or taken[s.key] == st.h) then mine[#mine + 1] = s end
                end
            end
            if not there then jobs[st.h] = nil; saveJobs()
            else
                local s = mine[math.random(math.max(#mine, 1))]
                local ok = s and assign(npc, st, s, USE[s.kind], 1e9)
                if ok then st.last = "job" return end
                st.mode, st.t = "idle", 3 return
            end
        end
        local night = NIGHT[Game.GetTimeSystem():GetGameTime():Hours()] or false
        local free = { relax = {}, work = {}, sleep = {} }
        local fav
        for _, s in ipairs(seats()) do
            if set[s.kind] and not taken[s.key] and not ((cut[s.key] or 0) > now) and dist2(s, at) < REACH * REACH then
                for act, kinds in pairs(ACT) do
                    for _, k in ipairs(kinds) do if k == s.kind then table.insert(free[act], s) end end
                end
                if s.key == st.fav then fav = s end
            end
        end
        local L = like(st)
        local A = Life.allow
        local w = {
            sleep = A.furniture and night and #free.sleep > 0 and 50 or 0,
            relax = A.furniture and #free.relax > 0 and L.relax * (night and 0.5 or 1) or 0,
            work = A.furniture and not night and #free.work > 0 and L.work or 0,
            chat = A.talk and set.chat and L.chat * (night and 0.3 or 1) or 0,
            look = A.walk and set.look and L.look * (night and 0.3 or 1) or 0,
            idle = set.idle and L.idle or 0,
            wander = A.walk and set.idle and L.wander * (night and 0.3 or 1) or 0,
        }
        if st.last and w[st.last] then w[st.last] = w[st.last] * 0.25 end
        for _ = 1, 4 do
            local sum = 0
            for _, k in ipairs(ACTS) do sum = sum + w[k] end
            if sum <= 0 then break end
            local r, act = math.random() * sum, nil
            for _, k in ipairs(ACTS) do r = r - w[k]; if r <= 0 and w[k] > 0 then act = k break end end
            act = act or "idle"
            local ok, s = false, nil
            if act == "sleep" or act == "relax" or act == "work" then
                s = (act == "relax" and fav and math.random() < 0.6) and fav or free[act][math.random(#free[act])]
                ok = assign(npc, st, s, act, act == "sleep" and 1e9 or span(LONG[act]))
                if ok == false then cut[s.key] = now + 60 end
                if ok and act == "relax" then st.fav = st.fav or s.key end
            elseif act == "chat" then ok = chat(npc, st, at)
            else
                if act == "look" then s = lookSpot(at)
                elseif act == "wander" then s = wanderSpot(at)
                else
                    local f = B.near(at.x, at.y, at.z, 1.5)
                    s = f and { x = f.x, y = f.y, z = f.z, yaw = math.random() * 360, kind = "idle" }
                end
                if s then ok = assign(npc, st, s, act == "look" and "look" or "idle", span(LONG[act == "look" and "look" or "idle"])) end
            end
            if ok then st.last = act return end
            w[act] = 0
        end
        st.mode, st.t = "idle", span(IDLE)
    end

    -- a person's piece is where they are now (aiming at them: scrap, move; the grid); true when anyone moved
    function Life.sync()
        prune()
        local moved = false
        for _, p in ipairs(S.pieces) do
            local e = p.it.npc and des():GetEntity(p.id)
            if e then
                local a = e:GetWorldPosition()
                if (a.x - p.o.x) ^ 2 + (a.y - p.o.y) ^ 2 > 0.04 then p.o, moved = { x = a.x, y = a.y, z = a.z }, true end
            end
        end
        return moved
    end

    -- E7 (tools/dev/exp_align.lua sets Life.alignLog): a sitter's or sleeper's body against their device 3 s into the
    -- workspot - where the animation has put them, in the device's own space (right, forward, up, turn) - to measure
    -- FWD, SEAT and LIE by. The body's root, not its hips (no bone read from script)
    Life.alignLog = false
    local function align(npc, st)
        local dev = des():GetEntity(st.dev)
        if not dev then return end
        local a, d, yaw = npc:GetWorldPosition(), dev:GetWorldPosition(), st.devYaw or st.seat.yaw
        local r = math.rad(yaw)
        local fx, fy, dx, dy = -math.sin(r), math.cos(r), a.x - d.x, a.y - d.y
        print(string.format("[Homestead] exp align: %s %s %s on %s: right %.3f fwd %.3f up %.3f turn %.1f (device %.2f, %.2f, %.2f yaw %.1f; seat top %.3f)",
            tostring(st.rec):match("[^.]+$") or "?", st.seat.kind, (PATHS[st.wsn or 0] or "?"):match("([^\\]+)%.workspot$") or "?",
            st.seat.piece and st.seat.piece.key or "-", dx * fy - dy * fx, dx * fx + dy * fy, a.z - d.z,
            (npc:GetWorldYaw() - yaw + 180) % 360 - 180, d.x, d.y, d.z, yaw, st.seat.z))
    end

    local function letGo(dt)
        local keep = {}
        for _, d in ipairs(drops) do d.t = d.t - dt; if d.t <= 0 then eng.delete(d.id) else keep[#keep + 1] = d end end
        drops = keep
    end
    local function newcomer(p, h)
        local st = { h = h, id = p.id, rec = p.it.record, mode = "idle", t = math.random() * IDLE[2] }
        who[h], order = st, nil
        return st
    end

    local function think(npc, st, dt)
        local at = npc:GetWorldPosition()
        st.t = st.t - dt
        B.keep(npc, st)
        if st.seat and st.seat.piece and not des():GetEntity(st.seat.piece.id) then rise(npc, st)
        elseif st.mode == "idle" then
            local out = not B.free(at.x, at.y, at.z) and B.near(at.x, at.y, at.z, 3)
            local moved = false
            if out then
                local dx, dy = out.x - at.x, out.y - at.y
                local l = math.max(math.sqrt(dx * dx + dy * dy), 1e-3)
                local far = { x = out.x + dx / l * 0.6, y = out.y + dy / l * 0.6, z = out.z }
                moved = B.moveTo(npc, st, B.free(far.x, far.y, far.z) and far or out)
                if moved then st.mode = "stroll" end
            end
            if not moved and st.t <= 0 then pick(npc, st, at) end
        elseif st.mode == "stroll" then
            if B.update(npc, st, dt) ~= nil then st.mode, st.t = "idle", span(IDLE) end
        elseif st.mode == "walk" then
            local r = B.update(npc, st, dt)
            if r then
                local l = BODY[st.set or "generic"][st.seat.kind]
                st.wsn = l[math.random(#l)]
                st.dev, st.devYaw = device(st.seat, st.wsn)
                st.mode, st.t = "spawn", 5
            elseif r == false then
                if Life.trace then Life.trace("lost", st, st.seat, false) end
                local o = st.partner and who[st.partner]
                if o then o.partner = nil; o.t = math.min(o.t, 2) end
                st.partner = nil; free(st); st.mode, st.t = "idle", span(IDLE)
            end
        elseif st.mode == "spawn" then
            local dev = des():GetEntity(st.dev)
            if dev and dev:FindComponentByName(CName.new("hs_ws")) then
                B.stop(npc, st)
                local ok = play(dev, npc, st)
                st.mode, st.t, st.tries = ok and "use" or "idle", ok and (st.dur or span(LONG.idle)) or span(IDLE), 0
                st.full, st.aligned = st.t, nil
                if not ok then free(st) end
            elseif st.t <= 0 then free(st); st.mode, st.t = "idle", span(IDLE) end
        elseif st.mode == "use" then
            local o = st.partner and who[st.partner]
            if st.act == "sleep" and not jobs[st.h] and not NIGHT[Game.GetTimeSystem():GetGameTime():Hours()] and math.random() < dt / 120 then
                st.t = 0
            elseif st.act == "chat" and st.full - st.t > 25 and not (o and o.mode == "use") then
                st.t = 0
            end
            if Life.alignLog and not st.aligned and st.full - st.t > 3 then st.aligned = true; pcall(align, npc, st) end
            if st.t <= 0 then rise(npc, st)
            elseif st.full - st.t > 2 and not Game.GetWorkspotSystem():IsActorInWorkspot(npc) then
                local dev = des():GetEntity(st.dev)
                st.tries = st.tries + 1
                C.log(string.format("workspot: %s out of %s (%s), try %d", tostring(st.rec):match("[^.]+$") or "?", st.seat.kind,
                    (PATHS[st.wsn or 0] or "?"):match("([^\\]+)%.workspot$") or "?", st.tries))
                if st.tries > 3 or not dev or (at.x - st.seat.x) ^ 2 + (at.y - st.seat.y) ^ 2 > 4 or not play(dev, npc, st) then rise(npc, st) end
            end
        end
    end
    local function gone(alive)
        for h, st in people() do if not alive[h] then free(st); who[h], order = nil, nil end end
    end

    -- Everyone's turn at once, dt on (tools/sim.py, tools/dev; the game takes turns, Life.step). away: V far off, only the devices let go.
    -- Without navigation (LiveNav missing, or Settings > People > Navigation off) people are props: nobody thinks and nothing is sent to them.
    -- Jobs stay in jobs.txt.
    function Life.tick(dt, away)
        letGo(dt)
        if away or not B.caps().walk then return end
        if S.build then cut = {} return end
        now = now + dt
        local alive = {}
        for _, p in ipairs(S.pieces) do
            if p.it.npc then
                local h = hashOf(p.id)
                alive[h] = true
                local npc = des():GetEntity(p.id)
                local st = who[h] or newcomer(p, h)
                if npc then think(npc, st, dt) end
            end
        end
        gone(alive)
    end

    -- Every frame (init.lua update): people take turns, one a frame, each about once a second (TURN), so a settlement's thinking doesn't land in one frame.
    local TURN, clock, rollT, cursor = 1, 0, 0, 0
    function Life.step(dt, away)
        letGo(dt)
        if away or not B.caps().walk then return end
        if S.build then cut = {} return end
        now, clock = now + dt, clock + dt
        if clock >= rollT then
            rollT = clock + TURN
            local alive = {}
            for _, p in ipairs(S.pieces) do
                if p.it.npc then
                    local h = hashOf(p.id)
                    alive[h] = true
                    if not who[h] then newcomer(p, h) end
                end
            end
            gone(alive)
        end
        local o = sorted()
        for k = 1, #o do
            local i = (cursor + k - 1) % #o + 1
            local st = who[o[i]]
            if st and clock - (st.turnT or -1e9) >= TURN then
                cursor = i
                local d = math.min(clock - (st.turnT or clock - TURN), 5)
                st.turnT = clock
                local npc = des():GetEntity(st.id)
                if npc then think(npc, st, d) end
                return
            end
        end
    end

    -- Doors open for whoever walks up to one and stay open, as Fallout's settlers leave them (shut behind them, one closed on the way back left them stuck).
    -- Squared distance from w to the line across a door's width (its local X, through its middle): a wide rolling door's middle is too far from
    -- anyone walking through near an end.
    local function offSpan(p, w)
        local a = local2world(p.o, p.yaw, p.it.min[1], p.it.cy, 0)
        local b = local2world(p.o, p.yaw, p.it.max[1], p.it.cy, 0)
        local dx, dy = b.x - a.x, b.y - a.y
        local t = math.max(0, math.min(1, ((w.x - a.x) * dx + (w.y - a.y) * dy) / math.max(dx * dx + dy * dy, 1e-9)))
        return (w.x - a.x - t * dx) ^ 2 + (w.y - a.y - t * dy) ^ 2
    end
    local function doors(walkers)
        for _, p in ipairs(S.pieces) do
            local lb = p.it.anim and not p.it.stash and Anim.label(p)
            if lb == "Open" then
                local d = math.huge
                for _, a in ipairs(walkers) do d = math.min(d, offSpan(p, a)) end
                if d < 1.4 ^ 2 then pcall(Anim.use, p) end
            end
        end
    end

    -- a piece scrapped or picked up (init.lua removePiece, workshop mode included - tick sleeps then): whoever's on it
    -- gets up at once, whoever's on the way to it does something else
    function Life.gone(p)
        for _, st in people() do
            if st.seat and st.seat.piece == p then
                local npc = des():GetEntity(st.id)
                if st.mode == "use" or st.mode == "spawn" then rise(npc, st)
                else B.stop(npc, st); free(st); st.mode, st.t = "idle", span(IDLE) end
            end
        end
    end

    -- every frame near the settlement, workshop mode too (init.lua update): LiveNav's world edits sent, colliders back
    -- once people are off them; a few times a second (not in workshop mode) the doors, for whoever walks (no doors
    -- without navigation: nobody walks to one)
    local acc = 0
    function Life.frame(dt)
        for p, t in pairs(ghosts) do
            if t - dt <= 0 then ghosts[p] = nil; solid(p, true) else ghosts[p] = t - dt end
        end
        LN.frame(dt)
        acc = acc + dt
        if acc < 0.25 or S.build then return end
        acc = 0
        local walkers = {}
        if B.caps().walk then
            for _, st in people() do
                local npc = (st.mode == "walk" or st.mode == "stroll") and des():GetEntity(st.id)
                if npc then walkers[#walkers + 1] = npc:GetWorldPosition() end
            end
        end
        if #walkers > 0 then doors(walkers) end
    end

    -- The navigation backend: chosen at onInit and at a session's change (init.lua), never mid-walk. LiveNav when installed and Settings >
    -- People > Navigation is on (Life.allow.nav), else null. World edits always go to LiveNav (a no-op without it) through here, so no hook site
    -- holds a backend; added pieces it finds itself, from S.world.
    function Life.choose() B = Life.allow.nav and LN.present() and LN or NAV.null end
    function Life.walks() return B.caps().walk end
    Life.pieceRemoved, Life.navClear, Life.navZone, Life.navDoor = LN.pieceRemoved, LN.clear, LN.zone, LN.door
    Life.navUnload, Life.navLoad = LN.unload, LN.load

    function Life.onEntity(e)
        local id = e:GetEntityID()
        if not des():IsTagged(id, CName.new("Homestead.ws")) then return false end
        for n, path in ipairs(PATHS) do
            if des():IsTagged(id, CName.new("hsws" .. n)) then
                local c = workWorkspotResourceComponent.new()
                c.name = CName.new("hs_ws")
                c.workspotResource = ResRef.FromString(path)
                e:AddComponent(c)
                break
            end
        end
        return true
    end

    -- a load, another settlement: everyone up, every device gone (lost: a session's end took the devices already - their
    -- ids aren't ours to delete in the next)
    function Life.reset(lost)
        for h, st in people() do
            local p = S.byId[h]
            local npc = p and des():GetEntity(p.id)
            if st.mode == "use" then rise(npc, st) else B.stop(npc, st); free(st) end
        end
        who, taken, order = {}, {}, nil
        if lost then drops, pruned = {}, false end
    end

    local function stop(st)
        local npc = des():GetEntity(st.id)
        if st.mode == "use" or st.mode == "spawn" then rise(npc, st)
        else B.stop(npc, st); free(st); st.mode = "idle" end
        st.t = 3
    end
    function Life.usable(p)
        for _, s in ipairs(p.it.seats or {}) do if USE[s[5]] then return true end end
        return false
    end
    local function reach(h, to)
        local p = S.byId[h]
        local e = p and des():GetEntity(p.id)
        if not e then return nil end
        return B.reach(e:GetWorldPosition(), to)
    end
    function Life.jobOf(h) return jobs[h] end
    function Life.job(h, p)
        if not Life.usable(p) then return false end
        jobs[h] = hashOf(p.id); saveJobs()
        local st = who[h]
        if st and not (st.seat and st.seat.piece and hashOf(st.seat.piece.id) == jobs[h]) then stop(st) end
        local why, d
        for _, s in ipairs(seats()) do
            if s.piece == p and USE[s.kind] then
                for _, a in ipairs(approaches(s)) do
                    why, d = reach(h, a)
                    if not why then return true, nil, d end
                end
            end
        end
        return true, why, d
    end
    function Life.unjob(h)
        if not jobs[h] then return false end
        local j = jobs[h]
        jobs[h] = nil; saveJobs()
        local st = who[h]
        if st and st.seat and (st.seat.spot == j or st.seat.piece and hashOf(st.seat.piece.id) == j) then stop(st) end
        return true
    end
    function Life.rejob(old, new)
        for h, j in pairs(jobs) do if j == old then jobs[h] = new end end
        if jobs[old] then jobs[new], jobs[old] = jobs[old], nil end
        saveJobs()
    end
    -- Wait there: a spot is a job too. `at` is what the crosshair hit (any surface); the spot is the navmesh point there, the nearest within 1 m,
    -- kept only from 1 m under the hit to 0.5 m over it, so the surface aimed at wins over the ground under it. Then the probe from where they stand
    -- decides. Returns false and why when there is no spot or no way, else true, the probe's length and the spot. Navigation off: refused.
    function Life.moveTo(h, at)
        if not B.caps().walk then return false, "navigation off" end
        local f = B.near(at.x, at.y, at.z, 1)
        if not f or f.z - at.z > 0.5 or at.z - f.z > 1 then return false, "no walkable spot there" end
        local why, d = reach(h, f)
        if why then return false, why, d, f end
        jobs[h] = string.format("%.2f,%.2f,%.2f", f.x, f.y, f.z); saveJobs()
        if who[h] then stop(who[h]) end
        return true, nil, d, f
    end

    function Life.state() return who end
    Life.people = people
    Life.jobs = jobs
    function Life.dbg() return taken, cut, now, seats(), drops end
    Life.backends, Life.livenav = NAV, LN
    function Life.backend() return B end
end
