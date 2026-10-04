-- Testing tools: fly mode (noclip) and a pop-in watch. Fly has a hotkey in CET's Hotkeys; GetMod("Homestead").fly().
-- init.lua requires this once everything it uses exists; M is C.Testing.
return function(M, C)
    local S, playerPos, say, v4, eng = C.S, C.playerPos, C.say, C.v4, C.Eng

    -- Fly (noclip): V flies by a teleport a frame and builds as on foot. W / S go where the view looks, A / D sideways,
    -- Space / C up and down, Shift fast. A teleport lands a frame late and undoes that frame's mouse turn, so the yaw
    -- is ours while flying: the mouse's motion (HomesteadMouse) times S.turnK, the degrees a unit of it turns V -
    -- learnt on foot in workshop mode (turnTick). Not learnt yet: teleports spaced out while the mouse moves. No
    -- entity attaches while V is teleported every frame: none while one of ours is attaching (WAIT at most).
    local FLY, WAIT, TURN = { speed = 8, fast = 30 }, 0.5, 4
    local cal = { yaw = nil, d = 0, x = 0 }
    local function turnTick()
        local dx, pl = S.mdx or 0, Game.GetPlayer()
        S.mdx = 0
        if not pl or not pl.GetWorldYaw or S.gz then cal.yaw = nil return end
        local yaw = pl:GetWorldYaw()
        if cal.yaw and dx ~= 0 then
            if dx * cal.x < 0 then cal.d, cal.x = 0, 0 end                 -- (a turn one way at a time)
            cal.d, cal.x = cal.d + (yaw - cal.yaw + 180) % 360 - 180, cal.x + dx
            if math.abs(cal.d) >= 20 then S.turnK, cal.d, cal.x = cal.d / cal.x, 0, 0 end
        end
        cal.yaw = yaw
    end
    local function flyTick(dt)
        local k, f = S.flyKeys, Game.GetCameraSystem():GetActiveCameraForward()
        local hl = math.max(math.sqrt(f.x * f.x + f.y * f.y), 1e-6)
        local fwd = (k.IK_W and 1 or 0) - (k.IK_S and 1 or 0)
        local side = (k.IK_D and 1 or 0) - (k.IK_A and 1 or 0)
        local up = (k.IK_Space and 1 or 0) - (k.IK_C and 1 or 0)
        local v = (k.IK_LShift and FLY.fast or FLY.speed) * dt
        local p = S.fly
        p.x = p.x + (f.x * fwd + f.y / hl * side) * v
        p.y = p.y + (f.y * fwd - f.x / hl * side) * v
        p.z = p.z + (f.z * fwd + up) * v
        local dx = S.mdx or 0
        S.mdx, cal.yaw = 0, nil
        if eng.pending() and (p.wait or 0) < WAIT then p.wait, p.yaw = (p.wait or 0) + dt, nil return end
        if not eng.pending() then p.wait = 0 end
        local pl = Game.GetPlayer()
        local yaw = pl.GetWorldYaw and pl:GetWorldYaw() or math.deg(math.atan2(-f.x, f.y))
        if S.turnK and not S.gz then
            p.yaw = (p.yaw or yaw) + S.turnK * dx
            yaw = p.yaw
        elseif dx ~= 0 then
            p.skip = (p.skip or 0) + 1
            if p.skip < ((fwd ~= 0 or side ~= 0 or up ~= 0) and 2 or TURN) then return end
        end
        p.skip = 0
        eng.teleport(pl, v4(p.x, p.y, p.z), EulerAngles.new(0, 0, yaw))
    end
    local function fly()
        if S.fly then S.fly = nil pcall(Homestead.Fly, S.build == true) say("Fly off") return end
        local p = playerPos()
        if not p then return end
        S.fly = { x = p.x, y = p.y, z = p.z + 0.3 }
        pcall(Homestead.Fly, true)
        say("Fly on: WASD where you look, Space up, C down, Shift fast")
    end
    registerHotkey("homestead_fly", "Fly (noclip): on / off", function() fly() end)

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

    M.flyTick, M.fly, M.popTick, M.popwatch, M.turnTick = flyTick, fly, popTick, popwatch, turnTick
end
