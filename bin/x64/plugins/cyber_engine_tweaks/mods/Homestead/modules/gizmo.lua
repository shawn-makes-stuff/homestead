-- the free-placement gizmo -------------------------------------------------------------------------------------------
-- Ctrl in free placement, holding a piece: the piece stops following the crosshair, the camera and V stand still (Homestead.Gizmo)
-- and the mouse moves a cursor of ours. Handles keep their on-screen size: the centre square slides the piece over the ground; the
-- X / Y / Z arrows move it along one axis (the grabbed point stays under the cursor); the rings turn it about the world's axes.
-- The wheel pushes it away / pulls it in. Shift: steps (0.1 m, 15 degrees). E places it, tilt and all; Ctrl lets it follow the
-- crosshair again. Right mouse held: camera and V free again, cursor kept. Drawn by HomesteadUI.Gizmo; projected with the camera's
-- field of view (taken as vertical) and the screen's shape. Ctrl edit (the gizmo on a placed piece): a handle let go sets the piece
-- down (C.gizmoApply); the wheel's push is set down once it rests (SETTLE); the next grab or notch takes it up again (C.gizmoPickup).
-- Nothing is taken up before the lifetime guard allows it, and a piece is set down two frames after take-up at the earliest.
return function(Gizmo, C)
    local Q, S, SFX, atan2, byKey, say = C.Q, C.S, C.SFX, C.atan2, C.byKey, C.say
    local screenInfo, sfx, try, view, lines = C.screenInfo, C.sfx, C.try, C.view, C.Lines.set

    local GZ = { hit = 0.022, segs = 48, step = 0.1, turn = 15, size = 0.2, sens = 1.25, cone = 16 }
    local SETTLE = 0.35                                              -- Ctrl edit: a push stands once the wheel rests this long (s)
    local AX = { { 1, 0, 0 }, { 0, 1, 0 }, { 0, 0, 1 } }

    local function gizmoCam()
        local eye, f = view()
        local rl = math.max(math.sqrt(f.y ^ 2 + f.x ^ 2), 1e-6)
        local r = { x = f.y / rl, y = -f.x / rl, z = 0 }                    -- right = forward x up (no roll)
        local u = { x = r.y * f.z, y = -r.x * f.z, z = r.x * f.y - r.y * f.x }
        local W, H, fov = screenInfo()
        return { eye = eye, f = f, r = r, u = u, tv = math.tan(math.rad(fov) / 2), aspect = W / H, W = W, H = H }
    end

    local function project(c, p)
        local dx, dy, dz = p.x - c.eye.x, p.y - c.eye.y, p.z - c.eye.z
        local z = dx * c.f.x + dy * c.f.y + dz * c.f.z
        if z < 0.05 then return nil end
        local x = dx * c.r.x + dy * c.r.y + dz * c.r.z
        local y = dx * c.u.x + dy * c.u.y + dz * c.u.z
        return 0.5 + x / (z * c.tv * c.aspect) / 2, 0.5 - y / (z * c.tv) / 2
    end

    local function cursorRay(c, p)
        local nx, ny = (p[1] - 0.5) * 2 * c.tv * c.aspect, (0.5 - p[2]) * 2 * c.tv
        local d = { x = c.f.x + c.r.x * nx + c.u.x * ny, y = c.f.y + c.r.y * nx + c.u.y * ny, z = c.f.z + c.r.z * nx + c.u.z * ny }
        local l = math.sqrt(d.x ^ 2 + d.y ^ 2 + d.z ^ 2)
        return { x = d.x / l, y = d.y / l, z = d.z / l }
    end

    local function axisParam(c, C, A, d)
        local b = A[1] * d.x + A[2] * d.y + A[3] * d.z
        if math.abs(b) > 0.985 then return nil end
        local wx, wy, wz = C.x - c.eye.x, C.y - c.eye.y, C.z - c.eye.z
        local dd, e = A[1] * wx + A[2] * wy + A[3] * wz, d.x * wx + d.y * wy + d.z * wz
        return (b * e - dd) / (1 - b * b)
    end

    local function planeHit(c, C, n, d)
        local dn = d.x * n[1] + d.y * n[2] + d.z * n[3]
        if math.abs(dn) < 0.08 then return nil end
        local t = ((C.x - c.eye.x) * n[1] + (C.y - c.eye.y) * n[2] + (C.z - c.eye.z) * n[3]) / dn
        if t <= 0 then return nil end
        return { x = c.eye.x + d.x * t, y = c.eye.y + d.y * t, z = c.eye.z + d.z * t }
    end

    local function gizmoCentre(it, o, q)
        local x, y, z = Q.rot(q, it.cx, it.cy, (it.min[3] + it.max[3]) / 2)
        return { x = o.x + x, y = o.y + y, z = o.z + z }
    end

    local function gizmoHandles(c, it, o, q)
        local C = gizmoCentre(it, o, q)
        local dist = math.sqrt((C.x - c.eye.x) ^ 2 + (C.y - c.eye.y) ^ 2 + (C.z - c.eye.z) ^ 2)
        local L = GZ.size * 2 * math.max(dist, 0.5) * c.tv               -- a fifth of the screen's height long
        local R = 0.62 * L
        local function sp(x, y, z) local u, v = project(c, { x = x, y = y, z = z }) return u and { u, v } or false end
        local hs = {}
        local sq = 0.09 * L
        hs[1] = { kind = "slide", axis = 0, pts = { sp(C.x - sq, C.y - sq, C.z), sp(C.x + sq, C.y - sq, C.z), sp(C.x + sq, C.y + sq, C.z), sp(C.x - sq, C.y + sq, C.z), sp(C.x - sq, C.y - sq, C.z) } }
        for a = 1, 3 do
            local A = AX[a]
            local e1, e2 = AX[a % 3 + 1], AX[(a + 1) % 3 + 1]
            local tip = { C.x + A[1] * L, C.y + A[2] * L, C.z + A[3] * L }
            local h, cr = 0.2 * L, 0.06 * L
            local base = { tip[1] - A[1] * h, tip[2] - A[2] * h, tip[3] - A[3] * h }
            local T, head, rim = sp(tip[1], tip[2], tip[3]), {}, {}
            for s = 0, GZ.cone do
                local t = 2 * math.pi * s / GZ.cone
                local cs, sn = math.cos(t) * cr, math.sin(t) * cr
                rim[#rim + 1] = sp(base[1] + e1[1] * cs + e2[1] * sn, base[2] + e1[2] * cs + e2[2] * sn, base[3] + e1[3] * cs + e2[3] * sn)
                head[#head + 1] = { T, rim[#rim] }
                if s > 0 then head[#head + 1] = { rim[#rim - 1], rim[#rim] } end
            end
            hs[#hs + 1] = { kind = "move", axis = a, L = L, pts = { sp(C.x + A[1] * 0.12 * L, C.y + A[2] * 0.12 * L, C.z + A[3] * 0.12 * L), sp(base[1], base[2], base[3]), T }, head = head }
            local ring = {}
            for s = 0, GZ.segs do
                local t = 2 * math.pi * s / GZ.segs
                local cs, sn = math.cos(t) * R, math.sin(t) * R
                ring[#ring + 1] = sp(C.x + e1[1] * cs + e2[1] * sn, C.y + e1[2] * cs + e2[2] * sn, C.z + e1[3] * cs + e2[3] * sn)
            end
            hs[#hs + 1] = { kind = "turn", axis = a, pts = ring }
        end
        local cu, cv = project(c, C)
        return hs, C, cu and { cu, cv }
    end

    local function segDist(c, p, a, b)
        local ax, ay, bx, by, px, py = a[1] * c.aspect, a[2], b[1] * c.aspect, b[2], p[1] * c.aspect, p[2]
        local dx, dy = bx - ax, by - ay
        local l2 = dx * dx + dy * dy
        local t = l2 > 0 and math.max(0, math.min(1, ((px - ax) * dx + (py - ay) * dy) / l2)) or 0
        return math.sqrt((px - ax - t * dx) ^ 2 + (py - ay - t * dy) ^ 2)
    end

    local function gizmoOff()
        if not S.gz then return end
        S.gz = nil
        try("gizmo", Homestead.Gizmo, false)
        lines("gizmo", nil)
    end

    local function gizmoOn(at)
        local h = S.hold
        local o = at or (S.place and S.place.o)
        if not (h and S.free and o) then return end
        h.q = h.q or Q.yaw(h.yaw)
        S.gz = { o = { x = o.x, y = o.y, z = o.z }, cx = 0.5, cy = 0.5 }
        local u, v = project(gizmoCam(), gizmoCentre(byKey[h.key], S.gz.o, h.q))
        if u then S.gz.cx, S.gz.cy = math.max(0.02, math.min(0.98, u)), math.max(0.02, math.min(0.98, v)) end
        -- The plugin takes the mouse (polled in gizmoTick): the game sees no motion, so its camera is left alone, no drift.
        S.gz.cap = try("gizmo", Homestead.Gizmo, true) == true
        say("Gizmo: drag the square to slide, arrows to move, rings to turn")
        sfx(SFX.open)
    end

    -- Ctrl edit: take the placed piece up. true: taken up (or nothing placed); nil: not yet (just set down); false: gone.
    local function takeUp(g)
        if not g.piece then return true end
        if not C.ready(g.piece) then return nil end
        if not C.gizmoPickup(g.piece) then gizmoOff() return false end
        g.piece, g.upAt = nil, C.Eng.now()
        return true
    end

    local function startDrag(g)
        local picked = g.piece ~= nil or g.settle ~= nil
        local up = takeUp(g)
        if up == nil then return end
        local h = g.grab
        g.grab, g.settle = nil, nil
        if not up then return end
        g.drag = { h = h, start = { g.cx, g.cy }, last = { g.cx, g.cy }, o0 = { x = g.o.x, y = g.o.y, z = g.o.z }, acc = 0, done = 0, picked = picked }
    end

    local function gizmoPress(down)
        local g = S.gz
        if not down then
            local d = g.drag
            g.drag, g.grab = nil, nil
            if d and (d.done ~= 0 or d.picked) then g.settle = 0 end
            return
        end
        if g.look or not g.hover then return end
        g.grab = g.hover
        startDrag(g)
    end

    local function gizmoWheel(dir)
        local g, c = S.gz, gizmoCam()
        local up = takeUp(g)
        if up == nil then g.notches = (g.notches or 0) + dir return end
        if not up then return end
        local C0 = gizmoCentre(byKey[S.hold.key], g.o, S.hold.q)
        local dist = math.sqrt((C0.x - c.eye.x) ^ 2 + (C0.y - c.eye.y) ^ 2 + (C0.z - c.eye.z) ^ 2)
        local step = (S.shiftDown and 1 or math.max(0.05, dist * 0.1)) * dir
        if dist + step < 0.5 then return end
        local d = cursorRay(c, { g.cx, g.cy })
        g.o = { x = g.o.x + d.x * step, y = g.o.y + d.y * step, z = g.o.z + d.z * step }
        if S.hold.kind == "move" then g.settle = SETTLE end
    end

    -- Ctrl edit's waits, each frame: notches and a grab that came before the piece could be taken up; a change set down
    -- once settled, and two frames at least after the take-up
    local function waits(g)
        if g.notches and (not g.piece or C.ready(g.piece)) then
            local n = g.notches
            g.notches = nil
            for _ = 1, math.abs(n) do if S.gz then gizmoWheel(n > 0 and 1 or -1) end end
        end
        if S.gz and g.grab then startDrag(g) end
        if S.gz and g.settle and not g.drag then
            g.settle = g.settle - (S.frameDt or 0)
            if g.settle <= 0 and C.Eng.now() - (g.upAt or -1e9) >= C.Eng.GUARD then g.settle = nil; C.gizmoApply() end
        end
    end

    local function gizmoMouse(dx, dy)
        local g = S.gz
        if not g or g.look then return end
        local W, H = screenInfo()
        g.cx = math.max(0, math.min(1, g.cx + dx * GZ.sens / W))
        g.cy = math.max(0, math.min(1, g.cy + dy * GZ.sens / H))
    end

    local function gizmoTick()
        if S.gz then waits(S.gz) end
        local g, h = S.gz, S.hold
        if not g then return end
        local held = h and S.free
        if not held and not g.piece then gizmoOff() return end
        if g.cap and not g.look then gizmoMouse(HomesteadImport.MouseX(), HomesteadImport.MouseY()) end
        local src = held and h or g.piece
        local it = byKey[src.key]
        local q = held and h.q or src.q or Q.yaw(src.yaw)
        local c = gizmoCam()
        local key = { c.eye.x, c.eye.y, c.eye.z, c.f.x, c.f.y, c.f.z, c.W, c.H, c.tv, g.o.x, g.o.y, g.o.z, q.i, q.j, q.k, q.r,
                      g.cx, g.cy, g.drag and 1 or 0, S.shiftDown and 1 or 0 }
        local same = g.key ~= nil
        for i = 1, #key do if not same or g.key[i] ~= key[i] then same = false break end end
        g.key = key
        if same then return end
        local hs, C, cs = gizmoHandles(c, it, g.o, q)
        local cur = { g.cx, g.cy }
        local d = g.drag
        if d then
            local k = d.h.kind
            local A = AX[d.h.axis] or { 0, 0, 1 }
            local ray = cursorRay(c, cur)
            if k == "slide" then
                local C0 = gizmoCentre(it, d.o0, h.q)
                local p0, p1 = planeHit(c, C0, { 0, 0, 1 }, cursorRay(c, d.start)), planeHit(c, C0, { 0, 0, 1 }, ray)
                if p0 and p1 then
                    local dx, dy = p1.x - p0.x, p1.y - p0.y
                    if S.shiftDown then dx, dy = math.floor(dx / GZ.step + 0.5) * GZ.step, math.floor(dy / GZ.step + 0.5) * GZ.step end
                    g.o = { x = d.o0.x + dx, y = d.o0.y + dy, z = d.o0.z }
                    d.done = math.sqrt(dx * dx + dy * dy)
                end
            elseif k == "move" then
                local C0 = gizmoCentre(it, d.o0, h.q)
                local s0, s1 = axisParam(c, C0, A, cursorRay(c, d.start)), axisParam(c, C0, A, ray)
                if s0 and s1 then
                    local ds = s1 - s0
                    if S.shiftDown then ds = math.floor(ds / GZ.step + 0.5) * GZ.step end
                    g.o = { x = d.o0.x + A[1] * ds, y = d.o0.y + A[2] * ds, z = d.o0.z + A[3] * ds }
                    d.done = ds
                end
            elseif k == "turn" then
                local e1, e2 = AX[d.h.axis % 3 + 1], AX[(d.h.axis + 1) % 3 + 1]
                local function ang(p)
                    local P = planeHit(c, C, A, cursorRay(c, p))
                    if P then return math.deg(atan2((P.x - C.x) * e2[1] + (P.y - C.y) * e2[2] + (P.z - C.z) * e2[3], (P.x - C.x) * e1[1] + (P.y - C.y) * e1[2] + (P.z - C.z) * e1[3])) end
                end
                local a1, a0 = ang(cur), ang(d.last)
                local amount
                if a1 and a0 then amount = (a1 - a0 + 540) % 360 - 180
                elseif cs then
                    local function sang(p) return math.deg(atan2(-(p[2] - cs[2]), (p[1] - cs[1]) * c.aspect)) end
                    local toCam = A[1] * (c.eye.x - C.x) + A[2] * (c.eye.y - C.y) + A[3] * (c.eye.z - C.z)
                    amount = ((sang(cur) - sang(d.last) + 540) % 360 - 180) * (toCam >= 0 and 1 or -1)
                end
                d.last = cur
                if amount then
                    d.acc = d.acc + amount
                    local want = S.shiftDown and math.floor(d.acc / GZ.turn + 0.5) * GZ.turn or d.acc
                    local delta = want - d.done
                    d.done = want
                    if delta ~= 0 then
                        local dq = Q.axis(A[1], A[2], A[3], delta)
                        local rx, ry, rz = Q.rot(dq, g.o.x - C.x, g.o.y - C.y, g.o.z - C.z)
                        g.o = { x = C.x + rx, y = C.y + ry, z = C.z + rz }
                        h.q = Q.norm(Q.mul(dq, h.q))
                        h.yaw = Q.yawOf(h.q)
                    end
                end
            end
        else
            local best, bd
            for _, hd in ipairs(hs) do
                local pref = hd.kind == "turn" and 0.004 or 0
                for s = 1, #hd.pts - 1 do
                    local a, b = hd.pts[s], hd.pts[s + 1]
                    if a and b then
                        local dd = segDist(c, cur, a, b) + pref
                        if dd < GZ.hit and (not bd or dd < bd) then best, bd = hd, dd end
                    end
                end
                if hd.kind == "slide" and hd.pts[1] and hd.pts[2] and hd.pts[3] and hd.pts[4] then
                    local minu, maxu = math.min(hd.pts[1][1], hd.pts[2][1], hd.pts[3][1], hd.pts[4][1]), math.max(hd.pts[1][1], hd.pts[2][1], hd.pts[3][1], hd.pts[4][1])
                    local minv, maxv = math.min(hd.pts[1][2], hd.pts[2][2], hd.pts[3][2], hd.pts[4][2]), math.max(hd.pts[1][2], hd.pts[2][2], hd.pts[3][2], hd.pts[4][2])
                    if cur[1] >= minu and cur[1] <= maxu and cur[2] >= minv and cur[2] <= maxv then best, bd = hd, 0 end
                end
            end
            g.hover = best and { kind = best.kind, axis = best.axis } or nil
        end
        local segs, act = {}, d and d.h or g.hover
        local function seg(a, b, col, w)
            if a and b then segs[#segs + 1] = a[1]; segs[#segs + 1] = a[2]; segs[#segs + 1] = b[1]; segs[#segs + 1] = b[2]; segs[#segs + 1] = col; segs[#segs + 1] = w end
        end
        for _, hd in ipairs(hs) do
            local on = act and act.kind == hd.kind and act.axis == hd.axis
            local col = on and 3 or (hd.kind == "slide" and 4 or hd.axis - 1)
            local w = hd.kind == "turn" and (on and 12 or 8) or (on and 18 or 13)
            for s = 1, #hd.pts - 1 do seg(hd.pts[s], hd.pts[s + 1], col, w) end
            for _, hh in ipairs(hd.head or {}) do seg(hh[1], hh[2], col, 7) end
        end
        lines("gizmo", segs, g.cx, g.cy)
    end

    local function gizmoLook(down)
        local g = S.gz
        if not g or (g.look or false) == down then return end
        g.look = down or nil
        if down then g.drag, g.grab = nil, nil end
        g.cap = try("gizmo", Homestead.Gizmo, not down) == true
    end
    Gizmo.on, Gizmo.off, Gizmo.press, Gizmo.wheel, Gizmo.tick, Gizmo.mouse = gizmoOn, gizmoOff, gizmoPress, gizmoWheel, gizmoTick, gizmoMouse
    Gizmo.look = gizmoLook
    Gizmo.cam, Gizmo.project, Gizmo.handles = gizmoCam, project, gizmoHandles
end
