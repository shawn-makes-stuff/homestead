-- Fallout's loose balls (its MISC items - a ball track's Steel Ball, the Nuka-Cade's, a basketball: Havok rolls them)
-- fall, roll and bounce here by this script: a sphere under gravity, held off whatever a ray finds under it or ahead of
-- it (the world and our pieces - Homestead.RayHit) and off every box of our pieces it reaches into as the sphere it
-- is (a ball track's two rails, a floor's edge: a ray from its middle passes them), rolling down what slopes and on
-- after a landing, turning as it
-- travels, slowed as it rolls, pushed when V walks into it. The game's own physics was tried first (2026-10-05: a
-- Dynamic collider made by script fell through everything - its collision masks are a preset's, and what the bits
-- are isn't known). The ball is its piece: the piece's place goes where the ball goes (p.o, S.info's place and the
-- grid's cells - so the crosshair, scrap and move find it where it is) and its mesh is drawn there; it has no
-- collider of its own. Where it comes to rest is kept across a save as people's places are (jobs.txt "<hash>a",
-- Life.nudge: the game keeps where an entity was made, not where it was moved to). B is C.Ball.
return function(B, C)
    local S, des, hashOf, try, Q = C.S, C.des, C.hashOf, C.try, C.Q
    local BALLS = { fo4_dlc05workshopballtrackball01 = 0.25, fo4_dlc04_nukacade_atomicrollersball01 = 0.35, fo4_dlc04nukacade_basketball01 = 0.75 }   -- key -> bounce
    -- m/s2; the share of its speed a second of rolling takes; m/s it rests under; a normal's z from which ground is
    -- level enough to rest on (10 degrees); m of V; m/s at most of V's own pace in a push (a fast travel isn't a kick)
    local G, ROLL, REST, FLAT, NEAR, PACE = 9.81, 0.35, 0.05, 0.985, 60, 10
    local SKIN = 0.002                                          -- m off a box at which the ball still touches it (at rest on it, it is a radius off)
    local on, scanT, was = {}, 0, nil                           -- entity hash -> { p, r, at (the centre, world), v, w (its spin, rad/s), q (how it is turned), still }
    function B.is(it) return BALLS[it.key] ~= nil end

    -- What is between two points -> point, normal; nil: nothing. The world by the game's ray; our own pieces by their
    -- boxes (the game's ray doesn't find their colliders: a ball fell through every Fallout piece onto the ground
    -- under it - user, 2026-10-05). The nearer of the two.
    local function hit(a, b)
        local dx, dy, dz = b.x - a.x, b.y - a.y, b.z - a.z
        local len = math.sqrt(dx * dx + dy * dy + dz * dz)
        if len < 1e-6 then return nil end
        local best, pt, n = len, nil, nil
        local h = Homestead.RayHit(Vector4.new(a.x, a.y, a.z, 1), Vector4.new(b.x, b.y, b.z, 1))
        if h[1].w ~= 0 then
            best = math.sqrt((h[1].x - a.x) ^ 2 + (h[1].y - a.y) ^ 2 + (h[1].z - a.z) ^ 2)
            pt, n = { x = h[1].x, y = h[1].y, z = h[1].z }, { x = h[2].x, y = h[2].y, z = h[2].z }
        end
        local dir = { x = dx / len, y = dy / len, z = dz / len }
        for _, p in ipairs(C.Grid.around(a.x, a.y, len + 0.5)) do
            if not BALLS[p.it.key] and not p.it.npc then
                for _, bx in ipairs(p.it.cboxes or p.it.boxes or {}) do
                    local t, nn = C.rayBox(p, bx, a, dir)
                    if t and t < best then
                        best, pt, n = t, { x = a.x + dir.x * t, y = a.y + dir.y * t, z = a.z + dir.z * t }, { x = nn[1], y = nn[2], z = nn[3] }
                    end
                end
            end
        end
        return pt, n
    end

    -- What of our pieces the ball reaches into, as a sphere: the nearest point of each box near it, and the way off
    -- it -> meet(point, normal). A ray from its middle finds only what is right under or ahead of that middle: a ball
    -- track's rails are two plates either side of it, and a ball set on a track fell between them (2026-10-06). Left
    -- out: a box it is more than its radius inside (as a ray starting inside one finds nothing), and what lies in the
    -- surface the ray down found (gp, gn: that floor itself, and the next box of a floor made of several - whose edge
    -- would stop a ball rolling over the seam).
    local function reaches(at, r, gp, gn, meet)
        for _, p in ipairs(C.Grid.around(at.x, at.y, r + SKIN)) do
            if not BALLS[p.it.key] and not p.it.npc then
                local list = p.it.cboxes or p.it.boxes or {}
                local far = -1                                    -- (a piece of many boxes: its bounds first)
                if #list > 4 and not p.it.cboxes then far = select(2, C.nearBox(p, C.boundsBox(p.it), at)) end
                if far < r + 0.25 then
                    for _, bx in ipairs(list) do
                        local q, d, n = C.nearBox(p, bx, at)
                        if d < r + SKIN and d > -r and not (gp and (q.x - gp.x) * gn.x + (q.y - gp.y) * gn.y + (q.z - gp.z) * gn.z < 1e-3) then meet(q, n) end
                    end
                end
            end
        end
    end

    -- The piece is where the ball is: its place (the piece list's, and S.info's - what refresh keeps a piece by), and
    -- the grid's cells once it has left the ones it was listed in (Grid.build's own reach).
    local function span(v, r) return math.floor((v - r) / C.Grid.size) * 4096 + math.floor((v + r) / C.Grid.size) end
    local function move(st, to)
        local p, r = st.p, C.Grid.reach(st.p.it)
        local info = S.info[hashOf(p.id)] or S.pending[hashOf(p.id)]
        local same = span(to.x, r) == span(p.o.x, r) and span(to.y, r) == span(p.o.y, r)
        st.at, p.o, p.at = to, to, C.anchorOf(p.it, to, p.yaw or 0)
        if info then info.o = to end
        if not same then C.Grid.build(S.pieces) end
    end

    -- The mesh to where the ball is, turned as it has rolled: within its entity, which stays where it was made (as
    -- the elevator's car and a turret's head are moved, and the ball itself before 2026-10-06 - seen in game. The
    -- entity teleported after the ball every frame instead was not seen to move: user, "the ball doesnt roll anymore").
    local function show(st)
        local p, e = st.p, des():GetEntity(st.p.id)
        local m = e and e:FindComponentByName(CName.new("hs_mesh1"))
        if not m then return end
        local w, r = e:GetWorldPosition(), math.rad(-(p.yaw or 0))
        local dx, dy = st.at.x - w.x, st.at.y - w.y
        m:SetLocalPosition(Vector4.new(dx * math.cos(r) - dy * math.sin(r), dx * math.sin(r) + dy * math.cos(r), st.at.z - w.z, 1))
        local q = Q.mul(Q.yaw(-(p.yaw or 0)), st.q)               -- (in its entity's space)
        m:SetLocalOrientation(Quaternion.new(q.i, q.j, q.k, q.r))
        st.sync = nil
    end

    local function keep(k, st)                                   -- where it lies is where a load finds it
        local o, a = st.at, st.kept
        if (o.x - a.x) ^ 2 + (o.y - a.y) ^ 2 + (o.z - a.z) ^ 2 < 4e-4 then return end
        C.Life.nudge(k, 0, 0, 0, 0, o, st.p.yaw or 0)
        st.kept, st.saved = o, C.Life.jobs[k .. "a"]
    end

    local function step(st, dt, v, vv)
        local at, vel, r = st.at, st.v, st.r
        vel.z = vel.z - G * dt
        local dx, dy = at.x - v.x, at.y - v.y                    -- V walks into it (or it rolls into V): it leaves at V's
        local d = dx * dx + dy * dy                               -- pace and a bit more, away from V
        if d < (r + 0.45) ^ 2 and math.abs(at.z - v.z - 0.3) < 1.2 then
            local l = math.max(math.sqrt(d), 0.05)
            local rel = ((vv.x - vel.x) * dx + (vv.y - vel.y) * dy) / l + 0.5
            if rel > 0 then vel.x, vel.y = vel.x + dx / l * rel * 1.2, vel.y + dy / l * rel * 1.2 end
        end
        -- what is under it, then what is ahead of it: off either it loses what speed went into it (some comes back:
        -- its bounce) and keeps what runs along it
        local hits, ground = {}, nil
        local function meet(pt, n, ray)
            local into = vel.x * n.x + vel.y * n.y + vel.z * n.z
            if into < 0 then
                local back = -into > 1.2 and st.bounce or 0       -- (a hard landing bounces; a ball at rest on a slope doesn't hop)
                vel.x, vel.y, vel.z = vel.x - (1 + back) * into * n.x, vel.y - (1 + back) * into * n.y, vel.z - (1 + back) * into * n.z
            end
            hits[#hits + 1] = { pt, n, ray }
        end
        local function touch(ux, uy, uz, reach)
            local pt, n = hit(at, { x = at.x + ux * reach, y = at.y + uy * reach, z = at.z + uz * reach })
            if pt then meet(pt, n, true) end
            return pt, n
        end
        local gp, gn = touch(0, 0, -1, r + math.max(0, -vel.z) * dt + 0.02)
        reaches(at, r, gp, gn, meet)
        local sp = math.sqrt(vel.x ^ 2 + vel.y ^ 2 + vel.z ^ 2)
        if sp > 1e-4 then touch(vel.x / sp, vel.y / sp, vel.z / sp, r + sp * dt + 0.02) end
        if #hits > 1 then                                         -- (held by several at once - two rails, a floor and a wall: into none of them)
            for _ = 1, 3 do
                for _, h in ipairs(hits) do
                    local n = h[2]
                    local into = vel.x * n.x + vel.y * n.y + vel.z * n.z
                    if into < 0 then vel.x, vel.y, vel.z = vel.x - into * n.x, vel.y - into * n.y, vel.z - into * n.z end
                end
            end
        end
        -- what it lies on: level ground if it touches any, else all that holds it up together (two rails: the way
        -- up between them), else the first thing it touched
        local ux, uy, uz = 0, 0, 0
        for _, h in ipairs(hits) do
            local n = h[2]
            if n.z > FLAT then ground = n break end
            if n.z > 0.1 then ux, uy, uz = ux + n.x, uy + n.y, uz + n.z end
        end
        if not ground and uz > 0 then
            local l = math.sqrt(ux * ux + uy * uy + uz * uz)
            ground = { x = ux / l, y = uy / l, z = uz / l }
        end
        ground = ground or (hits[1] and hits[1][2])
        if ground then
            local f, n = math.max(0, 1 - ROLL * dt), ground
            vel.x, vel.y, vel.z = vel.x * f, vel.y * f, vel.z * f
            -- (it rests on level enough ground once slow: under REST and what the slope gave it this frame)
            if n.z > FLAT and vel.x ^ 2 + vel.y ^ 2 + vel.z ^ 2 < (REST + G * math.sqrt(1 - n.z * n.z) * dt) ^ 2 then
                vel.x, vel.y, vel.z = 0, 0, 0
                st.still = (st.still or 0) + dt
            else st.still = 0 end
            -- rolling, not sliding: it turns about the axis across its travel, once round per circumference
            st.w = { x = (n.y * vel.z - n.z * vel.y) / r, y = (n.z * vel.x - n.x * vel.z) / r, z = (n.x * vel.y - n.y * vel.x) / r }
        else st.still = 0 end                                     -- (in the air: it keeps its spin)
        local w = st.w
        local wl = math.sqrt(w.x ^ 2 + w.y ^ 2 + w.z ^ 2)
        if wl > 1e-3 then st.q = Q.norm(Q.mul(Q.axis(w.x / wl, w.y / wl, w.z / wl, math.deg(wl * dt)), st.q)) end
        local to = { x = at.x + vel.x * dt, y = at.y + vel.y * dt, z = at.z + vel.z * dt }
        for _ = 1, #hits > 1 and 3 or 1 do                        -- (several: out of each without going into another)
            for _, h in ipairs(hits) do                           -- (a radius off what it touches: out of it, and onto what a ray
                local pt, n = h[1], h[2]                          -- found unless it is on its way off - the rays reach a little past it)
                local deep = r - ((to.x - pt.x) * n.x + (to.y - pt.y) * n.y + (to.z - pt.z) * n.z)
                if math.abs(deep) > 1e-5 and (deep > 0 or h[3] and vel.x * n.x + vel.y * n.y + vel.z * n.z < 0.2) then to.x, to.y, to.z = to.x + n.x * deep, to.y + n.y * deep, to.z + n.z * deep end
            end
        end
        if to.z < st.home.z - 200 then to, st.v = st.home, { x = 0, y = 0, z = 0 } end   -- (out of the world: back where it was put)
        if to.x ~= at.x or to.y ~= at.y or to.z ~= at.z or wl > 1e-3 then st.sync = true; move(st, to) end
    end

    function B.tick(dt, pos)
        scanT = scanT - dt
        if scanT <= 0 then
            scanT = 1
            for k in pairs(on) do if not S.byId[k] then on[k] = nil end end
            for _, p in ipairs(S.pieces) do
                if BALLS[p.it.key] and (p.o.x - pos.x) ^ 2 + (p.o.y - pos.y) ^ 2 < NEAR ^ 2 then
                    local k = hashOf(p.id)
                    local st = on[k]
                    if not st or st.p ~= p or st.at ~= p.o then  -- (new, or set down somewhere else)
                        st = { p = p, r = math.max(p.it.size[1], p.it.size[2], p.it.size[3]) / 2, at = p.o, home = p.o, kept = p.o,
                               v = { x = 0, y = 0, z = 0 }, w = { x = 0, y = 0, z = 0 }, q = { i = 0, j = 0, k = 0, r = 1 }, bounce = BALLS[p.it.key] }
                        on[k] = st
                    end
                    local a = C.Life.jobs[k .. "a"]              -- (after a load: where it had rolled to, at rest there)
                    if a and a ~= st.saved then
                        local x, y, z = a:match("^([^,]+),([^,]+),([^,]+),")
                        st.saved, st.kept, st.v, st.still = a, { x = tonumber(x), y = tonumber(y), z = tonumber(z) }, { x = 0, y = 0, z = 0 }, 1
                        move(st, st.kept)
                    end
                    st.sync = true                               -- (its entity made anew - a load's, a settlement come back in, a move: its mesh is back in its middle)
                end
            end
        end
        if not next(on) then was = nil return end                 -- (no ball near: nothing made a frame)
        local vv = { x = 0, y = 0 }                               -- V's own pace, from where V was a frame ago
        if was and dt > 0 then
            vv.x, vv.y = (pos.x - was.x) / dt, (pos.y - was.y) / dt
            local l = math.sqrt(vv.x ^ 2 + vv.y ^ 2)
            if l > PACE then vv.x, vv.y = vv.x / l * PACE, vv.y / l * PACE end
        end
        was = { x = pos.x, y = pos.y }
        dt = math.min(dt, 0.05)
        for k, st in pairs(on) do
            -- (workshop mode: they stay put, as everything does; one at rest sleeps till V is at it)
            if not S.build and ((st.still or 0) < 1 or (st.at.x - pos.x) ^ 2 + (st.at.y - pos.y) ^ 2 < 1) then
                -- (in steps of half its radius at most: a fast one doesn't pass through a rail between two frames)
                local n = math.max(1, math.min(8, math.ceil(math.sqrt(st.v.x ^ 2 + st.v.y ^ 2 + st.v.z ^ 2) * dt / (st.r * 0.5))))
                for _ = 1, n do try("ball", step, st, dt / n, pos, vv) end
                if (st.still or 0) >= 1 then try("ball", keep, k, st) end
            end
            if st.sync then try("ball", show, st) end
        end
    end
end
