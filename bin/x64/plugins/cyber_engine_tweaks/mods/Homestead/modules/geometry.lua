-- Geometry: turns (axes, quaternions Q), a piece's space and the world's, the zone's grid of slots and its circle,
-- where the pieces are (Grid: by 8 m cell, and their snap points by 2 m cell), rays against the world and our boxes
-- (cast: the game's ray, then our pieces' boxes near the line), the camera (view, read once a frame), and box overlap
-- (blockedBy). Nothing here changes the world; it asks the game for rays and the camera only.
return function(C)
    local S, Eng, atan2, v4 = C.S, C.Eng, C.atan2, C.v4
    local GRID, REACH, RADIUS = C.GRID, C.REACH, C.RADIUS

    -- world XY of the rotated mesh X and Y axes: the engine's turn, counter-clockwise about +Z (checked in game), worked
    -- out here - asking the game cost three calls per new angle, and a smoothly turning piece makes one every frame.
    local axesCache, axesN = {}, 0
    local function axes(yaw)
        local a = axesCache[yaw]
        if not a then
            local r = math.rad(yaw)
            local c, s = math.cos(r), math.sin(r)
            a = { c, s, -s, c }
            if axesN > 4096 then axesCache, axesN = {}, 0 end
            axesCache[yaw], axesN = a, axesN + 1
        end
        return a
    end

    local Q = {}
    -- full orientations (the gizmo tilts pieces): quaternions {i, j, k, r}, turning counter-clockwise about +Z as yaw does.
    -- A piece keeps its yaw for everything else (footprints, snapping, overlap); q, when set, is how it really stands.
    function Q.mul(a, b)
        return { i = a.r * b.i + a.i * b.r + a.j * b.k - a.k * b.j, j = a.r * b.j - a.i * b.k + a.j * b.r + a.k * b.i,
                 k = a.r * b.k + a.i * b.j - a.j * b.i + a.k * b.r, r = a.r * b.r - a.i * b.i - a.j * b.j - a.k * b.k }
    end
    function Q.axis(ax, ay, az, deg) local h = math.rad(deg) / 2; local s = math.sin(h) return { i = ax * s, j = ay * s, k = az * s, r = math.cos(h) } end
    function Q.rot(q, x, y, z)
        local tx, ty, tz = 2 * (q.j * z - q.k * y), 2 * (q.k * x - q.i * z), 2 * (q.i * y - q.j * x)
        return x + q.r * tx + (q.j * tz - q.k * ty), y + q.r * ty + (q.k * tx - q.i * tz), z + q.r * tz + (q.i * ty - q.j * tx)
    end
    function Q.yaw(yaw) return Q.axis(0, 0, 1, yaw) end
    function Q.yawOf(q) local x, y = Q.rot(q, 1, 0, 0) return math.deg(atan2(y, x)) % 360 end
    function Q.norm(q) local n = math.sqrt(q.i ^ 2 + q.j ^ 2 + q.k ^ 2 + q.r ^ 2) return { i = q.i / n, j = q.j / n, k = q.k / n, r = q.r / n } end
    function Q.tilted(q) local _, _, z = Q.rot(q, 0, 0, 1) return z < 0.99995 end
    function Q.toQuat(q, yaw) return q and Quaternion.new(q.i, q.j, q.k, q.r) or EulerAngles.new(0, 0, yaw):ToQuat() end
    function Q.square(yaw) return math.floor(yaw / 90 + 0.5) * 90 % 360 end
    function Q.toEuler(q, yaw) return q and GetSingleton("Quaternion"):ToEulerAngles(Quaternion.new(q.i, q.j, q.k, q.r)) or EulerAngles.new(0, 0, yaw) end

    local function local2world(o, yaw, lx, ly, lz)
        local a = axes(yaw)
        return { x = o.x + a[1] * lx + a[3] * ly, y = o.y + a[2] * lx + a[4] * ly, z = o.z + (lz or 0) }
    end

    local function originAt(at, yaw, lx, ly, lz)
        local a = axes(yaw)
        return { x = at.x - a[1] * lx - a[3] * ly, y = at.y - a[2] * lx - a[4] * ly, z = (at.z or 0) - (lz or 0) }
    end

    -- where a piece is held and stands: its middle (Fallout's P-WS-Rotation where it has one - what it turns about) at
    -- the height of its ground contact; so a held piece turns in place, never round a corner its model's origin sits at
    local function pivotOf(it) return it.pivot or { it.cx, it.cy } end
    local function anchorOf(it, o, yaw) local v = pivotOf(it); return local2world(o, yaw, v[1], v[2], it.base[3]) end
    local function originFromAnchor(it, at, yaw) local v = pivotOf(it); return originAt(at, yaw, v[1], v[2], it.base[3]) end


    local function cellOf(x, y) return math.floor((x - S.zone.x) / GRID), math.floor((y - S.zone.y) / GRID) end
    local function levelKey(z) return math.floor(z * 2 + 0.5) end
    local function slotKey(kind, x, y, z) return string.format("%s:%d:%d:%d", kind, math.floor(x * 2 + 0.5), math.floor(y * 2 + 0.5), levelKey(z)) end

    local function slotsOf(it, o, yaw)
        if it.kind == "road" or it.kind == "prefab" then return {} end
        if it.kind == "floor" then
            local c = local2world(o, yaw, it.cx, it.cy)
            return { slotKey("F", c.x, c.y, o.z) }
        elseif it.kind == "post" then
            local c = local2world(o, yaw, it.cx, it.cy)
            return { slotKey("P", c.x, c.y, o.z) }
        elseif it.kind == "wall" then
            local out, n = {}, math.max(1, math.floor(it.size[1] / GRID + 0.5))
            for k = 1, n do
                local lx = it.min[1] + (k - 0.5) * GRID
                local c = local2world(o, yaw, lx, it.face)
                table.insert(out, slotKey("W", c.x, c.y, o.z))
            end
            return out
        end
        return {}
    end

    -- The zone: the circle of RADIUS round the settlement's centre (always a circle). zoneDist: how far outside it a point is (m; negative inside).
    local function zoneDist(x, y) return math.sqrt((x - S.zone.x) ^ 2 + (y - S.zone.y) ^ 2) - RADIUS end
    local function inZone(x, y) return zoneDist(x, y) <= 0 end


    -- where the pieces are, by 8 m cell (each in every cell its reach touches): rays, overlap checks and snapping
    -- look only at the pieces near what they ask about, not at all of them (a settlement has
    -- hundreds). Rebuilt with the piece list (refresh).
    local Grid = { size = 8 }
    do
        local cells, stamp = {}, 0
        local function key(i, j) return (i + 50000) * 100000 + (j + 50000) end
        local function span(a, b) return math.floor(a / Grid.size), math.floor(b / Grid.size) end
        function Grid.build(pieces)
            cells = {}
            for _, p in ipairs(pieces) do
                local it = p.it
                local r = math.sqrt(it.size[1] ^ 2 + it.size[2] ^ 2) / 2 + math.sqrt(it.cx ^ 2 + it.cy ^ 2)
                local i0, i1 = span(p.o.x - r, p.o.x + r)
                local j0, j1 = span(p.o.y - r, p.o.y + r)
                for i = i0, i1 do for j = j0, j1 do
                    local k = key(i, j)
                    local c = cells[k]
                    if not c then c = {}; cells[k] = c end
                    c[#c + 1] = p
                end end
            end
        end
        function Grid.box(x0, y0, x1, y1)
            stamp = stamp + 1
            local out = {}
            local i0, i1 = span(math.min(x0, x1), math.max(x0, x1))
            local j0, j1 = span(math.min(y0, y1), math.max(y0, y1))
            for i = i0, i1 do for j = j0, j1 do
                local c = cells[key(i, j)]
                if c then for _, p in ipairs(c) do if p.gs ~= stamp then p.gs = stamp; out[#out + 1] = p end end end
            end end
            return out
        end
        function Grid.around(x, y, r) return Grid.box(x - r, y - r, x + r, y + r) end

        -- every built Fallout piece's snap points, in the world, by 2 m cell: a held piece asks only the cells around it
        -- (Fallout asks within 48 units of each of its points) - not every point of every piece near it, every frame
        local pts, PC, NONE = {}, 2, {}
        function Grid.named(c)
            if not c.base then
                local l = c.name:lower()
                local i = l:find("-dif2", 1, true) or l:find("-dif", 1, true)
                c.base, c.dif = i and c.name:sub(1, i - 1) or c.name, i ~= nil
            end
            return c
        end
        function Grid.snaps(it)
            if not it.cps then
                it.cps = {}
                for _, c in ipairs(it.connect or {}) do if not c.name:upper():find("^P%-WS") then it.cps[#it.cps + 1] = Grid.named(c) end end
            end
            return it.cps
        end
        function Grid.buildPoints(pieces)
            pts = {}
            for _, p in ipairs(pieces) do
                for _, c in ipairs(Grid.snaps(p.it)) do
                    local w = local2world(p.o, p.yaw, c.x, c.y, c.z)
                    local k = key(math.floor(w.x / PC), math.floor(w.y / PC))
                    local l = pts[k]
                    if not l then l = {}; pts[k] = l end
                    l[#l + 1] = { x = w.x, y = w.y, z = w.z, yaw = (p.yaw + c.yaw) % 360, c = c, piece = p }
                end
            end
        end
        function Grid.near(x, y, z, r, out)
            local n = 0
            for i = math.floor((x - r) / PC), math.floor((x + r) / PC) do
                for j = math.floor((y - r) / PC), math.floor((y + r) / PC) do
                    for _, b in ipairs(pts[key(i, j)] or NONE) do
                        if (b.x - x) ^ 2 + (b.y - y) ^ 2 <= r * r and (not z or math.abs(b.z - z) <= r
                            and math.sqrt((b.x - x) ^ 2 + (b.y - y) ^ 2 + (b.z - z) ^ 2) <= r) then n = n + 1; out[n] = b end
                    end
                end
            end
            return n
        end
        function Grid.points(x, y, r, f)
            local l = {}
            for k = 1, Grid.near(x, y, nil, r, l) do f(l[k]) end
        end
    end


    -- a turned box ({cx, cy, cz, hx, hy, hz, qi, qj, qk, qr}: Fallout's collision fitted, tools/colliders.py box_of - a
    -- brace, a sloped roof, a stair ramp): its axes in the piece's space (m, three columns) and the axis-aligned box
    -- round it (box), worked out once and kept on it. aabb: that box, or a plain box itself
    local function turn(b)
        local t = b.t
        if t then return t end
        local i, j, k, r = b[7], b[8], b[9], b[10]
        local n = math.sqrt(i * i + j * j + k * k + r * r)
        i, j, k, r = i / n, j / n, k / n, r / n
        local m = { 1 - 2 * (j * j + k * k), 2 * (i * j + k * r), 2 * (i * k - j * r),
                    2 * (i * j - k * r), 1 - 2 * (i * i + k * k), 2 * (j * k + i * r),
                    2 * (i * k + j * r), 2 * (j * k - i * r), 1 - 2 * (i * i + j * j) }
        local box = { b[1], b[2], b[3] }
        for x = 1, 3 do box[x + 3] = b[4] * math.abs(m[x]) + b[5] * math.abs(m[x + 3]) + b[6] * math.abs(m[x + 6]) end
        t = { m = m, box = box }
        b.t = t
        return t
    end
    local function aabb(b) return b[7] and turn(b).box or b end

    -- a ray (unit dir) against one of a piece's boxes (in its space; a turned one in its own frame): where it enters, t,
    -- and the face's world normal; nil if it misses, or starts inside. through: starting inside counts too (t 0), no
    local TMIN, TMAX, AXIS, SIGN
    local function slab(o, d, h, i)
        if math.abs(d) < 1e-9 then return not (o < -h or o > h) end
        local t1, t2 = (-h - o) / d, (h - o) / d
        local s = -1
        if t1 > t2 then t1, t2, s = t2, t1, 1 end
        if t1 > TMIN then TMIN, AXIS, SIGN = t1, i, s end
        if t2 < TMAX then TMAX = t2 end
        return not (TMIN > TMAX)
    end
    local function rayBox(p, b, eye, dir, through)
        local a = axes(p.yaw)
        local dx, dy, dz = eye.x - p.o.x, eye.y - p.o.y, eye.z - p.o.z
        local ox, oy, oz = dx * a[1] + dy * a[2] - b[1], dx * a[3] + dy * a[4] - b[2], dz - b[3]
        local ex, ey, ez = dir.x * a[1] + dir.y * a[2], dir.x * a[3] + dir.y * a[4], dir.z
        local m = b[7] and turn(b).m
        if m then
            ox, oy, oz = ox * m[1] + oy * m[2] + oz * m[3], ox * m[4] + oy * m[5] + oz * m[6], ox * m[7] + oy * m[8] + oz * m[9]
            ex, ey, ez = ex * m[1] + ey * m[2] + ez * m[3], ex * m[4] + ey * m[5] + ez * m[6], ex * m[7] + ey * m[8] + ez * m[9]
        end
        TMIN, TMAX, AXIS, SIGN = through and 0 or -math.huge, math.huge, 0, 0
        if not (slab(ox, ex, b[4], 1) and slab(oy, ey, b[5], 2) and slab(oz, ez, b[6], 3)) then return nil end
        local tmin, tmax, axis, sign = TMIN, TMAX, AXIS, SIGN
        if through then return tmin end
        if tmax < 0 or tmin < 0 then return nil end
        local nx, ny, nz = 0, 0, 0
        if m then nx, ny, nz = m[axis * 3 - 2] * sign, m[axis * 3 - 1] * sign, m[axis * 3] * sign
        elseif axis == 1 then nx = sign elseif axis == 2 then ny = sign else nz = sign end
        return tmin, { nx * a[1] + ny * a[3], nx * a[2] + ny * a[4], nz }
    end

    -- how high one of a piece's boxes reaches over its point (lx, ly), give or take `grow` across: its bottom and top
    -- (the piece's z), or nil. A turned box: where the upright line there passes through it (on a ramp, the slope's
    -- height there; grow only along its level-ish axes, so a ramp's top doesn't rise with it)
    local function span(b, lx, ly, grow)
        if not b[7] then
            if math.abs(lx - b[1]) <= b[4] + grow and math.abs(ly - b[2]) <= b[5] + grow then return b[3] - b[6], b[3] + b[6] end
            return nil
        end
        local m, lo, hi = turn(b).m, -math.huge, math.huge
        local px, py = lx - b[1], ly - b[2]
        for x = 0, 2 do
            local ux, uy, uz = m[3 * x + 1], m[3 * x + 2], m[3 * x + 3]
            local h, q = b[x + 4] + grow * math.sqrt(math.max(0, 1 - uz * uz)), ux * px + uy * py
            if math.abs(uz) < 1e-9 then
                if math.abs(q) > h then return nil end
            else
                local t1, t2 = (-h - q) / uz, (h - q) / uz
                if t1 > t2 then t1, t2 = t2, t1 end
                lo, hi = math.max(lo, t1), math.min(hi, t2)
                if lo > hi then return nil end
            end
        end
        return b[3] + lo, b[3] + hi
    end

    local function boundsBox(it)
        if not it.bb then it.bb = { it.cx, it.cy, (it.min[3] + it.max[3]) / 2, it.size[1] / 2, it.size[2] / 2, it.size[3] / 2 } end
        return it.bb
    end

    -- a piece with many boxes (a walk-in shack: thousands) keeps them in groups of up to 32 by place, each with its
    -- bounds as a box ({ box = {...}, boxes = {...} }), built once per item: rays and overlap tests look at a group's
    -- bounds before its boxes (a turned box counts by the axis-aligned box round it). false: few enough to test them all.
    local function groupsOf(it)
        if it.groups ~= nil then return it.groups end
        if #it.boxes <= 48 then it.groups = false return false end
        local function build(list, out)
            local lo, hi = { math.huge, math.huge, math.huge }, { -math.huge, -math.huge, -math.huge }
            for _, b in ipairs(list) do
                local x = aabb(b)
                for k = 1, 3 do lo[k] = math.min(lo[k], x[k] - x[k + 3]); hi[k] = math.max(hi[k], x[k] + x[k + 3]) end
            end
            if #list <= 32 then
                out[#out + 1] = { box = { (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2, (lo[3] + hi[3]) / 2, (hi[1] - lo[1]) / 2, (hi[2] - lo[2]) / 2, (hi[3] - lo[3]) / 2 }, boxes = list }
                return
            end
            local ax = 1
            for k = 2, 3 do if hi[k] - lo[k] > hi[ax] - lo[ax] then ax = k end end
            table.sort(list, function(x, y) return x[ax] < y[ax] end)
            local h = math.floor(#list / 2)
            local left, right = {}, {}
            for i, b in ipairs(list) do if i <= h then left[#left + 1] = b else right[#right + 1] = b end end
            build(left, out); build(right, out)
        end
        local list, out = {}, {}
        for _, b in ipairs(it.boxes) do list[#list + 1] = b end
        build(list, out)
        it.groups = out
        return out
    end

    local function nearer(p, list, eye, dir, best)
        for _, b in ipairs(list) do
            local t, n = rayBox(p, b, eye, dir)
            if t and t < best.t + (best.piece and 0 or 0.15) then
                best = { t = t, point = { x = eye.x + dir.x * t, y = eye.y + dir.y * t, z = eye.z + dir.z * t }, normal = n, piece = p }
            end
        end
        return best
    end
    local function cast(eye, dir, reach, skip)
        local best = { t = reach }
        local r = Eng.rayHit(v4(eye.x, eye.y, eye.z), v4(eye.x + dir.x * reach, eye.y + dir.y * reach, eye.z + dir.z * reach))
        local w, wn = r[1], r[2]
        if w.w > 0 then
            best.t = math.sqrt((w.x - eye.x) ^ 2 + (w.y - eye.y) ^ 2 + (w.z - eye.z) ^ 2)
            best.point, best.normal = { x = w.x, y = w.y, z = w.z }, { wn.x, wn.y, wn.z }
        end
        for _, p in ipairs(Grid.box(eye.x, eye.y, eye.x + dir.x * best.t, eye.y + dir.y * best.t)) do
            local tb = p ~= skip and rayBox(p, boundsBox(p.it), eye, dir, true)
            if tb and tb < best.t then
                local groups = groupsOf(p.it)
                if groups then
                    for _, g in ipairs(groups) do
                        local tg = rayBox(p, g.box, eye, dir, true)
                        if tg and tg < best.t then best = nearer(p, g.boxes, eye, dir, best) end
                    end
                else
                    best = nearer(p, #p.it.boxes > 0 and p.it.boxes or { boundsBox(p.it) }, eye, dir, best)
                end
            end
        end
        return best
    end

    -- the camera: read from the game once a frame (S.cam, onUpdate clears it) - aiming, placement and the gizmo
    -- all ask, and every call into the game costs; screen size and field of view: once a second
    local screenNow = { t = -1 }
    local function view()
        if S.debugView then return S.debugView.eye, S.debugView.dir end
        local c = S.cam
        if c then return c.eye, c.dir end
        local eye = Homestead.CameraPos()
        local f = Game.GetCameraSystem():GetActiveCameraForward()
        local len = math.sqrt(f.x * f.x + f.y * f.y + f.z * f.z)
        S.cam = { eye = { x = eye.x, y = eye.y, z = eye.z }, dir = { x = f.x / len, y = f.y / len, z = f.z / len } }
        return S.cam.eye, S.cam.dir
    end
    local function screenInfo()
        local now = os.clock()
        if now - screenNow.t > 1 then
            local okS, sz = pcall(Homestead.ScreenSize)
            local okF, fov = pcall(Homestead.CameraFOV)
            screenNow.W = (okS and sz and sz.X > 0) and sz.X or 1920
            screenNow.H = (okS and sz and sz.Y > 0) and sz.Y or 1080
            screenNow.fov = (okF and fov and fov > 10) and fov or 80
            screenNow.t = now
        end
        return screenNow.W, screenNow.H, screenNow.fov
    end

    local function aim() local eye, dir = view(); return cast(eye, dir, REACH) end

    local downs, downF = {}, -1
    local function groundZ(x, y, from)
        local top = from or (S.zone.z + 40)
        if downF ~= Eng.now() then downs, downF = {}, Eng.now() end
        local k = x .. ":" .. y .. ":" .. top
        local z = downs[k]
        if z then return z end
        local d = cast({ x = x, y = y, z = top }, { x = 0, y = 0, z = -1 }, 80)
        z = d.point and d.point.z or S.zone.z
        downs[k] = z
        return z
    end

    local function corners(it, o, yaw)
        local t = {}
        for _, c in ipairs({ { it.min[1], it.min[2] }, { it.max[1], it.min[2] }, { it.max[1], it.max[2] }, { it.min[1], it.max[2] } }) do
            t[#t + 1] = local2world(o, yaw, c[1], c[2])
        end
        return t
    end

    -- snap mode: no piece inside another, as in Fallout - their collision boxes (turned with their pieces) may touch or
    -- overlap by OVERLAP (or the give a snapped pose asks: blockedBy's), not more; the pieces a snap joins (skip: a set)
    -- are left out (voxel boxes overshoot a little, and joined pieces meet). A floor on an edge another floor already
    -- has hits that floor. Free placement doesn't check. -> the piece in the way, or nil
    local U = 0.0142875             -- (a Fallout unit, in metres)
    local OVERLAP = 15 * U          -- (fWorkshopSnapIntersectTolerance: 15 Fallout units, 0.21 m)
    local GIVE = OVERLAP
    local function tol(r1, r2) return math.min(GIVE, 1.5 * math.min(r1, r2)) end
    -- two boxes, either turned: their axis-aligned bounds first, then the 15 axes that can part two boxes in space
    -- (each one's three, and the crossings of theirs), with the same give on each
    local U1, U2 = {}, {}
    local function worldAxes(U, yaw, b)
        local a, m = axes(yaw), b[7] and turn(b).m
        for k = 0, 6, 3 do
            local x, y, z = 0, 0, 0
            if m then x, y, z = m[k + 1], m[k + 2], m[k + 3] elseif k == 0 then x = 1 elseif k == 3 then y = 1 else z = 1 end
            U[k + 1], U[k + 2], U[k + 3] = x * a[1] + y * a[3], x * a[2] + y * a[4], z
        end
    end
    local TX, TY, TZ, B1, B2
    local function apart(lx, ly, lz)
        local n = math.sqrt(lx * lx + ly * ly + lz * lz)
        if n < 1e-6 then return false end
        lx, ly, lz = lx / n, ly / n, lz / n
        local r1 = B1[4] * math.abs(U1[1] * lx + U1[2] * ly + U1[3] * lz) + B1[5] * math.abs(U1[4] * lx + U1[5] * ly + U1[6] * lz) + B1[6] * math.abs(U1[7] * lx + U1[8] * ly + U1[9] * lz)
        local r2 = B2[4] * math.abs(U2[1] * lx + U2[2] * ly + U2[3] * lz) + B2[5] * math.abs(U2[4] * lx + U2[5] * ly + U2[6] * lz) + B2[6] * math.abs(U2[7] * lx + U2[8] * ly + U2[9] * lz)
        return math.abs(TX * lx + TY * ly + TZ * lz) >= r1 + r2 - tol(r1, r2)
    end
    local function turnedHit(o1, y1, b1, o2, y2, b2)
        worldAxes(U1, y1, b1); worldAxes(U2, y2, b2)
        local a1, a2 = axes(y1), axes(y2)
        TX = o2.x + a2[1] * b2[1] + a2[3] * b2[2] - (o1.x + a1[1] * b1[1] + a1[3] * b1[2])
        TY = o2.y + a2[2] * b2[1] + a2[4] * b2[2] - (o1.y + a1[2] * b1[1] + a1[4] * b1[2])
        TZ, B1, B2 = o2.z + b2[3] - o1.z - b1[3], b1, b2
        for k = 0, 6, 3 do
            if apart(U1[k + 1], U1[k + 2], U1[k + 3]) or apart(U2[k + 1], U2[k + 2], U2[k + 3]) then return false end
        end
        for i = 0, 6, 3 do
            for j = 0, 6, 3 do
                if apart(U1[i + 2] * U2[j + 3] - U1[i + 3] * U2[j + 2], U1[i + 3] * U2[j + 1] - U1[i + 1] * U2[j + 3], U1[i + 1] * U2[j + 2] - U1[i + 2] * U2[j + 1]) then return false end
            end
        end
        return true
    end
    local DX, DY, A1, A2
    local function flat(ux, uy)
        local r1 = B1[4] * math.abs(A1[1] * ux + A1[2] * uy) + B1[5] * math.abs(A1[3] * ux + A1[4] * uy)
        local r2 = B2[4] * math.abs(A2[1] * ux + A2[2] * uy) + B2[5] * math.abs(A2[3] * ux + A2[4] * uy)
        return math.abs(DX * ux + DY * uy) >= r1 + r2 - tol(r1, r2)
    end
    local function boxHit(o1, y1, b1, o2, y2, b2)
        if b1[7] or b2[7] then return boxHit(o1, y1, aabb(b1), o2, y2, aabb(b2)) and turnedHit(o1, y1, b1, o2, y2, b2) end
        if math.abs(o1.z + b1[3] - (o2.z + b2[3])) >= b1[6] + b2[6] - tol(b1[6], b2[6]) then return false end
        local a1, a2 = axes(y1), axes(y2)
        DX = o2.x + a2[1] * b2[1] + a2[3] * b2[2] - (o1.x + a1[1] * b1[1] + a1[3] * b1[2])
        DY = o2.y + a2[2] * b2[1] + a2[4] * b2[2] - (o1.y + a1[2] * b1[1] + a1[4] * b1[2])
        A1, A2, B1, B2 = a1, a2, b1, b2
        return not (flat(a1[1], a1[2]) or flat(a1[3], a1[4]) or flat(a2[1], a2[2]) or flat(a2[3], a2[4]))
    end
    local function reach(it) return math.sqrt(it.size[1] ^ 2 + it.size[2] ^ 2) / 2 + math.sqrt(it.cx ^ 2 + it.cy ^ 2) end
    local function solidBoxes(it)
        if not it.solid then it.solid = #it.boxes > 0 and it.boxes or { boundsBox(it) } end
        return it.solid
    end
    local function blockedBy(it, o, yaw, skip, give, box)
        GIVE = give or OVERLAP
        local mine, mygroups = box and { box } or solidBoxes(it), not box and groupsOf(it) or nil
        for _, q in ipairs(Grid.around(o.x, o.y, reach(it))) do
            local rr = reach(it) + reach(q.it)
            if not (skip and skip[q]) and not q.it.npc and (q.o.x - o.x) ^ 2 + (q.o.y - o.y) ^ 2 < rr * rr and math.abs(q.o.z - o.z) < it.size[3] + q.it.size[3] + 1
               and boxHit(o, yaw, boundsBox(it), q.o, q.yaw, boundsBox(q.it)) then
                local qb, theirs, groups = boundsBox(q.it), solidBoxes(q.it), groupsOf(q.it)
                local function hits(b1)
                    local a1 = aabb(b1)
                    if not boxHit(o, yaw, a1, q.o, q.yaw, qb) then return false end
                    if groups then
                        for _, g in ipairs(groups) do
                            if boxHit(o, yaw, a1, q.o, q.yaw, g.box) then
                                for _, b2 in ipairs(g.boxes) do if boxHit(o, yaw, b1, q.o, q.yaw, b2) then return true end end
                            end
                        end
                    else
                        for _, b2 in ipairs(theirs) do
                            if boxHit(o, yaw, b1, q.o, q.yaw, b2) then return true end
                        end
                    end
                    return false
                end
                if mygroups then
                    for _, g1 in ipairs(mygroups) do
                        if boxHit(o, yaw, g1.box, q.o, q.yaw, qb) then
                            for _, b1 in ipairs(g1.boxes) do if hits(b1) then return q end end
                        end
                    end
                else
                    for _, b1 in ipairs(mine) do if hits(b1) then return q end end
                end
            end
        end
    end

    -- two points pair when their names match but for a -Dif suffix (P-<Family>[-Dif|-Dif2|-DifNNN]): X with X, X-Dif with
    -- X, X-Dif2 or X-Dif001; a suffixed name never with itself (X-Dif with X-Dif). Where a point sits decides top, bottom
    -- or side, not its name: an upper floor's underside P-Ceiling takes a wall top's P-Ceiling-Dif
    local function pairs_(a, b) return a.base == b.base and (not (a.dif or b.dif) or a.name ~= b.name) end

    C.Q, C.Grid, C.U = Q, Grid, U
    C.axes, C.local2world, C.originAt, C.pivotOf, C.anchorOf, C.originFromAnchor = axes, local2world, originAt, pivotOf, anchorOf, originFromAnchor
    C.cellOf, C.levelKey, C.slotKey, C.slotsOf = cellOf, levelKey, slotKey, slotsOf
    C.zoneDist, C.inZone, C.corners = zoneDist, inZone, corners
    C.rayBox, C.span, C.boundsBox, C.groupsOf, C.cast, C.view, C.screenInfo, C.aim, C.groundZ = rayBox, span, boundsBox, groupsOf, cast, view, screenInfo, aim, groundZ
    C.boxHit, C.reach, C.solidBoxes, C.blockedBy, C.pairs_ = boxHit, reach, solidBoxes, blockedBy, pairs_
end
