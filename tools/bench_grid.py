# run inside tools/sim.py (BENCH=1): a grid of shack floors built by snapping, a hole in its middle filled, then the
# time placement takes while a floor is held and the aim sweeps over the grid (GetMod("Homestead").prof)
F, S_ = 'fo4_workshop_shackmidfloor01', 3.6576
N = int(os.environ.get('BENCH_N', '5'))
x0, y0 = ZX - 20, ZY + 2
before = {id(p) for p in pieces(F)}
stand(x0 - 4, y0 - 4); fo4_hold(F); look_at(x0, y0, Z); SIM.tick(3); SIM.key('IK_E'); SIM.release('IK_E'); SIM.tick(2)
A0 = min(pieces(F), key=lambda p: (p.o.x - x0 - 2) ** 2 + (p.o.y - y0 - 2) ** 2)
ox, oy, oz = A0.o.x, A0.o.y, A0.o.z
hole = (N // 2, N // 2)
miss = 0
for j in range(N):
    for i in range(N):
        if (i, j) in ((0, 0), hole): continue
        cx, cy = ox + i * S_, oy + j * S_
        if i and (i - 1, j) != hole: stand(cx - S_, cy); fo4_hold(F); look_at(cx - S_ / 2, cy + 0.4, oz)      # (on the floor before it, facing
        else: stand(cx, cy - S_); fo4_hold(F); look_at(cx + 0.4, cy - S_ / 2, oz)      # the edge between them)
        SIM.tick(3)
        o = st.place.o
        if not (st.place.ok and abs(o.x - cx) < 0.01 and abs(o.y - cy) < 0.01):
            miss += 1; continue
        SIM.key('IK_E'); SIM.release('IK_E'); SIM.tick(2)
check(miss == 0, 'BENCH grid %dx%d by snapping, each from the floor before it: %d floors, %d not snapped where wanted' % (N, N, len(pieces(F)), miss))
hx, hy = ox + hole[0] * S_, oy + hole[1] * S_
res = []
for sx, sy, ax, ay in ((0, -S_, 0, -S_ / 2), (-S_, 0, -S_ / 2, 0.5), (0, S_, 0.3, S_ / 2), (S_, 0, S_ / 2, -0.4)):   # (from each side)
    stand(hx + sx, hy + sy); fo4_hold(F); look_at(hx + ax, hy + ay, oz); SIM.tick(3)
    o = st.place.o
    res.append('%s%s' % ('ok' if st.place.ok else 'NO(%s)' % st.place.why, '@hole' if abs(o.x - hx) < 0.01 and abs(o.y - hy) < 0.01 else '@(%.1f,%.1f)' % (o.x - hx, o.y - hy)))
check(res == ['ok@hole'] * 4, 'BENCH a hole in the middle of floors takes a floor, from each side: %s' % res)
res = []
for sx, sy, ax, ay in ((0, -S_, 0, 0), (-S_, 0, 0.6, -0.5), (0, S_, -0.9, 0.7), (S_, 0, 0.4, 1.1)):   # (aimed into it, not at an edge)
    stand(hx + sx, hy + sy); fo4_hold(F); look_at(hx + ax, hy + ay, oz); SIM.tick(3)
    o = st.place.o
    res.append('%s%s' % ('ok' if st.place.ok else 'NO', '@hole' if abs(o.x - hx) < 0.01 and abs(o.y - hy) < 0.01 else '@(%.1f,%.1f)' % (o.x - hx, o.y - hy)))
check(res == ['ok@hole'] * 4, 'BENCH aimed anywhere into the hole, it fills it: %s' % res)
lua('function() SIM.mod.prof(true) end')()
stand(ox - 3, oy - 3); fo4_hold(F)
import time as _bt
t0 = _bt.time()
for k in range(120):
    f = k / 120.0
    look_at(ox + f * (N - 1) * S_, oy + (0.5 + 0.5 * math.sin(k / 7.0)) * (N - 1) * S_, oz); SIM.tick(1)
print('BENCH sweep 120 frames, %.1f ms/frame wall in the sim' % ((_bt.time() - t0) * 1000 / 120))
print('BENCH prof:', lua('function() return SIM.mod.prof() end')())
# one more floor placed (E): the frame it lands in and the next few
lua('function() SIM.mod.prof(true) end')()
cx, cy = ox + N * S_, oy
stand(cx - S_, cy); fo4_hold(F); look_at(cx - S_ / 2, cy, oz); SIM.tick(3)
lua('function() SIM.mod.prof(true) end')()
t0 = _bt.time(); SIM.key('IK_E'); SIM.release('IK_E'); SIM.tick(1); t1 = _bt.time(); SIM.tick(5); t2 = _bt.time()
print('BENCH place: E frame %.1f ms, next 5 frames %.1f ms' % ((t1 - t0) * 1000, (t2 - t1) * 1000))
print('BENCH prof:', lua('function() return SIM.mod.prof() end')())
# scrap: what only a piece holds up goes with it - a raised floor with a wall on its edge and a radio on it; floors on
# the ground (the grid) are left
W_, RD_ = 'fo4_workshop_shackwallflat03', 'fo4_radiofreedomreceiveroff'
bx, by = ZX + 8, ZY + 10
stand(bx, by - 6.4); fo4_hold(F); SIM.key('IK_Q'); SIM.release('IK_Q'); SIM.tick(1); look_at(bx, by, Z + 1.3); SIM.tick(3)
SIM.key('IK_E'); SIM.release('IK_E'); SIM.tick(2)
RF = min(pieces(F), key=lambda p: (p.o.x - bx) ** 2 + (p.o.y - by) ** 2)
ftop = RF.o.z + lua('function(k) return SIM.it(k).max[3] end')(F)
stand(RF.o.x, RF.o.y - 1); fo4_hold(W_); look_at(RF.o.x + 0.2, RF.o.y + 1.5, ftop); SIM.tick(3)
wall_ok = bool(st.snapped) and st.place.ok
SIM.key('IK_E'); SIM.release('IK_E'); SIM.tick(2)
fo4_hold(RD_); look_at(RF.o.x - 0.5, RF.o.y, ftop); SIM.tick(3); SIM.key('IK_E'); SIM.release('IK_E'); SIM.tick(2)
near_ = lambda k: [p for p in pieces(k) if (p.o.x - RF.o.x) ** 2 + (p.o.y - RF.o.y) ** 2 < 16]
before_ = (len(near_(W_)), len(near_(RD_)), len(pieces(F)))
lua('function(p) local S = SIM.mod.state if not S.build then SIM.mod.build() end S.level, S.hold = 0, nil S.target = p end')(RF)
SIM.key('IK_R'); SIM.release('IK_R'); SIM.tick(2)
after_ = (len(near_(W_)), len(near_(RD_)), len(pieces(F)))
check(wall_ok and before_[:2] == (1, 1) and after_ == (0, 0, before_[2] - 1),
      "scrapping a raised floor takes what only it held up: its wall and the radio on it (before %s, after %s; '%s')" % (before_, after_, st.toast))
# move: what only a piece holds up goes with it, as it stood on it
stand(bx, by - 6.4); fo4_hold(F); SIM.key('IK_Q'); SIM.release('IK_Q'); SIM.tick(1); look_at(bx, by, Z + 1.3); SIM.tick(3)
SIM.key('IK_E'); SIM.release('IK_E'); SIM.tick(2)
fresh = lambda: min(pieces(F), key=lambda p: (p.o.x - bx) ** 2 + (p.o.y - by) ** 2)
RF = fresh(); ftop = RF.o.z + lua('function(k) return SIM.it(k).max[3] end')(F)
stand(RF.o.x, RF.o.y - 1); fo4_hold(W_); look_at(RF.o.x + 0.2, RF.o.y + 1.5, ftop); SIM.tick(3); SIM.key('IK_E'); SIM.release('IK_E'); SIM.tick(2)
fo4_hold(RD_); look_at(RF.o.x - 0.5, RF.o.y, ftop); SIM.tick(3); SIM.key('IK_E'); SIM.release('IK_E'); SIM.tick(2)
RF = fresh()
rel = lambda q, p: (round(q.o.x - p.o.x, 2), round(q.o.y - p.o.y, 2), round(q.o.z - p.o.z, 2))
w0, r0 = rel(near_(W_)[0], RF), rel(near_(RD_)[0], RF)
lua('function(p) local S = SIM.mod.state S.level, S.hold = 0, nil S.target = p end')(RF)
SIM.key('IK_E'); SIM.release('IK_E'); SIM.tick(2)
carrying = lua('function() local h = SIM.mod.state.hold return h and h.kind, h and h.carry and #h.carry end')()
stand(bx + 2, by - 6.4); look_at(bx + 2, by, Z); SIM.tick(3)
SIM.key('IK_E'); SIM.release('IK_E'); SIM.tick(2)
NF = min(pieces(F), key=lambda p: (p.o.x - bx - 2) ** 2 + (p.o.y - by) ** 2)
nw = [p for p in pieces(W_) if (p.o.x - NF.o.x) ** 2 + (p.o.y - NF.o.y) ** 2 < 16]
nr = [p for p in pieces(RD_) if (p.o.x - NF.o.x) ** 2 + (p.o.y - NF.o.y) ** 2 < 16]
check(carrying[0] == 'move' and carrying[1] == 2 and len(nw) == 1 and len(nr) == 1 and rel(nw[0], NF) == w0 and rel(nr[0], NF) == r0,
      'moving a floor carries what only it holds up, as it stood on it (carried %s; wall %s -> %s, radio %s -> %s)' % (carrying[1], w0, nw and rel(nw[0], NF), r0, nr and rel(nr[0], NF)))
# turning a held piece keeps it in place: it turns about its middle (or Fallout's P-WS-Rotation), not its model origin
ST = 'fo4_workshop_shackbalconystairs01'
stand(bx + 6, by - 12); fo4_hold(ST); look_at(bx + 6, by - 6, Z); SIM.tick(3)
mids = []
for yw in (0, 30, 90, 200):
    lua('function(y) SIM.mod.state.hold.yaw = y end')(yw); SIM.tick(2)
    m = lua('''function(k) local st = SIM.mod.state local it = SIM.it(k) local a = SIM.axes(st.place.yaw)
        local v = it.pivot or { it.cx, it.cy }
        return st.place.o.x + a[1] * v[1] + a[3] * v[2], st.place.o.y + a[2] * v[1] + a[4] * v[2], tostring(st.joined) end''')(ST)
    mids.append((round(m[0], 2), round(m[1], 2)))
spread = max(math.hypot(a[0] - mids[0][0], a[1] - mids[0][1]) for a in mids)
check(spread < 0.05, 'a held piece turns in place, about its middle (moved %.2f m over four turns: %s)' % (spread, mids))
# a door in a wall whose doorway point is tilted (Fallout's outer-cap door walls): it closes in the wall's plane
OW, SD = 'fo4_workshop_shackwalloutercap01door01', 'fo4_workshop_shackdoor01'
stand(bx + 14, by - 8); fo4_hold(OW); look_at(bx + 14, by - 2, Z); SIM.tick(3); SIM.key('IK_E'); SIM.release('IK_E'); SIM.tick(2)
Wp = min(pieces(OW), key=lambda p: (p.o.x - bx - 14) ** 2 + (p.o.y - by + 2) ** 2)
pt = lua('''function(k, p) for _, c in ipairs(SIM.it(k).connect) do
    if c.name:lower() == "p-door-dif2" then local a = SIM.axes(p.yaw) return p.o.x + a[1] * c.x + a[3] * c.y, p.o.y + a[2] * c.x + a[4] * c.y, p.o.z + c.z end end end''')(OW, Wp)
stand(pt[0], pt[1] - 3); fo4_hold(SD); look_at(pt[0], pt[1], pt[2]); SIM.tick(3)
rel = (st.place.yaw - Wp.yaw) % 180
check(bool(st.snapped) and st.snapped.key == OW and min(rel, 180 - rel) < 1, 'a door in a tilted-point doorway (outer-cap wall) closes in the wall (turned %.0f against it)' % ((st.place.yaw - Wp.yaw) % 360))
