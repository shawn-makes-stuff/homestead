-- Testing tools: a pop-in watch (GetMod("Homestead").popwatch()).
-- init.lua requires this once everything it uses exists; M is C.Testing.
return function(M, C)
    local S, playerPos, say = C.S, C.playerPos, C.say

    -- Pop-in watch (console: GetMod("Homestead").popwatch(), again to stop): ten times a second, checks whether each
    -- piece and part has its entity; each change goes to scripting.log with distance, angle off the view and time gone.
    local function popTick(dt)
        local w = S.popwatch
        w.clock, w.t = w.clock + dt, w.t - dt
        if w.t > 0 then return end
        w.t = 0.1
        local eye, dir = C.view()
        for _, p in ipairs(S.pieces) do
            for i = 0, #(p.parts or {}) do
                local id = i == 0 and p.id or p.parts[i]
                local h = C.hashOf(id)
                local on, was = C.des():GetEntity(id) ~= nil, w.on[h]
                if was ~= nil and was ~= on then
                    local dx, dy, dz = p.o.x - eye.x, p.o.y - eye.y, p.o.z - eye.z
                    local d = math.max(math.sqrt(dx * dx + dy * dy + dz * dz), 1e-6)
                    local off = math.deg(math.acos(math.max(-1, math.min(1, (dx * dir.x + dy * dir.y + dz * dir.z) / d))))
                    C.log(string.format("popwatch: %s%s %s at %.1f m, %.0f deg off the view%s", p.key, i > 0 and (" part " .. i) or "",
                        on and "spawned" or "despawned", d, off, on and string.format(", gone %.1f s", w.clock - (w.at[h] or w.clock)) or ""))
                end
                if not on and was ~= false then w.at[h] = w.clock end
                w.on[h] = on
            end
        end
    end
    local function popwatch()
        if S.popwatch then S.popwatch = nil say("Pop-in watch off") return end
        S.popwatch = { clock = 0, t = 0, on = {}, at = {} }
        local pos, best, bd = playerPos(), nil, math.huge
        for _, p in ipairs(S.pieces) do
            local d = pos and (p.o.x - pos.x) ^ 2 + (p.o.y - pos.y) ^ 2 or 0
            if d < bd and not p.it.npc then best, bd = p, d end
        end
        local e = best and C.des():GetEntity(best.id)
        local c = e and e:FindComponentByName(CName.new("hs_mesh1"))
        if c then
            pcall(function() C.log(string.format("popwatch: %s hs_mesh1 LODMode %s, forcedLodDistance %s, autoHideDistance %s, forceLODLevel %s",
                best.key, tostring(c.LODMode), tostring(c.forcedLodDistance), tostring(c.autoHideDistance), tostring(c.forceLODLevel))) end)
        end
        say("Pop-in watch on: scripting.log")
    end

    M.popTick, M.popwatch = popTick, popwatch
end
