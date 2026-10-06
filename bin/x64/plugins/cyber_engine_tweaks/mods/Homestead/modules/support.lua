-- Support: what holds a piece up, as Fallout's supported items - the pieces under its footprint, the one it is mounted
-- on, the ones its snap points join (not above it), and the ground or the world's own things. heldUpOnlyBy(p): what only
-- p holds up, then what only those hold, and so on (scrapping takes them, moving carries them along).
return function(C)
    local v4, hashOf, Eng, axes, local2world, Grid = C.v4, C.hashOf, C.Eng, C.axes, C.local2world, C.Grid
    local boundsBox, groupsOf, corners, U, reach, pairs_, span = C.boundsBox, C.groupsOf, C.corners, C.U, C.reach, C.pairs_, C.span

    -- Footprint is 0.9 of the piece's bounds (fWorkshopSupportedItemBoundsMult), looked at 64 units down.
    local SUPPORT = 0.15
    local function boxesAt(p, x, y, grow, f)
        -- A turned piece: test where the upright line at x, y passes through it (on a ramp, its slope's height).
        local a = axes(p.yaw)
        local dx, dy = x - p.o.x, y - p.o.y
        local lx, ly = dx * a[1] + dy * a[2], dx * a[3] + dy * a[4]
        local function test(list)
            for _, b in ipairs(list) do
                local lo, hi = span(b, lx, ly, grow)
                if lo and f(p.o.z + lo, p.o.z + hi) then return true end
            end
        end
        local groups = groupsOf(p.it)
        if groups then
            for _, g in ipairs(groups) do if span(g.box, lx, ly, grow) and test(g.boxes) then return true end end
            return false
        end
        return test(#p.it.boxes > 0 and p.it.boxes or { boundsBox(p.it) }) or false
    end
    local function holders(B)
        local it, out, ground = B.it, {}, false
        local bottom, top = B.o.z + it.min[3], B.o.z + it.max[3]
        local mid = local2world(B.o, B.yaw, it.cx, it.cy)
        local feet = { mid }
        for _, c in ipairs(corners(it, B.o, B.yaw)) do feet[#feet + 1] = { x = mid.x + (c.x - mid.x) * 0.9, y = mid.y + (c.y - mid.y) * 0.9 } end
        local near = Grid.around(mid.x, mid.y, reach(it) + 1)
        for _, f in ipairs(feet) do
            for _, A in ipairs(near) do
                if A ~= B and not out[A] and boxesAt(A, f.x, f.y, SUPPORT, function(_, top) return math.abs(top - bottom) <= SUPPORT end) then
                    out[A] = true
                end
            end
            -- Ground: terrain within reach under it, or a world thing - a ray from just inside its bottom that meets none of ours.
            if not ground then
                local t = Eng.terrain(v4(f.x, f.y, bottom))
                ground = t.w > 0 and bottom - t.z < 64 * U
                if not ground then
                    local r = Eng.rayHit(v4(f.x, f.y, bottom + 0.05), v4(f.x, f.y, bottom - 64 * U))
                    local hz = r[1].z
                    if r[1].w > 0 and hz <= bottom + 0.02 then
                        local ours = false
                        for _, A in ipairs(near) do
                            if A ~= B and boxesAt(A, f.x, f.y, SUPPORT, function(lo, hi) return hz >= lo - 0.05 and hz <= hi + 0.05 end) then ours = true break end
                        end
                        ground = not ours
                    end
                end
            end
        end
        local m = it.mount  -- wall decor: the piece its mount point is on
        if m then
            local w = local2world(B.o, B.yaw, m.x, m.y, m.z)
            for _, A in ipairs(near) do
                if A ~= B and boxesAt(A, w.x, w.y, 0.1, function(lo, hi) return w.z >= lo - 0.1 and w.z <= hi + 0.1 end) then out[A] = true end
            end
        end
        for _, c in ipairs(Grid.snaps(it)) do
            local w = local2world(B.o, B.yaw, c.x, c.y, c.z)
            local function below(A) return A.o.z + (A.it.min[3] + A.it.max[3]) / 2 <= top + 0.01 end
            local function on(b) if b.piece ~= B and math.abs(b.z - w.z) < 0.03 and pairs_(c, b.c) and below(b.piece) then out[b.piece] = true end end
            Grid.points(w.x, w.y, 0.03, on)
        end
        return out, ground
    end
    local function heldUpOnlyBy(x)
        local function id(p) return p.id and hashOf(p.id) or p end
        local gone, out, queue, memo = { [id(x)] = true }, {}, { x }, {}
        while #queue > 0 do
            local R = table.remove(queue)
            for _, B in ipairs(Grid.around(R.o.x, R.o.y, reach(R.it) + 2)) do
                if not gone[id(B)] and not B.bench and not B.it.npc then
                    local h = memo[B]
                    if not h then local o, g = holders(B); h = { o = o, g = g }; memo[B] = h end
                    if not h.g and next(h.o) then
                        local all = true
                        for A in pairs(h.o) do if not gone[id(A)] then all = false break end end
                        if all then gone[id(B)] = true; out[#out + 1] = B; queue[#queue + 1] = B end
                    end
                end
            end
        end
        return out
    end

    C.heldUpOnlyBy = heldUpOnlyBy
end
