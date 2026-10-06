-- Fallout's elevators (Contraptions Workshop): one piece in the menu, two in the world - the shaft, and the car that
-- travels in it. Fallout moves the car by script, so there is no animation of it: the importer splits the car off as
-- the piece's one moving part, held still (tools/fo4/anim.py CARRIED: catalog anim.rest "Held"), hangs Fallout's own
-- buttons on (convert.py BUTTON), and here it travels. As in Fallout: the car's panel has a button a floor, each floor
-- two call buttons - the crosshair on one becomes the game's hand (init.lua), and a click or F sends the car there. The car's collider moves with it; Fallout's own
-- motor, bell and button sound (with Audioware). Not saved: a loaded game finds every car at the ground. El is C.Elevator.
return function(El, C)
    local des, hashOf, try = C.des, C.hashOf, C.try
    local H, SPEED = 3.6576, 1.6                                 -- m a floor (Fallout's 256 units), m a second
    local FLOORS = { fo4_dlc05elevatorcar2 = 2, fo4_dlc05elevatorcar3 = 3, fo4_dlc05elevatorcar4 = 4 }
    -- Where the buttons are, in the piece's space (the models' Button nodes, measured): the panel's by floor (x; in the
    -- car, on its +Y wall), a floor's two call buttons (x, y; on the shaft), all BZ over their floor
    local PANEL = { [2] = { -0.114, 0.114 }, [3] = { -0.293, 0, 0.289 }, [4] = { -0.343, -0.114, 0.114, 0.343 } }
    local PY, CALL, BZ = 1.21, { { -1.616, -1.458 }, { 1.601, 1.458 } }, 1.429
    local AIM, REACH = 0.11, 3.0                                 -- m the crosshair may pass a button by; m it reaches
    local MOTOR, BELL, BUTTON = "hs_objelevatorplatformmotorlpm", "hs_objloadelevatorutilityding", "hs_objloadelevatorutilitybuttoncall"   -- (Fallout's: tools/fo4/sounds.py WANTED)
    local cars = {}                                              -- entity hash -> { p, z (m up from the ground floor), to (floor, 0 the ground) }

    -- the floors of an elevator whose car is a part of its own (an import since 2026-10-05); nil: not one, or an older import
    function El.floors(p) return p.it.anim and p.it.anim.rest == "Held" and FLOORS[p.it.key] or nil end
    local function state(p)
        local h = hashOf(p.id)
        cars[h] = cars[h] or { z = 0, to = 0 }
        cars[h].p = p
        return cars[h]
    end

    -- the button V's crosshair is on -> its floor (0 the ground), and whether it is the car's panel; nil: none
    local function button(p, n, st)
        local eye, dir = C.view()
        local best, bd, panel
        local function near(x, y, z, f, car)
            local w = C.local2world(p.o, p.yaw, x, y, z)
            local vx, vy, vz = w.x - eye.x, w.y - eye.y, w.z - eye.z
            local t = vx * dir.x + vy * dir.y + vz * dir.z
            local d = vx * vx + vy * vy + vz * vz - t * t         -- (the crosshair's line past it, squared)
            if t > 0 and t < REACH and d < AIM * AIM and (not bd or d < bd) then best, bd, panel = f, d, car end
        end
        for f = 1, n do
            near(PANEL[n][f], PY, BZ + st.z, f - 1, true)
            for _, c in ipairs(CALL) do near(c[1], c[2], BZ + (f - 1) * H, f - 1, false) end
        end
        return best, panel
    end

    -- The elevator a button of which is under V's crosshair, and what the button says. Asked of the elevators near V
    -- themselves (listed once a second): the crosshair's ray finds a piece by its colliders as it was placed, and the car's
    -- are at the ground - upstairs it found nothing, and F did nothing but on the first floor (user, 2026-10-05).
    local near, nearT = {}, 0
    function El.hover(pos)
        if os.clock() - nearT > 1 then
            near, nearT = {}, os.clock()
            for _, p in ipairs(C.S.pieces) do
                if FLOORS[p.it.key] and (p.o.x - pos.x) ^ 2 + (p.o.y - pos.y) ^ 2 < 36 and El.floors(p) then near[#near + 1] = p end
            end
        end
        for _, p in ipairs(near) do
            local l = C.S.byId[hashOf(p.id)] and El.label(p)
            if l then return p, l end
        end
    end

    function El.label(p)
        local n, st = El.floors(p), state(p)
        if st.z ~= st.to * H then return nil end                 -- (on its way)
        local f, panel = button(p, n, st)
        if not f or f == st.to then return nil end               -- (no button there, or the car is at that floor)
        return panel and ("Floor " .. (f + 1)) or "Call elevator"
    end
    function El.use(p)
        local n, st = El.floors(p), state(p)
        if st.z ~= st.to * H then return end
        local f = button(p, n, st)
        if not f or f == st.to then return end
        st.to = f
        C.Anim.sfx(p, BUTTON, true); C.Anim.sfx(p, MOTOR, true)
    end

    local function place(st)
        local p = st.p
        local e, a = des():GetEntity(p.id), p.it.anim
        if not e then return end
        local f = a.seqs[a.rest].f                               -- the car's rest place: x y z of the part's first frame
        local m = e:FindComponentByName(CName.new("hs_mesh" .. a.first))
        if m then m:SetLocalPosition(Vector4.new(f[1], f[2], f[3] + st.z, 1)) end
        local c = e:FindComponentByName(CName.new("hs_pcol1"))
        if c then c:SetLocalPosition(Vector4.new(0, 0, st.z, 1)) end
    end

    function El.tick(dt)
        for h, st in pairs(cars) do
            local want = st.to * H
            if st.z ~= want then
                local d = want - st.z
                st.z = math.abs(d) <= SPEED * dt and want or st.z + (d > 0 and SPEED or -SPEED) * dt
                try("elevator", place, st)
                if st.z == want then C.Anim.sfx(st.p, MOTOR, false); C.Anim.sfx(st.p, BELL, true) end   -- (there)
            elseif not des():GetEntity(st.p.id) then cars[h] = nil end   -- (scrapped, or out of the world)
        end
    end
end
