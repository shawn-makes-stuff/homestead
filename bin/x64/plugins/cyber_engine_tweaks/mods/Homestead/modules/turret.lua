-- Turrets (modules/own/turrets.lua): a turret turns its head at whoever is attacking V and fires. Only them: hostile,
-- alive, in combat, on V's own list of threats (Homestead.Attackers) - police who aren't after V are left alone.
-- The head is the piece's one moving part (catalog anim: its rest pose is frame 1 of the idle sequence), turned about the
-- vertical through its pivot and tipped up or down. With no one to aim at it sweeps side to side - by this script too
-- (the import's sweep keyframes are not played: a spotlight's light has to go with its head).
-- A hit takes a share of the target's health, as V's doing. Tur is C.Turret (init.lua requires this).
return function(Tur, C)
    local S, des, hashOf, try, Q = C.S, C.des, C.hashOf, C.try, C.Q
    local T = require("modules/own/turrets")
    local SCAN, PITCH, AIMED, CHEST = 0.5, 35, 4, 1.2            -- s between looks; degrees; m up a target
    local SWEEP, PERIOD = 35, 9                                  -- idle: degrees either way, seconds there and back
    local on, scanT = {}, 0                                     -- entity hash -> { p, yaw, pitch, cool, npc }
    local LIT = { "hs_light", "hs_beam" }

    local function wrap(d) return (d + 180) % 360 - 180 end
    local function toward(v, to, by) local d = wrap(to - v); return v + math.max(-by, math.min(by, d)) end

    local function head(p)                                      -- the head's pivot in the world
        local f = p.it.anim.seqs[p.it.anim.rest].f
        local r = math.rad(p.yaw or 0)
        return { x = p.o.x + f[1] * math.cos(r) - f[2] * math.sin(r), y = p.o.y + f[1] * math.sin(r) + f[2] * math.cos(r), z = p.o.z + f[3] }
    end

    local function pose(st)
        local e = des():GetEntity(st.p.id)
        local a = st.p.it.anim
        local c = e and e:FindComponentByName(CName.new("hs_mesh" .. a.first))
        if not c then return end
        local f = a.seqs[a.rest].f
        local q = Q.mul(Q.yaw(st.yaw), Q.mul(Q.axis(1, 0, 0, st.pitch), { i = f[4], j = f[5], k = f[6], r = f[7] }))
        c:SetLocalOrientation(Quaternion.new(q.i, q.j, q.k, q.r))
        for i, at in ipairs(not T[st.p.it.key].rate and st.p.it.lights or {}) do   -- (a spotlight: its lights and their beams
            for _, name in ipairs(LIT) do                                          -- with its head, round the pivot)
                local l, r = e:FindComponentByName(CName.new(name .. i)), math.rad(st.yaw)
                if l then
                    l:SetLocalPosition(Vector4.new(f[1] - math.sin(r) * (at.pos[2] - f[2]), f[2] + math.cos(r) * (at.pos[2] - f[2]), at.pos[3], 1))
                    l:SetLocalOrientation(EulerAngles.new(0, st.pitch, st.yaw):ToQuat())
                end
            end
        end
    end

    -- where a target is from a turret: yaw and pitch for its head (degrees, the piece's space), and how far
    local function aim(p, at)
        local h = head(p)
        local dx, dy, dz = at.x - h.x, at.y - h.y, at.z + CHEST - h.z
        local flat = math.sqrt(dx * dx + dy * dy)
        return wrap(math.deg(math.atan2(-dx, dy)) - (p.yaw or 0)), math.max(-PITCH, math.min(PITCH, math.deg(math.atan2(dz, flat)))),
               math.sqrt(flat * flat + dz * dz), h
    end

    local function clear(h, at)                                 -- nothing of the world between the head and the target
        local hit = Homestead.Ray(Vector4.new(h.x, h.y, h.z, 1), Vector4.new(at.x, at.y, at.z + CHEST, 1))
        return hit.w == 0 or (hit.x - at.x) ^ 2 + (hit.y - at.y) ^ 2 + (hit.z - at.z - CHEST) ^ 2 < 0.6 ^ 2
    end

    local function scan(pos, fight)
        local npcs = {}
        local ok, list = pcall(Homestead.Attackers)
        for _, n in ipairs(fight and ok and list or {}) do npcs[#npcs + 1] = { npc = n, at = n:GetWorldPosition() } end
        for k, st in pairs(on) do
            st.npc = nil
            if not S.byId[k] then on[k] = nil end                 -- (scrapped, or picked up)
        end
        for _, p in ipairs(S.pieces) do
            local t = T[p.it.key]
            if t and p.it.anim and (p.o.x - pos.x) ^ 2 + (p.o.y - pos.y) ^ 2 < 100 ^ 2 then
                local best, bd
                for _, n in ipairs(npcs) do
                    local _, _, d, h = aim(p, n.at)
                    if d < t.range and (not bd or d < bd) and clear(h, n.at) then best, bd = n.npc, d end
                end
                local k = hashOf(p.id)                        -- (every turret near V is ours to turn: its head sweeps by this
                on[k] = on[k] or { yaw = 0, pitch = 0, cool = 0, phase = (tonumber(k:match("%d+")) or 0) % 628 / 100 }   -- script, not by the
                on[k].p, on[k].npc = p, best                  -- import's keyframes - so a spotlight's beam goes with it)
                S.playing[k], S.running[k] = nil, true
            end
        end
    end

    local function fire(st, t, h)
        local r = math.rad((st.p.yaw or 0) + st.yaw)
        local m = t.muzzle
        Homestead.TurretHit(st.npc, t.dmg)
        Homestead.SoundAt(st.p.id, t.sound)
        local w = WorldTransform.new()
        w:SetPosition(Vector4.new(h.x - math.sin(r) * m[1], h.y + math.cos(r) * m[1], h.z + m[2], 1))
        w:SetOrientation(EulerAngles.new(0, st.pitch, (st.p.yaw or 0) + st.yaw):ToQuat())
        local res = gameFxResource.new()
        res.effect = ResRef.FromString(t.flash)
        Game.GetFxSystem():SpawnEffect(res, w, false)
    end

    function Tur.tick(dt, pos)
        scanT = scanT - dt
        if scanT <= 0 then
            scanT = SCAN
            local ok, fight = pcall(function() return Game.GetPlayer():IsInCombat() end)
            try("turret scan", scan, pos, ok and fight)
        end
        for k, st in pairs(on) do
            local t = T[st.p.it.key]
            local yaw, pitch, h = SWEEP * math.sin(os.clock() * 6.2832 / PERIOD + st.phase), 0, nil   -- (idle: side to side)
            if st.npc then
                local ok, at = pcall(function() return st.npc:GetWorldPosition() end)
                local far
                if ok and at then yaw, pitch, far, h = aim(st.p, at) else st.npc = nil end
            end
            st.yaw, st.pitch = toward(st.yaw, yaw, t.turn * dt), toward(st.pitch, pitch, t.turn * dt)
            try("turret pose", pose, st)
            st.cool = st.cool - dt
            if st.npc and t.rate and st.cool <= 0 and math.abs(wrap(yaw - st.yaw)) < AIMED then
                st.cool = 1 / t.rate
                try("turret fire", fire, st, t, h)
            end
        end
    end
end
