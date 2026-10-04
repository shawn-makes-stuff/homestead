-- Placement: where the held piece goes and whether it may stand there (placement(): the gizmo's pose, free hover,
-- Fallout snapping through connect points, decor on a surface or a wall, kit slots on the 3 m grid, roads, props on
-- a 0.5 m grid), its preview entity (syncGhost), and the actions that change the world: place, startMove, restore,
-- scrap, and the gizmo's Ctrl edit (gizmoApply / gizmoPickup).
return function(C)
    local S, byKey, atan2, des, v4, hashOf, say, GRID = C.S, C.byKey, C.atan2, C.des, C.v4, C.hashOf, C.say, C.GRID
    local STOREY, REACH, BUDGET, SFX = C.STOREY, C.REACH, C.BUDGET, C.SFX
    local OUTLINE, Eng, Gizmo, Life, sfx, timed, axes = C.OUTLINE, C.Eng, C.Gizmo, C.Life, C.sfx, C.timed, C.axes
    local Q, local2world, originAt = C.Q, C.local2world, C.originAt
    local originFromAnchor, cellOf, slotsOf = C.originFromAnchor, C.cellOf, C.slotsOf
    local inZone, Grid, cast, view, groundZ, corners, U = C.inZone, C.Grid, C.cast, C.view, C.groundZ, C.corners, C.U
    local reach, blockedBy, pairs_, spawnPiece, del = C.reach, C.blockedBy, C.pairs_, C.spawnPiece, C.del
    local removePiece, outline = C.removePiece, C.outline

    local SETTLE = 0.12           -- a new held piece waits this long before its preview spawns (fast scrolling)
    local STICK = 0.35            -- a snapped slot holds until the aim is this much closer to another (m)

    -- Placement works like Fallout 4's workshop: the held piece is centred on the crosshair, standing on what it meets. Snap placement (the default):
    -- Fallout's pieces point to point, kit pieces to slots on the 3 m grid, everything else to a 0.5 m grid and quarter turns. Free placement (Q) holds
    -- it on the crosshair's line at any turn, the wheel's distance out, through anything. Aimed past the border or at the sky, it stops at the furthest fitting spot.
    local SNAP = 0.5

    -- Is a world hit floor-like? Our pieces have exact normals. The game's hit normal isn't trusted: a short ray straight
    -- down from just above the hit that lands on the same spot means there is something to stand on there. (Kept on
    local function floorLike(a)
        if a.piece then return a.normal[3] >= 0.6 end
        if a.floor == nil then
            local d = cast({ x = a.point.x, y = a.point.y, z = a.point.z + 0.3 }, { x = 0, y = 0, z = -1 }, 0.6)
            a.floor = d.point ~= nil and math.abs(d.point.z - a.point.z) < 0.08
        end
        return a.floor
    end

    -- The aim: { eye, dir, hit, p = where the crosshair meets the world (or the far end of the reach), surface = p is
    -- something to stand on, wall = the XY normal when p is on the side of one of our pieces, sky = nothing was hit }
    local function aimAt()
        local eye, dir = view()
        local reach = S.dist or REACH
        local a = cast(eye, dir, reach)
        local r = { eye = eye, dir = dir, hit = a }
        if a.point and floorLike(a) then
            r.p, r.surface = a.point, true
        elseif a.point then
            r.p = { x = a.point.x - dir.x * 0.05, y = a.point.y - dir.y * 0.05, z = a.point.z }
            if a.piece then
                local nl = math.max(math.sqrt(a.normal[1] ^ 2 + a.normal[2] ^ 2), 1e-6)
                r.wall = { a.normal[1] / nl, a.normal[2] / nl }
            end
        else
            r.p, r.sky = { x = eye.x + dir.x * reach, y = eye.y + dir.y * reach, z = eye.z + dir.z * reach }, true
        end
        return r
    end

    local function fits(it, o, yaw)
        for _, w in ipairs(corners(it, o, yaw)) do if not inZone(w.x, w.y) then return false end end
        return true
    end

    -- the furthest point from `from` toward `to` (XY) where ok(point) holds: `to` itself when it does, else found by
    -- bisection along the line. Returns the point and whether it was pulled back; nil when nothing on the line will do.
    local function clampAlong(from, to, ok)
        if ok(to) then return to, false end
        if not ok(from) then return nil, true end
        local lo, hi = 0, 1
        for _ = 1, 16 do
            local m = (lo + hi) / 2
            if ok({ x = from.x + (to.x - from.x) * m, y = from.y + (to.y - from.y) * m }) then lo = m else hi = m end
        end
        return { x = from.x + (to.x - from.x) * lo, y = from.y + (to.y - from.y) * lo }, true
    end

    local function inside(r)
        if inZone(r.eye.x, r.eye.y) then return { x = r.eye.x, y = r.eye.y } end
        return S.zone
    end

    -- the highest ground or floor under a footprint (its centre and corners), from rays cast down from height `from`:
    -- a piece stands on the tallest thing under it within half a metre of the aim, so it never sinks in on a slope
    local standZ
    do
        local DOWN, FROM = { x = 0, y = 0, z = -1 }, {}
        local function topAt(x, y, from, z)
            FROM.x, FROM.y, FROM.z = x, y, from
            local d = cast(FROM, DOWN, 80)
            if d.point then return z and math.max(z, d.point.z) or d.point.z end
            return z
        end
        function standZ(it, at, yaw, from)
            local o, a, lo, hi = originFromAnchor(it, { x = at.x, y = at.y, z = 0 }, yaw), axes(yaw), it.min, it.max
            local z = topAt(o.x + a[1] * lo[1] + a[3] * lo[2], o.y + a[2] * lo[1] + a[4] * lo[2], from, nil)
            z = topAt(o.x + a[1] * hi[1] + a[3] * lo[2], o.y + a[2] * hi[1] + a[4] * lo[2], from, z)
            z = topAt(o.x + a[1] * hi[1] + a[3] * hi[2], o.y + a[2] * hi[1] + a[4] * hi[2], from, z)
            z = topAt(o.x + a[1] * lo[1] + a[3] * hi[2], o.y + a[2] * lo[1] + a[4] * hi[2], from, z)
            return topAt(at.x, at.y, from, z)
        end
    end

    local function snapXY(q)
        return { x = S.zone.x + math.floor((q.x - S.zone.x) / SNAP + 0.5) * SNAP, y = S.zone.y + math.floor((q.y - S.zone.y) / SNAP + 0.5) * SNAP }
    end

    -- Anything that isn't a kit piece in grid mode: the spot is on the crosshair's line (Fallout 4): where it meets the world, or held at arm's
    -- length (5-15 m by size) when it meets nothing, pulled back along the line until the piece fits inside the zone. Free mode never goes below the
    -- terrain unless the wheel lowers it. A building is held out in front, far enough to be seen whole (near side 0.6 of its size ahead, 3 m at least).
    local function holdOut(it, r, p)
        if it.kind ~= "prefab" then return p end
        local l = math.sqrt(r.dir.x ^ 2 + r.dir.y ^ 2)
        local big = math.max(it.size[1], it.size[2])
        local want = big / 2 + math.max(3, 0.6 * big)
        if l < 1e-3 or (p.x - r.eye.x) ^ 2 + (p.y - r.eye.y) ^ 2 >= want ^ 2 then return p end
        return { x = r.eye.x + r.dir.x / l * want, y = r.eye.y + r.dir.y / l * want, z = p.z }
    end

    local function propPlacement(h, it, r, snap)
        local yaw = h.yaw
        local eye, dir = r.eye, r.dir
        local function spot(p) return snap and snapXY(p) or p end
        local function ok(p) local s2 = spot(p); return fits(it, originFromAnchor(it, { x = s2.x, y = s2.y, z = 0 }, yaw), yaw) end
        local c
        if r.wall and snap then
            local ax = axes(yaw)
            local nx, ny = r.wall[1], r.wall[2]
            local depth = math.abs(nx * ax[1] + ny * ax[2]) * it.size[1] / 2 + math.abs(nx * ax[3] + ny * ax[4]) * it.size[2] / 2
            local q = { x = r.hit.point.x + nx * (depth + 0.03), y = r.hit.point.y + ny * (depth + 0.03) }
            local xy = clampAlong(inside(r), q, ok)
            if not xy then return nil, yaw end
            c = { x = xy.x, y = xy.y, z = r.hit.point.z }
        else
            local function on(t) return { x = eye.x + dir.x * t, y = eye.y + dir.y * t, z = eye.z + dir.z * t } end
            local big = math.max(it.size[1], it.size[2], it.size[3])
            local hold = S.dist or math.max(5, math.min(15, 3 + 2 * big))
            local t = r.sky and (dir.z < -0.02 and (S.dist or REACH) or hold) or math.max(r.hit.t - (r.surface and 0 or 0.05), 0)
            if not ok(on(t)) then
                if ok(on(0)) then
                    local lo, hi = 0, t
                    for _ = 1, 16 do local m = (lo + hi) / 2; if ok(on(m)) then lo = m else hi = m end end
                    t = lo
                    c = on(t)
                else
                    local xy = clampAlong(inside(r), on(t), ok)
                    if not xy then return nil, yaw end
                    c = { x = xy.x, y = xy.y, z = on(t).z }
                end
            else
                c = on(t)
            end
            if r.surface and t >= r.hit.t - 1e-6 then c.z = r.hit.point.z end
        end
        if it.kind == "prefab" then
            local q = holdOut(it, r, c)
            q = ok(q) and q or clampAlong(inside(r), q, ok)
            if q then c = { x = q.x, y = q.y, z = c.z } end
        end
        local xy = spot(c)
        local z
        if snap then
            z = standZ(it, xy, yaw, math.min(c.z, eye.z + 1) + 0.5)
        else
            local ok, t = pcall(Eng.terrain, v4(xy.x, xy.y, c.z))
            z = (ok and t and t.w > 0) and math.max(c.z, t.z) or c.z
        end
        if not z then return nil, yaw end
        return originFromAnchor(it, { x = xy.x, y = xy.y, z = z }, yaw), yaw
    end

    local function knownLevel(z)
        local best, bz
        for _, l in pairs(S.levels) do
            for k = -3, 6 do
                local c = l + k * STOREY
                local d = math.abs(c - z)
                if d < 1.5 and (not best or d < best) then best, bz = d, c end
            end
        end
        return bz
    end

    local function yawFacing(nx, ny)
        for y = 0, 270, 90 do
            local a = axes(y)
            if a[3] * nx + a[4] * ny > 0.9 then return y end
        end
        return 0
    end

    -- Kit placement at aim point p (from kitAim): origin, yaw, slot. The slot under p (cell, nearest edge, nearest
    -- corner) takes the piece, with hysteresis against the last one so it doesn't flicker. Pure: S.slot is set by placement.
    local function kitAim(r)
        local eye, dir, a = r.eye, r.dir, r.hit
        local zref = a.point and a.point.z or (eye.z - 1.7)
        if a.piece and a.piece.it.kind and a.normal[3] < 0.7 then
            zref = a.piece.o.z + (a.point.z > a.piece.o.z + 0.6 * STOREY and STOREY or 0)
        end
        local level = knownLevel(zref)
        local plane = level or zref
        local p
        if math.abs(dir.z) > 1e-4 then
            local t = (plane - eye.z) / dir.z
            if t > 0 and t <= REACH then p = { x = eye.x + dir.x * t, y = eye.y + dir.y * t } end
        end
        if not p then p = { x = r.p.x, y = r.p.y } end
        if a.piece and a.normal[3] < 0.7 and a.point then
            p = { x = a.point.x + a.normal[1] * 0.3, y = a.point.y + a.normal[2] * 0.3 }
        end
        return p, level, zref
    end

    local function kitPlacement(h, it, r, p, level, zref)
        local i, j = cellOf(p.x, p.y)
        local x0, y0 = S.zone.x + i * GRID, S.zone.y + j * GRID
        local prev = S.slot and S.slot.key == h.key and S.slot
        local slot
        if it.kind == "floor" then
            local c = { x = x0 + GRID / 2, y = y0 + GRID / 2 }
            if prev and prev.kind == "floor" and math.abs(p.x - prev.c.x) < GRID / 2 + STICK and math.abs(p.y - prev.c.y) < GRID / 2 + STICK then c = prev.c end
            slot = { kind = "floor", c = c }
        elseif it.kind == "post" then
            local c = { x = S.zone.x + math.floor((p.x - S.zone.x) / GRID + 0.5) * GRID, y = S.zone.y + math.floor((p.y - S.zone.y) / GRID + 0.5) * GRID }
            local function d(q) return math.sqrt((p.x - q.x) ^ 2 + (p.y - q.y) ^ 2) end
            if prev and prev.kind == "post" and d(prev.c) < d(c) + STICK then c = prev.c end
            slot = { kind = "post", c = c }
        else
            local u, v = p.x - x0, p.y - y0
            local edges = { { d = v, dir = "x", along = y0 }, { d = GRID - v, dir = "x", along = y0 + GRID },
                            { d = u, dir = "y", along = x0 }, { d = GRID - u, dir = "y", along = x0 + GRID } }
            table.sort(edges, function(e1, e2) return e1.d < e2.d end)
            local e = edges[1]
            local len = math.max(1, math.floor(it.size[1] / GRID + 0.5)) * GRID
            local mid
            if e.dir == "x" then
                local cxm = len > GRID and (S.zone.x + math.floor((p.x - S.zone.x) / GRID + 0.5) * GRID) or (x0 + GRID / 2)
                mid = { x = cxm, y = e.along, tx = 1, ty = 0 }
            else
                local cym = len > GRID and (S.zone.y + math.floor((p.y - S.zone.y) / GRID + 0.5) * GRID) or (y0 + GRID / 2)
                mid = { x = e.along, y = cym, tx = 0, ty = 1 }
            end
            if prev and prev.kind == "wall" then
                local function dseg(m) local dx, dy = p.x - m.x, p.y - m.y; local along = math.abs(dx * m.tx + dy * m.ty); return math.abs(dx * m.ty - dy * m.tx) + math.max(0, along - len / 2) end
                if (prev.mid.x ~= mid.x or prev.mid.y ~= mid.y) and dseg(prev.mid) < dseg(mid) + STICK then mid = prev.mid end
            end
            slot = { kind = "wall", mid = mid }
        end
        slot.key = h.key
        local z = level
        if not z then
            local pts = slot.kind == "floor" and { { slot.c.x - 1.4, slot.c.y - 1.4 }, { slot.c.x + 1.4, slot.c.y - 1.4 }, { slot.c.x - 1.4, slot.c.y + 1.4 }, { slot.c.x + 1.4, slot.c.y + 1.4 }, { slot.c.x, slot.c.y } }
                or slot.kind == "post" and { { slot.c.x, slot.c.y } }
                or { { slot.mid.x, slot.mid.y }, { slot.mid.x - slot.mid.tx * 1.4, slot.mid.y - slot.mid.ty * 1.4 }, { slot.mid.x + slot.mid.tx * 1.4, slot.mid.y + slot.mid.ty * 1.4 } }
            for _, q in ipairs(pts) do
                local g = groundZ(q[1], q[2], zref + 3)
                z = z and math.max(z, g) or g
            end
            z = z + 0.02
        end
        if slot.kind == "floor" or slot.kind == "post" then
            return originAt({ x = slot.c.x, y = slot.c.y, z = z }, h.yaw, it.cx, it.cy), h.yaw, slot
        end
        local m = slot.mid
        local nx, ny = m.ty, -m.tx
        local ah = axes(h.yaw)
        local out = (ah[3] * nx + ah[4] * ny) >= 0 and 1 or -1
        if h.flip then out = -out end
        local yaw = yawFacing(nx * out, ny * out)
        return originAt({ x = m.x, y = m.y, z = z }, yaw, it.cx, it.face), yaw, slot
    end

    -- road pieces (grid mode): the origin snaps to a 1 m grid, then latches end to end onto a road piece already built at
    -- the same turn if one is within LATCH of that (their lengths run along X: the held piece's end meets the other's).
    -- On the ground, clamped into the zone like the rest.
    local ROAD_SNAP, LATCH = 1.0, 2.0
    local function roadPlacement(h, it, r)
        local yaw = h.yaw
        local a = axes(yaw)
        local function want(p) return originAt(p, yaw, it.cx, it.cy) end
        local function snapped(p)
            local o = want(p)
            return { x = S.zone.x + math.floor((o.x - S.zone.x) / ROAD_SNAP + 0.5) * ROAD_SNAP, y = S.zone.y + math.floor((o.y - S.zone.y) / ROAD_SNAP + 0.5) * ROAD_SNAP, z = 0 }
        end
        local p0 = holdOut(it, r, (kitAim(r)))
        local p = clampAlong(inside(r), p0, function(q) return fits(it, snapped(q), yaw) end) or p0
        local o = snapped(p)
        local free, best = want(p), LATCH
        for _, q in ipairs(S.pieces) do
            if it.kind == "road" and q.it.kind == "road" and (q.yaw - yaw) % 360 < 0.5 then
                for _, dx in ipairs({ q.it.min[1] - it.max[1], q.it.max[1] - it.min[1] }) do
                    local c = { x = q.o.x + a[1] * dx, y = q.o.y + a[2] * dx, z = 0 }
                    local d = math.sqrt((c.x - free.x) ^ 2 + (c.y - free.y) ^ 2)
                    if d < best and fits(it, c, yaw) then best, o = d, c end
                end
            end
        end
        local c = local2world(o, yaw, it.cx, it.cy)
        local z = standZ(it, c, yaw, math.min(r.p.z, r.eye.z) + 0.5) or S.zone.z
        o.z = z - it.base[3] + 0.01
        return o, yaw
    end

    -- free placement: the piece hovers in the middle of the view, at a distance its size asks for (or the wheel's); it
    -- knows nothing of the ground or other pieces (it may go into them)
    local function holdDistance(it) return S.dist or math.max(3, math.min(25, 2 + 1.2 * math.max(it.size[1], it.size[2], it.size[3]))) end
    local function centred(it, c, yaw) return originAt(c, yaw, it.cx, it.cy, (it.min[3] + it.max[3]) / 2) end
    local function hoverPlacement(h, it, r)
        local d = holdDistance(it)
        return centred(it, { x = r.eye.x + r.dir.x * d, y = r.eye.y + r.dir.y * d, z = r.eye.z + r.dir.z * d }, h.yaw), h.yaw
    end

    -- Fallout 4 pieces are held and snap as Fallout4.exe does it, every frame anew. Held: the piece's middle on the view line, twice its bounds'
    -- radius out (300 units at least, 1024 at most), turned with the view. Dropped: its base onto what is under its footprint when within 70 units
    -- below it, or above it by any amount. Snapped: each of its points on screen asks for built points on screen within 1.414 x its radius (catalog
    -- snapR, WorkshopSnapPointRadius; else 48 units) whose names pair; the nearest pair wins and the piece is turned to fit it. Equally near ones
    -- with another name: the rotate keys step through them. A snapped pose in something's way is no snap. 75 points or more: never snaps by itself.
    local fo4Placement, holdDepth
    do                                                            -- (its helpers in here: the main chunk is at LuaJIT's 200 locals)
        local SNAP_QUERY, SNAP_JOIN = 48 * U, 8 * U                  -- (WouldBeSnappedDistance: 8 units, two points as one)
        local DROP, CAST, STEP = 70 * U, 128 * U, 10 * U             -- (fDropModeCastDist 1.0 x 70 units; the cast's reach; the
        local SCREEN, HOLD_MAX = 32 * U, 1024 * U                    -- drop's on-screen test from 10 units; fPointInFrustumRadius)
        local SHRINK, TARGET_ONLY = 8 * U, 75                        -- (fWorkshopSnapIntersectAdjust; uWorkshopSnapTargetOnlyThreshold)
        local pivotOf, screenInfo = C.pivotOf, C.screenInfo
        local FROM, DOWN = {}, { x = 0, y = 0, z = -1 }
        local function radiusOf(it)
            if not it.rad then it.rad = math.sqrt(it.size[1] ^ 2 + it.size[2] ^ 2 + it.size[3] ^ 2) / 2 end
            return it.rad
        end
        function holdDepth(it) return math.min(math.max(300 * U, 2 * radiusOf(it)), HOLD_MAX) end
        local function onScreen(r, x, y, z)
            local W, H, fov = screenInfo()
            local d, vx, vy, vz = r.dir, x - r.eye.x, y - r.eye.y, z - r.eye.z
            local depth, l = vx * d.x + vy * d.y + vz * d.z, math.sqrt(d.x * d.x + d.y * d.y)
            if depth < -SCREEN then return false end
            local rx, ry = 1, 0
            if l > 1e-6 then rx, ry = d.y / l, -d.x / l end
            local tv = math.tan(math.rad(fov) / 2)
            local th = tv * W / H
            return math.abs(vx * rx + vy * ry) <= depth * th + SCREEN * math.sqrt(1 + th * th)
                and math.abs(vx * ry * d.z - vy * rx * d.z + vz * (rx * d.y - ry * d.x)) <= depth * tv + SCREEN * math.sqrt(1 + tv * tv)
        end
        local function heldPose(h, it, r)
            local d = math.min(math.max(S.dist or 0, holdDepth(it)), HOLD_MAX)
            local v, c = pivotOf(it), { x = r.eye.x + r.dir.x * d, y = r.eye.y + r.dir.y * d, z = r.eye.z + r.dir.z * d }
            local o = originAt(c, h.yaw, v[1], v[2], (it.min[3] + it.max[3]) / 2)
            local b, sink = o.z + it.base[3], (it.sink or 0) > 0
            -- Fallout casts the piece's shape down from its lower 128 units' top and stands it on what that meets. With rays: what is under its middle
            -- lifts it, else what is under its footprint from its base down. A P-WS-SinkMax piece (a foundation; Fallout4.exe 0x140391d2c, 0x1403b9e80): its
            -- cast ends at its base; with its base in the terrain by no more than its SinkMax it stays as held, deeper or in a built piece its base goes onto that.
            FROM.x, FROM.y, FROM.z = c.x, c.y, math.max(b + math.min(it.size[3], CAST), r.eye.z)
            local d0 = cast(FROM, DOWN, 80)
            local z = d0.point and d0.point.z > b and d0.point.z or nil
            if sink then
                if not z then return o end
                if not d0.piece then                           -- in the terrain: as held down to its SinkMax, no deeper
                    if z - b <= it.sink then return o end
                    z = z - it.sink
                end
            elseif not z then
                z = standZ(it, c, h.yaw, b + 0.05)
            end
            if not z or b - z > DROP then return o end
            if math.abs(z - b) >= STEP and not onScreen(r, o.x, o.y, z - it.base[3]) then return o end
            o.z = z - it.base[3]
            return o
        end
        local function at3(o, yaw, c)
            local a = axes(yaw)
            return o.x + a[1] * c.x + a[3] * c.y, o.y + a[2] * c.x + a[4] * c.y, o.z + (c.z or 0)
        end
        local function within(p, x, y, z, r)
            local a, dx, dy, lo, hi = axes(p.yaw), x - p.o.x, y - p.o.y, p.it.min, p.it.max
            local lx, ly, lz = dx * a[1] + dy * a[2], dx * a[3] + dy * a[4], z - p.o.z
            local ex = math.max(lo[1] - lx, 0, lx - hi[1])
            local ey = math.max(lo[2] - ly, 0, ly - hi[2])
            local ez = math.max(lo[3] - lz, 0, lz - hi[3])
            return ex * ex + ey * ey + ez * ez <= r * r
        end
        local NA, NB, TI, TB, BOX, VLO, VHI, NB_NONE = {}, {}, {}, {}, {}, {}, {}, {}
        function fo4Placement(h, it, r, o0, yaw0)
            if not o0 then o0, yaw0 = heldPose(h, it, r), h.yaw end
            local mine = Grid.snaps(it)
            local function none(why) S.snapped, S.joined, S.snapAt, S.ties, S.snapWhy = false, false, nil, 0, why return o0, yaw0 end
            if #mine == 0 or #mine >= TARGET_ONLY then return none("no points of its own to snap with") end
            local function taken(hc, b)
                if b.piece.it.ignoreOcc then return false end
                for k = 1, Grid.near(b.x, b.y, b.z, 4 * U, NB) do
                    if NB[k] ~= b and NB[k].c.name == hc.name then return true end
                end
                return false
            end
            local rad = it.snapR or SNAP_QUERY
            local bi, bb, bd, nt = nil, nil, math.huge, 0
            for _, hc in ipairs(mine) do
                local x, y, z = at3(o0, yaw0, hc)
                if onScreen(r, x, y, z) then
                    for k = 1, Grid.near(x, y, z, rad * 1.41421356, NA) do
                        local b = NA[k]
                        if pairs_(hc, b.c) and onScreen(r, b.x, b.y, b.z) and within(b.piece, x, y, z, rad) and not taken(hc, b) then
                            local d = math.floor(math.sqrt((b.x - x) ^ 2 + (b.y - y) ^ 2 + (b.z - z) ^ 2) * 1e4 + 0.5)
                            if d < bd then
                                bi, bb, bd, nt = hc, b, d, 0
                            elseif d == bd and b.c.name ~= bb.c.name then
                                local new = true
                                for t = 1, nt do if TB[t].c.name == b.c.name then new = false break end end
                                if new then nt = nt + 1; TI[nt], TB[nt] = hc, b end
                            end
                        end
                    end
                end
            end
            if not bb then return none("no pairing point in reach") end
            if (S.tie or 0) > nt then S.tie = 0 end
            local hc, b = bi, bb
            if (S.tie or 0) > 0 then hc, b = TI[S.tie], TB[S.tie] end
            local yaw = (b.yaw + 180 - hc.yaw) % 360
            local o = originAt(b, yaw, hc.x, hc.y, hc.z)
            local by = {}
            for _, c in ipairs(mine) do
                local x, y, z = at3(o, yaw, c)
                for k = 1, Grid.near(x, y, z, SNAP_JOIN, NB) do by[NB[k].piece] = true end
            end
            if not it.must and not it.mount then
                local v, lo, hi = it.vbox or NB_NONE, VLO, VHI
                lo[1], lo[2], lo[3], hi[1], hi[2], hi[3] = it.min[1], it.min[2], it.min[3] + math.max(it.sink or 0, 0), it.max[1], it.max[2], it.max[3]
                if v.xy then lo[1], lo[2], hi[1], hi[2] = -v.xy / 2, -v.xy / 2, v.xy / 2, v.xy / 2
                else lo[1], hi[1], lo[2], hi[2] = v.x0 or lo[1], v.x1 or hi[1], v.y0 or lo[2], v.y1 or hi[2] end
                lo[3], hi[3] = v.z0 or lo[3], v.z1 or hi[3]
                for k = 1, 3 do
                    local half = (hi[k] - lo[k]) / 2
                    BOX[k], BOX[k + 3] = (hi[k] + lo[k]) / 2, half - (half > SHRINK and SHRINK or 0.4 * half)
                end
                local q = blockedBy(it, o, yaw, by, 0, BOX)
                if q then return none("snap in the way of " .. q.it.name) end
            end
            S.snapped, S.joined, S.snapAt, S.ties = b.piece, by, b, nt + 1
            return o, yaw
        end
    end

    -- the snap points on screen (Settings "Show snap points"): built ones within 6 m of the held piece as small crosses
    -- (cyan; the one it snaps to yellow), the held piece's own green; not occluded - a point behind a wall shows too
    local function snapDots(it, o, yaw)
        local c, segs = Gizmo.cam(), {}
        local function dot(w, col, s)
            local u, v = Gizmo.project(c, w)
            if not u or u < 0 or u > 1 or v < 0 or v > 1 then return end
            local n = #segs
            segs[n + 1], segs[n + 2], segs[n + 3], segs[n + 4], segs[n + 5], segs[n + 6] = u - s, v, u + s, v, col, 5
            segs[n + 7], segs[n + 8], segs[n + 9], segs[n + 10], segs[n + 11], segs[n + 12] = u, v - s * c.aspect, u, v + s * c.aspect, col, 5
        end
        local at = S.snapAt
        Grid.points(o.x, o.y, 6, function(b) dot(b, b == at and 3 or 5, 0.004) end)
        for _, cc in ipairs(Grid.snaps(it)) do dot(local2world(o, yaw, cc.x, cc.y, cc.z), 1, 0.003) end
        return segs
    end

    -- Fallout pieces without snap points (decorations, furniture, crops): on what the crosshair is on, as in Fallout.
    -- One with an autoplace point (catalog `mount`: posters, signs, paintings, lettering; hanging lights) sticks to the
    -- wall - or ceiling - under the crosshair: that point on the face, its +Y into it, so the piece lies flat against it
    -- facing out. Anything else stands on the surface under the crosshair: the ground, a table, a rug, a statue's plinth.
    -- Aimed at nothing within reach: held at free placement's distance, on what is under that spot.
    local function surfacePlacement(h, it, r)
        local a, m = r.hit, it.mount
        if it.lie then h.q = nil end
        S.snapped = a.piece or false
        if a.point then
            local n = a.normal
            if m and m.kind == "wall" and math.abs(n[3]) < 0.5 then
                local want = math.deg(atan2(-n[2], -n[1]))
                local yaw = (want - m.dir) % 360
                local p = { x = a.point.x + n[1] * 0.005, y = a.point.y + n[2] * 0.005, z = a.point.z }
                return originAt(p, yaw, m.x, m.y, m.z), yaw
            elseif m and m.kind == "ceiling" and n[3] < -0.7 then
                return originAt({ x = a.point.x, y = a.point.y, z = a.point.z - 0.005 }, h.yaw, m.x, m.y, m.z), h.yaw
            elseif floorLike(a) and it.lie then
                local z = standZ(it, a.point, h.yaw, a.point.z + 0.3) or a.point.z
                h.q = Q.norm(Q.mul(Q.yaw(h.yaw), Q.axis(0, 1, 0, 90)))
                local o = originFromAnchor(it, { x = a.point.x, y = a.point.y, z = 0 }, h.yaw)
                o.z = math.max(z, a.point.z) + it.max[1] + 0.005
                return o, h.yaw
            elseif floorLike(a) then
                local z = standZ(it, a.point, h.yaw, a.point.z + math.max(0.3, it.size[3]))
                return originFromAnchor(it, { x = a.point.x, y = a.point.y, z = math.max(z or a.point.z, a.point.z) }, h.yaw), h.yaw
            end
        end
        S.snapped = false
        if r.surface then return originFromAnchor(it, r.p, h.yaw), h.yaw end
        local d = holdDistance(it)
        if a.point then
            local z = standZ(it, r.p, h.yaw, r.p.z + 0.5) or r.p.z
            return originFromAnchor(it, { x = r.p.x, y = r.p.y, z = z }, h.yaw), h.yaw
        end
        return centred(it, { x = r.eye.x + r.dir.x * d, y = r.eye.y + r.dir.y * d, z = r.eye.z + r.dir.z * d }, h.yaw), h.yaw
    end

    local function placement()
        local h = S.hold
        local it = byKey[h.key]
        if S.gz then
            local yaw = Q.yawOf(h.q)
            S.placeKey = h.key
            if not fits(it, S.gz.o, yaw) then return S.gz.o, yaw, false, "Outside the zone" end
            if h.kind == "new" and S.cost + it.cost > BUDGET and C.Settings.on("buildLimit") then return S.gz.o, yaw, false, "Too big: over the zone's size limit" end
            return S.gz.o, yaw, true
        end
        if it.fo4 and not S.free then
            local _, dir = view()
            local cy = math.deg(atan2(dir.y, dir.x))
            if S.camFor == h and S.camYaw then h.yaw = (h.yaw + cy - S.camYaw) % 360 end
            S.camFor, S.camYaw = h, cy
        else
            S.camFor = nil
        end
        local r = timed("aimat", aimAt)
        local o, yaw, q
        S.joined = false
        if S.free then
            o, yaw = hoverPlacement(h, it, r)
        elseif it.connect then
            local wo, wyaw
            if it.mount then wo, wyaw = timed("surface", surfacePlacement, h, it, r) end
            local wall = S.snapped
            o, yaw, q = timed("snap", fo4Placement, h, it, r, wo, wyaw)
            if not S.snapped and it.mount then S.snapped = wall end
        elseif it.fo4 or (not it.kind and not it.npc) then
            o, yaw = timed("surface", surfacePlacement, h, it, r)
        elseif (it.kind == "road" or it.kind == "prefab") then
            o, yaw = roadPlacement(h, it, r)
        elseif it.kind then
            local p0, level, zref = kitAim(r)
            local slot
            local function ok(p) local o2, y2 = kitPlacement(h, it, r, p, level, zref); return fits(it, o2, y2) end
            local p = clampAlong(inside(r), p0, ok) or p0
            o, yaw, slot = kitPlacement(h, it, r, p, level, zref)
            S.slot = slot
        else
            o, yaw = propPlacement(h, it, r, not S.free)
        end
        if not o then return nil, yaw, false, "Nothing to place it on" end
        local key = h.key
        if it.upper and not S.free then
            local low
            for _, z in pairs(S.levels) do low = low and math.min(low, z) or z end
            if low and o.z > low + STOREY / 2 then key = it.upper; it = byKey[key] end
        end
        S.placeKey = key
        if not fits(it, o, yaw) then return o, yaw, false, "Outside the zone" end
        if it.must and not S.free and not S.joined then return o, yaw, false, "Must be snapped" end   -- (doors: Fallout's
                                                                 -- WorkshopMustBeSnapped; free placement goes anywhere)
        if it.fo4 and not S.free and not S.joined then
            q = timed("blocked", blockedBy, it, o, yaw, S.snapped and { [S.snapped] = true })
        end
        if q then return o, yaw, false, "Blocked by " .. q.it.name end
        if it.kind and not S.free then
            for _, k in ipairs(slotsOf(it, o, yaw)) do
                if S.occupied[k] then return o, yaw, false, "Already built here" end
            end
        end
        if h.kind == "new" and S.cost + it.cost > BUDGET and C.Settings.on("buildLimit") then return o, yaw, false, "Too big: over the zone's size limit" end
        return o, yaw, true
    end

    local function finishOf(key, app)
        for _, a in ipairs(byKey[key].apps) do if a == app then return app end end
        return byKey[key].apps[1]
    end

    -- the held piece's preview entity (no colliders). It is moved with the teleportation facility: writing the entity's
    -- transform moves the entity but not what is drawn, so the preview stayed where it spawned.
    local function dropGhost()
        if S.ghost then
            for _, id in ipairs(S.ghost.ids) do del(id) end
            for _, c in ipairs(S.ghost.carry or {}) do for _, id in ipairs(c.ids) do del(id) end end
        end
        S.ghost = nil
    end

    local function carriedAt(c, o, yaw)
        local w = local2world(o, yaw, c.lx, c.ly, c.dz)
        local q = c.q and Q.norm(Q.mul(Q.yaw(yaw - c.yaw0), c.q)) or nil
        return w, (yaw + c.dyaw) % 360, q
    end

    -- A preview is made only once what it shows has stayed the same SETTLE seconds: scrolling the menu, or aiming
    -- across a storey's height (the upper twin and back, a frame apart), makes none and deletes none on the way
    local function syncGhost(o, yaw, valid, dt)
        local h = S.hold
        if not h or not o then dropGhost() return end
        local key = S.placeKey or h.key
        local app = finishOf(key, h.app)
        local want = key .. "|" .. app
        if h.want ~= want then h.t, h.want = h.want and 0 or h.t, want end
        if not S.ghost or S.ghost.key ~= key or S.ghost.app ~= app then
            h.t = (h.t or SETTLE) + dt
            if h.t < SETTLE then dropGhost() return end
            dropGhost()
            local main, ids = spawnPiece(key, app, o, yaw, true, h.q)
            S.ghost = { id = main, ids = ids, key = key, app = app, t = 0, o = o, yaw = yaw, carry = {} }
            for _, c in ipairs(h.carry or {}) do
                local w, cy, cq = carriedAt(c, o, yaw)
                local _, cids = spawnPiece(c.key, c.app, w, cy, true, cq)
                table.insert(S.ghost.carry, { ids = cids, c = c })
            end
        end
        local g = S.ghost
        local e = des():GetEntity(g.id)
        if e then
            if g.yaw ~= yaw or g.q ~= h.q or g.o.x ~= o.x or g.o.y ~= o.y or g.o.z ~= o.z or not g.placed then
                local all = true
                local function move(id, w, turn)
                    local pe = des():GetEntity(id)
                    all = (pe and Eng.teleport(pe, v4(w.x, w.y, w.z), turn)) and all
                end
                for _, id in ipairs(g.ids) do move(id, o, Q.toEuler(h.q, yaw)) end
                for _, gc in ipairs(g.carry or {}) do
                    local w, cy, cq = carriedAt(gc.c, o, yaw)
                    for _, id in ipairs(gc.ids) do move(id, w, Q.toEuler(cq, cy)) end
                end
                if all then g.o, g.yaw, g.q, g.placed = o, yaw, h.q, true end
            end
            g.t = g.t - dt
            local want = valid and OUTLINE.valid or OUTLINE.invalid
            if g.outline ~= want or g.t <= 0 then
                g.outline, g.t = want, 0.5
                for _, id in ipairs(g.ids) do outline(id, want) end
                for _, gc in ipairs(g.carry or {}) do for _, id in ipairs(gc.ids) do outline(id, want) end end
            end
        end
    end

    local function restore()
        local o = S.hold and S.hold.orig
        if o then
            local id = spawnPiece(o.key, o.app, o.o, o.yaw, false, o.q); sfx(SFX.back)
            if o.id then Life.rejob(hashOf(o.id), hashOf(id)) end
        end
        for _, c in ipairs(S.hold and S.hold.carry or {}) do spawnPiece(c.key, c.app, c.o0, c.yaw0c, false, c.q) end
        S.hold, S.rot = nil, 0
        C.index()
    end

    local function place(keepGizmo)
        local h = S.hold
        if not h then return end
        local o, yaw, ok, why = placement()
        if not ok then say(why); sfx(SFX.refuse) return end
        local key = S.placeKey or h.key
        local id, _, piece = spawnPiece(key, finishOf(key, h.app), o, yaw, false, h.q)
        if h.kind == "move" and h.orig.id then Life.rejob(hashOf(h.orig.id), hashOf(id)) end
        for _, c in ipairs(h.carry or {}) do local w, cy, cq = carriedAt(c, o, yaw); spawnPiece(c.key, c.app, w, cy, false, cq) end
        sfx((byKey[h.key].kind and not S.free) and SFX.build or SFX.drop)
        if not keepGizmo then Gizmo.off() end
        if h.kind == "move" then S.hold, S.rot = nil, 0 end
        C.index()
        return piece
    end

    local function startMove(p)
        if not C.ready(p) then return false end
        local carry, a = {}, axes(p.yaw)
        for _, d in ipairs(C.heldUpOnlyBy(p)) do
            local dx, dy = d.o.x - p.o.x, d.o.y - p.o.y
            carry[#carry + 1] = { key = d.key, app = d.app, q = d.q, lx = dx * a[1] + dy * a[2], ly = dx * a[3] + dy * a[4],
                                  dz = d.o.z - p.o.z, dyaw = d.yaw - p.yaw, yaw0 = p.yaw, o0 = d.o, yaw0c = d.yaw }
            removePiece(d)
        end
        removePiece(p)
        sfx(SFX.grab)
        S.hold = { kind = "move", key = p.key, app = p.app, yaw = p.yaw, q = p.q, flip = false, carry = carry, orig = { key = p.key, app = p.app, o = p.o, yaw = p.yaw, q = p.q, id = p.id } }
        S.target, S.slot, S.dist = nil, nil, nil
        C.index()
        return true
    end

    -- Ctrl edit (the gizmo on a placed piece): a handle let go or the wheel turned stands at once, no E: the piece is placed where the gizmo has
    -- it, the gizmo staying put with nothing held; the next grab or wheel notch takes it up again (gizmoPickup), and Tab puts it back only to the
    -- last change. A piece newly picked from the menu (or being turned, held) still takes E.
    local function gizmoApply()
        local h, g = S.hold, S.gz
        if not (h and h.kind == "move" and g) then return end
        local _, _, ok = placement()
        if not ok then return end
        g.piece = place(true)
        if not g.piece then Gizmo.off() return end
        g.o = g.piece.o
    end

    local function gizmoPickup(p)
        local cur = S.byId[hashOf(p.id)]
        if not (cur and startMove(cur)) then return false end
        S.free = true
        S.hold.q = S.hold.q or Q.yaw(S.hold.yaw)
        return true
    end

    local function scrap()
        local h = S.hold
        local deps = {}
        if h and h.kind == "move" then
            if h.key == "workbench" then say("The workbench can't be scrapped"); sfx(SFX.refuse) return end
            deps = h.carry or {}
            S.hold, S.rot = nil, 0
        elseif S.target then
            if S.target.bench then say("The workbench can't be scrapped"); sfx(SFX.refuse) return end
            deps = C.heldUpOnlyBy(S.target)
            removePiece(S.target)
            S.target = nil
        else return end
        for _, p in ipairs(deps) do if p.id then removePiece(p) end end
        say(#deps > 0 and string.format("Scrapped, and %d piece%s it held up", #deps, #deps > 1 and "s" or "") or "Scrapped")
        sfx(SFX.scrap)
        C.index()
    end

    C.placement, C.aimAt, C.holdDistance, C.snapDots, C.dropGhost, C.holdDepth = placement, aimAt, holdDistance, snapDots, dropGhost, holdDepth
    C.syncGhost, C.carriedAt, C.finishOf, C.restore, C.place = syncGhost, carriedAt, finishOf, restore, place
    C.startMove, C.gizmoApply, C.gizmoPickup, C.scrap = startMove, gizmoApply, gizmoPickup, scrap
end
