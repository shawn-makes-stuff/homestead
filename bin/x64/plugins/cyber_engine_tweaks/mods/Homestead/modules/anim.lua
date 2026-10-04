-- Animations: Fallout's own sequences (catalog `anim`, tools/fo4/anim.py), sampled at 15 frames a second: per frame, per
-- moving part, x y z i j k r in the piece's space; the parts are the piece's meshes from anim.first.
-- What a piece does follows its sequence names, as in Fallout: a door (Open / Close) opens and shuts on E; a trap (Set,
-- TripTransition / Trip, Tripped) springs and resets on E; a switchable machine (On, TurningOff, Off) goes off and on; a running
-- loop (a generator's On) plays whenever V is within LOOP_NEAR m. Only pieces near V animate. A moving part's collider is off
-- while it is away from its rest (an open door lets V through). Sounds (catalog `snd`, tools/fo4/sounds.py, via Audioware when
-- installed): a sequence's cues as it plays, and `hum`, what a running piece loops while V is near. A lamp (catalog `lights`)
-- switches on and off on E. Not saved: a reloaded game finds everything at rest, lit. Anim is C.Anim (init.lua requires this).
return function(Anim, C)
    local S, catalog, des, hashOf, lumens, try = C.S, C.catalog, C.des, C.hashOf, C.lumens, C.try
    local view = C.view

    local RATE, LOOP_NEAR = 15, 40
    local SND = catalog.sounds or {}

    local function sfx(p, ev, play)
        local t = SND[ev]
        if not t then return end
        local h = hashOf(p.id)
        local on = S.sfx[h] or {}
        S.sfx[h] = on
        if play then
            if t.loop and on[ev] then return end
            local v = ev .. "_" .. math.random(0, t.n - 1)
            local ok, played = pcall(Homestead.Sfx, p.id, v, true, t.loop, t.vol)
            if ok and played and t.loop then on[ev] = v end
        elseif on[ev] then
            try("sound", Homestead.Sfx, p.id, on[ev], false, false, 0)
            on[ev] = nil
        end
    end
    local function hum(p, on) for _, ev in ipairs(p.it.snd and p.it.snd.hum or {}) do sfx(p, ev, on) end end

    local function lamp(p, on)
        S.dark[hashOf(p.id)] = not on or nil
        local e = des():GetEntity(p.id)
        if not e then return end
        for i, l in ipairs(p.it.lights) do
            local c = e:FindComponentByName(CName.new("hs_light" .. i))
            if c then if on then c:SetIntensity(lumens(l)) end c:ToggleLight(on) end
        end
        local g = p.it.glow and e:FindComponentByName(CName.new("hs_mesh" .. p.it.glow))
        if g then g:Toggle(on) end
        -- A Night City lamp: its mesh in its off look instead (init.lua onEntity).
        local off = p.it.off and e:FindComponentByName(CName.new("hs_off"))
        if off then
            off:Toggle(not on)
            local m = e:FindComponentByName(CName.new("hs_mesh1"))
            if m then m:Toggle(on) end
        end
    end
    local NEXT = { TripTransition = "Tripped", Trip = "Tripped", SetTransitionFromTripped = "Set", TurningOn = "On", TurningOff = "Off" }

    local function kind(a)
        local s = a.seqs
        if s.Open and s.Close then return "door" end
        if s.Set and (s.TripTransition or s.Trip) then return "trap" end
        if s.On and (s.TurningOff or s.Off) then return "switch" end
        if a.rest and s[a.rest] and s[a.rest].loop then return "loop" end
    end
    Anim.kind = kind

    local function state(p)
        local h = hashOf(p.id)
        local st = S.anims[h]
        if not st then st = { p = p, at = p.it.anim.rest, seq = nil, t = 0 }; S.anims[h] = st end
        return st
    end

    -- A door in a building (Structures: doors, gates, a boxcar's - not a vending machine's flap or a container's lid): true
    -- shut (at rest, still), false open or moving; nil not a door. Its leaves block traffic while shut (Life.navDoor, livenav.lua).
    function Anim.shut(p)
        local a, it = p.it.anim, p.it
        if not (a and it.cat == "Structures" and not it.stash and kind(a) == "door") then return nil end
        local h = hashOf(p.id)
        return not S.playing[h] and (S.anims[h] and S.anims[h].at or a.rest) == a.rest
    end
    local function door(p)
        local s = Anim.shut(p)
        if s ~= nil then C.Life.navDoor(p, s) end
    end

    -- The parts' mesh components and colliders: found once, again after the entity streams out and back in, and rechecked
    -- every half second. Entities are not compared for this: CET hands out a new handle each time.
    local relook
    local function comps(st)
        local e = des():GetEntity(st.p.id)
        if not e then st.mesh = nil return nil end
        local now = os.clock()
        if not st.mesh or now - (st.found or 0) > 0.5 then
            local a = st.p.it.anim
            local fresh = not st.mesh
            st.mesh, st.col, st.found = {}, {}, now
            for k = 1, a.n do
                st.mesh[k] = e:FindComponentByName(CName.new("hs_mesh" .. (a.first + k - 1)))
                st.col[k] = e:FindComponentByName(CName.new("hs_pcol" .. k))
            end
            if fresh then st.lv, st.colOn = nil, nil; relook(st) end
        end
        return st.mesh
    end

    local v = {}
    local function apply(st, name, t)
        local a = st.p.it.anim
        local s = a.seqs[name]
        local ms = comps(st)
        if not s or not ms then return end
        local f = s.f
        local nf = #f / (7 * a.n)
        local x = math.max(0, math.min(nf - 1, t * RATE))
        local f0 = math.floor(x)
        local f1, w = math.min(nf - 1, f0 + 1), x - f0
        st.lv = st.lv or {}
        for k = 1, a.n do
            local c = ms[k]
            if c then
                local i0, i1 = (f0 * a.n + k - 1) * 7, (f1 * a.n + k - 1) * 7
                local sg = (f[i0 + 4] * f[i1 + 4] + f[i0 + 5] * f[i1 + 5] + f[i0 + 6] * f[i1 + 6] + f[i0 + 7] * f[i1 + 7]) < 0 and -1 or 1
                for j = 1, 7 do v[j] = f[i0 + j] + ((j > 3 and sg or 1) * f[i1 + j] - f[i0 + j]) * w end
                local lv = st.lv[k]
                if not lv then lv = {}; st.lv[k] = lv end
                local same = lv[1] ~= nil
                for j = 1, 7 do if same and math.abs(lv[j] - v[j]) > 1e-5 then same = false end end
                if not same then
                    for j = 1, 7 do lv[j] = v[j] end
                    local l = math.sqrt(v[4] ^ 2 + v[5] ^ 2 + v[6] ^ 2 + v[7] ^ 2)
                    c:SetLocalPosition(Vector4.new(v[1], v[2], v[3], 1))
                    c:SetLocalOrientation(Quaternion.new(v[4] / l, v[5] / l, v[6] / l, v[7] / l))
                end
            end
        end
    end
    local function seen(st)
        local eye, dir = view()
        local o = st.p.o
        local dx, dy, dz = o.x - eye.x, o.y - eye.y, o.z - eye.z
        local d2 = dx * dx + dy * dy + dz * dz
        return d2 < 36 or (dx * dir.x + dy * dir.y + dz * dir.z) > 0.17 * math.sqrt(d2)   -- (80 degrees off the view)
    end

    local function colliders(st, on)
        comps(st)
        if st.colOn == on or not st.col then return end
        st.colOn = on
        for _, c in pairs(st.col) do if c then pcall(function() c:Toggle(on) end) end end
    end

    local function spread(h, salt)
        local x = salt
        for i = 1, #h do x = (x * 31 + h:byte(i)) % 1000003 end
        return x / 1000003
    end

    function relook(st)  -- comps: fresh components - put the parts and colliders where its state has them, unless mid-move
        local a = st.p.it.anim
        if S.playing[hashOf(st.p.id)] or not st.at or not a.seqs[st.at] then return end
        if st.at ~= a.rest then
            local s = a.seqs[st.at]
            local f = s.f
            local nf = #f / (7 * a.n)
            for k = 1, a.n do
                local c = st.mesh[k]
                local i = ((nf - 1) * a.n + k - 1) * 7
                if c then
                    local l = math.sqrt(f[i + 4] ^ 2 + f[i + 5] ^ 2 + f[i + 6] ^ 2 + f[i + 7] ^ 2)
                    c:SetLocalPosition(Vector4.new(f[i + 1], f[i + 2], f[i + 3], 1))
                    c:SetLocalOrientation(Quaternion.new(f[i + 4] / l, f[i + 5] / l, f[i + 6] / l, f[i + 7] / l))
                end
            end
            for _, c in pairs(st.col) do if c then pcall(function() c:Toggle(false) end) end end
            st.colOn = false
        end
    end

    function Anim.play(p, name)
        local st = state(p)
        local s = p.it.anim.seqs[name]
        if not s then return end
        st.seq, st.t, st.cue, st.rate = name, 0, 1, 1
        -- A running loop: each piece at its own point and pace, so a row of turrets doesn't sweep in step.
        if s.loop and s.dur > 0 then
            local h = hashOf(p.id)
            st.t, st.rate = spread(h, 7) * s.dur, 0.92 + 0.16 * spread(h, 13)
        end
        st.cues = p.it.snd and p.it.snd.seq[name]
        S.playing[hashOf(p.id)] = st
        colliders(st, false)
        door(p)
    end

    function Anim.tick(dt)
        for h, st in pairs(S.playing) do
            local a = st.p.it.anim
            local s = a.seqs[st.seq]
            st.t = st.t + dt * (st.rate or 1)
            local c = st.cues
            while c and c[st.cue] and c[st.cue][1] <= st.t do sfx(st.p, c[st.cue][3], c[st.cue][2] == 1) st.cue = st.cue + 1 end
            if s.loop then
                if s.dur > 0 then st.t = st.t % s.dur end
                if seen(st) then try("animation", apply, st, st.seq, st.t) end
            elseif st.t >= s.dur then
                try("animation", apply, st, st.seq, s.dur)
                st.at = st.seq
                if st.p.it.lights and (st.at == "On" or st.at == "Off") then try("light", lamp, st.p, st.at == "On") end
                local nx = NEXT[st.seq]
                if nx and a.seqs[nx] then Anim.play(st.p, nx)
                else
                    S.playing[h] = nil
                    colliders(st, st.at == a.rest)
                    door(st.p)
                end
            elseif seen(st) then
                try("animation", apply, st, st.seq, st.t)
            end
        end
    end

    -- What E does to it (nil: nothing), as the prompt says it. A container (catalog `stash`): E opens V's stash through the
    -- game's stash device riding in it; the lid opens with it and closes when the menu goes (Anim.stashTick).
    local function stashOf(p)
        for _, id in ipairs(p.parts or {}) do
            local e = des():GetEntity(id)
            if e and e:GetClassName().value == "Stash" then return e end
        end
    end
    local function openStash(p)
        local e = stashOf(p)
        if not e then return end
        local ps = e:GetDevicePS()
        local act = ps:ActionOpenStash()
        act:SetExecutor(Game.GetPlayer())
        Game.GetPersistencySystem():QueuePSDeviceEvent(act)
        local a = p.it.anim
        if a and a.seqs.Open and state(p).at ~= "Open" then Anim.play(p, "Open") end
        S.stashOpen, S.stashT = p, 0
    end

    function Anim.label(p)
        if p.it.stash then return "Open" end
        local a = p.it.anim
        if not a then return p.it.lights and (S.dark[hashOf(p.id)] and "Turn on" or "Turn off") end
        local k = kind(a)
        if not k or k == "loop" then return nil end
        local at = state(p).at
        if k == "door" then return (at == "Open") and "Close" or "Open" end
        if k == "trap" then return (at == "Set") and "Trigger" or "Reset" end
        if k == "switch" then return (at == "Off") and "Turn on" or "Turn off" end
    end

    function Anim.use(p)
        if p.it.stash then try("stash", openStash, p) return end
        if not p.it.anim then try("light", lamp, p, S.dark[hashOf(p.id)] ~= nil) return end
        local a, st = p.it.anim, state(p)
        local k = kind(a)
        if S.playing[hashOf(p.id)] and not a.seqs[st.seq].loop then return end
        if k == "door" then Anim.play(p, st.at == "Open" and "Close" or "Open")
        elseif k == "trap" then
            if st.at == "Set" then Anim.play(p, a.seqs.TripTransition and "TripTransition" or "Trip")
            else Anim.play(p, a.seqs.SetTransitionFromTripped and "SetTransitionFromTripped" or "Set") end
        elseif k == "switch" then
            if st.at == "Off" then Anim.play(p, a.seqs.TurningOn and "TurningOn" or "On")
            else Anim.play(p, a.seqs.TurningOff and "TurningOff" or "Off") end
        end
    end

    function Anim.stashTick(dt)
        local p = S.stashOpen
        S.stashT = S.stashT + dt
        if S.stashT < 1 or Homestead.InMenu() then return end
        S.stashOpen = nil
        if p.it.anim and p.it.anim.seqs.Close and state(p).at == "Open" then Anim.play(p, "Close") end
    end

    function Anim.near(pos)
        for _, p in ipairs(S.pieces) do
            local a, sn = p.it.anim, p.it.snd
            if a or (sn and sn.hum[1]) then
                local h, d2 = hashOf(p.id), (p.o.x - pos.x) ^ 2 + (p.o.y - pos.y) ^ 2
                local at = a and (S.anims[h] and S.anims[h].at or a.rest)
                local run = not a or a.seqs[at] and a.seqs[at].loop and at or at ~= "Off" and a.seqs.Idle and a.seqs.Idle.loop and "Idle"
                if run then                                   -- (Idle: what runs while it's on - a ceiling fan's blades)
                    if d2 < LOOP_NEAR ^ 2 then
                        if not S.running[h] then
                            S.running[h] = true
                            if a then Anim.play(p, run) end
                        end
                        hum(p, true)
                    elseif d2 > (LOOP_NEAR + 10) ^ 2 and S.running[h] then
                        S.running[h], S.playing[h] = nil, nil
                        hum(p, false)
                    end
                elseif S.running[h] and not S.playing[h] then S.running[h] = nil end
            end
        end
    end

    function Anim.forget(id)
        local h = hashOf(id)
        for _, v in pairs(S.sfx[h] or {}) do try("sound", Homestead.Sfx, id, v, false, false, 0) end
        try("sound", Homestead.SfxForget, id)
        S.playing[h], S.anims[h], S.sfx[h], S.running[h], S.dark[h] = nil, nil, nil, nil, nil
    end
end
