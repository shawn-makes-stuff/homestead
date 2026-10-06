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
        chicken = { idle = { "animals\\chicken__stand_ground__stand_around__01" } },   -- (ours: tools/make_workspots.py
        iguana = { idle = { "animals\\iguana__sit_ground__sit_around__01" } },         -- ANIMALS)
        cow = {},                                             -- (none: no animation in the game is made for its rig)
    }
    local GROUP = { ManAverage = "generic", WomanAverage = "generic", ManBig = "big", ManMassive = "big", ManFat = "fat",
                    WomanFat = "fat", Child = "child", ChildMale = "child", ChildFemale = "child" }
    -- what they do, the spots each uses, and for how long (seconds; a bed: till morning)
    local ACT = { relax = { "chair", "couch", "table", "stool" }, work = { "work", "counter", "kneel", "guard" },
                  sleep = { "bed", "floorbed" } }
    local LONG = { relax = { 240, 600 }, work = { 180, 420 }, look = { 25, 70 }, chat = { 60, 180 }, idle = { 30, 90 } }
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
    -- Animals with nothing to walk with (their graph is the cinematic props': no locomotion): they play their one
    -- animation where they are put, with navigation or without, and take no job, pose or talk. The cow has none: it
    -- stands as placed. By the record's name (a body type is no guide: theirs is whatever the record happens to say).
    local PET = { chicken = true, iguana = true, cow = true }
    local ANIMAL = { cat = true, chicken = true, iguana = true, cow = true }
    local function pet(rec)
        rec = (rec or ""):lower()
        return (rec:find("chicken", 1, true) and "chicken") or (rec:find("iguana", 1, true) and "iguana")
            or (rec:find("fake_cow", 1, true) and "cow") or nil
    end
    local function petJob(rec, st)                              -- (off: its animation didn't play - think)
        local s = pet(rec)
        return s and BODY[s].idle and not (st and st.off) and "a-idle" or nil
    end
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
    local taken, put = {}, {}                                   -- (put: people set where the gizmo left them, this session)
    local carried                                               -- (who the gizmo has: Life.carry)
    -- Jobs (Command mode): person hash -> the hash of the piece they're assigned to, or a spot "x,y,z" they were sent to. They go to it and
    -- use it for good until cleared; kept in jobs.txt (entity ids survive a save: persistSpawn), checked against the pieces there are when they come up.
    -- They are the save's own (user, 2026-10-05): every change is a new revision in the file ("<rev>|<person>=<job>", "<rev>|"
    -- alone: that revision, with or without jobs) and the game's fact hs_jobs, kept in the save, says which this save has -
    -- an older save loaded has what its people had then. Lines with no revision (before this) are revision 0, what a save
    -- without the fact has. No fact to ask (no game): the latest.
    local JOBS = (HS_DIR or "") .. "jobs.txt"
    local KEEP = 60                                              -- revisions kept: a save older than that many changes loses its jobs
    local jobs, revs, top = {}, {}, 0
    local function fact(v)
        local ok, r = pcall(function()
            local q = Game.GetQuestsSystem()
            if v then q:SetFactStr("hs_jobs", v) end
            return q:GetFactStr("hs_jobs")
        end)
        return ok and tonumber(r) or nil
    end
    -- WHO A JOB IS OF. In here jobs go by entity hash, as everything does - but an entity's id is a session's: a load
    -- gives every piece a new one (the log, 2026-10-05: "revision 79, 9 entries" read, and nobody took theirs up; the
    -- ids in jobs.txt only ever grew). So in the file a person and a seat go by their own tag, "hsu:<uid>" (given at
    -- the first need: Codeware's AssignTag; read back as text by Homestead.Uid, found again by GetTaggedID): a key or a
    -- value "U<uid>". The file's entries are `raw`; each becomes a job as soon as its entities are in the world
    -- (resolve, every second from posts: a save's entities are listed late), and stays raw - kept, written back - till then.
    local uids, byUid, raw = {}, {}, {}
    local function uidOf(h)
        if uids[h] then return uids[h] end
        local p = S.byId[h]
        local ok, u = pcall(function() return des():Uid(p.id) end)
        if not (p and ok and u) then return nil end
        if u == "" then
            u = string.format("%d%05d", os.time(), math.random(0, 99999))   -- (digits: a key's o / a suffix stays plain)
            local set, took = pcall(function() return des():AssignTag(p.id, "hsu:" .. u) end)
            if not set or took == false then return nil end
        end
        uids[h], byUid[u] = u, h
        return u
    end
    local function hashOfUid(u)
        if byUid[u] and S.byId[byUid[u]] then return byUid[u] end
        local ok, id = pcall(function() return des():GetTaggedID("hsu:" .. u) end)
        local h = ok and id and hashOf(id)
        if h and S.byId[h] then uids[h], byUid[u] = u, h; return h end
    end
    local function there(x)                                      -- a file's "U<uid>" (or, from before, a hash) -> the hash now, or nil
        if x:sub(1, 1) ~= "U" then return x end
        return hashOfUid(x:sub(2))
    end
    local function resolve()
        local left = 0
        for k, v in pairs(raw) do
            local suffix = k:match("^U.*([oa])$") or ""
            local who = there(suffix ~= "" and k:sub(1, -2) or k)
            local val = v
            if suffix == "" then
                if v:sub(1, 1) == "U" then val = there(v)
                elseif v:sub(1, 3) == "c-U" then local o = there(v:sub(3)); val = o and ("c-" .. o) end
            end
            if who and val then jobs[who .. suffix], raw[k] = val, nil else left = left + 1 end
        end
        return left
    end
    local function named(h)                                      -- a hash -> what the file calls it
        local u = uidOf(h)
        return u and ("U" .. u) or h
    end

    -- Read at the first need once the game runs and its first refresh is through (Life.step; whatever changes a job reads
    -- first too). This save's revision (the game's fact hs_jobs; the log shows it read right); none to go by: the latest.
    -- Nothing is dropped at a load.
    local loaded = false
    local function loadJobs()
        if loaded then return end
        loaded = true
        revs, top = {}, 0
        local f = io.open(JOBS, "r")
        if f then
            for line in f:lines() do
                local r, a, b = line:match("^(%d+)|(%w*)=?([%w%.,%-]*)$")
                if not r then a, b = line:match("^(%w+)=([%w%.,%-]+)$"); r = a and 0 end
                r = tonumber(r)
                if r then
                    revs[r], top = revs[r] or {}, math.max(top, r)
                    if a and a ~= "" then revs[r][a] = b end
                end
            end
            f:close()
        end
        local r = fact()
        if not r or r == 0 or not revs[r] then r = top end
        for a in pairs(jobs) do jobs[a] = nil end              -- (the same table: Life.jobs is it)
        raw, uids, byUid = {}, {}, {}
        local n = 0
        for a, b in pairs(revs[r] or {}) do                    -- (an id of a session past - "<n>ULL", before the tags - is
            if not (a .. b):find("ULL", 1, true) then raw[a], n = b, n + 1 end   -- nobody's now, or somebody else's)
        end
        local left = resolve()
        C.log(string.format("jobs: revision %s of %d (the save's: %s), %d entries, %d of them whose people aren't here yet", tostring(r), top, tostring(fact()), n, left))
    end
    local function saveJobs()
        top = top + 1
        local out = {}
        for k, v in pairs(raw) do out[k] = v end                 -- (not yet of anyone here: kept as they are)
        for k, v in pairs(jobs) do
            local suffix = k:match("([oa])$") and not S.byId[k] and k:sub(-1) or ""
            local key = named(suffix ~= "" and k:sub(1, -2) or k) .. suffix
            if suffix == "" then
                if v:find("^c%-") then v = "c-" .. named(v:sub(3))
                elseif not v:find("[,%-]") then v = named(v) end
            end
            out[key] = v
        end
        revs[top] = out
        fact(top)
        local f = io.open(JOBS, "w")
        if not f then return end
        for r, t in pairs(revs) do
            if r > top - KEEP then
                f:write(r, "|\n")
                for h, j in pairs(t) do f:write(r, "|", h, "=", j, "\n") end
            else revs[r] = nil end
        end
        f:close()
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
    -- st.jump: put straight back into it (a load, the gizmo) - set onto the device and jumped to the idle they hold there
    -- (modules/own/idles.lua), not walked through the way in again.
    local IDLES = require("modules/own/idles")
    local function play(dev, npc, st)
        local lie = SIDE[st.seat.kind]
        if lie or st.jump then
            pcall(function() eng.teleport(npc, dev:GetWorldPosition(), EulerAngles.new(0, 0, st.devYaw or st.seat.yaw)) end)
        end
        local ok = pcall(function() Game.GetWorkspotSystem():PlayInDeviceSimple(dev, npc, false, CName.new("hs_ws"),
            CName.new("None"), CName.new("None"), 0.5, 1) end)
        if ok and lie then pcall(function() Game.GetWorkspotSystem():SendJumpCommandEnt(npc, LIE_LOOP, true) end)
        elseif ok then
            ghost(st.seat.piece, 3)
            local idle = st.jump and IDLES[(PATHS[st.wsn or 0] or ""):match("([^\\]+)%.workspot$") or ""]
            if idle then pcall(function() Game.GetWorkspotSystem():SendJumpToAnimEnt(npc, CName.new(idle), true) end) end
        end
        return ok
    end

    -- The workspot's file is asked for when its device is made and played once it is in (Codeware's ResourceDepot): the
    -- device's component has it as an async ref set by script, and played before its animations were loaded the body
    -- T-posed for a moment, the first time an animation was used after the game's start (user, 2026-10-06). st.res is
    -- kept while they use it. No depot, a load that failed or took the spawn's 5 s: played as it was.
    local function fetch(n)
        local ok, t = pcall(function() return Game.GetResourceDepot():LoadResource(ResRef.FromString(PATHS[n])) end)
        return ok and t or nil
    end
    local function ready(st)
        local t = st.res
        if not t then return true end
        local ok, r = pcall(function() return t:IsLoaded() or t:IsFailed() end)
        return not ok or r
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
        return eng.create(spec), yaw, fetch(n)
    end

    local drops = {}
    local function free(st)
        if st.seat and st.seat.key then taken[st.seat.key] = nil end
        if st.dev then drops[#drops + 1] = { id = st.dev, t = 6 } end
        st.seat, st.dev, st.res = nil, nil, nil
    end

    local function rise(npc, st)
        if npc and ANIMAL[st.set] then
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
            -- (the photo mode's cast - Rita Wheeler - name no body type the sets know: people of average build; so are
            -- the Fallout people we build on the game's average body - the game said "Undefined" for one, 2026-10-06)
            st.set = pet(rec) or (ok and GROUP[b]) or (rec:find("cat") and "cat") or (rec:find("photomode", 1, true) and "generic") or false
            if not st.set then C.log(string.format("people: no animations for %s (body type %s)", tostring(st.rec), tostring(ok and b))) end
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
        return o.set and not ANIMAL[o.set] and not o.partner and not jobs[o.h]
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
                local f = free[USE[s.kind]]
                if f then f[#f + 1] = s end
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

    -- an animal that can't walk (PET): its animation where it is, for good
    local function stay(npc, st, at)
        local l = body(npc, st).idle
        local ok, yaw = pcall(function() return npc:GetWorldYaw() end)
        st.seat, st.act, st.dur = { x = at.x, y = at.y, z = at.z, yaw = ok and yaw or 0, kind = "idle" }, "idle", 1e9
        st.wsn, st.jump = l[math.random(#l)], true
        st.dev, st.devYaw, st.res = device(st.seat, st.wsn)
        st.mode, st.t = "spawn", 5
    end

    local function think(npc, st, dt)
        local at = npc:GetWorldPosition()
        st.t = st.t - dt
        B.keep(npc, st)
        if st.seat and st.seat.piece and not des():GetEntity(st.seat.piece.id) then rise(npc, st)
        elseif st.mode == "idle" and body(npc, st) and PET[st.set] then
            if st.t <= 0 and not st.held and petJob(st.rec, st) then stay(npc, st, at) end
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
                st.dev, st.devYaw, st.res = device(st.seat, st.wsn)
                st.mode, st.t = "spawn", 5
            elseif r == false then
                if Life.trace then Life.trace("lost", st, st.seat, false) end
                local o = st.partner and who[st.partner]
                if o then o.partner = nil; o.t = math.min(o.t, 2) end
                st.partner = nil; free(st); st.mode, st.t = "idle", span(IDLE)
            end
        elseif st.mode == "spawn" then
            local dev = des():GetEntity(st.dev)
            if dev and dev:FindComponentByName(CName.new("hs_ws")) and (ready(st) or st.t <= 0) then
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
                if st.tries > 3 or not dev or (at.x - st.seat.x) ^ 2 + (at.y - st.seat.y) ^ 2 > 4 or not play(dev, npc, st) then
                    st.off = PET[st.set] and st.tries > 3 or nil  -- (an animal's one animation not playing - an import
                    rise(npc, st)                                 -- from before it had it: left standing, not tried on and on)
                end
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
        if S.settled ~= nil then loadJobs() end
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

    -- People as props (user, 2026-10-05): without navigation nobody walks, so a person with a job is put at it and kept in
    -- its workspot till it changes. A job (jobs.txt) is a piece's hash (its seat, bed or work spot), "p-<pose>" (an
    -- animation where they stand: POSES) or "c-<person's hash>" (talking with them: both have it). Given from workshop
    -- mode: a person placed on a piece or by someone (placement.lua place -> Life.post), an animation's card placed on one
    -- (People > Animations: modules/own/poses.lua, Life.setPose).
    local POSE, had = {}, {}                                     -- id -> { name, <body set> = { workspot (PATHS), new } }
    for _, w in ipairs(PATHS) do had[w] = true end               -- (new: not one the people's own sets use - an import
    for _, x in ipairs(require("modules/own/poses")) do          -- since 2026-10-05, level 2, has its looping copy)
        local e = { name = x.name }
        for _, set in ipairs({ "generic", "big", "fat", "child", "cat" }) do
            local w = x[set]
            if w then
                w = (w:sub(1, 1) == "@" and "base\\workspots\\" .. w:sub(2) or W .. w) .. ".workspot"
                PATHS[#PATHS + 1] = w
                e[set] = { #PATHS, new = not had[w] }
            end
        end
        POSE[x.id] = e
    end
    local function got(w) return w and (not w.new or C.Settings.level() >= 2) end
    -- Someone whose own standing animations don't play when placed from their record stands in this one while they
    -- have no job (the bar droid: "takes animations now, but when spawned he is tposed" - user, 2026-10-06; the
    -- animation wrapper entities.lua `wake` switches on did not make him stand). record -> a job, never saved.
    local REST = { ["Character.cz_con_foodshop_01"] = "p-stand-ground.stand-around.04" }
    local function own(p, kind) return { x = p.o.x, y = p.o.y, z = p.o.z, yaw = p.yaw or 0, kind = kind } end
    -- a job -> where (a seat as seats() gives them, or their own spot) and the workspots to pick from; nil: nothing to do
    local function posted(p, h, job, npc, st, all)
        local b = body(npc, st)
        if not b then return end
        local kind, v = job:match("^(%a)%-(.+)$")
        if kind == "p" then
            local w = POSE[v] and POSE[v][st.set]
            if got(w) then return own(p, v:find("^lie") and "floorbed" or "pose"), { w[1] } end
        elseif kind == "a" then                                   -- (an animal's own: PET)
            return own(p, v), b[v]
        elseif kind == "c" then
            if S.byId[v] then return own(p, "chat"), b.chat or b.idle end
            jobs[h] = nil; saveJobs()
        else
            for _, s in ipairs(all()) do
                if hashOf(s.piece.id) == job and USE[s.kind] and not taken[s.key] and b[s.kind] then
                    local a, b2, c, d = (jobs[h .. "o"] or ""):match("^([^,]+),([^,]+),([^,]+),([^,]+)$")   -- (Life.nudge)
                    if a then s = setmetatable({ x = s.x + a, y = s.y + b2, z = s.z + c, yaw = s.yaw + d }, { __index = s }) end
                    return s, b[s.kind]
                end
            end
        end
    end
    local postT, soon = 0, false                                -- (soon: someone's device is on its way - looked at again shortly)
    local function posts(dt)
        postT = postT + dt
        if postT < (soon and 0.1 or 1) then return end
        soon = false
        local d, list = postT, nil
        postT = 0
        local function all() list = list or seats(); return list end
        if next(raw) then resolve() end                          -- (jobs whose people weren't in the world yet)
        local alive = {}
        for _, p in ipairs(S.pieces) do
            local h = p.it.npc and hashOf(p.id)
            if h then alive[h] = true end
            local held = h and who[h] and who[h].held           -- (under the gizmo: Life.carry has them)
            local at = h and not held and not put[h] and jobs[h .. "a"]   -- (where the gizmo left them: Life.nudge)
            if at then
                local e = des():GetEntity(p.id)
                local x, y, z, w = at:match("^([^,]+),([^,]+),([^,]+),([^,]+)$")
                x, y, z, w = tonumber(x), tonumber(y), tonumber(z), tonumber(w)
                if e and w and eng.teleport(e, Vector4.new(x, y, z, 1), EulerAngles.new(0, 0, w), true) ~= false then
                    put[h], p.o, p.yaw = true, { x = x, y = y, z = z }, w
                end
            end
            local job = h and not held and not at and (petJob(p.it.record, who[h]) or (not pet(p.it.record) and jobs[h])
                or REST[p.it.record])                            -- (not in the tick they are put where they were left)
            local npc = job and not job:find(",", 1, true) and des():GetEntity(p.id)
            if npc then
                local st = who[h] or newcomer(p, h)
                if st.mode == "spawn" or st.mode == "use" then
                    if st.mode == "use" then st.t = math.max(st.t, 60) end   -- (no getting up by the clock)
                    think(npc, st, d)
                    soon = soon or st.mode == "spawn"
                else
                    local s, l = posted(p, h, job, npc, st, all)
                    local a = s and s.piece and approaches(s)[1]
                    if s and l and (not a or eng.teleport(npc, Vector4.new(a.x, a.y, a.z, 1), EulerAngles.new(0, 0, s.yaw)) ~= false) then
                        if s.key then taken[s.key] = st.h end
                        st.seat, st.act, st.dur, st.wsn, st.jump = s, USE[s.kind] or "idle", 60, l[math.random(#l)], true
                        st.dev, st.devYaw, st.res = device(s, st.wsn)
                        st.mode, st.t, soon = "spawn", 5, true
                    end
                end
            end
        end
        gone(alive)                                               -- (someone picked up or scrapped: their seat is free again)
    end

    -- Every frame (init.lua update): people take turns, one a frame, each about once a second (TURN), so a settlement's thinking doesn't land in one frame.
    local TURN, clock, rollT, cursor = 1, 0, 0, 0
    function Life.step(dt, away)
        letGo(dt)
        if S.settled == nil then return end                       -- (the game not up yet: no jobs read, none carried out)
        loadJobs()
        if not away and not B.caps().walk then posts(dt) end
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
        if not des():IsTagged(id, "Homestead.ws") then return false end
        for n, path in ipairs(PATHS) do
            if des():IsTagged(id, "hsws" .. n) then
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
        if lost then                                              -- (a load: this save's jobs, read at its first refresh)
            drops, loaded, put, carried = {}, false, {}, nil
            for a in pairs(jobs) do jobs[a] = nil end
        end
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
        loadJobs()
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
        loadJobs()
        if not jobs[h] then return false end
        local j = jobs[h]
        jobs[h] = nil; saveJobs()
        local st = who[h]
        if st and st.seat and (st.seat.spot == j or st.seat.piece and hashOf(st.seat.piece.id) == j) then stop(st) end
        return true
    end
    -- Workshop mode's people (posts, above). Life.spot: where a person placed at `at` stands and faces - by a piece's first free
    -- seat, or a step in front of someone, facing them; nil: no room. Life.post: the job that goes with it (at nil: put
    -- somewhere else - a seat or a talk is left, a pose kept) -> what to say. Life.setPose: an animation of poses.lua for a
    -- person -> whether they took it, and what to say.
    local function set(h, v)
        local old = jobs[h]
        if old and old:find("^c%-") and jobs[old:sub(3)] == "c-" .. h then
            jobs[old:sub(3)] = nil
            if who[old:sub(3)] then stop(who[old:sub(3)]) end
        end
        jobs[h], jobs[h .. "o"] = v, nil
        if who[h] then stop(who[h]) end
        saveJobs()
    end
    -- The gizmo on someone at a seat, a bed or a stall: they stay on it, moved and turned by as much (jobs.txt
    -- "<hash>o" = dx,dy,dz,dyaw from the seat, summed). -> false: no job to keep (the caller places them as usual)
    function Life.nudge(h, dx, dy, dz, dyaw, o, yaw)
        loadJobs()
        local j = jobs[h]
        if o and not (j and not j:find("[,%-]")) then            -- (moved as they are, with no seat: the game keeps where an
            jobs[h .. "a"] = string.format("%.3f,%.3f,%.3f,%.1f", o.x, o.y, o.z, yaw)   -- entity was made, not where it was
            put[h] = true                                         -- moved to - so their place is a job too: "<hash>a",
            saveJobs()                                            -- put back at a load, posts)
            return true
        end
        if not j or j:find(",", 1, true) then return false end
        if j:find("-", 1, true) then return true end              -- (a pose, a talk: where they stand is theirs)
        local a, b, c, d = (jobs[h .. "o"] or "0,0,0,0"):match("^([^,]+),([^,]+),([^,]+),([^,]+)$")
        jobs[h .. "o"] = string.format("%.3f,%.3f,%.3f,%.1f", a + dx, b + dy, c + dz, d + dyaw)
        saveJobs()
        return true
    end
    function Life.spot(at)
        if at.it.npc then
            local r = math.rad(at.yaw or 0)
            return { x = at.o.x - math.sin(r), y = at.o.y + math.cos(r), z = at.o.z }, (at.yaw or 0) + 180
        end
        for _, s in ipairs(seats()) do
            if s.piece == at and USE[s.kind] and not taken[s.key] then return approaches(s)[1], s.yaw end
        end
    end
    function Life.post(h, at)
        loadJobs()
        jobs[h .. "a"] = nil                                     -- (placed by hand: made where they stand)
        if not at then
            if jobs[h] and not jobs[h]:find("^p%-") then set(h, nil) end
            return "placed"
        end
        if at.it.npc then
            local o = hashOf(at.id)
            set(o, "c-" .. h); set(h, "c-" .. o)
            return "talking with " .. at.it.name
        end
        set(h, hashOf(at.id))
        return "at the " .. at.it.name
    end
    function Life.setPose(p, id)
        loadJobs()
        local h = hashOf(p.id)
        local st = who[h] or newcomer(p, h)
        local npc = des():GetEntity(p.id)
        if npc then body(npc, st) end
        if id == "none" then
            if (jobs[h] or ""):find("^p%-") then set(h, nil) end
            return true, "as placed"
        end
        if jobs[h] and not jobs[h]:find("^p%-") then return false, "they have a spot already - put them down somewhere else first" end
        local w = POSE[id] and st.set and POSE[id][st.set]
        if not w then return false, "that one isn't made for their body" end
        if not got(w) then return false, "import again to get this animation (Settings > Mods > Homestead)" end
        set(h, "p-" .. id)
        return true, POSE[id].name
    end
    -- The gizmo on someone (placement.lua, h.live): they are moved as they stand, each frame it moves. Someone at a
    -- seat or in an animation gets up first and stands under the gizmo while it has them: in a workspot a body stays
    -- where the workspot began, whatever is moved (seen 2026-10-05), and one started again in the frame it was stopped
    -- isn't a thing known to work - Appearance Menu Mod, which does this for a living, stops, moves, waits and starts
    -- again (its Poses:RestartAnimation). Let go (no arguments), they take their seat or pose up again where they now
    -- are, by the way a load puts them there (posts): what the gizmo leaves is what the save gives back.
    function Life.carry(p, o, yaw)
        if not p then
            local st = carried and who[carried.h]
            if st and st.held then st.held = nil; postT = 0.7 end   -- (posts: in 0.3 s - AMM's wait between a move and a pose)
            carried = nil
            return
        end
        local h = hashOf(p.id)
        local c = carried
        if not c or c.h ~= h then
            if c then Life.carry() end
            c = { h = h, x = p.o.x, y = p.o.y, z = p.o.z, at = p.yaw or 0 }
            carried = c
        end
        if math.abs(c.x - o.x) + math.abs(c.y - o.y) + math.abs(c.z - o.z) < 1e-3 and math.abs((c.at - yaw + 180) % 360 - 180) < 0.05 then return end
        c.x, c.y, c.z, c.at = o.x, o.y, o.z, yaw
        local st, npc = who[h], des():GetEntity(p.id)
        if st and not st.held then
            C.log(string.format("gizmo: %s moved (%s)", p.it.name, st.mode))
            if npc and (st.mode == "use" or st.mode == "spawn") then pcall(function() Game.GetWorkspotSystem():StopInDevice(npc) end) end
            free(st)
            st.held, st.mode, st.t = true, "idle", 0
        end
        if npc then eng.teleport(npc, Vector4.new(o.x, o.y, o.z, 1), EulerAngles.new(0, 0, yaw), true) end
    end

    function Life.rejob(old, new)
        loadJobs()
        for h, j in pairs(jobs) do if j == old then jobs[h] = new elseif j == "c-" .. old then jobs[h] = "c-" .. new end end
        if jobs[old] then jobs[new], jobs[old] = jobs[old], nil end
        if jobs[old .. "o"] then jobs[new .. "o"], jobs[old .. "o"] = jobs[old .. "o"], nil end
        jobs[old .. "a"] = nil                                   -- (made again where they were put: no place to restore)
        saveJobs()
    end
    -- Wait there: a spot is a job too. `at` is what the crosshair hit (any surface); the spot is the navmesh point there, the nearest within 1 m,
    -- kept only from 1 m under the hit to 0.5 m over it, so the surface aimed at wins over the ground under it. Then the probe from where they stand
    -- decides. Returns false and why when there is no spot or no way, else true, the probe's length and the spot. Navigation off: refused.
    function Life.moveTo(h, at)
        loadJobs()
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
