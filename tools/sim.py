"""Offline run of the CET mod against stubbed engine APIs (lupa): a scripted build session, checking the logic and
catching Lua runtime errors. It proves nothing about the game side (spawning, colliders, input, drawing).
usage: python tools/sim.py
"""
import glob, os
import lupa.luajit21 as lupa                      # CET runs LuaJIT 2.1: test on the same VM
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(ROOT, 'bin', 'x64', 'plugins', 'cyber_engine_tweaks', 'mods', 'Homestead')
L = lupa.LuaRuntime(unpack_returned_tuples=True)
import tempfile
SETDIR = tempfile.mkdtemp(prefix='hs_sim_') + os.sep         # (the settings' files: CET keeps them in the mod's folder)
os.environ['HS_SIM_DIR'] = SETDIR
L.execute(r'''
MOD_DIR = ...
local ground = 180.4
local function vec(x, y, z, w) return { x = x or 0, y = y or 0, z = z or 0, w = w or 0 } end
Vector4 = { new = vec }
Vector3 = { new = function(x, y, z) return { x = x, y = y, z = z } end }
Quaternion = { new = function(i, j, k, r) return { i = i, j = j, k = k, r = r } end }
Transform = { new = function() return {} end }
EulerAngles = { new = function(r, p, y)
    return { yaw = y, ToQuat = function(self)
        local a = math.rad(y)
        return { yaw = y, i = 0, j = 0, k = math.sin(a / 2), r = math.cos(a / 2), Transform = function(_, v)
            return vec(v.x * math.cos(a) - v.y * math.sin(a), v.x * math.sin(a) + v.y * math.cos(a), v.z, v.w) end }
    end } end }
StatusEffectHelper = { ApplyStatusEffect = function() end, RemoveStatusEffect = function() end }   -- (fly holds V still)
CName = { new = function(s) return { hash = s } end }        -- CET: no readable text, like the game's name hashes
ResRef = { FromString = function(s) return s end }
local function ctor() return { new = function(t) return t or {} end } end
gameFxResource = ctor()
DynamicEntitySpec, entMeshComponent, entColliderComponent, physicsColliderBox = ctor(), ctor(), ctor(), ctor()
physicsFilterData, physicsQueryFilter, physicsSimulationFilter, entRenderHighlightEvent, MappinData = ctor(), ctor(), ctor(), ctor(), ctor()
TweakDBID = { new = function(s) return s end }
AIMoveToCommand, workWorkspotResourceComponent = ctor(), ctor()
Enum = { new = function(t, v) return v end }                  -- (an enum's value: its name)
EnumInt = function(e) return tonumber(e) end                  -- (a command's state: the mock's LiveNav hand-off sets 3, Cancelled)
WorldPosition = { new = function() local w = {} function w:SetVector4(v) w.v = v end return w end }
AIPositionSpec = { new = function() local p = {} function p:SetWorldPosition(w) p.w = w end return p end }
moveMovementType = { Walk = 0 }
gamedataMappinVariant = setmetatable({}, { __index = function(_, k) return k end })
gameinteractionsChoiceType = gamedataMappinVariant

-- dynamic entity system. SIM.defer = K: the game's deferred lifecycle - an entity made now attaches (onEntity; GetEntity
-- and GetTaggedIDs see it) K frames on, not in the call. Either way the lifetime guard's rule is held: the mod deletes
-- or teleports an entity only once it has attached and two frames have passed (SIM.violations says each that didn't)
local nextId, ents, unborn = 1, {}, {}
SIM = { ents = ents, events = {}, hub = nil, restricted = false, created = 0, ws = {}, frame = 0, violations = {}, cmds = {}, stacked = 0, meshes = 0, inits = 0 }
SIM.defer = 2                                    -- (deferred unless a check says otherwise: the people's checks run their
                                                 -- days without frames, so their devices would never attach)
local function byMod(level)                      -- (called from the mod's own files, not from these checks)
    local i = debug.getinfo(level + 1, "S")
    return i ~= nil and i.source:sub(1, 1) == "@" and i.source:find("Homestead", 1, true) ~= nil
end
local function guarded(what, id)                 -- (the mod touching an entity: has it settled?)
    if not byMod(3) then return end
    local e = ents[id.hash]
    local why = unborn[id.hash] and "before it attached" or (e and e.attached and SIM.frame - e.attached < 2 and "a frame after it attached")
    if why then table.insert(SIM.violations, string.format("%s %s %s (frame %d)", what, tostring(id.hash), why, SIM.frame)) end
end
local function entity(id, spec)
    local e = { id = id, spec = spec, comps = {}, pos = spec.position }
    local stash = tostring(spec.templatePath):find("stash.ent", 1, true) ~= nil
    function e:GetEntityID() return id end
    function e:GetClassName() return { value = stash and 'Stash' or spec.templatePath and 'entEntity' or 'NPCPuppet' } end
    if stash then                                  -- (the game's stash device: its own collider and icon slot)
        local function comp(cls, name) local c = { cls = cls, nm = name }
            function c:GetClassName() return { value = self.cls } end
            function c:GetName() return { value = self.nm } end
            function c:Toggle(on) self.on = on end
            return c end
        e.comps = { comp("entColliderComponent", "collider"), comp("entSlotComponent", "UI_Slots"), comp("entMeshComponent", "mesh") }
    end
    function e:GetAttitudeTowards() return "Neutral" end
    function e:GetWorldYaw() return e.yaw or 0 end
    function e:GetComponents() return self.comps end
    function e:GetWorldPosition() return e.pos end
    function e:GetWorldOrientation() return spec.orientation end
    function e:AddComponent(c) table.insert(self.comps, c)   -- (SIM.meshes: mesh components and collider boxes dressed
        SIM.meshes = SIM.meshes + (c.mesh and 1 or 0) + (c.colliders and #c.colliders or 0) end   -- on, all told)
    function e:FindComponentByName(n)            -- (found ones move and switch like the game's: calls recorded)
        for _, c in ipairs(self.comps) do if c.name and c.name.hash == n.hash then
            c.SetLocalPosition = c.SetLocalPosition or function(self, p) self.lp = p end
            c.SetLocalOrientation = c.SetLocalOrientation or function(self, q) self.lq = q end
            c.Toggle = c.Toggle or function(self, on) self.on = on end
            c.SetIntensity = c.SetIntensity or function() end
            c.ToggleLight = c.ToggleLight or function() end
            return c end end
    end
    function e:GetWorldTransform() local t = {}; function t:SetPosition(p) e.pos = p end; function t:SetOrientationEuler(r) e.yaw = r.yaw end; return t end
    function e:SetWorldTransform(t) end
    function e:QueueEvent(ev) table.insert(SIM.events, { id = id.hash, outline = ev.outlineIndex }) end
    function e:GetBodyType() return { value = spec.recordID and 'WomanAverage' or 'Undefined' } end
    function e:GetAIControllerComponent()        -- (a walk arrives at once; offNav: one sent off the navmesh. SIM.cmds: the
                                                 -- command each one is under - one that finishes when there is done at
                                                 -- once, another holds till cancelled; SIM.stacked: one sent over another)
        return { SendCommand = function(_, c) e.pos = c.movementTarget.w.v; SIM.walks = (SIM.walks or 0) + 1
                                              if c.ignoreNavigation ~= false then SIM.offNav = (SIM.offNav or 0) + 1 end
                                              if SIM.cmds[id.hash] then SIM.stacked = SIM.stacked + 1 end
                                              SIM.cmds[id.hash] = not c.finishWhenDestinationReached and c or nil end,
                 CancelCommand = function(_, c) if SIM.cmds[id.hash] == c then SIM.cmds[id.hash] = nil end end } end
    return e
end
local DES = {}
function DES:IsReady() return true end
function DES:CreateEntity(spec)
    local id = { hash = nextId }; nextId = nextId + 1
    local e = entity(id, spec)
    SIM.created = SIM.created + 1
    if SIM.defer and byMod(2) then unborn[id.hash] = { e = e, at = SIM.frame + SIM.defer } return id end   -- (the
                                                 -- checks' own: as streamed in from a save, there already)
    ents[id.hash], e.attached = e, SIM.frame
    SIM.init(e)                                  -- Entity/Initialize right away
    return id
end
function SIM.attach()                            -- (deferred: those due attach, at a frame's start)
    for h, u in pairs(unborn) do
        if SIM.frame >= u.at then unborn[h] = nil; ents[h], u.e.attached = u.e, SIM.frame; SIM.init(u.e) end
    end
end
function DES:DeleteEntity(id) guarded("delete", id); ents[id.hash], unborn[id.hash], SIM.off[id.hash] = nil, nil, nil; return true end
-- Codeware's DisableEntity / EnableEntity (sites.lua: settlements by distance): out, the entity goes and its state stays
-- (id, tags, spec: SIM.off) - GetTaggedIDs and IsTagged still see it; back in, a fresh entity at its spec's place,
-- attaching as a new one does (SIM.defer). The guard's rule held: disabled only once settled, enabled 2 frames after
-- its disable at the soonest (SIM.violations)
SIM.off = {}
function DES:DisableEntity(id)
    guarded("disable", id)
    local e = ents[id.hash]
    if not e then return false end
    ents[id.hash], SIM.off[id.hash], e.offAt = nil, e, SIM.frame
    return true
end
function DES:EnableEntity(id)
    local o = SIM.off[id.hash]
    if not o then return false end
    if byMod(2) and SIM.frame - o.offAt < 2 then table.insert(SIM.violations, string.format("enable %s a frame after its disable (frame %d)", tostring(id.hash), SIM.frame)) end
    SIM.off[id.hash] = nil
    local e = entity(id, o.spec)
    if SIM.defer then unborn[id.hash] = { e = e, at = SIM.frame + SIM.defer } else ents[id.hash], e.attached = e, SIM.frame; SIM.init(e) end
    return true
end
function DES:AssignTag(id, tag)
    local e = ents[id.hash] or SIM.off[id.hash] or (unborn[id.hash] and unborn[id.hash].e)
    if not e then return false end
    for _, t in ipairs(e.spec.tags) do if t.hash == tag.hash then return true end end
    table.insert(e.spec.tags, tag)
    return true
end
function DES:DeleteTagged(tag) for _, id in ipairs(self:GetTaggedIDs(tag)) do ents[id.hash] = nil end end
function DES:GetEntity(id) return ents[id.hash] end
function DES:GetTags(id) local e = ents[id.hash] or SIM.off[id.hash]; return e and e.spec.tags or {} end
SIM.tagChecks = 0
function DES:IsTagged(id, tag)
    SIM.tagChecks = SIM.tagChecks + 1
    local e = ents[id.hash] or SIM.off[id.hash]
    if not e then return false end
    for _, t in ipairs(e.spec.tags) do if t.hash == tag.hash then return true end end
    return false
end
function DES:GetTaggedIDs(tag)
    local out = {}
    for _, set in ipairs({ ents, SIM.off }) do
        for h, e in pairs(set) do for _, t in ipairs(e.spec.tags) do if t.hash == tag.hash then table.insert(out, e.id) end end end
    end
    table.sort(out, function(a, b) return a.hash < b.hash end)
    return out
end
function DES:IsPopulated(tag) return #self:GetTaggedIDs(tag) > 0 end

SIM.player = vec(4938, 1594, ground)
-- the world: flat ground plus one rock (a solid box) east of the zone centre
SIM.rock = { min = { 4938 + 15, 1594 - 5, ground }, max = { 4938 + 17, 1594 + 5, ground + 4 } }
function SIM.world(a, b)
    local best, bn = math.huge, nil
    local d = { b.x - a.x, b.y - a.y, b.z - a.z }
    if (a.z - ground) * (b.z - ground) <= 0 and a.z ~= b.z then
        best, bn = (a.z - ground) / (a.z - b.z), vec(0, 0, 1, 0)
    end
    local o, r = { a.x, a.y, a.z }, SIM.rock
    local tmin, tmax, ax, sg = 0, 1, 0, 0
    for i = 1, 3 do
        if math.abs(d[i]) < 1e-9 then
            if o[i] < r.min[i] or o[i] > r.max[i] then tmin = 2 end
        else
            local t1, t2 = (r.min[i] - o[i]) / d[i], (r.max[i] - o[i]) / d[i]
            local s = -1
            if t1 > t2 then t1, t2, s = t2, t1, 1 end
            if t1 > tmin then tmin, ax, sg = t1, i, s end
            if t2 < tmax then tmax = t2 end
        end
    end
    if tmin <= tmax and tmin <= 1 and tmin < best and ax > 0 then
        best = tmin
        bn = vec(ax == 1 and sg or 0, ax == 2 and sg or 0, ax == 3 and sg or 0, 0)
    end
    if not bn or best > 1 then return { vec(0, 0, 0, 0), vec(0, 0, 1, 0) } end
    return { vec(a.x + d[1] * best, a.y + d[2] * best, a.z + d[3] * best, 1), bn }
end
SIM.fwd = vec(0, 1, 0)
local cam = {}
function cam:GetActiveCameraForward() return SIM.fwd end
function cam:ProjectPoint(p) return vec(0.1, 0.1, 0, 1) end
Game = {
    GetDynamicEntitySystem = function() return DES end,
    GetPlayer = function() return { GetWorldPosition = function() return SIM.player end } end,   -- (the main menu has one too)
    GetSystemRequestsHandler = function() return { IsPreGame = function() return SIM.mainMenu == true end } end,
    GetCameraSystem = function() return cam end,
    GetMountedVehicle = function() return nil end,
    GetFxSystem = function() return { SpawnEffect = function() SIM.fx = (SIM.fx or 0) + 1 return { Kill = function() end } end } end,
    GetMappinSystem = function() return { RegisterMappin = function() return 1 end } end,
    GetWorkspotSystem = function() return { PlayInDeviceSimple = function(_, dev, npc) SIM.ws[npc:GetEntityID().hash] = dev end,
                                            IsActorInWorkspot = function(_, npc) return SIM.ws[npc:GetEntityID().hash] ~= nil end,
                                            GetExtendedInfo = function() return { isActive = true, entering = false, exiting = false } end,
                                            SendJumpCommandEnt = function(_, npc, id) SIM.jumps = SIM.jumps or {}; table.insert(SIM.jumps, id) end,
                                            SendFastExitSignal = function(_, npc) SIM.ws[npc:GetEntityID().hash] = nil end } end,
    GetTimeSystem = function() return { GetGameTime = function() return { Hours = function() return SIM.hour or 12 end } end } end,
    GetTeleportationFacility = function() return { Teleport = function(_, e, p, r)
        if e.GetEntityID then guarded("teleport", e:GetEntityID()) end
        e.pos = p; e.yaw = r.yaw; SIM.teleports = (SIM.teleports or 0) + 1 end } end,
}
-- ray: ground plane, from the camera 1.7 m above the player
Homestead = {
    CameraPos = function() return vec(SIM.player.x, SIM.player.y, SIM.player.z + 1.7, 1) end,
    Ray = function(a, b) return SIM.world(a, b)[1] end,
    RayHit = function(a, b) return SIM.world(a, b) end,
    TerrainBelow = function(p) return vec(p.x, p.y, ground, 1) end,       -- the sim's terrain is the flat ground
    Restrict = function(on) SIM.restricted = on end,
    Sound = function(n) SIM.sounds = SIM.sounds or {}; table.insert(SIM.sounds, n) end,
    InMenu = function() return SIM.inMenu == true end,
    Gizmo = function(on) SIM.gizmoOn = on end,
    Hint = function(action, label, show, hold, order) SIM.ghints = SIM.ghints or {}; SIM.ghints[action] = show and label or nil end,
    ScreenSize = function() return { X = 1920, Y = 1080 } end,
    CameraFOV = function() return 80 end,
    Sfx = function(id, ev, play, loop, vol) SIM.sfx = SIM.sfx or {}; table.insert(SIM.sfx, { ev = ev, play = play, loop = loop }) return true end,
    SfxForget = function() end,
}
GetDisplayResolution = function() return 1920, 1080 end
SIM.ui = {}
HomesteadUI = {
    Render = function(prompt, build, level, cats, cat, crumb, names, thumbs, item, detail, count, budget, key, toast, extra)
        assert(extra == nil, 'Render takes 14 arguments (CET: 15 at most)')
        SIM.ui = { prompt = prompt, hud = build, level = level, crumb = crumb, names = names, thumbs = thumbs, item = item,
                   detail = detail, key = key, toast = toast }
    end,
    Use = function(show, x, y, label, key) SIM.useUI = show and { x = x, y = y, label = label, key = key } or nil end,
    Gizmo = function(segs, cx, cy, label) SIM.gz = { n = #segs / 6, cx = cx, cy = cy, label = label } SIM.gzSegs, SIM.gzCx = segs, cx end,
    Target = function(name) SIM.targetName = name end,       -- (the looked-at piece's name: its own widget)
}
HomesteadImport = {                                          -- (the RED4ext plugin's natives)
    Start = function(mode) SIM.started, SIM.running = mode, true return true end,
    Running = function() return SIM.running == true end,
    Stop = function() local r = SIM.running SIM.running, SIM.stopped = false, true return r == true end,
    Path = function() return SIM.importer end,
    MouseSet = function(on) return false end,                -- (no game window here: the gizmo takes the restriction path)
    GameKeys = function() return "Reload|IK_R\nChoice2|IK_R\nToggleCrouch|IK_C\nJump|IK_Space\nChoice1_Hold|IK_F\nIconicCyberware|IK_E\nVisionHold|IK_Tab\nQuickMelee|IK_Q\nDodge|IK_LControl\n" end,
    MouseX = function() return 0 end, MouseY = function() return 0 end,
}
WorldTransform = { new = function()
    local t = {}
    function t:SetPosition(p) t.pos = p end
    function t:SetOrientationEuler(e) t.yaw = e.yaw end
    function t:SetOrientation(q) t.q = q end
    return t
end }
function GetSingleton(n) return { ToEulerAngles = function(_, q) return { yaw = q.yaw } end } end
local function yes() return true end                            -- (one function for every call: a new one each made garbage
local noop = setmetatable({}, { __index = function() return yes end })   -- the mod doesn't, and the garbage checks count it)
ImGui = noop
ImGuiCond, ImGuiCol, ImGuiWindowFlags = setmetatable({}, { __index = function() return 1 end }), setmetatable({}, { __index = function() return 1 end }), setmetatable({}, { __index = function() return 1 end })
local handlers, observers = {}, {}
function registerForEvent(n, f) handlers[n] = f end
function registerHotkey(id, label, f) SIM.hotkeys = SIM.hotkeys or {}; SIM.hotkeys[id] = f end
function Observe(c, m, f) observers[c .. "." .. m] = f end
function SIM.init(e) SIM.inits = SIM.inits + 1 local f = observers["HomesteadService.HomesteadEntity"]; if f then f(nil, e) end end
function SIM.key(k, shift)                -- a press; arrows are tapped (pressed and let go), other keys stay down until SIM.release
    observers["HomesteadService.HomesteadKey"](nil, k, true, shift or false)
    if k == "IK_Left" or k == "IK_Right" or k == "IK_Up" or k == "IK_Down" then observers["HomesteadService.HomesteadKey"](nil, k, false, false) end
end
function SIM.hold(k) observers["HomesteadService.HomesteadKey"](nil, k, true, false) end
function SIM.release(k) observers["HomesteadService.HomesteadKey"](nil, k, false, false) end
function SIM.mouse(dx, dy) observers["HomesteadService.HomesteadMouse"](nil, dx, dy) end
function SIM.tick(n) for _ = 1, n or 1 do SIM.frame = SIM.frame + 1; SIM.attach(); handlers.onUpdate(1 / 60) end end
function SIM.step() SIM.frame = SIM.frame + 1; SIM.attach(); SIM.mod.calls.frame() end   -- (a bare frame: a check's own loop)
function SIM.session()                           -- (a load: what isn't saved - a preview, the border's wall - is gone)
    for h, e in pairs(ents) do if e.spec.persistSpawn == false then ents[h] = nil end end
    observers["HomesteadService.HomesteadSession"](nil, true)
end
function SIM.handlers() return handlers end
package.path = MOD_DIR .. "/?.lua;" .. package.path
SIM.ns = { opts = {} }                         -- Native Settings UI (GetMod("nativeSettings")): records the options
do
    local NS = {}
    function NS.addTab(path, label) SIM.ns.tab = label end
    function NS.addSubcategory(path, label) end
    local function add(kind) return function(path, label, desc, ...)
        local o = { kind = kind, path = path, label = label, desc = desc, args = { ... } }
        local idx = ({ ... })[kind == "button" and 4 or kind == "selector" and 5 or 4]
        table.insert(SIM.ns.opts, o) return o end end
    NS.addSwitch, NS.addButton, NS.addSelectorString, NS.addKeyBinding, NS.addRangeInt = add("switch"), add("button"), add("selector"), add("key"), add("range")
    function NS.removeOption(o) for i, x in ipairs(SIM.ns.opts) do if x == o then table.remove(SIM.ns.opts, i) break end end end
    function NS.setOption(o, v) o.value = v end
    function GetMod(name) if name == "nativeSettings" then return NS end end
end
function SIM.opt(label)                       -- the option whose label starts so
    for _, o in ipairs(SIM.ns.opts) do if o.label:sub(1, #label) == label then return o end end
end
function SIM.importRow()                     -- the status line's button: Import, or Cancel while it runs
    for _, o in ipairs(SIM.ns.opts) do if o.kind == "button" and o.desc:sub(1, 23) == "Makes Homestead's piece" then return o end end
end
function SIM.press(label) local o = SIM.opt(label) local f = o.kind == "button" and o.args[3] or o.kind == "switch" and o.args[3] or o.kind == "range" and o.args[6] or o.args[4] return f end
HS_NATIVE = "only"                            -- the stashed Cyberpunk pieces, for these checks
HS_DIR = os.getenv("HS_SIM_DIR")
math.randomseed(7)                            -- (the same run every time)
do                                            -- strict globals: reading one that doesn't exist is an error (in game a nil
    local absent = { TweakDB = true, HS_NATIVE = true }   -- global fails only on the path that reads it); the mod writing one is noted
    SIM.globalWrites = {}
    setmetatable(_G, { __index = function(_, k) if absent[k] then return nil end error("undefined global " .. tostring(k), 2) end,
                       __newindex = function(t, k, v)
                           local i = debug.getinfo(2, "S")
                           if i and i.source:find("Homestead", 1, true) then SIM.globalWrites[#SIM.globalWrites + 1] = tostring(k) end
                           rawset(t, k, v)
                       end })
end
do local cn = CName; CName = nil                              -- at launch CET loads the mod before the game's types exist
    SIM.mod = dofile(MOD_DIR .. "/init.lua"); CName = cn end   -- (a CName at load time: "Mod Homestead failed to load", user 2026-10-03)
function SIM.it(key) for _, it in ipairs(require("catalog").items) do if it.key == key then return it end end end
function SIM.axes(yaw) local q = EulerAngles.new(0, 0, yaw):ToQuat(); local ex, ey = q:Transform(Vector4.new(1,0,0,0)), q:Transform(Vector4.new(0,1,0,0)); return { ex.x, ex.y, ey.x, ey.y } end
''', MOD.replace('\\', '/'))
SIM = L.globals().SIM
lua = L.eval
L.execute(r'''
-- LiveNav (the optional navmesh addon: modules/livenav.lua), mocked: every call counted (LN.n), its objects kept as
-- world boxes (LN.objs). Its navmesh, for the walking natives (Homestead.NavPoint / NavPath): the ground and the tops
-- of walkTop boxes, cut where a box stands in a body (BODY m round, from KNEE over the feet to HEAD). No routing: a way
-- is there when its end is on the navmesh (within 0.3 m). SIM.liveNav(false): not installed (reading LiveNav then throws, as in game)
local BODY, KNEE, HEAD, CLIMB = 0.15, 0.3, 1.8, 0.6
local LN = { n = {}, objs = {}, files = {}, traffic = {} }
local ffi = require("ffi")
rawset(_G, "LN", LN)
local function qmul(a, b) return { i = a.r * b.i + a.i * b.r + a.j * b.k - a.k * b.j, j = a.r * b.j - a.i * b.k + a.j * b.r + a.k * b.i,
    k = a.r * b.k + a.i * b.j - a.j * b.i + a.k * b.r, r = a.r * b.r - a.i * b.i - a.j * b.j - a.k * b.k } end
local function qrot(q, x, y, z) local t = qmul(qmul(q, { i = x, j = y, k = z, r = 0 }), { i = -q.i, j = -q.j, k = -q.k, r = q.r }) return t.i, t.j, t.k end
local function count(op) LN.n[op] = (LN.n[op] or 0) + 1 end
local function put(id, f, t, walk)                 -- (10 floats a box, in the transform's space)
    assert(type(id) == "string" and type(walk) == "boolean" and t.pos and t.q and #f % 10 == 0, "AddBoxes(id, floats, transform, walkTop)")
    local o, bs, r = t.pos, {}, 0
    for k = 1, #f, 10 do
        local q = qmul(t.q, { i = f[k + 6], j = f[k + 7], k = f[k + 8], r = f[k + 9] })
        local x, y, z = qrot(t.q, f[k], f[k + 1], f[k + 2])
        bs[#bs + 1] = { x = o.x + x, y = o.y + y, z = o.z + z, h = { f[k + 3], f[k + 4], f[k + 5] }, inv = { i = -q.i, j = -q.j, k = -q.k, r = q.r } }
        r = math.max(r, math.sqrt(x * x + y * y + f[k + 3] ^ 2 + f[k + 4] ^ 2))
    end
    LN.objs[id] = { boxes = bs, walk = walk, x = o.x, y = o.y, r = r + 1, floats = #f }
    return true
end
local MOCK = {
    Status = function() return "queued 0;" end,
    AddBoxes = function(id, f, t, walk) count("add") return put(id, f, t, walk) end,
    AddBoxesFile = function(id, path, t, walk)       -- (the file: little-endian float32, 10 a box; false: can't be read)
        local fh = io.open(path, "rb")
        if not fh then count("nofile") return false end
        local s = fh:read("*a")
        fh:close()
        local p, f = ffi.cast("const float*", s), {}
        for i = 0, #s / 4 - 1 do f[i + 1] = p[i] end
        count("file") LN.files[id] = f
        return put(id, f, t, walk)
    end,
    AddTrafficBoxes = function(id, f, t)             -- (traffic only: kept apart in LN.traffic, the navmesh never sees them)
        assert(type(id) == "string" and t.pos and t.q and #f > 0 and #f % 10 == 0, "AddTrafficBoxes(id, floats, transform)")
        count("traffic") LN.traffic[id] = { f = f, pos = t.pos, q = t.q }
        return true
    end,
    RemovePrefix = function(p) count("prefix") local n = 0
        for _, t in ipairs({ LN.objs, LN.traffic }) do for id in pairs(t) do if id:sub(1, #p) == p then t[id], n = nil, n + 1 end end end
        return n end,
    Rebuild = function() count("rebuild") return 1 end,
}
function SIM.liveNav(on) rawset(_G, "LiveNav", on and MOCK or nil) end
SIM.liveNav(true)
local function boxesNear(x, y, f)
    for _, o in pairs(LN.objs) do
        if (o.x - x) ^ 2 + (o.y - y) ^ 2 < o.r * o.r then for _, b in ipairs(o.boxes) do f(o, b) end end
    end
end
local function over(b, x, y, m)                    -- (x, y) over box b's footprint, grown m (its turn: a box's own)
    local lx, ly = qrot(b.inv, x - b.x, y - b.y, 0)
    return math.abs(lx) <= b.h[1] + m and math.abs(ly) <= b.h[2] + m
end
-- LiveNav's removal hand-off (RemoveObject, Release): whoever stands on the object (feet 0.6 m under to 0.3 m over a
-- box top) with a move command has it cancelled (its state 3, Cancelled) and falls to the ground under them
local function handoff(id)
    local o, n = LN.objs[id], 0
    for k, c in pairs(o and SIM.cmds or {}) do
        local e, on = SIM.ents[k], false
        for _, b in ipairs(e and o.boxes or {}) do
            local top = b.z + b.h[3]
            on = on or (over(b, e.pos.x, e.pos.y, 0) and e.pos.z >= top - 0.6 and e.pos.z <= top + 0.3)
        end
        if on then
            c.state, SIM.cmds[k], n = 3, nil, n + 1
            e.pos = Vector4.new(e.pos.x, e.pos.y, Homestead.TerrainBelow(Vector4.new(e.pos.x, e.pos.y, e.pos.z, 1)).z, 1)
        end
    end
    return n
end
function MOCK.RemoveObject(id) count("remove") handoff(id) LN.objs[id], LN.traffic[id] = nil, nil return true end
function MOCK.Release(id) count("release") return handoff(id) end
local function cut(x, y, s)                        -- a box in a body standing at height s on (x, y)
    local c = false
    boxesNear(x, y, function(o, b) c = c or (b.z + b.h[3] > s + KNEE and b.z - b.h[3] < s + HEAD and over(b, x, y, BODY)) end)
    return c
end
local function stand(x, y, z, r)                   -- the height one stands at on (x, y) near z, or nil (cut)
    local s = Homestead.TerrainBelow(Vector4.new(x, y, z + 1, 1)).z
    if math.abs(s - z) > r + CLIMB then s = nil end
    boxesNear(x, y, function(o, b)
        local top = b.z + b.h[3]
        if o.walk and math.abs(top - z) <= r + CLIMB and (not s or math.abs(top - z) < math.abs(s - z)) and over(b, x, y, 0) then s = top end
    end)
    if not s then return nil end
    return not cut(x, y, s) and s or nil
end
local function levels(x, y, z)                     -- every height one can step to on (x, y) from z (a tread up, the ground
    local near, out = {}, {}                       -- under it): Probe's flood climbs stairs by these (the boxes there
    boxesNear(x, y, function(o, b) if over(b, x, y, BODY) then near[#near + 1] = b; b.walk = o.walk end end)   -- looked up once)
    local function try(s)
        if math.abs(s - z) > CLIMB then return end
        for _, b in ipairs(near) do if b.z + b.h[3] > s + KNEE and b.z - b.h[3] < s + HEAD then return end end
        out[#out + 1] = s
    end
    try(Homestead.TerrainBelow(Vector4.new(x, y, z + 1, 1)).z)
    for _, b in ipairs(near) do if b.walk and over(b, x, y, 0) then try(b.z + b.h[3]) end end
    return out
end
Homestead.NavPoint = function(x, y, z, r)          -- (the nearest of the spot and rings round it, out to r)
    for ring = 0, 3 do
        for k = 0, ring > 0 and 7 or 0 do
            local a, d = k * math.pi / 4, r * ring / 3
            local s = stand(x + math.cos(a) * d, y + math.sin(a) * d, z, r)
            if s then return Vector4.new(x + math.cos(a) * d, y + math.sin(a) * d, s, 1) end
        end
    end
    return Vector4.new(x, y, z, 0)
end
-- LiveNav.Nearest: of every level one can stand at (the ground, a walkable top; not cut) on the spot and rings round it
-- out to ext.x, within ext.z up or down, the nearest p; ext <= 0: Probe's own 0.5 across, 1 up and down. W = 0: none
-- (p). Probe's ends are these, as LiveNav's. Counted in LN.nearest
function MOCK.Nearest(p, ext)
    LN.nearest = (LN.nearest or 0) + 1
    local r, h, best, bd = ext.x > 0 and ext.x or 0.5, ext.z > 0 and ext.z or 1, nil, math.huge
    for ring = 0, 3 do
        for k = 0, ring > 0 and 7 or 0 do
            local a, d = k * math.pi / 4, r * ring / 3
            local x, y = p.x + math.cos(a) * d, p.y + math.sin(a) * d
            local function try(s)
                local dd = d * d + (s - p.z) ^ 2
                if math.abs(s - p.z) <= h and dd < bd and not cut(x, y, s) then best, bd = Vector4.new(x, y, s, 1), dd end
            end
            try(Homestead.TerrainBelow(Vector4.new(x, y, p.z, 1)).z)
            boxesNear(x, y, function(o, b) if o.walk and over(b, x, y, 0) then try(b.z + b.h[3]) end end)
        end
    end
    return best or Vector4.new(p.x, p.y, p.z, 0)
end
Homestead.NavPath = function(a, b)                 -- (its end: the navmesh nearest b, a little off at most)
    local e = Homestead.NavPoint(b.x, b.y, b.z, 0.3)
    return e.w == 1 and { a, e } or {}
end
-- LiveNav.Probe (Detour on its navmesh): this one flooded from a on a 0.5 m grid (8 ways, a step of CLIMB at most to
-- every level there - a tread up, the ground below - so it climbs stairs (the nearest alone never left the ground),
-- within 3 m of the box round a and b): the plan length a -> b when b's reached, -1 when an end is off the navmesh,
-- else minus the length to where it got nearest b (a partial path: b on another island). Counted in LN.probes, not
-- LN.n (the world edits' counts)
function MOCK.Probe(a, b)
    LN.probes = (LN.probes or 0) + 1
    if a.x == b.x and a.y == b.y and a.z == b.z then           -- (on the navmesh? Counted; LN.down: still falling, so many asks)
        LN.selfProbes = (LN.selfProbes or 0) + 1
        if (LN.down or 0) > 0 then LN.down = LN.down - 1 return -1 end
    end
    local n0, D = LN.nearest, Vector4.new(0, 0, 0, 0)
    local pa, pb = MOCK.Nearest(a, D), MOCK.Nearest(b, D)
    LN.nearest = n0                                            -- (Probe's own: not counted)
    if pa.w ~= 1 or pb.w ~= 1 then return -1 end
    local G, M = 0.5, 3
    local x0, x1, y0, y1 = math.min(pa.x, pb.x) - M, math.max(pa.x, pb.x) + M, math.min(pa.y, pb.y) - M, math.max(pa.y, pb.y) + M
    local q, seen, best, bx, by, i = { { 0, 0, pa.z } }, {}, math.huge, pa.x, pa.y, 1
    while q[i] do
        local c = q[i]; i = i + 1
        local x, y = pa.x + c[1] * G, pa.y + c[2] * G
        local d = (x - pb.x) ^ 2 + (y - pb.y) ^ 2
        if d <= G * G and math.abs(c[3] - pb.z) <= CLIMB then return math.sqrt((pb.x - pa.x) ^ 2 + (pb.y - pa.y) ^ 2) end
        if d < best then best, bx, by = d, x, y end
        for dx = -1, 1 do
            for dy = -1, 1 do
                local nx, ny = x + dx * G, y + dy * G
                for _, s in ipairs(nx >= x0 and nx <= x1 and ny >= y0 and ny <= y1 and levels(nx, ny, c[3]) or {}) do
                    local k = (c[1] + dx) .. "," .. (c[2] + dy) .. "," .. math.floor(s * 2)
                    if not seen[k] then seen[k] = true; q[#q + 1] = { c[1] + dx, c[2] + dy, s } end
                end
            end
        end
    end
    return -math.max(math.sqrt((bx - pa.x) ^ 2 + (by - pa.y) ^ 2), 0.01)
end
''')
def count(tag): return lua('function(t) return #Game.GetDynamicEntitySystem():GetTaggedIDs(CName.new(t)) end')(tag)
def check(cond, what):
    print(('ok   ' if cond else 'FAIL ') + what)
    if not cond and not os.environ.get('KEEP_GOING'): raise SystemExit(1)   # (KEEP_GOING=1: every failure listed)
PERF = []                                                    # (reported at the end, not checked: per stretch of the run,
def perf(name):                                              # the most of each game call the mod made in one frame)
    PERF.append((name, lua('function() local t = {} for k, v in pairs(SIM.mod.calls.peak) do t[#t + 1] = k .. " " .. v end table.sort(t) SIM.mod.calls.reset() return table.concat(t, ", ") end')()))
def scenario(seed):                                         # a scenario's own random numbers (what ran before doesn't
    perf('to scenario %d' % seed)                           # steer it) and fresh call peaks
    lua('function(s) math.randomseed(s) end')(seed)
def ecalls(k, kind='last'):                                  # the game calls the mod counted (modules/engine.lua)
    return lua('function(k, w) return SIM.mod.calls[w][k] or 0 end')(k, kind)

import math
SIM.handlers()['onInit']()
SIM.session()
SIM.mod.prof(True)                                           # (each step's average / worst, reported at the end)
st = SIM.mod.state
EYE = 1.7
def look_at(x, y, z):
    ex, ey, ez = SIM.player.x, SIM.player.y, SIM.player.z + EYE
    dx, dy, dz = x - ex, y - ey, z - ez
    d = math.sqrt(dx * dx + dy * dy + dz * dz)
    SIM.fwd.x, SIM.fwd.y, SIM.fwd.z = dx / d, dy / d, dz / d
def stand(x, y): SIM.player.x, SIM.player.y = x, y
def pieces(key=None): return [p for p in st.pieces.values() if key is None or p.key == key]
def hints():                                                # the game's own list (Homestead.Hint): labels and actions
    g = lua('function() local o = {} for a, l in pairs(SIM.ghints or {}) do o[#o + 1] = l o[#o + 1] = a end return table.concat(o, "|") end')()
    return g.split('|') if g else []
def hold(key): SIM.key(key)
CATS = list(lua('''function() local _, _, c = SIM.mod.zone() return c end''')().values())   # the mod's tabs (Search first)
def to_tabs():                                      # Tab back up to the category tabs (not out)
    while st.level > 0: SIM.key('IK_Tab')
    SIM.tick(2)
def picked(): return SIM.mod.picked()               # (name, index, count) of the selected kid in the row
def menu_to(cat, path, key=None, app='default'):
    """walk the menu with its keys: back to the tabs, across to the category, down the path ("Roads/Large"), onto the item"""
    while st.level > 0: SIM.key('IK_Up')
    if cat not in CATS: cat, path = 'Night City', cat + '/' + path      # (Cyberpunk's own kinds: folders of one tab)
    want = CATS.index(cat) + 1
    while st.cat < want: SIM.key('IK_Right')
    while st.cat > want: SIM.key('IK_Left')
    for part in path.split('/'):
        SIM.key('IK_Down')
        while picked()[1] > 1: SIM.key('IK_Left')
        for _ in range(60):
            if picked()[0] == part: break
            SIM.key('IK_Right')
    if key:
        SIM.key('IK_Down')
        while picked()[1] > 1: SIM.key('IK_Left')
        for _ in range(200):
            if st.hold and st.hold.key == key and st.hold.app == app: break
            SIM.key('IK_Right')
    SIM.tick(10)                                      # the preview spawns once the pick settles
G = 3.0; ZX, ZY, Z = 4938, 1594, 180.4

SIM.tick(90)
check(count('Homestead.bench') == 0 and lua('function() return SIM.mod.zone().key end')() == 'none', 'no settlement until V founds one: no workbench, nowhere to build')
stand(ZX, ZY - 12); look_at(ZX, ZY, Z + 1.7); SIM.tick(2)       # (founded facing north: its plot centred 12 m ahead)
check(lua('function() return SIM.mod.found() end')(), 'found: a settlement where V stands, its workbench 3 m ahead')
SIM.tick(10)
check(count('Homestead.bench') == 1, "one workbench, the settlement's")
FIRST = lua('function() return SIM.mod.zone().key end')()          # (the first settlement: where all that follows is built)
_edge = lua('function() local z = SIM.mod.zone() return SIM.mod.sites.edge(z, { x = z.x + 200, y = z.y }), SIM.mod.sites.edge(z, { x = z.x + 50, y = z.y - 50 }) end')()
check(abs(_edge[0] - 150) < 1e-6 and _edge[1] == 0, "by distance: a settlement's area is its circle's box - 200 m from the centre is 150 m off its edge (%.1f), a point on it 0" % _edge[0])
bench = pieces('workbench')[0]
stand(bench.at.x, bench.at.y - 2); look_at(bench.at.x, bench.at.y, Z + 0.5)
SIM.tick(70)
check(st.nearBench and SIM.ui.prompt and SIM.ui.key == 'F', 'the [F] Workshop prompt shows at the workbench (key %s)' % SIM.ui.key)
lua('function() SIM.mod.keys.bind("hold", "IK_G") end')(); SIM.tick(2)
kg = SIM.ui.key
lua('function() SIM.mod.keys.bind("hold", "IK_F") end')(); SIM.tick(2)
check(kg == 'G' and SIM.ui.key == 'F', 'the workshop key rebound to G: the prompt says G, and F again once back (%s)' % kg)
perf('start')
SIM.key('IK_F'); SIM.tick(1)
check(st.build and SIM.restricted, 'tapping F at the workbench enters workshop mode')
perf('workshop entry (first)')
SIM.tick(60)
check(st.build, '...and keeping F down after the tap does not throw you out')
SIM.release('IK_F'); SIM.key('IK_Tab'); SIM.tick(2)
check(not st.build, 'Tab at the tabs leaves workshop mode')
SIM.hold('IK_R'); SIM.tick(5); SIM.key('IK_F'); SIM.release('IK_F'); SIM.tick(45); SIM.release('IK_R'); SIM.tick(1)
cw = (st.cmd is not None, st.build)
SIM.key('IK_R'); SIM.tick(45); SIM.release('IK_R'); SIM.tick(2)
check(cw == (True, False) and st.cmd is None and not st.build, 'R held, F tapped at the bench (workshop mode on): Command mode takes over, workshop mode left first (%s)' % (cw,))
# a key held when a menu opens: its release goes to the menu - counted as let go, nothing toggles by itself
stand(ZX + 10, ZY + 10); SIM.tick(2)
SIM.hold('IK_F'); SIM.tick(5); SIM.inMenu = True; SIM.release('IK_F'); SIM.tick(2); SIM.inMenu = False; SIM.tick(60)
check(not st.build and not st.fHeld, 'F held as a menu opens, let go in the menu: no workshop mode by itself')
# hold F anywhere in the zone
stand(ZX + 10, ZY + 10); look_at(ZX + 12, ZY + 14, Z); SIM.tick(3)
gh = lua('function() return SIM.ghints and SIM.ghints.Choice1_Hold end')()
check(not st.nearBench and gh == 'Workshop' and 'F' not in hints(), "in the zone, away from the bench: a hold-F Workshop hint in the game's own list (%s)" % gh)
SIM.key('IK_F'); SIM.tick(20)
check(not st.build, 'a short F press does nothing')
SIM.tick(30)
check(st.build, 'holding F 0.6 s enters workshop mode')
SIM.release('IK_F'); SIM.tick(1)
check(SIM.ui.hud and SIM.ui.level == 0 and 'Exit' in hints(), 'the menu is up at the category tabs')

# the menu: a tree (Structure > type > style > items), folders marked with their counts, no wrapping at the ends
def row(): return [SIM.ui.names[k] for k in range(1, len(SIM.ui.names) + 1)]
while st.cat < CATS.index('Structure') + 1: SIM.key('IK_Right')           # (Fallout's tabs come first)
SIM.key('IK_Down'); SIM.tick(1)
check(st.level == 1 and st.hold is None and SIM.ui.names[1] == 'Walls' and SIM.ui.thumbs[1].isdigit(),
      'Down opens Structure: its piece types, as folders with a count (%s, %s)' % (SIM.ui.names[1], SIM.ui.thumbs[1]))
check(row()[:5] == ['Walls', 'Doorways', 'Windows', 'Floors', 'Roofs'], 'every piece type is a folder, walls first (%s)' % ', '.join(row()))
SIM.key('IK_Left'); SIM.tick(1)
check(picked()[1] == 1, 'Left at the first folder stays there (no wrapping)')
SIM.key('IK_Down'); SIM.tick(1)
check(st.level == 2 and st.hold is None and row()[0] == 'Badlands' and 'Heywood' in row() and 'Walls' in SIM.ui.crumb, 'Down again: the styles walls come in (%s)' % ', '.join(row()))
SIM.key('IK_Down'); SIM.tick(1)
check(st.level == 3 and st.hold.key == 'wall' and 'Badlands' in SIM.ui.crumb, 'the Badlands folder holds its first wall (%s: %s)' % (SIM.ui.crumb, st.hold.key))
names = row()
check(names[0] == 'Badlands Wall' and 'Badlands Wall Blue' in names and 'Badlands Upper Wall' not in names, 'inside: the wall with its finishes; the upper twin is not a separate item (%s)' % ', '.join(names))
for _ in range(len(names) + 3): SIM.key('IK_Right')
check(picked()[1] == len(names), 'Right past the last item stops at the end (%d of %d)' % (picked()[1], len(names)))
SIM.key('IK_Up'); SIM.tick(1)
check(st.level == 2 and st.hold is None, 'Up goes back a folder and drops the piece')
# floors: a 2 x 1 slab
menu_to('Structure', 'Floors/Badlands', 'floor')
check(st.level == 3 and st.hold.key == 'floor', 'the Floors folder holds a Floor')
stand(ZX + 1.5, ZY - 6)
cell_c = (ZX + 1.5, ZY + 1.5)                                # the cell (0, 0)
look_at(cell_c[0] + 0.6, cell_c[1] + 0.4, Z); SIM.tick(3)
o = st.place.o
fl = [p for p in [None]][0]
it = lua('function(k) return nil end')
check(st.place.ok, 'the floor preview is valid on open ground')
SIM.key('IK_E'); SIM.tick(2)
f1 = pieces('floor')[0]
check(abs(f1.at.x - cell_c[0]) < 0.05 and abs(f1.at.y - cell_c[1]) < 0.05, 'the floor fills the grid cell under the aim (%.2f, %.2f)' % (f1.at.x, f1.at.y))
check(abs(f1.o.z - (Z + 0.02)) < 0.01, 'a first floor takes the ground level (%.2f)' % f1.o.z)
SIM.tick(2)
check(not st.place.ok and SIM.ui.toast in ('', None) or not st.place.ok, 'the same cell again shows invalid (already built)')
SIM.key('IK_E'); SIM.tick(1)
check(len(pieces('floor')) == 1 and 'Already' in (SIM.ui.toast or '') and SIM.sounds[len(SIM.sounds)] == 'ui_menu_item_crafting_fail', 'building on a built cell is refused, with the fail blip: %s' % SIM.ui.toast)
look_at(cell_c[0] + 3.0, cell_c[1] + 0.2, Z); SIM.tick(3)
SIM.key('IK_E'); SIM.tick(2)
check(len(pieces('floor')) == 2 and SIM.sounds[len(SIM.sounds) - 1] == 'lcm_fs_heavy_boots_concrete_land', 'a second floor in the next cell, with a dull thud')
pend = lua('''function() local S = SIM.mod.state local function n() local k = 0 for _ in pairs(S.pending) do k = k + 1 end return k end
    local before = n() SIM.mod.refresh() return before, n(), S.ghost ~= nil and S.pending[tostring(S.ghost.id.hash)] == nil end''')()
check(pend[0] == 2 and pend[1] == 0 and pend[2], 'placed: in the piece list at once, pending until a refresh lists it, then nothing left (the cheap refresh can run); the preview never was (%s)' % (pend,))
f2 = [p for p in pieces('floor') if p.id.hash != f1.id.hash][0]
check(abs(f2.o.z - f1.o.z) < 1e-6 and abs(f2.at.x - (cell_c[0] + 3)) < 0.05, 'it joins the first floor\'s level and cell grid')
wv = lua('''function(p) local S, M, D = SIM.mod.state, SIM.mod, Game.GetDynamicEntitySystem()
    local h, w0 = tostring(p.id.hash), S.world
    M.refresh(); M.refresh(true)
    local still = S.world == w0
    local get = D.GetTaggedIDs                                 -- (just spawned, the game not listing it yet)
    D.GetTaggedIDs = function(self, tag) local out = {} for _, id in ipairs(get(self, tag)) do if tostring(id.hash) ~= h then out[#out + 1] = id end end return out end
    S.pending[h] = S.info[h]
    M.refresh()
    local kept = S.byId[h] == p and S.world == w0
    D.GetTaggedIDs = get
    M.refresh()
    return still, kept, S.byId[h] == p and S.world == w0 and next(S.pending) == nil end''')(f2)
check(all(wv), 'the world version: a look that finds nothing changed leaves it; a piece of ours the game does not list yet stays in the list, the world unchanged (%s)' % (wv,))

# walls on the floor's edges
menu_to('Structure', 'Walls/Badlands', 'wall')
SIM.tick(20)
stand(cell_c[0], cell_c[1])                                   # standing on the floor, in cell (0, 0)
look_at(cell_c[0] + 0.2, cell_c[1] - 1.2, Z)                  # near its south edge (y = ZY)
SIM.tick(3)
check(st.place.ok, 'wall preview valid on the floor edge')
y_held = st.place.yaw
stand(cell_c[0], cell_c[1] - 4); look_at(cell_c[0] + 0.2, ZY, Z); SIM.tick(3)   # (round to its other side)
check(st.place.ok and st.place.yaw == y_held, 'walked round to its other side, the wall keeps its facing (%s, %s)' % (y_held, st.place.yaw))
stand(cell_c[0], cell_c[1]); look_at(cell_c[0] + 0.2, cell_c[1] - 1.2, Z); SIM.tick(3)
SIM.key('IK_E'); SIM.tick(2)
w1 = pieces('wall')[0]
wit = w1.it
face = lua('function(p) local a = SIM.axes(p.yaw) return p.o.x + a[1]*p.it.cx + a[3]*p.it.face, p.o.y + a[2]*p.it.cx + a[4]*p.it.face, a[3], a[4] end')(w1)
fx, fy, nx, ny = face
check(abs(fy - ZY) < 0.02 and abs(fx - cell_c[0]) < 0.02, 'the wall\'s outer face sits on the south edge line, centred on the cell (%.2f, %.2f)' % (fx, fy))
check(ny > 0.9, 'its outer face looks the way it was held (turn 0: +Y), not by the floor or the camera (normal %.2f, %.2f)' % (nx, ny))
check(abs(w1.o.z - f1.o.z) < 1e-6, 'it stands on the floor\'s level')
# hysteresis: an aim just over the diagonal toward the east edge keeps the south edge
look_at(cell_c[0] + 0.2, cell_c[1] - 1.2, Z); SIM.tick(2)
look_at(cell_c[0] + 0.9, cell_c[1] - 0.8, Z); SIM.tick(2)
key_before = (st.slot.mid.x, st.slot.mid.y)
check(abs(key_before[1] - ZY) < 0.01, 'a little past the corner diagonal, the slot sticks to the south edge')
look_at(cell_c[0] + 1.3, cell_c[1] - 0.1, Z); SIM.tick(2)
check(abs(st.slot.mid.x - (ZX + 3)) < 0.01, 'clearly nearer the east edge, it moves there')
SIM.key('IK_E'); SIM.tick(2)
w2 = [p for p in pieces('wall') if p.id.hash != w1.id.hash][0]
f2x, f2y, n2x, n2y = lua('function(p) local a = SIM.axes(p.yaw) return p.o.x + a[1]*p.it.cx + a[3]*p.it.face, p.o.y + a[2]*p.it.cx + a[4]*p.it.face, a[3], a[4] end')(w2)
check(abs(f2x - (ZX + 3)) < 0.02 and abs(n2x) > 0.9, 'an east wall on the edge between the two floors')
# flip
look_at(cell_c[0] - 1.2, cell_c[1] + 0.2, Z); SIM.tick(2)                  # the west edge
y0 = st.place.yaw
SIM.key('IK_LeftMouse'); SIM.release('IK_LeftMouse'); SIM.tick(2)
check((st.place.yaw - y0) % 360 == 180, 'LMB flips a wall (%.0f -> %.0f)' % (y0, st.place.yaw))
SIM.key('IK_LeftMouse'); SIM.release('IK_LeftMouse'); SIM.tick(1)
# the preview is redrawn on a turn alone
g = lua('function(h) return SIM.ents[h] end')(st.ghost.id.hash)
p0 = (g.pos.x, g.pos.y, g.pos.z)
SIM.key('IK_LeftMouse'); SIM.release('IK_LeftMouse'); SIM.tick(1)
check(g.yaw == st.place.yaw and abs(g.pos.x - st.place.o.x) < 1e-6 and abs(g.pos.y - st.place.o.y) < 1e-6, 'the preview follows a flip (yaw %s)' % g.yaw)
SIM.key('IK_LeftMouse'); SIM.release('IK_LeftMouse'); SIM.tick(1)

# upper storey: aim at the top of the south wall -> a floor on level + 4
menu_to('Structure', 'Floors/Badlands', 'floor')
stand(cell_c[0], cell_c[1] - 8)
look_at(cell_c[0], ZY + 0.05, f1.o.z + 4.0)                  # the wall's top edge
SIM.tick(3)
check(abs(st.place.o.z - (f1.o.z + 4.0)) < 1e-6, 'aiming at a wall top: the floor goes one storey up (%.2f)' % st.place.o.z)
g = lua('function(h) return SIM.ents[h] end')(st.ghost.id.hash)
p0 = (g.pos.x, g.pos.y, g.pos.z); y0 = st.place.yaw
SIM.key('IK_LeftMouse'); SIM.release('IK_LeftMouse'); SIM.tick(1)
check(g.yaw == st.place.yaw and (st.place.yaw - y0) % 360 == 90, 'LMB turns a floor 90 degrees and the preview follows')
# a wall a storey up: the ground wall swaps to its twin without the foundation lip, by itself
up_z = st.place.o.z
SIM.key('IK_E'); SIM.tick(2)
menu_to('Structure', 'Walls/Badlands', 'wall')
look_at(cell_c[0] + 0.2, ZY + 0.3, up_z + 0.05); SIM.tick(3)
check(abs(st.place.o.z - up_z) < 1e-6 and st.placeKey == 'wall_upper' and st.ghost.key == 'wall_upper', 'a wall on the upper floor becomes the upper wall (%s at +%.1f)' % (st.placeKey, st.place.o.z - Z))
look_at(cell_c[0] + 0.2, ZY - 1.2, Z); SIM.tick(3)
check(st.placeKey == 'wall', '...and back on the ground it is the ground wall again')
# aimed across the storey's height a frame at a time (the upper twin and back): no preview made or deleted on the
# way - one once the aim rests (before: one made and one deleted every frame)
SIM.tick(10); c0 = ecalls('create', 'total') + ecalls('create', 'n')
for k in range(20):
    if k % 2 == 0: look_at(cell_c[0] + 0.2, ZY + 0.3, up_z + 0.05)
    else: look_at(cell_c[0] + 0.2, ZY - 1.2, Z)
    SIM.tick(1)
c1 = ecalls('create', 'total') + ecalls('create', 'n')
SIM.tick(10)
check(c1 - c0 == 0 and st.ghost is not None and st.ghost.key == 'wall' and not lua('function() return #SIM.violations end')(),
      'aimed up a storey and back down a frame at a time: no preview made on the way (%d), one once the aim rests (%s; %s)' % (c1 - c0, st.ghost and st.ghost.key, lua('function() return table.concat(SIM.violations, "; ") end')() or 'no violations'))
menu_to('Structure', 'Floors/Badlands', 'floor')

# free placement
SIM.key('IK_Q'); SIM.tick(1)
check(st.free and "Snap Placement" in hints(), "Q switches to free placement")
y0 = st.hold.yaw
SIM.key('IK_RightMouse'); SIM.tick(30); SIM.release('IK_RightMouse'); SIM.tick(2)
check(abs(((y0 - st.hold.yaw) % 360) - 45) < 3, 'free: holding RMB turns smoothly, 90 deg/s (%.1f)' % ((y0 - st.hold.yaw) % 360))
# a piece turning about its own origin: the preview gets a hair of movement each turn so it is redrawn
menu_to('Furniture', 'Tables/Work Tables', 'table')
g = lua('function(h) return SIM.ents[h] end')(st.ghost.id.hash) if st.ghost else None
SIM.tick(3)
g = lua('function(h) return SIM.ents[h] end')(st.ghost.id.hash)
zs = []
SIM.key('IK_RightMouse')
for _ in range(6): SIM.tick(1); zs.append((round(g.pos.x, 4), round(g.pos.y, 4), round(g.pos.z, 4)))
SIM.release('IK_RightMouse')
check(g.yaw == st.place.yaw and len(set(zs)) >= 2, 'turning in place: the preview transform changes every frame (%d distinct)' % len(set(zs)))
check(st.hold.key == 'table', '(holding the Work Table)')
# free: the piece hovers in the middle of the view at a distance its size asks for, knowing nothing of the ground or
# other pieces; the wheel pushes it out / pulls it in along the line
def mid():
    return lua("""function() local st = SIM.mod.state; local it = SIM.it(st.hold.key); local a = SIM.axes(st.place.yaw)
        return st.place.o.x + a[1]*it.cx + a[3]*it.cy, st.place.o.y + a[2]*it.cx + a[4]*it.cy, st.place.o.z + (it.min[3] + it.max[3]) / 2 end""")()
def on_ray(x, y, z):
    ex, ey, ez = SIM.player.x, SIM.player.y, SIM.player.z + 1.7
    fx, fy, fz = SIM.fwd.x, SIM.fwd.y, SIM.fwd.z
    l = math.sqrt(fx * fx + fy * fy + fz * fz); fx, fy, fz = fx / l, fy / l, fz / l
    t = (x - ex) * fx + (y - ey) * fy + (z - ez) * fz
    return math.sqrt((ex + fx * t - x) ** 2 + (ey + fy * t - y) ** 2 + (ez + fz * t - z) ** 2), t
hold_d = lua('function() local it = SIM.it(SIM.mod.state.hold.key) return math.max(3, math.min(25, 2 + 1.2 * math.max(it.size[1], it.size[2], it.size[3]))) end')()
for name, target in (('the ground far off', (ZX + 7.2, ZY + 9.6, Z)), ('the ground close by', (ZX, ZY - 6, Z - 3)), ('a rock face', (ZX + 15, ZY + 1, Z + 2.5)), ('the sky', (ZX, ZY + 40, Z + 30))):
    stand(ZX, ZY - 10) if name != 'a rock face' else stand(ZX + 8, ZY)
    look_at(*target); SIM.tick(2)
    off, t = on_ray(*mid())
    check(st.place.ok and off < 0.05 and abs(t - hold_d) < 0.05, 'free, aimed at %s: the piece hovers mid-view, %.1f m out (%.2f off the line)' % (name, t, off))
stand(ZX, ZY - 10); look_at(ZX + 7.2, ZY + 9.6, Z); SIM.tick(2)
t0 = on_ray(*mid())[1]
SIM.key('IK_MouseWheelUp'); SIM.tick(1); SIM.key('IK_MouseWheelUp'); SIM.tick(1); SIM.key('IK_MouseWheelUp', True); SIM.tick(2)
off, t1 = on_ray(*mid())
want = t0
for big in (1, 1, 3): want += max(0.25, want * 0.15) * big   # (a notch: 15% of its distance, at least 0.25 m; Shift 3x)
check(abs(t1 - want) < 1e-6 and off < 0.05 and 'Nearer / Further' in hints(),
      'free: two wheel notches and a Shift notch push it out by a share of its distance (%.2f -> %.2f m, %.2f off the line)' % (t0, t1, off))
o_held = (st.place.o.x, st.place.o.y, st.place.o.z)
SIM.key('IK_E'); SIM.tick(2)
tables = pieces('table')
check(len(tables) == 1 and abs(tables[0].o.z - o_held[2]) < 1e-6, 'it is built right where it hovered')
check('cmn_generic_work_small_object_drop' in [SIM.sounds[k] for k in range(1, len(SIM.sounds) + 1)][-2:], 'a free piece lands with a small drop sound')
SIM.key('IK_MouseWheelDown', True); SIM.tick(1); SIM.key('IK_MouseWheelDown'); SIM.tick(1); SIM.key('IK_MouseWheelDown'); SIM.tick(1)
check(on_ray(*mid())[1] < t1 - 2, 'the wheel pulls it back in (%.2f m out)' % on_ray(*mid())[1])
lua('function() SIM.mod.state.dist = nil end')()
def base():
    return lua('function() local st = SIM.mod.state; local it = SIM.it(st.hold.key); local a = SIM.axes(st.place.yaw); return st.place.o.x + a[1]*it.base[1] + a[3]*it.base[2], st.place.o.y + a[2]*it.base[1] + a[4]*it.base[2], st.place.o.z + it.base[3] end')()
stand(ZX, ZY - 10); look_at(ZX, ZY + 40, Z + 30); SIM.tick(2)
SIM.key('IK_Q'); SIM.tick(3)
bx, by, bz = base()
check(not st.free and on_ray(*mid())[0] < 1e-3 and bz > Z + 0.1 and st.place.ok, 'grid, aimed at the sky: it hovers mid-view, its middle on the line as a free piece does (%.1f m out, %.3f off, base %.2f up)' % (on_ray(*mid())[1], on_ray(*mid())[0], bz - Z))
# snap: the wheel pulls the aim in short of the ground - the piece comes nearer, held mid-view on the line (as free)
stand(ZX - 8, ZY + 12); look_at(ZX - 2, ZY + 12, Z); SIM.tick(2)
bx, by, bz0 = base(); d0 = math.hypot(bx - (ZX - 8), by - (ZY + 12))
check(abs(bz0 - Z) < 1e-6, 'snap, aimed at the ground: it stands on it (base %.2f up)' % (bz0 - Z))
for _ in range(2): SIM.key('IK_MouseWheelDown', True); SIM.tick(1)
SIM.tick(1)
bx, by, bz = base(); d1 = math.hypot(bx - (ZX - 8), by - (ZY + 12))
check(not st.free and d1 < d0 - 1.5 and on_ray(*mid())[0] < 1e-3 and st.place.ok, 'snap: the wheel brings it nearer, held on the line (%.1f -> %.1f m, %.3f off)' % (d0, d1, on_ray(*mid())[0]))
for _ in range(30): SIM.key('IK_MouseWheelUp', True); SIM.tick(1)
SIM.tick(1)
bx, by, bz = base()
check(abs(math.hypot(bx - (ZX - 8), by - (ZY + 12)) - d0) < 0.3, 'snap: pushed past the ground it is aimed at, it stays where the aim meets it (%.1f m)' % math.hypot(bx - (ZX - 8), by - (ZY + 12)))
lua('function() SIM.mod.state.dist = nil end')()
SIM.key('IK_Q'); SIM.tick(2)
# free: no collision with placed pieces - aimed at the wall built earlier, it hovers mid-view, into the wall
fx0, fy0 = face[0], face[1]
stand(fx0, fy0 - 3); look_at(fx0, fy0, Z + 1.0); SIM.tick(3)
off, t = on_ray(*mid())
check(st.free and off < 0.05 and abs(t - hold_d) < 0.05, 'free, aimed at a placed wall: it hovers mid-view, into the wall, not pushed out (%.1f m)' % t)
menu_to('Structure', 'Floors/Badlands', 'floor')
SIM.key('IK_Q'); SIM.tick(1)
check(not st.free and st.hold.yaw % 90 == 0, 'Q back to the grid squares the turn up')

# back to the tabs; the bench: R refused, E grabs, E places
depth = st.level
for _ in range(depth): SIM.key('IK_Tab')
SIM.tick(1)
check(depth == 3 and st.level == 0 and st.build, 'Tab steps back a level at a time (items > kinds > styles > tabs)')
stand(bench.at.x, bench.at.y + 2.5); look_at(bench.at.x, bench.at.y, bench.at.z + 0.5); SIM.tick(3)
check(st.target is not None and st.target.key == 'workbench' and (SIM.targetName or '') != '', 'looking at the workbench names it (%s)' % SIM.targetName)
check('Move' in hints() and 'Scrap' not in hints(), 'hints: Move, no Scrap for the workbench')
SIM.key('IK_R'); SIM.tick(1)
check(count('Homestead.bench') == 1, "R doesn't scrap the workbench")
SIM.key('IK_E'); SIM.tick(90)
check(count('Homestead.bench') == 0 and count('Homestead.ghost') == 1, 'E grabs the workbench; no new one spawns while it is carried (%d, %d, %s)' % (count('Homestead.bench'), count('Homestead.ghost'), st.hold and st.hold.kind))
look_at(bench.at.x + 2, bench.at.y - 1, Z); SIM.tick(2); SIM.key('IK_E'); SIM.tick(2)
check(count('Homestead.bench') == 1, 'E puts it down in its new spot')

# the zone: the circle of RADIUS round the settlement's centre, twice the old 25 m half-size; no Boundary Posts
R = lua('function() return SIM.mod.C.RADIUS end')()
zc = lua('function() local z, C = SIM.mod.zone(), SIM.mod.C return z.x, z.y, C.inZone(z.x + C.RADIUS, z.y), C.inZone(z.x + C.RADIUS + 0.01, z.y), C.inZone(z.x - 35.3, z.y + 35.3), C.inZone(z.x - 35.4, z.y + 35.4) end')()
check(R == 50 and zc[2] and not zc[3] and zc[4] and not zc[5], 'the zone is a circle of 50 m (the old square: 25 m each way): a point on it is in, one 1 cm past it out, the same on the diagonal (%s)' % (zc[2:],))
check('Zone' not in CATS and not lua('function() return SIM.mod.C.byKey.boundary ~= nil end')(), 'no Boundary Post in the menu or the catalog the mod reads, no Zone tab (%s)' % CATS[-2:])
stand(ZX + 32, ZY + 20); look_at(ZX + 32, ZY + 23, Z); SIM.tick(3)
menu_to('Containers', 'Barrels & Tanks/Barrels', 'barrel')
look_at(ZX + 32, ZY + 23, Z); SIM.tick(3)
check(st.place.ok, 'a prop outside the old square but inside the circle is valid')
# aimed past the border: as in Fallout, a prop there is refused (it shows red), and follows the aim again when it comes back
stand(ZX + 28, ZY + 26); look_at(ZX + 38, ZY + 38, Z); SIM.tick(3)       # (the ground 53.7 m from the centre)
why = lua('function() local _, _, ok, why = SIM.mod.placement() return tostring(ok), why end')()
check(not st.place.ok and 'Outside' in str(why[1]), 'aimed past the border: a prop there is refused, outside the zone (%s)' % why[1])
look_at(ZX + 24, ZY + 26, Z); SIM.tick(3)
bx, by, bz = base()
check(st.place.ok and abs(bx - (ZX + 24)) < 0.3 and abs(by - (ZY + 26)) < 0.3, 'aim back inside: it follows the crosshair again (%.2f, %.2f)' % (bx - ZX - 24, by - ZY - 26))
look_at(ZX + 24, ZY + 26, Z + 40); SIM.tick(3)
bx, by, bz = base()
check(st.place.ok and on_ray(*mid())[0] < 1e-3 and bz > Z + 0.1, 'aimed at the sky near the border: held mid-view on the line, inside (%.3f off, base %.2f up)' % (on_ray(*mid())[0], bz - Z))

# the border: one entity with one mesh - the holographic wall round the circle -, in workshop mode only; no collider,
# not a piece: rays, the aim and placement go through it; nothing made or asked per frame while it stands
ring = lua('''function() local S = SIM.mod.state
    local ids = Game.GetDynamicEntitySystem():GetTaggedIDs(CName.new("Homestead.border"))
    local e = #ids == 1 and SIM.ents[ids[1].hash]
    if not e then return #ids end
    local c, cols = e.comps[1], 0
    for _, x in ipairs(e.comps) do cols = cols + (x.colliders and 1 or 0) end
    local z = SIM.mod.zone()
    return #ids, #e.comps, c.mesh, c.visualScale.x, c.visualScale.y, c.visualScale.z, cols, e.spec.persistSpawn, e.spec.alwaysSpawned,
        e.spec.position.x - z.x, e.spec.position.y - z.y, e.spec.position.z - z.z, c.castShadows, S.byId[tostring(ids[1].hash)] ~= nil, S.ring.id.hash == ids[1].hash
end''')()
check(isinstance(ring, tuple) and ring[:9] == (1, 1, 'homestead\\border.mesh', R, R, 60, 0, False, True) and ring[9:12] == (0, 0, -30) and ring[12] == 'Never' and not ring[13] and ring[14],
      'workshop mode: the border is one entity round the centre - one mesh scaled to the radius, 30 m below the ground to 30 m over it, no collider, no shadows, not saved, not a piece (%s)' % (ring,))
stand(ZX + 44, ZY); SIM.fwd.x, SIM.fwd.y, SIM.fwd.z = 1, 0, 0; SIM.tick(2)        # (6 m inside the wall, looking straight out through it)
thru = lua('function() local a = SIM.mod.aim() return a.piece == nil and a.point == nil end')()
stand(ZX + 53, ZY); look_at(ZX + 47, ZY, Z); SIM.tick(3)                # (3 m outside it, aiming at the ground 3 m inside)
bx, by, bz = base()
check(thru and st.build and st.place.ok and abs(bx - (ZX + 47)) < 0.3 and abs(by - ZY) < 0.3,
      'the wall stops no ray: the aim through it meets nothing, a prop aimed through it from outside stands where aimed (%s, %.2f, %.2f)' % (thru, bx - ZX - 47, by - ZY))
SIM.key('IK_Tab'); SIM.key('IK_Tab'); SIM.tick(1)
stand(ZX + 20, ZY); look_at(ZX + 20, ZY + 5, Z + 20); SIM.tick(3)
_c0 = (SIM.created, ecalls('create', 'total'), ecalls('delete', 'total'))
SIM.tick(120)
_c1 = (SIM.created, ecalls('create', 'total'), ecalls('delete', 'total'))
check(count('Homestead.border') == 1 and _c0 == _c1 and not lua('function() return SIM.handlers().onDraw ~= nil end')(),
      'the border shown, 120 frames: nothing made or deleted for it, no draw handler left (%s)' % (_c1,))
SIM.press('Settlement border')(False); SIM.tick(4)
off = count('Homestead.border')
SIM.press('Settlement border')(True); SIM.tick(4)
check(off == 0 and count('Homestead.border') == 1 and st.build, 'Settings > Building > Settlement border off: the wall goes at once, in workshop mode; on: back (%d, %d)' % (off, count('Homestead.border')))
to_tabs(); SIM.key('IK_Tab'); SIM.tick(4)
gone_ring = (st.build, count('Homestead.border'), st.ring is None)
stand(ZX + 20, ZY); SIM.key('IK_F'); SIM.tick(45); SIM.release('IK_F'); SIM.tick(4)
check(gone_ring == (False, 0, True) and st.build and count('Homestead.border') == 1, 'leaving workshop mode the wall goes; back in, one again (%s, %d)' % (gone_ring, count('Homestead.border')))

# R scraps a wall
stand(cell_c[0], cell_c[1] - 4); look_at(cell_c[0], ZY, Z + 1.5); SIM.tick(3)
n = count('Homestead'); tgt = st.target
_k0 = sorted(p.key for p in st.pieces.values())
SIM.key('IK_R'); SIM.tick(1)
_k1 = sorted(p.key for p in st.pieces.values())
gone_ = [k for k in set(_k0) if _k0.count(k) != _k1.count(k)]
check(tgt is not None and tgt.key == 'wall' and count('Homestead') == n - 1 and gone_ == ['wall'],
      'R scraps the wall under the crosshair; the upper floor stays, another wall holds it up too (%s)' % st.toast)
to_tabs(); SIM.key('IK_Tab'); SIM.tick(2)
check(not st.build and not SIM.restricted and count('Homestead.ghost') == 0, 'Tab at the tabs leaves workshop mode')

# the harvest: a rock from Nature, held down Right scrolls the group, then one is built
stand(ZX - 10, ZY + 10); SIM.key('IK_F'); SIM.tick(45); SIM.release('IK_F'); SIM.tick(1)
menu_to('Nature', 'Rocks/Canyon Rocks', None)
SIM.key('IK_Down'); SIM.tick(10)
first = st.hold.key
check(first.startswith('h_'), 'a harvested item is held (%s)' % first)
SIM.hold('IK_Right'); SIM.tick(60); SIM.release('IK_Right')
k1 = picked()[1]
SIM.tick(30)
k2 = picked()[1]
check(k1 >= 6 and k1 == k2, 'holding Right a second auto-repeats through the items (to %d), and stops on release' % k1)
check(st.ghost is not None and st.ghost.key == st.hold.key, 'the preview catches up once scrolling stops')
stand(ZX - 12, ZY + 12); look_at(ZX - 14, ZY + 14, Z); SIM.tick(3)
rock = st.hold.key
SIM.key('IK_E'); SIM.tick(2)
check(len(pieces(rock)) == 1, 'a harvested piece is built')
to_tabs()

# roads: 1 m snap, and a second straight latches onto the first one's end
menu_to('Roads', 'Large/Straight', 'road_l600')
stand(ZX - 6, ZY - 20); look_at(ZX - 6.3, ZY - 12.4, Z); SIM.tick(3)
SIM.key('IK_E'); SIM.tick(2)
r1 = pieces('road_l600')[0]
c1 = lua('function(p) return p.o.x + p.it.cx, p.o.y + p.it.cy end')(r1)
look_at(c1[0] - 6.8, c1[1] + 0.7, Z); SIM.tick(3)
check(st.place.ok and abs(st.place.o.x - (r1.o.x - 6)) < 1e-6 and abs(st.place.o.y - r1.o.y) < 1e-6,
      'a road aimed near the end of another latches onto it exactly (%.2f, %.2f from the first)' % (st.place.o.x - r1.o.x, st.place.o.y - r1.o.y))
look_at(c1[0] - 14, c1[1] + 4.3, Z); SIM.tick(3)
check(abs(st.place.o.x - round(st.place.o.x)) < 1e-6 and abs(st.place.o.x - (r1.o.x - 6)) > 1, 'away from it, it snaps to the 1 m grid instead')
to_tabs()

# people: the preview is the mannequin (our template), the placed one is the character record itself
menu_to('People', 'Main Characters', 'npc_judy')
check(st.hold.key == 'npc_judy' and st.ghost is not None, 'People: Judy is held, with a preview')
gspec = lua('function(h) return SIM.ents[h].spec end')(st.ghost.id.hash)
check(gspec.templatePath == 'homestead\\empty.ent' and gspec.recordID is None, 'the preview is a mannequin on our template')
stand(ZX - 8, ZY - 8); look_at(ZX - 10, ZY - 5, Z); SIM.tick(3)
SIM.key('IK_E'); SIM.tick(2)
judy = pieces('npc_judy')
spec = lua('function(h) return SIM.ents[h].spec end')(judy[0].id.hash) if judy else None
check(judy and spec.recordID == 'Character.Judy' and spec.templatePath is None and spec.persistSpawn, 'E places Judy from her record, saved with the game')
to_tabs()

# reload: pieces come back from their tags and transforms alone. The save is one from before the circle (2026-10-03):
# Boundary Posts, and a piece built out by them, 70 m from the centre - the posts go (once, logged), the piece stays its
# settlement's
lua('function() SIM.said, SIM.print = {}, print print = function(s) SIM.said[#SIM.said + 1] = tostring(s) SIM.print(s) end end')()
far = lua('''function() local C, z = SIM.mod.C, SIM.mod.zone()
    local id = C.spawnPiece("barrel", "default", { x = z.x + 70, y = z.y, z = 180.4 }, 0, false) C.index()
    for _, d in ipairs({ { -40, -20 }, { 30, -25 }, { 80, 30 }, { -30, 35 } }) do
        Game.GetDynamicEntitySystem():CreateEntity({ position = Vector4.new(z.x + d[1], z.y + d[2], 180.4, 1), orientation = EulerAngles.new(0, 0, 0):ToQuat(),
            persistSpawn = true, post = true, tags = { CName.new("Homestead"), CName.new("hs:boundary"), CName.new("hsapp:default") } })
    end
    return id.hash end''')()
SIM.tick(3)
posts0 = count('hs:boundary')
before = sorted((p.key, round(p.o.x, 2), round(p.o.y, 2), round(p.o.z, 2), p.yaw % 360) for p in st.pieces.values())
lua('function() for _, e in pairs(SIM.ents) do e.comps = {} end end')()
SIM.session()
lua('function() for _, e in pairs(SIM.ents) do SIM.init(e) end end')()
ok = lua('function() for _, e in pairs(SIM.ents) do if #e.comps == 0 and not e.spec.post then return false end end return true end')()
check(ok, 'after a reload every piece gets its meshes (and colliders) back from its tags')
lua('function() SIM.mod.state.info = {} end')()          # a fresh CET load: nothing cached
SIM.tagChecks = 0
SIM.tick(70)
per = SIM.tagChecks / max(len(st.pieces) + count('Homestead.part'), 1)
check(per < 40, 'finding what an entity is takes few tag checks with %d items (%.1f per piece or part)' % (lua('function() return #require("catalog").items end')(), per))
after = sorted((p.key, round(p.o.x, 2), round(p.o.y, 2), round(p.o.z, 2), p.yaw % 360) for p in st.pieces.values())
check(before == after and count('Homestead.bench') == 1, 'every piece is found again where it was (%d), one workbench' % len(after))
said_posts = lua('function() local n = 0 for _, s in ipairs(SIM.said) do if s:find("Boundary Posts", 1, true) then n = n + 1 end end return n end')
kept_far = [p for p in pieces('barrel') if p.id.hash == far and abs(p.o.x - (ZX + 70)) < 0.01]
check(posts0 == 4 and count('hs:boundary') == 0 and len(kept_far) == 1 and said_posts() == 1 and st.pieces[len(st.pieces)] is not None,
      "a save with Boundary Posts: its %d posts are deleted at the load, logged once (%d); the barrel 70 m out, past the circle, is still the settlement's (%d)" % (posts0, said_posts(), len(kept_far)))
SIM.session(); SIM.tick(70)
check(said_posts() == 1 and len([p for p in pieces('barrel') if p.id.hash == far]) == 1, 'the next load: no posts left, nothing logged again, the far barrel still there (%d)' % said_posts())
lua('function(h) local S = SIM.mod.state SIM.mod.C.removePiece(S.byId[tostring(h)]) SIM.mod.C.index() end')(far); SIM.tick(4)
# a save from 0.1 can hold two workbenches: one is removed
lua('function() local spec = { position = Vector4.new(4930, 1580, 180.4, 1), orientation = EulerAngles.new(0,0,0):ToQuat(), tags = { CName.new("Homestead"), CName.new("hs:workbench"), CName.new("hsapp:default"), CName.new("Homestead.bench") } } Game.GetDynamicEntitySystem():CreateEntity(spec) end')()
SIM.tick(70)
check(count('Homestead.bench') == 1, 'an extra workbench is removed')
# the pop-in (2026-10-03): every entity of ours is always spawned - otherwise Codeware leaves it to the game's population
# system, which despawned pieces V wasn't looking at and spawned them again in sight, late. A piece saved before (no
# "hsas" tag) is made again where it stands, once, never in workshop mode
check(lua("""function() for _, e in pairs(SIM.ents) do local mine = false
    for _, t in ipairs(e.spec.tags or {}) do mine = mine or t.hash == "hsv2" end
    if mine and e.spec.alwaysSpawned ~= true then return false end end return true end""")(), 'every piece, part and preview the mod made is always spawned')
def old_piece(key, x, y):                                    # (as a save from before the fix streams it in)
    return lua("""function(k, x, y) return Game.GetDynamicEntitySystem():CreateEntity({ position = Vector4.new(x, y, 180.4, 1),
        orientation = EulerAngles.new(0, 0, 90):ToQuat(), tags = { CName.new("Homestead"), CName.new("hs:" .. k), CName.new("hsapp:default") } }).hash end""")(key, x, y)
def at_spot(key, x, y): return [p for p in pieces(key) if abs(p.o.x - x) < 0.01 and abs(p.o.y - y) < 0.01]
lua('function() SIM.said = {} end')()                        # (print is caught since the reload above)
SIM.mod.build(); h_old = old_piece('floor', ZX + 9, ZY + 9); SIM.mod.refresh(); SIM.tick(10)
kept = [p.id.hash for p in at_spot('floor', ZX + 9, ZY + 9)] == [h_old]
SIM.mod.exit(); SIM.tick(10)
now = at_spot('floor', ZX + 9, ZY + 9)
spec = lua('function(h) local s = SIM.ents[h] and SIM.ents[h].spec if not s then return "gone" end local t = false for _, x in ipairs(s.tags) do t = t or x.hash == "hsas" end return tostring(s.alwaysSpawned) .. " " .. tostring(t) end')(now[0].id.hash) if now else 'none'
gone = lua('function(h) return SIM.ents[h] == nil end')(h_old)
SIM.tick(10)
again = [p.id.hash for p in at_spot('floor', ZX + 9, ZY + 9)] == [now[0].id.hash] if now else False
said = lua('function() print = SIM.print local n = 0 for _, l in ipairs(SIM.said) do if l:find("made 1 pieces again", 1, true) then n = n + 1 end end return n end')()
check(kept and len(now) == 1 and now[0].yaw % 360 == 90 and spec == 'true true' and gone and again and said == 1,
      'a piece saved streamed (no hsas tag): kept as it is in workshop mode (%s); out of it made again in place, always spawned and tagged (%d, yaw %s, %s), the old one gone (%s), only once (%s), logged once (%d)' %
      (kept, len(now), now[0].yaw if now else None, spec, gone, again, said))
lua('function(h) local S = SIM.mod.state for _, p in ipairs(S.pieces) do if p.id.hash == h then SIM.mod.C.removePiece(p) end end SIM.mod.C.index() end')(now[0].id.hash); SIM.tick(3)

look_at(ZX, ZY + 50, Z + 1.7 + EYE); SIM.tick(30)             # (frames a removed check ran: later scenarios count them)

# Fallout 4 pieces snap to each other through their connect points (point onto point of the same name, facing opposite)
def fo4_hold(key):
    lua('function(k) local S = SIM.mod.state if not S.build then SIM.mod.build() end S.free = false S.level = 1 S.hold = { kind = "new", key = k, app = "default", yaw = 0, flip = false, t = 1 } end')(key)
def held_yaw(y): lua('function(y) SIM.mod.state.hold.yaw = y end')(y)
def clear(x, y, r=12):                                       # a clear site: what earlier checks built there goes
    lua('''function(x, y, r) local d = Game.GetDynamicEntitySystem()
        for h, e in pairs(SIM.ents) do local q = e.spec.position
            if q and (q.x - x) ^ 2 + (q.y - y) ^ 2 < r * r and not d:IsTagged(e.id, CName.new("Homestead.bench")) then d:DeleteEntity(e.id) end end
        SIM.mod.refresh() end''')(x, y, r)
def put(key, x, y, z, yaw=0):                                # a piece standing exactly there (as the game streams one in); refresh after
    lua('''function(k, x, y, z, yaw) Game.GetDynamicEntitySystem():CreateEntity({ position = Vector4.new(x, y, z, 1),
        orientation = EulerAngles.new(0, 0, yaw):ToQuat(), alwaysSpawned = true, tags = { CName.new("Homestead"), CName.new("hs:" .. k), CName.new("hsapp:default"), CName.new("hsas") } }) end''')(key, x, y, z, yaw)
def refresh(): lua('function() SIM.mod.refresh() end')()
def snap():                                                  # snapped?, origin x, y, z, yaw, how many pieces it joins
    return lua('''function() local S = SIM.mod.state local n = 0 for _ in pairs(S.joined or {}) do n = n + 1 end
        return S.snapped ~= false and S.snapped ~= nil, S.place.o.x, S.place.o.y, S.place.o.z, S.place.yaw % 360, n end''')()
def spot_for(key, name, n, tx, ty, yaw):                     # where to aim so the held piece's n-th point of that name is at tx, ty
    return lua('''function(k, name, n, tx, ty, yaw) local it = SIM.it(k) local v, a, m = it.pivot or { it.cx, it.cy }, SIM.axes(yaw), 0
        for _, c in ipairs(it.connect) do if c.name == name then m = m + 1 if m == n then
            local dx, dy = c.x - v[1], c.y - v[2] return tx - a[1] * dx - a[3] * dy, ty - a[2] * dx - a[4] * dy end end end end''')(key, name, n, tx, ty, yaw)
def hold_at(key, x, y, z, yaw, eye):                         # held with its middle where it would be with its origin at
    m = lua("""function(k, x, y, z, yaw) local it = SIM.it(k) local v, a = it.pivot or { it.cx, it.cy }, SIM.axes(yaw)   # x, y, z
        return x + a[1] * v[1] + a[3] * v[2], y + a[2] * v[1] + a[4] * v[2], z + (it.min[3] + it.max[3]) / 2 end""".replace('#', '--'))(key, x, y, z, yaw)
    d = lua('function(k) return SIM.mod.C.holdDepth(SIM.it(k)) end')(key)   # (V on eye's bearing from it, as far off as Fallout
    dz = m[2] - (SIM.player.z + EYE)                             # holds it - twice its radius, 300 units at least - looking at it)
    d = max(d, abs(dz) + 0.05); L = math.sqrt(d * d - dz * dz)
    bx, by = eye[0] - m[0], eye[1] - m[1]; bl = math.hypot(bx, by) or 1
    if bl < 1e-6: bx, by, bl = 0, -1, 1
    stand(m[0] + bx / bl * L, m[1] + by / bl * L); fo4_hold(key); held_yaw(yaw)
    lua('function(d) SIM.mod.state.dist = d end')(d)
    look_at(*m); SIM.tick(3)
    r = lua('function() local _, _, ok, why = SIM.mod.placement() return ok, why end')()
    lua('function() SIM.mod.state.dist = nil end')()
    return snap(), r[0], r[1]
def aim_mid(key, x, y, z, yaw=0, frm=None):                  # held with its middle over x, y, its base at z, V looking from frm
    o = lua('function(k, x, y, z, yaw) local o = SIM.mod.C.originFromAnchor(SIM.it(k), { x = x, y = y, z = z }, yaw) return o.x, o.y, o.z end')(key, x, y, z, yaw)
    return hold_at(key, o[0], o[1], o[2], yaw, frm or (x, y - 8))
def pt_at(k, n, x, y, z, yaw):                               # the origin that puts its point named n at x, y, z, turned yaw
    return lua("""function(k, n, x, y, z, yaw) for _, c in ipairs(SIM.it(k).connect) do if c.name:lower() == n:lower() then local a = SIM.axes(yaw)
        return x - a[1] * c.x - a[3] * c.y, y - a[2] * c.x - a[4] * c.y, z - c.z end end end""")(k, n, x, y, z, yaw)
def pt_of(k, n, x, y, z, yaw):                               # where its point named n is, the piece at x, y, z turned yaw
    return lua("""function(k, n, x, y, z, yaw) for _, c in ipairs(SIM.it(k).connect) do if c.name:lower() == n:lower() then local a = SIM.axes(yaw)
        return x + a[1] * c.x + a[3] * c.y, y + a[2] * c.x + a[4] * c.y, z + c.z end end end""")(k, n, x, y, z, yaw)
def hold_depth(k): return lua('function(k) return SIM.mod.C.holdDepth(SIM.it(k)) end')(k)
def pair_pose(kb, nb, ib, ka, a, na, ia):                     # the origin and turn that put B's ib-th point named nb on
    return lua("""function(kb, nb, ib, ka, ax, ay, az, ayaw, na, ia)     -- A's ia-th named na (A at a: x, y, z, yaw), facing opposite
        local function nth(k, n, i) local m = 0 for _, c in ipairs(SIM.it(k).connect) do if c.name == n then m = m + 1 if m == i then return c end end end end
        local ca, cb, A = nth(ka, na, ia), nth(kb, nb, ib), SIM.axes(ayaw)
        local wx, wy, wz = ax + A[1] * ca.x + A[3] * ca.y, ay + A[2] * ca.x + A[4] * ca.y, az + ca.z
        local yaw = (ayaw + ca.yaw + 180 - cb.yaw) % 360
        local B = SIM.axes(yaw)
        return wx - B[1] * cb.x - B[3] * cb.y, wy - B[2] * cb.x - B[4] * cb.y, wz - cb.z, yaw end""")(kb, nb, ib, ka, *a, na, ia)
E = 3.6576                                                   # (a shack floor's side)
fo4_in = lua('function() return SIM.it("fo4_workshop_shackmidfloor01") ~= nil end')()
check(fo4_in, 'the Fallout shack pieces are in the catalog (their keys: fo4_ + the record name)')
if fo4_in:
    clear(ZX - 12, ZY + 12)
    if os.environ.get('BENCH'):                               # (BENCH=1: grid-mode placement timing over a floor grid, then stop)
        exec(open(os.path.join(ROOT, 'tools', 'bench_grid.py'), encoding='utf-8').read())
        raise SystemExit(0)
    stand(ZX - 12, ZY + 4); fo4_hold('fo4_workshop_shackmidfloor01'); look_at(ZX - 12, ZY + 12, Z); SIM.tick(3)
    check(st.place.ok and not st.snapped, 'a Fallout floor with nothing near: on the ground at the crosshair')
    SIM.key('IK_E'); SIM.tick(2)
    A = pieces('fo4_workshop_shackmidfloor01')[0]
    ax_, ay_, az_ = A.o.x, A.o.y, A.o.z
    stand(ax_ - 0.5, ay_)                                     # (on the first floor, facing its east edge)
    fo4_hold('fo4_workshop_shackmidfloor01'); look_at(ax_ + 1.6, ay_ + 0.3, az_); SIM.tick(3)
    o = st.place.o
    check(st.snapped and abs(o.x - (ax_ + 3.6576)) < 1e-3 and abs(o.y - ay_) < 1e-3 and abs(o.z - az_) < 1e-3 and st.place.yaw % 360 == 0,
          'a second floor aimed at the east edge of the first snaps on beside it, edge to edge (%.3f, %.3f)' % (o.x - ax_, o.y - ay_))
    # the snap points shown (a Building setting, off by default): the built floor's points in cyan, the one snapped to
    # yellow, the held floor's own green; off again when the setting goes
    SIM.gz = None
    SIM.press('Show snap points')(True); SIM.tick(2)
    dots = lua('function() local n = { [1] = 0, [3] = 0, [5] = 0 } for i = 5, #SIM.gzSegs, 6 do n[SIM.gzSegs[i]] = (n[SIM.gzSegs[i]] or 0) + 1 end return n[5], n[3], n[1], SIM.gzCx end')()
    check(SIM.gz is not None and dots[0] >= 2 and dots[1] == 2 and dots[2] >= 2 and dots[3] == -1,
          'snap points shown: the built floor\'s in cyan, the one snapped to yellow, the held floor\'s own green, no cursor (%s)' % (dots,))
    SIM.press('Show snap points')(False); SIM.tick(2)
    check(SIM.gz is not None and SIM.gz.n == 0, 'snap points off again: the lines cleared (%s)' % (SIM.gz and SIM.gz.n,))
    # aimed past the edge, where the new floor goes (its middle at the crosshair, a point of it near the edge's):
    # the same spot however it is held, at the held turn; turned 30 it snaps square (0), turned 50 the other way (90)
    held = []
    for y_, sx_, sy_ in ((0, -0.5, 0), (90, -0.5, 0), (90, 6, 0.3), (180, 6, 0.3), (270, 6, -0.3)):   # (from either side)
        s = hold_at('fo4_workshop_shackmidfloor01', ax_ + E - 0.16, ay_ + 0.2, az_, y_, (ax_ + E + sx_, ay_ + sy_ * 20))[0]; held.append((y_, s[0], round(s[1] - ax_, 3), round(s[2] - ay_, 3), s[4]))
    check(all(s and abs(x - E) < 1e-3 and abs(y) < 1e-3 and abs(yw - y_) < 1e-6 for y_, s, x, y, yw in held),
          'a floor aimed past the east edge of another snaps on beside it as it is held, whichever way and side (held, snapped, x, y, yaw: %s)' % held)
    turned = []
    for y_, n_, want in ((30, 3, 0), (50, 1, 90)):            # (its point that comes to the edge: the west one, the north one)
        held_yaw(y_); sx, sy = spot_for('fo4_workshop_shackmidfloor01', 'P-Floor', n_, ax_ + 1.829 + 0.1, ay_ + 0.1, y_)
        aim_mid('fo4_workshop_shackmidfloor01', sx, sy, az_ - 0.2, y_, (ax_ + 9, ay_))
        s = snap(); turned.append((y_, s[0], round(s[1] - ax_, 3), round(s[2] - ay_, 3), s[4]))
    check(all(s and abs(x - E) < 1e-3 and abs(y) < 1e-3 and abs(yw - w) < 1e-6 for (y_, s, x, y, yw), (_, _, w) in zip(turned, ((30, 3, 0), (50, 1, 90)))),
          'held turned 30 it snaps square (0), turned 50 the other way (90): the pair nearest where it is held (%s)' % turned)
    held_yaw(0)
    hold_at('fo4_workshop_shackwallflat03', ax_ + 0.3, ay_ + E + 0.3, az_, 0, (ax_, ay_ + 12)); SIM.tick(1)   # (its floor point by the north edge's)
    o, yw = st.place.o, st.place.yaw
    check(st.snapped and abs(o.x - ax_) < 1e-3 and abs(o.y - ay_) < 1e-3 and abs(o.z - az_) < 1e-3 and abs(yw - 180) < 1e-6,
          "a wall held facing out at a lone floor's north edge (180 off what the edge takes): turned to fit, on that edge, as in Fallout (yaw %.0f)" % yw)
    held_yaw(180); SIM.tick(3)
    o, yw = st.place.o, st.place.yaw
    check(st.snapped and abs(o.x - ax_) < 1e-3 and abs(o.y - ay_) < 1e-3 and abs(o.z - az_) < 1e-3 and abs(yw - 180) < 1e-6,
          'held facing in, it stands on that edge (yaw %.0f)' % yw)
    SIM.key('IK_E'); SIM.tick(2)
    hold_at('fo4_workshop_shackmidroof01', ax_ + 0.2, ay_ - 0.2, az_, 0, (ax_, ay_ - 9)); SIM.tick(1)   # (over the floor, by the wall's top)
    o = st.place.o
    check(st.snapped and abs(o.x - ax_) < 1e-3 and abs(o.y - ay_) < 1e-3 and abs(o.z - az_) < 1e-3,
          'a roof aimed at the top of the wall sits on it, over the same floor (%.3f, %.3f, %.3f)' % (o.x - ax_, o.y - ay_, o.z - az_))
    sp_ = pair_pose('fo4_workshop_shackbalconystairs01', 'P-Balcony01', 1, 'fo4_workshop_shackmidfloor01', (ax_, ay_, az_, 0), 'P-Balcony01-Dif', 3)
    hold_at('fo4_workshop_shackbalconystairs01', sp_[0] + 0.2, sp_[1] + 0.2, sp_[2], sp_[3], (sp_[0] + 6, sp_[1] - 3)); SIM.tick(1)
    check(st.snapped, 'stairs aimed at a balcony point of the floor snap to it')
    hold_at('fo4_workshop_shackmidfloor01', ax_ + E + 0.2, ay_ + 0.1, az_, 0, (ax_ + E, ay_ - 8)); SIM.tick(1); SIM.key('IK_E'); SIM.tick(2)
    east = [p for p in pieces('fo4_workshop_shackmidfloor01') if abs(p.o.x - (ax_ + 3.6576)) < 1e-3 and abs(p.o.y - ay_) < 1e-3]
    hold_at('fo4_workshop_shackmidfloor01', ax_ + E + 0.2, ay_ + 0.1, az_, 0, (ax_ + E, ay_ - 8)); SIM.tick(1)
    o = st.place.o
    taken = abs(o.x - (ax_ + 3.6576)) < 0.05 and abs(o.y - ay_) < 0.05 and abs(o.z - az_) < 0.05
    check(len(east) == 1 and not (taken and st.place.ok), 'snap mode: an edge that already has a floor is not snapped onto again (%.2f, %.2f, ok %s)' % (o.x - ax_, o.y - ay_, st.place.ok))
    SIM.key('IK_Q'); SIM.tick(3)
    check(st.free and st.place.ok, 'free placement: into other pieces is fine (no check)')
    SIM.key('IK_Q'); SIM.tick(2)                                # (back to snapping)
    # Fallout's snapping, case by case, on a site of its own (the pieces set down exactly)
    SF, SW, SU, SB, SS = ('fo4_workshop_shack' + k for k in ('midfloor01', 'wallflat03', 'midfloortoroof01', 'balconyfloor01', 'balconystairs01'))
    SX, SY, FZ = ZX + 2, ZY + 24, Z + 0.2                      # (a floor on the ground: its top, where its points are)
    lua('function() SIM.mod.state.hold = nil end')(); SIM.tick(1)
    def site(*ps):                                            # the site cleared, then these pieces on it: (key, dx, dy, z, yaw)
        clear(SX, SY)
        for k, dx, dy, z, *yw in ps: put(k, SX + dx, SY + dy, z, *yw)
        refresh()
    def at(s, x, y, z=None, yaw=None):                        # snapped there (origin within a millimetre), at that turn
        return s[0] and abs(s[1] - x) < 1e-3 and abs(s[2] - y) < 1e-3 and (z is None or abs(s[3] - z) < 1e-3) and (yaw is None or abs((s[4] - yaw + 180) % 360 - 180) < 1e-6)
    # two floors sharing an edge: a wall held facing north there faces into the far one, on its edge
    site((SF, 0, 0, FZ), (SF, 0, E, FZ))
    s = hold_at(SW, SX + 0.2, SY + E + 0.2, FZ, 0, (SX, SY + E + 10))[0]
    check(at(s, SX, SY + E, FZ, 0) or at(s, SX, SY, FZ, 180), 'a wall held at an edge two floors share: on that edge, facing into one of them - the first found, as in Fallout (%s)' % (s,))
    # a 3x3 ring of floors without its middle: a floor aimed into the hole fills it, joining all four sides
    ring = [(SF, i * E, j * E, FZ) for i in (-1, 0, 1) for j in (-1, 0, 1) if (i, j) != (0, 0)]
    site(*ring)
    AIMS = ((0, 0), (0.4, 0.3), (-0.45, 0.2), (0.3, -0.4), (-0.2, -0.45))   # (within the snap radius of the middle)
    def fill(key):
        out = []
        for dx, dy in AIMS:
            aim_mid(key, SX + dx, SY + dy, Z, 0, (SX, SY - 9))
            s = snap(); out.append((at(s, SX, SY, FZ, 0), s[5], st.place.ok))
        return out
    h = fill(SF)
    check(all(a and n == 4 and ok for a, n, ok in h), 'a floor aimed into the hole in a ring of floors snaps into it, joining all four, not blocked by them (%s)' % h)
    # ... and a small (balcony) floor aimed at a corner of the hole: in that corner, on the quarter points of two sides
    aim_mid(SB, SX + 0.914 + 0.2, SY + 0.914 + 0.1, Z, 0, (SX, SY - 9))
    s = snap()
    check(at(s, SX + 0.914, SY + 0.914, FZ, 0) and s[5] == 2 and st.place.ok, 'a balcony floor aimed at a corner of the hole: in the corner, joining its two sides (%s)' % (s,))
    for i, j in ((0, 1), (0, -1), (1, 0), (-1, 0)): put(SW, SX + i * E, SY + j * E, FZ, {(0, 1): 0, (0, -1): 180, (1, 0): 270, (-1, 0): 90}[(i, j)])
    refresh()                                                 # (the ring's floors with walls on the hole's edges)
    h = fill(SF)
    check(all(a and n == 8 and ok for a, n, ok in h), 'the ring\'s floors carrying walls on the hole\'s edges: it still snaps in, meeting the four floors and the four walls (%s)' % h)
    # a balcony floor swept along a lone floor's east edge, quarter point to quarter point: its snap changes once, never back
    site((SF, 0, 0, FZ))
    stand(SX + 7, SY); fo4_hold(SB)
    runs = []
    for k in range(41):
        look_at(SX + 1.829 + 0.914 + 0.1, SY - 1.1 + 2.2 * k / 40, Z); SIM.tick(1)
        s = snap()
        if s[0] and (not runs or abs(runs[-1] - s[2]) > 1e-3): runs.append(s[2])
    on_floor = []
    for k in range(41):                                       # (the crosshair on the floor, by its edge)
        look_at(SX + 1.6, SY - 1.1 + 2.2 * k / 40, FZ); SIM.tick(1)
        s = snap()
        if s[0] and (not on_floor or abs(on_floor[-1] - s[2]) > 1e-3): on_floor.append(s[2])
    want = [round(SY - 0.914, 3), round(SY + 0.914, 3)]
    check([round(y, 3) for y in runs] == want and [round(y, 3) for y in on_floor] == want,
          'a balcony floor swept along an edge from one quarter point to the other: one change, no flicker (beyond %s, on it %s)' % ([round(y - SY, 2) for y in runs], [round(y - SY, 2) for y in on_floor]))
    # sticky: two built P-Floor points 0.4 m apart, both facing east (floor A's east point; B, turned, has one there
    # too); a floor's west point swept from one to the other: the pair it has stays till the other is nearer by 0.25 m
    # (SNAP_STICK), either way - one change each way, at a clear margin, never a flip between near-equal ones
    site((SF, 0, 0, FZ), (SF, 0, 0.4, FZ, 90))
    seq = []
    for wy_ in (0, 0.25, 0.38, 0.15, 0.02):                   # (the held west point's y off A's east point, 0.05 m east of it)
        px, py = SX + 1.879 + 1.829, SY + wy_                  # (where its middle goes: on the ground, clear of A and B)
        aim_mid(SF, px, py, Z, 0, (px + 9, py))
        s = snap(); seq.append('A' if at(s, SX + E, SY, FZ, 0) else 'B' if at(s, SX + E, SY + 0.4, FZ, 0) else '-')
    check(seq == ['A', 'B', 'B', 'A', 'A'], 'not sticky (Fallout: every frame anew): the nearer of two points 0.4 m apart at once, either way (west point at 0, 0.25, 0.38, 0.15, 0.02 m: %s)' % ''.join(seq))
    # looking down a row of five floors, the crosshair on the second: never a snap out by the fifth
    site(*[(SF, 0, k * E, FZ) for k in range(5)])
    stand(SX, SY - 2.5); fo4_hold(SF)
    far = []
    for dx, dy in ((0, 0), (0.5, 1.0), (-0.6, -1.2), (0.3, 1.6), (-1.2, 0.4)):
        look_at(SX + dx, SY + E + dy, FZ); SIM.tick(3)
        s = snap(); far.append((s[0], round(s[2] - SY, 2)))
    check(all(not s or y < 3 * E - 1 for s, y in far), 'looking down a row of floors, the crosshair on the second: nothing snaps out by the fifth (%s)' % far)
    # 11 candidates in its own reach, some in another piece's way: a free one counted within 0.25 m (SNAP_STICK) of the
    # nearest's distance wins over it; none free that near - it snaps to the first all the same, red ("Blocked by"),
    # never out to the free one 0.63 m off
    def placement_ok(): return tuple(lua('function() local _, _, ok, why = SIM.mod.placement() return ok, why end')())
    clear(SX, SY)
    stand(SX, SY); fo4_hold(SF); lua('function() SIM.mod.state.dist = 3 end')(); look_at(SX, SY, Z + 10); SIM.tick(3)   # (held overhead)
    P0 = (st.place.o.x, st.place.o.y, st.place.o.z)
    wx, wy, wz = P0[0] - 1.829, P0[1], P0[2]                  # (its west point, as held)
    # floors west of its west point, their east points near it (y, dz off it: all above its middle - nothing under it
    # to drop onto - a level at least 0.12 m from the next, points 0.15 m apart on one: none taken, none in another's
    # way), the furthest alone on its level
    LV = [(0, 0.12), (0.15, 0.12), (-0.3, 0.12), (0.45, 0.12), (0, 0.24), (-0.15, 0.24), (0.3, 0.24), (0, 0.36), (0.15, 0.36), (-0.3, 0.36), (0.2, 0.6)]
    for y, dz in LV: put(SF, wx - 1.829, wy + y, wz + dz)
    refresh(); SIM.tick(2)
    s0 = snap()
    def block(*lv):                                           # (in the way of a level's poses: a floor north of it, turned)
        for dz in lv: put(SF, P0[0], P0[1] + 2.7, P0[2] + dz, 45)
        refresh(); SIM.tick(2)
        return snap(), placement_ok()
    s1 = block(0.12, 0.36)                                    # (the nearest's level and the third's: the 0.24 m one free)
    s2 = block(0.24)                                          # (all within reach but the last in the way; the points made
                                                              # anew with the pieces, the pair it had is gone: the nearest)
    lua('function() SIM.mod.state.dist = nil end')()
    check(at(s0, P0[0], P0[1], P0[2] + 0.12, 0) and not s1[0][0] and not s2[0][0],
          'the nearest snap in another piece\'s way: no snap at all, it stays where it is held - no second choice, as in Fallout (free %s; in the way %s; %s)' % (s0[:5], s1, s2))
    # a roof beside a built roof (docs/snap_families_research_2026-10-03.md, section 4): two cells, floors and perimeter
    # walls, roof A built; roof B held where it goes snaps there, free - the shared edge open (held at each quarter turn)
    # or a wall on it (that wall's point faces the wrong way for B: its top plate vetoed roof03/04, and roof05's low box
    # hit A's corner wall even with the edge open). Every piece with a point on B's points is left out, and the give is
    # the roofs' WorkshopItemOverlap (32 units: set here as the import's catalog has it)
    lua('function() for i = 1, 5 do local it = SIM.it("fo4_workshop_shackmidroof0" .. i) it.ovl, it.vbox = 32 * 0.0142875, { xy = 256 * 0.0142875 } end end')()
    bad = []
    for r_ in range(1, 6):
        RF = 'fo4_workshop_shackmidroof0%d' % r_
        for shared in (False, True):
            site((SF, 0, 0, FZ), (SF, E, 0, FZ), *[(SW, 0, 0, FZ, y) for y in (0, 180, 270) + ((90,) if shared else ())],
                 *[(SW, E, 0, FZ, y) for y in (0, 180, 90)], (RF, 0, 0, FZ))
            for yw in (0,) if shared else (0, 90, 180, 270):
                s, ok, why = hold_at(RF, SX + E, SY, FZ, yw, (SX + E + 4, SY - 3))
                if not (at(s, SX + E, SY, FZ) and ok): bad.append((r_, shared, yw, s[0], why, st.snapWhy))
    check(not bad, 'roofs 01-05 beside a built roof snap there, free: the shared edge open at each quarter turn, or a wall on it (failing: %s)' % bad)
    # WorkshopMustBeSnapped (Fallout's 22 doors; set here as the import's catalog has it): held turned 180 and aimed at
    # its doorway's hinge jamb from 4 m inside, a door turns and snaps into the frame; held unsnapped it is refused in
    # snap mode ("Must be snapped"), free placement puts it anywhere
    DF, DO = 'fo4_workshop_shackwalloutercap01door01', 'fo4_workshop_shackdoor01'
    lua('function(k) SIM.it(k).must = true end')(DO)
    site((SF, 0, 0, FZ), (DF, 0, 0, FZ))
    dw = pair_pose(DO, 'P-Door-Dif', 1, DF, (SX, SY, FZ, 0), 'P-Door-Dif2', 1)
    hy = (dw[3] + 180) % 360                                  # (its hinge point 0.3 m from the frame's, the door the wrong way round)
    hp = pt_of(DO, 'P-Door-Dif', *dw)
    hold_at(DO, *pt_at(DO, 'P-Door-Dif', hp[0] + 0.2, hp[1] + 0.2, hp[2], hy), hy, (SX, SY + 8)); SIM.tick(1)
    d1 = (snap(), placement_ok())
    hold_at(DO, SX + 9, SY + 9, FZ, 0, (SX + 9, SY + 2)); SIM.tick(1); d2 = (snap()[0], placement_ok())
    SIM.key('IK_Q'); SIM.tick(2); d3 = placement_ok(); SIM.key('IK_Q'); SIM.tick(2)
    check(at(d1[0], *dw) and d1[1][0] and not d2[0] and d2[1] == (False, 'Must be snapped') and d3[0],
          'a door held turned 180, aimed at its doorway\'s hinge jamb from 4 m: turned, in the frame; unsnapped: "Must be snapped"; free: anywhere (%s; %s; %s)' % (d1, d2, d3))
    # taken: a built point with one of the held point's own kind within 4 units (Fallout's query; was 8) is passed over -
    # unless its piece has WorkshopIgnoreNonRefOccupiedSnap (set here on the shack floor for the check)
    tk = []
    for dy_, ign in ((0.03, False), (0.03, True), (0.07, False)):
        lua('function(k, v) SIM.it(k).ignoreOcc = v or nil end')(SF, ign)
        site((SF, 0, 0, FZ), (SF, 0, dy_, FZ))                # (two floors 2 or 5 units apart: their east points too)
        tk.append(hold_at(SF, SX + E + 0.02, SY, FZ, 0, (SX + E + 4, SY))[0][0])
    lua('function(k) SIM.it(k).ignoreOcc = nil end')(SF)
    check(tk == [False, True, True], 'taken: another floor\'s point 2 units off - passed over, taken unless the piece ignores it; 5 units off - not taken (%s)' % tk)
    # Fallout's families, one scenario each (docs/snap_families_research_2026-10-03.md, section 7); per-piece values the
    # import's catalog carries are set here (snapR = WorkshopSnapPointRadius x U)
    def setv(k, **kv):
        for f, v in kv.items(): lua('function(k, f, v) SIM.it(k)[f] = v end')(k, f, v)
    def qturn(s): return s[4] % 90 < 1e-6 or s[4] % 90 > 90 - 1e-6
    R3 = 'fo4_workshop_shackmidroof03'
    # an upper floor held over four walls, half a metre off: on their tops
    site((SF, 0, 0, FZ), *[(SW, 0, 0, FZ, y) for y in (0, 90, 180, 270)])
    s = hold_at(SU, SX + 0.4, SY + 0.3, FZ + 3.2, 0, (SX, SY - 8))
    check(at(s[0], SX, SY, FZ + 3.2) and s[1], 'an upper floor held over four walls, half a metre off: on the wall tops (%s)' % (s[0][:5],))
    # a wall held at any quarter turn by a lone floor's edge turns to it and stands on it
    site((SF, 0, 0, FZ))
    wt = []
    for yw in (90, 180, 270):
        wt.append(at(hold_at(SW, *pt_at(SW, 'P-Floor-Dif', SX + 0.2, SY - 1.829 - 0.2, FZ, yw), yw, (SX, SY - 9))[0], SX, SY, FZ, 0))   # (its floor point by the edge's)
    check(all(wt), 'a wall held at 90, 180, 270 by a lone floor\'s south edge: turned to it, on it (%s)' % wt)
    # per-piece radius: a metal wall (96 units) snaps from 1.2 m off; a concrete wall (16 units) from 0.1 m, not 0.3 m
    MW, CW, CF = 'fo4_workshop_shackmetalwallouter01a', 'fo4_workshopconcretewall01', 'fo4_workshopconcretemidfloor01'
    setv(MW, snapR=96 * 0.0142875); setv(CW, snapR=16 * 0.0142875)
    site((SF, 0, 0, FZ))
    mw = pair_pose(MW, 'P-Floor', 1, SF, (SX, SY, FZ, 0), 'P-Floor', 2)
    m1 = hold_at(MW, mw[0] + 1.2, mw[1], mw[2], mw[3], (mw[0] + 5, mw[1] - 3))[0]
    site((CF, 0, 0, FZ))
    cw = pair_pose(CW, 'P-Floor', 1, CF, (SX, SY, FZ, 0), 'P-Floor', 1)
    c1 = hold_at(CW, cw[0], cw[1] + 0.1, cw[2], cw[3], (cw[0] + 5, cw[1] - 3))[0]
    c3 = hold_at(CW, cw[0], cw[1] + 0.4, cw[2], cw[3], (cw[0] + 5, cw[1] - 3))[0]   # (past 1.414 x its 0.23 m)
    check(at(m1, *mw) and at(c1, *cw) and not c3[0], 'per-piece radius: a metal wall snaps from 1.2 m off; a concrete wall from 0.1 m, not from 0.4 m (%s; %s; %s)' % (m1[:5], c1[:5], c3[:5]))
    # a railing onto a balcony floor's edge, held at any quarter turn
    RL = 'fo4_workshop_shackbalconyrailing01'
    site((SB, 0, 0, FZ))
    rl = pair_pose(RL, 'P-Balcony01-Dif2', 1, SB, (SX, SY, FZ, 0), 'P-Balcony01', 1)
    def point_at(k, n, x, y, z, yaw):                         # the origin that puts its point named n at x, y, z, turned yaw
        return lua('''function(k, n, x, y, z, yaw) for _, c in ipairs(SIM.it(k).connect) do if c.name == n then local a = SIM.axes(yaw)
            return x - a[1] * c.x - a[3] * c.y, y - a[2] * c.x - a[4] * c.y, z - c.z end end end''')(k, n, x, y, z, yaw)
    rr = [at(hold_at(RL, *point_at(RL, 'P-Balcony01-Dif2', SX + 0.1, SY - 0.914 - 0.1, FZ, yw), yw, (SX + 2, SY - 3))[0], *rl) for yw in (0, 90, 180, 270)]
    check(all(rr), 'a railing held at 0, 90, 180, 270 by a balcony floor\'s edge: on it (%s)' % rr)
    # scaffolding frames (32 units, 0.46 m): one stacks on another from 0.40 m off, not from 0.52 m
    SC = 'fo4_dlc05scaffframe1x1x1a'
    setv(SC, snapR=32 * 0.0142875)
    site((SC, 0, 0, Z))
    sk = pair_pose(SC, 'P-SFrameStack01', 1, SC, (SX, SY, Z, 0), 'P-SFrameStack01-Dif', 1)
    s1 = hold_at(SC, sk[0] + 0.35, sk[1] + 0.2, sk[2], 0, (SX + 4, SY - 3))[0]
    s2 = hold_at(SC, sk[0] + 0.45, sk[1] + 0.25, sk[2], 0, (SX + 4, SY - 3))[0]
    check(at(s1, *sk) and not s2[0], 'scaffolding: a frame stacks on a frame from 0.40 m off, not from 0.52 m (%s; %s)' % (s1[:5], s2[:5]))
    # warehouse walls: end to end (P-WrhsWall01-Dif on -Dif2: straight on, before the corner pair at the same end) and
    # stacked (P-WrhsStack01-Dif on -Dif2)
    WH = 'fo4_dlc05wrhswalld01'
    site((WH, 0, 0, Z))
    we = pair_pose(WH, 'P-WrhsWall01-Dif', 1, WH, (SX, SY, Z, 0), 'P-WrhsWall01-Dif2', 1)
    ws = pair_pose(WH, 'P-WrhsStack01-Dif', 1, WH, (SX, SY, Z, 0), 'P-WrhsStack01-Dif2', 1)
    w1 = hold_at(WH, we[0] + 0.3, we[1] + 0.2, we[2], 0, (we[0] + 3, we[1] - 5))[0]; SIM.tick(1); nt = st.ties
    SIM.key('IK_LeftMouse'); SIM.release('IK_LeftMouse'); SIM.tick(2); w1b = snap()
    w2 = hold_at(WH, ws[0] + 0.3, ws[1] - 0.2, ws[2], 0, (ws[0] + 3, ws[1] - 6))[0]
    check((at(w1, *we) or at(w1b, *we)) and w1[:5] != w1b[:5] and nt == 2 and at(w2, *ws),
          'warehouse walls: end to end - the end and the corner pair exactly as near, the rotate key steps to the other (%s, then %s; want %s; %s of them) - and stacked (%s at %s)' % (w1[:5], w1b[:5], we, nt, w2[:5], ws))
    # vault rooms: edge to edge (P-VaultRoom01 on P-VaultRoom01)
    VR = 'fo4_vltworkshoproomquartersfloorceiling01'
    site((VR, 0, 0, Z))
    ve = pair_pose(VR, 'P-VaultRoom01', 2, VR, (SX, SY, Z, 0), 'P-VaultRoom01', 1)
    v1 = hold_at(VR, ve[0] + 0.3, ve[1] + 0.3, ve[2], 0, (ve[0] + 5, ve[1] - 4))[0]
    check(at(v1, *ve), 'vault rooms: one edge to edge with another (%s at %s)' % (v1[:5], ve))
    # the junk fence has no snap points: by a floor and a fence it never snaps; Shack Stairs (stairs01) has two P-Balcony01
    # (the research's "never snaps" read its points wrong): its foot onto a floor's quarter point
    JF, ST = 'fo4_workshop_junkwall03', 'fo4_workshop_shackstairs01'
    site((SF, 0, 0, FZ), (JF, 0, -6, Z))
    j1 = [hold_at(JF, SX + dx, SY + dy, Z, 0, (SX + dx + 3, SY + dy - 5))[0][0] for dx, dy in ((2.0, 0), (0.2, -5.9), (0, -2.5))]
    stq = pair_pose(ST, 'P-Balcony01', 1, SF, (SX, SY, FZ, 0), 'P-Balcony01-Dif', 3)
    s3 = hold_at(ST, stq[0] + 0.2, stq[1] + 0.2, stq[2], stq[3], (stq[0] + 6, stq[1] - 3))[0]
    check(not any(j1) and at(s3, *stq), 'the junk fence never snaps (%s); Shack Stairs\' foot onto a floor\'s quarter point (%s at %s)' % (j1, s3[:5], stq))
    # held low, its base under the ground (looked down short of where the line meets the ground): lifted onto the ground
    # when that is within its P-WS-SinkMax (catalog sink: a scaffolding frame's 1.37 m), else it floats sunk in
    clear(SX, SY)
    sb = []
    for sk_ in (1.372, None):
        setv(SC, sink=sk_); stand(SX, SY); fo4_hold(SC); held_yaw(0); look_at(SX + 4.09, SY, Z + 0.4); SIM.tick(3)
        sb.append(round(lua('function(k) return SIM.mod.state.place.o.z + SIM.it(k).base[3] end')(SC) - Z, 3))   # (its base, up)
    setv(SC, sink=0.2)                                         # (past its SinkMax; asked without a frame: later scenarios count them)
    sb.insert(1, round(lua('function(k) local o = SIM.mod.placement() return o.z + SIM.it(k).base[3] end')(SC) - Z, 3))
    setv(SC, sink=None)
    check(-1.372 <= sb[0] < -0.3 and sb[1] == -0.2 and sb[2] == 0, 'held with its base under the ground: within its SinkMax it stays sunk as held (base %.3f); past it, sunk that far and no deeper (%.3f); without one it is lifted onto the ground (%.3f)' % tuple(sb))
    # an upper floor aimed at a wall's top sits on it (its underside P-Ceiling on the wall's P-Ceiling-Dif); a wall
    # aimed there doesn't (two P-Ceiling-Dif never pair)
    site((SF, 0, 0, FZ), (SW, 0, 0, FZ, 180))
    stand(SX, SY - 1); fo4_hold(SU); look_at(SX + 0.2, SY + 1.7, FZ + 2.75); SIM.tick(3)
    s, ok = snap(), st.place.ok
    fo4_hold(SW); held_yaw(180); SIM.tick(3)
    s2 = snap()
    check(at(s, SX, SY, FZ + 3.2) and s[4] % 90 < 1e-6 and ok and not s2[0],'an upper floor aimed at a wall top sits on it (square: at whichever quarter turn its nearest point gives); a wall aimed there does not stack on it (%s; %s)' % (s[:5], s2[:5]))
    # point names (Fallout's rule): the same name, or a -Dif suffix on one side; a suffixed name never with itself
    names = ('P-Floor', 'P-Floor', 'P-Door-Dif', 'P-Door-Dif', 'P-Door-Dif', 'P-Door-Dif2', 'P-Wall-Dif015', 'P-Wall-Dif016',
             'P-Wall-dif2', 'P-Wall-Dif', 'P-Floor', 'P-Floor-Dif', 'P-Floor', 'P-Ceiling', 'P-Wall-Dif015', 'P-Wall-Dif015')
    pr = [lua('function(a, b) return SIM.mod.pairs(a, b) end')(names[i], names[i + 1]) for i in range(0, len(names), 2)]
    check(pr == [True, False, True, True, True, True, False, False], 'connect point names pair as in Fallout (%s)' % pr)
    # stairs: the bottom on a floor's quarter point, the top on an upper floor's
    QX, QY = SX - 0.914, SY - 1.829                           # (the floor's south edge, west quarter: facing south)
    site((SF, 0, 0, FZ), (SU, -E, 0, FZ + 3.2))
    sx, sy = spot_for(SS, 'P-Balcony01', 2, QX + 0.15, QY - 0.1, 0)
    aim_mid(SS, sx, sy, Z, 0, (sx + 3, sy - 8))
    s = snap()
    jk = lua('function() local o = {} for p in pairs(SIM.mod.state.joined or {}) do o[#o + 1] = p.key end table.sort(o) return table.concat(o, " ") end')()
    check(at(s, QX, QY - 0.914, FZ, 0) and jk == ' '.join(sorted([SF, SU])), 'stairs: the bottom on a floor\'s quarter point, the top on the upper floor\'s (%s, joins %s)' % (s[:5], jk))
    # held as Fallout holds a new item: its middle (P-WS-Rotation, else its bounds' centre) on the view line 300 units
    # (4.29 m) out whatever its size - a wall face nearer doesn't pull it in - then its base dropped onto what is under it
    # within a metre; else it floats there, centred
    HOLD = 300 * 0.0142875
    def held():                                               # snapped?, its middle off the line, how far out, base height
        m = lua("""function() local st = SIM.mod.state local it = SIM.it(st.hold.key) local v, a = it.pivot or { it.cx, it.cy }, SIM.axes(st.place.yaw)
            return st.place.o.x + a[1] * v[1] + a[3] * v[2], st.place.o.y + a[2] * v[1] + a[4] * v[2], st.place.o.z + (it.min[3] + it.max[3]) / 2, st.place.o.z + it.base[3] end""")()
        off, t = on_ray(*m[:3])
        return st.snapped, round(off, 3), round(t, 3), round(m[3] - Z, 3)
    clear(SX, SY)
    stand(SX, SY); fo4_hold(SW); look_at(SX, SY + 10, Z + EYE); SIM.tick(3); h1 = held()     # (looked at level)
    fo4_hold(SF); look_at(SX + 3, SY - 10, Z + 6); SIM.tick(3); h2 = held()                  # (looked up)
    site((SW, 0, 0.23, Z, 180))                               # (a wall, its face to V 2 m ahead)
    fo4_hold('fo4_dlc05scaffframe1x1x1a'); look_at(SX + 0.3, SY + 2, Z + 2.6); SIM.tick(3); h3 = held()   # (nothing on the wall pairs)
    check(h1[0] is False and abs(h1[2] - hold_depth(SW)) < 0.05 and abs(h1[3]) < 1e-3 and h2[0] is False and h2[1] < 1e-3 and abs(h2[2] - hold_depth(SF)) < 1e-3 and h2[3] > 1
          and h3[0] is False and h3[1] < 1e-3 and abs(h3[2] - HOLD) < 1e-3 and hold_depth(SF) > hold_depth(SW) > HOLD,
          'held as Fallout holds it, twice its radius out (300 units at least): a wall looked at level stands on the ground %.2f m out; a floor looked up floats centred on the line %.2f m out; a scaffolding frame aimed at a wall face 2 m off is 4.29 m out, through it (snapped, off the line, out, base up: %s %s %s)' % (hold_depth(SW), hold_depth(SF), h1, h2, h3))
    # a big piece is held further, so that V is never in it (holdDepth: its footprint's reach round the held middle and
    # 0.4 m across, its half height and V's 1.7 m up or down) - the Large Shack (12 m) 10.5 m out; looked down at the
    # ground nearer, on it pushed out along the heading - never round V however V looks (V's feet, waist or eye inside
    # its bounds?); the wheel's distance still wins
    LS = 'fo4_workshop_shackprefabcompletelg01'
    clear(SX, SY)
    ls = lua('''function(k) local it = SIM.it(k) local v = it.pivot or { it.cx, it.cy }
        local rx, ry = math.max(v[1] - it.min[1], it.max[1] - v[1]), math.max(v[2] - it.min[2], it.max[2] - v[2])
        return math.sqrt((math.sqrt(rx * rx + ry * ry) + 0.4) ^ 2 + ((it.max[3] - it.min[3]) / 2 + 1.7 + math.max(it.sink or 0, 0)) ^ 2), it.size[1], it.size[2] end''')(LS)
    def inside_v():                                           # V's feet, waist or eye inside the held piece's bounds?
        return lua('''function(k, x, y, z) local st = SIM.mod.state local it, o = SIM.it(k), st.place.o local a = SIM.axes(st.place.yaw)
            for _, h in ipairs({ 0, 0.85, 1.7 }) do local dx, dy, dz = x - o.x, y - o.y, z + h - o.z
                local lx, ly = dx * a[1] + dy * a[2], dx * a[3] + dy * a[4]
                if lx > it.min[1] and lx < it.max[1] and ly > it.min[2] and ly < it.max[2] and dz > it.min[3] and dz < it.max[3] then return true end
            end return false end''')(LS, SIM.player.x, SIM.player.y, SIM.player.z)
    stand(SX, SY); fo4_hold(LS)
    inv = []
    for hy in (0, 30):
        held_yaw(hy)
        for yw in range(0, 360, 45):
            for p in (-60, -40, -20, 0, 20, 40):
                a_, b_ = math.radians(yw), math.radians(p)
                look_at(SX + 10 * math.cos(b_) * math.sin(a_), SY + 10 * math.cos(b_) * math.cos(a_), Z + EYE + 10 * math.sin(b_)); SIM.tick(1)
                if not st.place or inside_v(): inv.append((hy, yw, p))
    held_yaw(0); look_at(SX, SY + 10, Z + EYE + 6); SIM.tick(2); hl = held()               # (looked up: it floats)
    lua('function() SIM.mod.state.dist = 5 end')(); look_at(SX, SY + 10, Z + EYE); SIM.tick(2); hw = held()   # (level: sunk, floating)
    lua('function() SIM.mod.state.dist = nil end')()
    check(hl[0] is False and hl[1] < 1e-3 and abs(hl[2] - 1024 * 0.0142875) < 1e-3 and abs(hw[2] - hl[2]) < 0.5,
          'the Large Shack (%.1f x %.1f m) is held 1024 units out - twice its radius, capped (%.2f m); the wheel at 5 m brings it no nearer (%.2f m), as in Fallout\'s build mode' % (ls[1], ls[2], hl[2], hw[2]))
    # snapped though in the way: a roof aimed from inside at a room's wall where a roof turned 45 already sits (none of
    # its points on the held roof's or the walls': not taken, not joined) snaps onto the walls all the same, red
    # ("Blocked by"); the turned roof gone, the same aim snaps there free
    site((SF, 0, 0, FZ), *[(SW, 0, 0, FZ, y) for y in (0, 90, 180, 270)], (R3, 0, 0, FZ, 45))
    rb = hold_at(R3, SX + 0.3, SY + 0.2, FZ, 0, (SX, SY - 9))
    lua('''function(k, x, y) local d = Game.GetDynamicEntitySystem()   -- (the turned roof taken away)
        for _, p in ipairs(SIM.mod.state.pieces) do if p.key == k and (p.o.x - x) ^ 2 + (p.o.y - y) ^ 2 < 1 then d:DeleteEntity(p.id) end end SIM.mod.refresh() end''')(R3, SX, SY)
    rv = hold_at(R3, SX + 0.3, SY + 0.2, FZ, 0, (SX, SY - 9))
    check(not rb[0][0] and at(rv[0], SX, SY, FZ) and rv[1],
          'a roof held over a room where a roof turned 45 sits: no snap, it stays where it is held (%s); that roof gone: snapped, free (%s)' % (rb, rv))
    # Fallout's reach: the built piece within the radius (48 units: 0.69 m) of the held point; the yaw follows the view; 75 points or more never snap
    site((SF, 0, 0, FZ))
    n1 = hold_at(SF, SX + E + 0.6, SY, FZ, 0, (SX + E + 9, SY))[0]
    n2 = hold_at(SF, SX + E + 0.75, SY, FZ, 0, (SX + E + 9, SY))[0]
    lua('function(k) local it = SIM.it(k) SIM.mod.C.Grid.snaps(it) SIM.cps = it.cps local t = {} for i = 1, 75 do t[i] = SIM.cps[1 + i % #SIM.cps] end it.cps = t end')(SF)
    n3 = hold_at(SF, SX + E + 0.2, SY, FZ, 0, (SX + E + 9, SY))[0]
    lua('function(k) SIM.it(k).cps = SIM.cps end')(SF)
    clear(SX, SY); stand(SX, SY); fo4_hold(SF); look_at(SX, SY + 10, Z + 6); SIM.tick(2); y0 = st.hold.yaw
    look_at(SX + 10, SY, Z + 6); SIM.tick(2); y1 = st.hold.yaw
    check(at(n1, SX + E, SY, FZ, 0) and not n2[0] and not n3[0] and abs((y1 - y0) % 360 - 270) < 1e-6,
          'a floor snaps from 0.6 m off (%s), not from 0.75 m (%s); with 75 points it never snaps (%s); held, it turns with the view (north to east: %.0f)' % (n1[0], n2[0], n3[0], (y1 - y0) % 360))
    lua('function() SIM.mod.state.hold = nil end')(); SIM.tick(1)
    clear(SX, SY)
    # every weapon of the game is a prop: on a floor it lies on its side, on a wall it hangs upright, its side to it
    WK = 'wpn_preset_ajax_default'
    has_w = lua('function(k) return SIM.it(k) ~= nil end')(WK)
    check(has_w, 'the Ajax (every weapon of the game: tools/make_weapons.py) is in the catalog')
    if has_w:
        fo4_hold(WK); lua('function(k) SIM.mod.state.hold.app = SIM.it(k).apps[1] end')(WK)
        stand(ax_ - 2.5, ay_); look_at(ax_ - 0.5, ay_, az_); SIM.tick(3)
        lying = lua('function() local q = SIM.mod.state.hold.q return q ~= nil and 1 - 2 * (q.i * q.i + q.j * q.j) < 0.5 end')()   # (its up turned away)
        stand(ax_, ay_ - 0.5); look_at(ax_ + 0.3, ay_ + 1.85, az_ + 1.5); SIM.tick(3)
        wall = lua('function() local S = SIM.mod.state return S.hold.q == nil and S.snapped ~= false and S.snapped ~= nil end')()
        check(lying and wall and st.place.ok, 'a weapon on a floor lies on its side (%s); on a wall it hangs upright against it (%s)' % (lying, wall))
        SIM.key('IK_E'); SIM.release('IK_E'); SIM.tick(2)            # (placed: a piece with no boxes at all)
        to_tabs()
        placed_w = [p for p in st.pieces.values() if p.key == WK]
        other = next((p for p in st.pieces.values() if p.key != WK and not p.bench), None)
        mv = lua('''function(p) local S = SIM.mod.state S.target = p
            local ok = pcall(function() SIM.mod.startMove(p) end) local held = S.hold and S.hold.kind
            pcall(function() SIM.mod.restore() end) return ok, held end''')(other) if other else (False, None)
        check(placed_w and mv[0] and mv[1] == 'move', 'with a weapon placed (no boxes), other pieces still pick up and move (%s, %s)' % (bool(placed_w), mv[1]))
    n_w = lua('function() local n = 0 for _, it in ipairs(require("catalog").items) do if it.key:find("^wpn_") then n = n + 1 end end return n end')()
    check(n_w == 97, 'one menu entry per weapon, not per look (%d)' % n_w)
    # Cyberpunk decor: its back to the wall (looked at: the front has the vents, pickups, screen); hanging ones on a ceiling
    mk = lua('function(...) local o = {} for i, k in ipairs({...}) do local m = SIM.it(k) and SIM.it(k).mount o[i] = m and (m.kind .. m.dir) or "none" end return table.concat(o, " ") end')(
        'h_electric_guitar_a', 'h_tv_large_a', 'h_poor_airconditioner_d', 'h_ceiling_lamp_long_a')
    check(mk == 'wall180 wall90 wall270 ceiling0',
          'decor mounts: guitar, TV, air-con on a wall by their backs, the long ceiling lamp hangs (%s)' % (mk,))
    check(lua('function() return SIM.it("h_achilles_a").stashed == true end')(), 'the old static gun meshes are out (the real weapons are in)')
    gr = lua('''function() local m, l = SIM.it("h_morgue_table_c"), SIM.it("lamp")
        return m.base[3] - m.min[3], l.base[3] end''')()
    check(abs(gr[0]) < 1e-6 and gr[1] == 0, 'Night City props stand on their bottom (a morgue table: not sunk by the part under its origin); a street lamp keeps its footing in the ground')
    # the gizmo on a piece looked at: Ctrl takes it up where it stands (no E first), free placement from there
    lt = lua('''function() local cd, hl, dl = SIM.it("h_nkts_candle_a"), SIM.it("h_kitsch_hanging_lamp_a"), SIM.it("h_poor_desk_lamp_a")
        local function n(t) return t and #t or 0 end
        return n(cd.lights), n(cd.fx), cd.fx and cd.fx[1].path or "", n(hl.lights), hl.lights and (hl.lights[1].pos[3] - hl.min[3]) or -1, n(dl.lights) end''')()
    check(lt[0] == 1 and lt[1] == 1 and 'candle' in lt[2] and lt[3] == 1 and 0 < lt[4] < 0.3 and lt[5] == 1,
          'Night City lamps give light (a hanging lamp under its shade, a desk lamp), and a candle has its flame (%s)' % (lt,))
    fs = lua('''function() local it = SIM.it("h_candle_stand_funeral_a") local n, lo, hi = 0, 9, -9
        for _, f in ipairs(it.fx or {}) do n = n + 1; lo = math.min(lo, f.pos[3]); hi = math.max(hi, f.pos[3]) end
        return n, lo, hi, it.lights and #it.lights or 0, it.max[3] end''')()
    import re as _re
    fd = float(_re.search(r'^FLAME_DOWN = ([\d.]+)', open(os.path.join(os.path.dirname(__file__), 'build_catalog.py'), encoding='utf-8').read(), _re.M).group(1))
    check(fs[0] == 40 and abs(fs[1] - (0.498 - fd)) < 0.01 and abs(fs[2] - (0.498 - fd)) < 0.01 and fs[3] == 1,
          'the funeral candle stand: a flame on each of its 40 candles, %.0f cm under their tips (%.3f, the stand %.2f high), one light (%s)' % (fd * 100, fs[2], fs[4], fs))
    se = lua('''function() local ch, so, fr = SIM.it("h_poor_residential_chair_a"), SIM.it("sofa"), SIM.it("h_rich_asian_couchette_a_footrest_b")
        local s = ch.seats and ch.seats[1] or {}
        return s[5] or "", s[6] or -1, s[2] or -9, so.seats and #so.seats or 0, fr.seats and #fr.seats or 0 end''')()
    check(se[0] == 'chair' and 0.35 < se[1] < 0.6 and se[2] > 0 and se[3] == 4 and se[4] == 0,
          'Night City chairs and sofas can be sat on: seat height, facing off the back, a sofa seats four, a footrest none (%s)' % (se,))
    du = lua('''function() local seen, d = {}, {}
        for _, it in ipairs(require("catalog").items) do
            if it.cat == "Night City" and not it.stashed then
                local k = it.group .. "/" .. it.name
                if seen[k] then d[#d + 1] = k end
                seen[k] = true
            end
        end
        return #d, table.concat(d, ", ") end''')()
    check(du[0] == 0, 'Night City: no two props shown in a folder by the same name (%s)' % (du[1][:300] or 'none',))
    # a Night City plant looked at: the game's outline doesn't draw on foliage, so its box is drawn instead (lines only,
    # no cursor), and goes when V looks away
    PX, PY = ZX - 30, ZY + 20
    stand(PX, PY - 4); fo4_hold('h_bamboo_low'); look_at(PX, PY, Z); SIM.tick(3); SIM.key('IK_E'); SIM.release('IK_E'); SIM.tick(3)
    lua('function() local S = SIM.mod.state S.hold = nil end')(); SIM.tick(2)
    lua('function() SIM.gz = nil end')()
    look_at(PX, PY, Z + 0.5); SIM.tick(3)
    pb = lua('function() local g = SIM.gz return g and g.n or -1, g and g.cx or 0, SIM.mod.state.target and SIM.mod.state.target.key or "" end')()
    look_at(PX, PY + 40, Z + 30); SIM.tick(3)
    pb2 = lua('function() return SIM.gz and SIM.gz.n or -1 end')()
    check(pb[0] >= 8 and pb[1] < 0 and pb[2] == 'h_bamboo_low' and pb2 == 0,
          'a Night City plant looked at shows its box (%s lines, no cursor; looked away: %s lines)' % (pb[0], pb2))
    stand(ax_ - 2.5, ay_); look_at(ax_, ay_, az_); SIM.tick(3)
    T0 = st.target
    if T0:
        o0 = (T0.o.x, T0.o.y, T0.o.z)
        SIM.key('IK_LControl'); SIM.release('IK_LControl'); SIM.tick(2)
        g = lua('function() local S = SIM.mod.state return S.gz and S.gz.o.x, S.gz and S.gz.o.y, S.hold and S.hold.kind, S.free end')()
        check(g[2] == 'move' and g[3] and abs(g[0] - o0[0]) < 1e-3 and abs(g[1] - o0[1]) < 1e-3,
              'Ctrl on a piece looked at: the gizmo takes it where it stands, in free placement (%s)' % (g[2],))
        # Ctrl edit applies as it goes: the wheel pushes it, and once the wheel rests it stands there - the gizmo on it,
        # nothing held
        n_held = len(pieces(T0.key))
        SIM.key('IK_MouseWheelUp'); SIM.tick(3)
        wait_ = (st.hold is not None, len(pieces(T0.key)) == n_held)
        SIM.tick(30)
        a = lua('function() local S = SIM.mod.state return S.hold == nil, S.gz ~= nil and S.gz.piece ~= nil, S.gz and S.gz.piece and S.gz.piece.o.x, S.gz and S.gz.piece and S.gz.piece.o.y end')()
        moved = a[2] is not None and math.hypot(a[2] - o0[0], a[3] - o0[1]) > 0.02
        there = [p for p in pieces(T0.key) if a[2] is not None and math.hypot(p.o.x - a[2], p.o.y - a[3]) < 1e-3]
        check(all(wait_) and a[0] and a[1] and moved and len(pieces(T0.key)) == n_held + 1 and len(there) == 1 and SIM.gizmoOn,
              'Ctrl edit: the wheel pushes the piece, held while the wheel may turn on, and once it rests it stands there, the gizmo on it with nothing held (held at first %s, moved %s, %d placed)' % (wait_, moved, len(pieces(T0.key))))
        # the next grab takes it up again (not in the frame it was spawned: that crashed the game)
        def handle0(kind, axis):
            hs = lua('function() local hs = SIM.mod.gizmoView() local out = {} for _, h in ipairs(hs) do out[#out + 1] = h end return out end')()
            return next(hs[i] for i in hs if hs[i].kind == kind and hs[i].axis == axis)
        hz = handle0('move', 3); a1, b1 = hz.pts[1], hz.pts[2]
        for _ in range(6):
            dx, dy = ((a1[1] + b1[1]) / 2 - st.gz.cx) * 1920, ((a1[2] + b1[2]) / 2 - st.gz.cy) * 1080
            SIM.mouse(dx, dy); SIM.tick(1)
        SIM.hold('IK_LeftMouse'); SIM.tick(1)
        g2 = lua('function() local S = SIM.mod.state return S.hold and S.hold.kind, S.gz and S.gz.piece == nil, S.gz and S.gz.drag ~= nil end')()
        check(g2[0] == 'move' and g2[1] and g2[2] and len(pieces(T0.key)) == n_held,
              'Ctrl edit: grabbing a handle takes the piece up again for the drag (%s)' % (g2,))
        SIM.release('IK_LeftMouse'); SIM.tick(2)
        check(st.hold is None and st.gz is not None and len(pieces(T0.key)) == n_held + 1, 'Ctrl edit: let go without moving - set down again, the gizmo still on it')
        SIM.key('IK_LControl'); SIM.release('IK_LControl'); SIM.tick(2)
        check(st.hold is None and st.gz is None and not SIM.gizmoOn and len(pieces(T0.key)) == n_held + 1 and len(there) == 1,
              'Ctrl again: done - it stands where the gizmo left it, nothing held (%d placed)' % len(pieces(T0.key)))
        SIM.key('IK_Q'); SIM.release('IK_Q'); SIM.tick(1)
    else: check(False, 'a piece under the crosshair for the gizmo check')
    SIM.key('IK_Q'); SIM.tick(1)
    # top and bottom: a hovering Upper Floor takes a wall under it (the wall's top point on the floor's underside one)
    UF = 'fo4_workshop_shackmidfloortoroof01'
    stand(ZX - 30, ZY + 4); fo4_hold(UF); SIM.key('IK_Q'); SIM.tick(1); look_at(ZX - 30, ZY + 12, Z + 10); SIM.tick(3)
    SIM.key('IK_E'); SIM.tick(2)
    F = pieces(UF)[0]; fx, fy, fz = F.o.x, F.o.y, F.o.z
    hold_at('fo4_workshop_shackwallflat03', fx + 0.2, fy + 0.2, fz - 3.2 + 0.2, 180, (fx, fy - 9)); SIM.tick(1)   # (its top by the floor's underside; facing in)
    o = st.place.o
    check(st.place.ok and st.snapped and st.snapped.key == UF and abs(o.z - (fz - 3.2)) < 0.02,
          'snap mode: a wall aimed under a hovering upper floor hangs from it, its top on the floor underside (%.2f below, %s)' % (fz - o.z, st.snapped and st.snapped.key))
    # wall decor sticks to the wall under the crosshair, flat against it: its autoplace point on the face, +Y into it
    PO = 'fo4_dlc05_posteraframe01'
    stand(ax_, ay_ - 3); fo4_hold(PO); look_at(ax_ + 0.3, ay_ + 1.8, az_ + 1.5); SIM.tick(3)
    m = lua('''function(k) local st = SIM.mod.state local it = SIM.it(k) local m = it.mount local a = SIM.axes(st.place.yaw)
        local c, s = math.cos(math.rad(m.dir)), math.sin(math.rad(m.dir))
        return a[1] * c + a[3] * s, a[2] * c + a[4] * s, st.place.o.y + a[2] * m.x + a[4] * m.y, st.place.o.z + m.z end''')(PO)
    check(st.place.ok and m[1] > 0.99 and ay_ + 1.6 < m[2] < ay_ + 2.0 and abs(m[3] - (az_ + 1.5)) < 0.3,
          'wall decor: a poster aimed at a wall lies flat on it, facing out, at the crosshair (into-wall dir %.2f, %.2f; at y+%.2f)' % (m[0], m[1], m[2] - ay_))
    NL = 'fo4_dlc02workshopneonlightletter01-red-b'
    fo4_hold(NL); look_at(ax_ + 0.3, ay_ + 1.8, az_ + 1.5); SIM.tick(3)
    m = lua('''function(k) local st = SIM.mod.state local m = SIM.it(k).mount local a = SIM.axes(st.place.yaw)
        local c, s = math.cos(math.rad(m.dir)), math.sin(math.rad(m.dir))
        return a[2] * c + a[4] * s, st.place.o.y + a[2] * m.x + a[4] * m.y, st.place.o.z + m.z end''')(NL)
    check(st.place.ok and m[0] > 0.99 and ay_ + 1.6 < m[1] < ay_ + 2.0 and abs(m[2] - (az_ + 1.5)) < 0.3,
          'a neon letter with no letter to join goes on the wall like decor (into-wall %.2f, at y+%.2f, z+%.2f)' % (m[0], m[1] - ay_, m[2] - az_))
    PF = 'fo4_workshop_shackprefabcompletesm01'             # ... and on a prefab's wall (its hollow walk-in boxes)
    stand(ZX - 20, ZY - 14); fo4_hold(PF); look_at(ZX - 20, ZY - 6, Z); SIM.tick(3); SIM.key('IK_E'); SIM.release('IK_E'); SIM.tick(2)
    P = pieces(PF)
    if P:
        pmin = lua('function(k) return SIM.it(k).min[2] end')(PF)
        wy = P[0].o.y + pmin                                    # its south face (placed at yaw 0)
        stand(P[0].o.x, wy - 3); fo4_hold(NL); look_at(P[0].o.x, wy, az_ + 1.6); SIM.tick(3)
        m = lua('''function(k) local st = SIM.mod.state local m = SIM.it(k).mount local a = SIM.axes(st.place.yaw)
            local c, s = math.cos(math.rad(m.dir)), math.sin(math.rad(m.dir))
            return a[2] * c + a[4] * s, st.place.o.y + a[2] * m.x + a[4] * m.y, st.place.o.z + m.z end''')(NL)
        hy = lua('function() local a = SIM.mod.aim() return a.point and a.point.y, a.piece and a.piece.key end')()
        wy = hy[0] if hy[0] else wy                             # (the wall is where the crosshair meets it: the porch roof sticks out)
        check(st.place.ok and m[0] > 0.99 and abs(m[1] - wy) < 0.1 and m[2] > az_ + 1.0 and hy[1] == PF,
              "a neon letter aimed at a prefab shack's wall goes on that wall (into-wall %.2f, %.2f m off the face, z+%.2f)" % (m[0], m[1] - wy, m[2] - az_))
    else: check(False, 'a prefab shack placed for the wall-letter check')
    # decor stands on what the crosshair is on: a radio on a table top
    TB, RD = 'fo4_metaltableround01', 'fo4_radiofreedomreceiveroff'
    stand(ZX + 20, ZY + 16); fo4_hold(TB); look_at(ZX + 20, ZY + 20, Z); SIM.tick(3); SIM.key('IK_E'); SIM.tick(2)
    T = pieces(TB)[0]
    fo4_hold(RD); look_at(T.o.x, T.o.y, T.o.z + 0.8); SIM.tick(3)
    top = lua('function(k) return SIM.it(k).max[3] end')(TB)
    check(st.place.ok and abs(st.place.o.z - (T.o.z + top)) < 0.12 and st.snapped and st.snapped.key == TB,
          'decor on a table: aimed at its top, it stands on it (%.2f above the table base, top %.2f)' % (st.place.o.z - T.o.z, top))
    # a door snaps into a doorway frame (the frame's P-Door-Dif2 takes the door's P-Door-Dif)
    DW, DR = 'fo4_workshop_shackmetalprefabdoorway01', 'fo4_workshop_utilmetaldoor01'
    stand(ZX + 20, ZY - 16); fo4_hold(DW); look_at(ZX + 20, ZY - 8, Z); SIM.tick(3); SIM.key('IK_E'); SIM.tick(2)
    Dp = pieces(DW)[0]
    pt = lua('''function(k, p) for _, c in ipairs(SIM.it(k).connect) do
        if c.name:lower() == "p-door-dif2" then local a = SIM.axes(p.yaw) return p.o.x + a[1] * c.x + a[3] * c.y, p.o.y + a[2] * c.x + a[4] * c.y, p.o.z + c.z end end end''')(DW, Dp)
    hy = (Dp.yaw + 270) % 360
    hold_at(DR, *pt_at(DR, 'P-Door-Dif', pt[0] + 0.1, pt[1] + 0.2, pt[2], hy), hy, (Dp.o.x - 8, Dp.o.y)); SIM.tick(1)   # (its hinge point by the frame's)
    check(st.snapped and st.snapped.key == DW and st.place.ok, 'a door aimed at a doorway frame snaps into it (%s)' % (st.snapped and st.snapped.key))
    # Fallout's own animations: the door, placed, opens on E outside workshop mode (its leaf swings, its collider off)
    SIM.key('IK_E'); SIM.release('IK_E'); SIM.tick(2)
    Dd = [p for p in pieces(DR)]
    check(len(Dd) == 1 and SIM.it(DR).anim and SIM.mod.anim.kind(SIM.it(DR).anim) == 'door', 'a Fallout door comes with its Open and Close sequences')
    if Dd:
        lua('function() SIM.mod.exit() end')(); SIM.tick(2)
        stand(Dd[0].o.x - 2.0, Dd[0].o.y); look_at(Dd[0].o.x, Dd[0].o.y, Dd[0].o.z + 1.2); SIM.tick(4)
        check(st.useLabel == 'Open' and SIM.useUI and SIM.useUI.label == 'Open' and SIM.useUI.key == 'F', 'a closed door in reach: the prompt on it says Open, by F (%s, %s)' % (st.useLabel, SIM.useUI and SIM.useUI.label))
        lua('function() SIM.mod.keys.bind("hold", "IK_G") end')(); SIM.tick(4)
        ug = SIM.useUI and SIM.useUI.key
        lua('function() SIM.mod.keys.bind("hold", "IK_F") end')(); SIM.tick(4)
        check(ug == 'G', 'the use key rebound to G: the prompt on the door shows G (%s)' % ug)
        SIM.key('IK_F'); SIM.release('IK_F'); SIM.tick(150)          # (F tapped: the game's interact key)
        at = lua('function() for _, a in pairs(SIM.mod.state.anims) do return a.at, a.mesh and a.mesh[1] and a.mesh[1].lq ~= nil, a.col and a.col[1] and a.col[1].on end end')()
        check(at[0] == 'Open' and at[1] and at[2] == False, "E opens it: its leaf turns, its collider component is switched off (%s, moved %s, collider on %s)" % tuple(at))
        SIM.tick(4)
        check(st.useLabel == 'Close', 'an open door: the prompt says Close (%s)' % st.useLabel)
        SIM.key('IK_F'); SIM.release('IK_F'); SIM.tick(150)
        at = lua('function() for _, a in pairs(SIM.mod.state.anims) do return a.at, a.col and a.col[1] and a.col[1].on end end')()
        check(at[0] == 'Close' and at[1] == True, 'E again closes it, its collider component back on (%s, %s)' % tuple(at))
        evs = lua('function() local o = {} for _, x in ipairs(SIM.sfx or {}) do if x.play then o[#o + 1] = x.ev end end return table.concat(o, " ") end')()
        check('hs_drsmetalsingleutil01open_' in evs and 'hs_drsmetalsingleutil01close_' in evs,
              "the door's own Fallout sounds play as it opens and shuts (%s)" % evs[-80:])
        lua('function() SIM.mod.build() end')(); SIM.tick(1)
        LP = 'fo4_workshopstreetlamp01'
        stand(Dd[0].o.x + 6, Dd[0].o.y - 6); fo4_hold(LP); look_at(Dd[0].o.x + 6, Dd[0].o.y - 3, Z); SIM.tick(3)
        SIM.key('IK_E'); SIM.release('IK_E'); SIM.tick(2)
        L = pieces(LP)
        lua('function() SIM.mod.exit() end')(); SIM.tick(2)
        if L:
            stand(L[0].o.x + 2.0, L[0].o.y); look_at(L[0].o.x, L[0].o.y, L[0].o.z + 1.5); SIM.tick(4)
            l1 = st.useLabel
            SIM.key('IK_F'); SIM.release('IK_F'); SIM.tick(4)
            check(l1 == 'Turn off' and st.useLabel == 'Turn on', 'a lamp, lit, says Turn off; E puts it out and it says Turn on (%s, %s)' % (l1, st.useLabel))
        else: check(False, 'a street lamp placed for the switch check')
        lua('function() SIM.mod.build() end')(); SIM.tick(1)
        NL = 'h_poor_desk_lamp_a'                            # a Night City lamp: off, its mesh shows its off look
        stand(Dd[0].o.x + 6, Dd[0].o.y - 10); fo4_hold(NL); look_at(Dd[0].o.x + 6, Dd[0].o.y - 7, Z); SIM.tick(3)
        SIM.key('IK_E'); SIM.release('IK_E'); SIM.tick(2)
        N = pieces(NL)
        lua('function() SIM.mod.exit() end')(); SIM.tick(2)
        looks = lambda: tuple(lua('''function(h) local e = SIM.ents[h]
            local function on(c) if not c then return "none" end if c.on ~= nil then return c.on end return c.isEnabled end
            local o = e:FindComponentByName(CName.new("hs_off"))
            return o and o.meshAppearance.hash, on(e:FindComponentByName(CName.new("hs_mesh1"))), on(o) end''')(N[0].id.hash)) if N else None
        if N:
            l0 = looks()
            stand(N[0].o.x + 1.5, N[0].o.y); look_at(N[0].o.x, N[0].o.y, N[0].o.z + 0.3); SIM.tick(4)
            SIM.key('IK_F'); SIM.release('IK_F'); SIM.tick(4)
            l1 = looks()
            SIM.key('IK_F'); SIM.release('IK_F'); SIM.tick(4)
            l2 = looks()
            check(l0 == (SIM.it(NL).off, True, False) and l1[1:] == (False, True) and l2[1:] == (True, False),
                  "a Night City lamp switched off shows its mesh's off look, on again its lit one (%s, %s, %s)" % (l0, l1, l2))
        else: check(False, 'a Night City lamp placed for the off-look check')
        lua('function() SIM.mod.build() end')(); SIM.tick(1)
    # a Fallout container stores things: the game's stash device rides in it (Open Stash on it opens V's stash)
    FL = 'fo4_footlocker01'
    stand(ZX + 12, ZY - 20); fo4_hold(FL); look_at(ZX + 12, ZY - 16, Z); SIM.tick(3); SIM.key('IK_E'); SIM.release('IK_E'); SIM.tick(3)
    stashes = lua('''function() local n, part = 0, 0 for _, e in pairs(SIM.ents) do local t = tostring(e.spec.templatePath)
        if t:find("stash.ent") then n = n + 1 for _, g in ipairs(e.spec.tags) do if g.hash == "Homestead.part" then part = part + 1 end end end end return n, part end''')()
    F = pieces(FL)
    check(len(F) == 1 and stashes[0] == 1 and stashes[1] == 1 and F[0].parts and len(F[0].parts) == 1,
          'a footlocker brings its stash device, a part of it (%d stash, %d tagged part)' % tuple(stashes))
    SIM.tick(30)
    sb = lua('''function() for _, e in pairs(SIM.ents) do if e:GetClassName().value == "Stash" then
        local col, slot, mesh, ours = e.comps[1], e.comps[2], e.comps[3], 0
        for _, c in ipairs(e.comps) do if c.name and tostring(c.name.hash):find("^hs_") then ours = ours + 1 end end
        return ours, col.colliders and #col.colliders or 0, slot.localTransform ~= nil, tostring(col.on), tostring(mesh.on) end end end''')()
    check(sb and sb[0] == 0 and sb[1] == 1 and sb[2] and sb[3] == 'false' and sb[4] == 'false',
          "the stash device's own branch: no meshes of ours, its collider the container's box, its icon over it, then all of it off (%s)" % (sb,))
    lua('function(p) local S = SIM.mod.state if not S.build then SIM.mod.build() end S.level, S.hold = 0, nil S.target = p end')(F[0]); SIM.key('IK_R'); SIM.release('IK_R'); SIM.tick(2)
    gone = lua('''function() local n = 0 for _, e in pairs(SIM.ents) do if tostring(e.spec.templatePath):find("stash.ent") then n = n + 1 end end return n end''')()
    check(not pieces(FL) and gone == 0, 'scrapped, its stash goes with it (%d left)' % gone)
    lua('function() SIM.defer = nil end')()
    scenario(101)
    # people use furniture: a placed person walks to a free chair, sits on it (one of Cyberpunk's chair workspots, on a
    # device at the chair's own Fallout marker), gets up after a while, and the device goes
    CH = 'fo4_npcchairvaultsit03'
    stand(ZX + 18, ZY - 20); fo4_hold(CH); look_at(ZX + 18, ZY - 16, Z); SIM.tick(3); SIM.key('IK_E'); SIM.release('IK_E'); SIM.tick(3)
    fo4_hold('npc_judy'); look_at(ZX + 21, ZY - 16, Z); SIM.tick(3); SIM.key('IK_E'); SIM.release('IK_E'); SIM.tick(3)
    lua('function() SIM.mod.exit() end')(); SIM.tick(2)
    C0 = pieces(CH)
    res = lua('''function(cx, cy)
        local L = SIM.mod.life
        local sat, path, near, dev, up, gone
        for i = 1, 1500 do
            local ok, err = pcall(L.tick, 1)
            if not ok then return false, err end
            SIM.step()                               -- (a frame: deletions are done at a frame's start)
            for h, st in L.people() do
                if st.mode == "use" and st.seat and st.seat.piece and st.seat.piece.key == "fo4_npcchairvaultsit03" and not sat then
                    sat, dev = true, st.dev
                    local d = SIM.ents[dev.hash]
                    for _, c in ipairs(d and d.comps or {}) do if c.workspotResource then path = c.workspotResource end end
                    local q = d and d.spec.position
                    near = q and (q.x - cx) ^ 2 + (q.y - cy) ^ 2 < 1
                end
                if sat and st.dev ~= dev then up = true end
            end
            if up and not SIM.ents[dev.hash] then gone = true break end
        end
        return sat, path, near, up, gone end''')(C0[0].o.x, C0[0].o.y) if C0 else (None,) * 5
    check(bool(res[0]) and 'sit_chair' in str(res[1]) and res[2], 'a placed person sits on a Fallout chair: a chair workspot on a device at its marker (%s)' % (res[1],))
    check(bool(res[3]) and bool(res[4]), 'they get up after a while, and the device is deleted')
    dd = lua('''function()
        local L = SIM.mod.life
        for _, st in L.people() do st.like = { relax = 50, work = 0, look = 0, chat = 0, idle = 0.01, wander = 0 } end
        local dev
        for i = 1, 1500 do L.tick(1) for _, st in L.people() do if st.mode == "use" and st.dev then dev = st.dev end end if dev then break end end
        for _, st in L.people() do st.like = nil end
        if not dev then return "nobody sat" end
        L.reset()
        local kept = SIM.ents[dev.hash] ~= nil
        for i = 1, 7 do L.tick(1) SIM.step() end
        return tostring(kept) .. " " .. tostring(SIM.ents[dev.hash] == nil) end''')()
    check(dd == 'true true', 'everyone up at once (a reset): the device they sat on stays for their exit, deleted a few seconds on (%s)' % dd)
    scenario(102)
    # a seat something else stands in the way of (a wall across its front): known as out of reach, left be
    if C0:
        c0 = C0[0]
        fwd = lua('function(p) local r = math.rad(p.yaw) return p.o.x - math.sin(r) * 0.6, p.o.y + math.cos(r) * 0.6, p.yaw end')(c0)
        lua('''function(x, y, z, cx, cy)                     -- (whoever got up in front of the chair: off to the side first - the
            for _, st in SIM.mod.life.people() do        -- table would land on them, and a person inside a piece never picks)
                local e = SIM.ents[tonumber(st.h)] or SIM.ents[st.h]
                if e and e.pos and (e.pos.x - x) ^ 2 + (e.pos.y - y) ^ 2 < 4 then e.pos = Vector4.new(cx + 2.5, cy + 2.5, z, 1) end
            end end''')(fwd[0], fwd[1], c0.o.z, c0.o.x, c0.o.y)
        stand(fwd[0] + 2.5, fwd[1]); fo4_hold('fo4_metaltableround01')   # (near: someone may stand further back on the line)
        look_at(fwd[0], fwd[1], Z); SIM.tick(3); SIM.key('IK_E'); SIM.release('IK_E'); SIM.tick(2)   # (its middle on that spot)
        lua('function() SIM.mod.exit() end')(); SIM.tick(2)
        bl = lua('''function(x, y, z)
            local L = SIM.mod.life
            local blocked = not L.backend().free(x, y, z)
            local sat, from = false, nil
            for _, st in L.people() do st.like = { relax = 50, work = 0, look = 0, chat = 0, idle = 0.01, wander = 0 } end   -- (sitters, not
            local tr = {}
            L.trace = function(ev, st, s, ok) if #tr < 30 then tr[#tr + 1] = string.format("%s %s %s %s path%d", ev, tostring(s.kind), tostring(s.piece and s.piece.key or "-"), tostring(ok), st.goal and 1 or 0) end end
            for i = 1, 3000 do                                                                                                         -- a random day)
                L.tick(1)
                for h, st in L.people() do
                    if st.seat and st.seat.piece and st.seat.piece.key == "fo4_npcchairvaultsit03" then
                        local e = st.goal
                        if st.mode == "walk" and e then from = from or e end
                        if st.mode == "use" and from then sat = true end
                    end
                end
                if sat then break end
            end
            local m = {}                                                        -- (who did what, if nobody sat: the fail's text)
            for h, st in L.people() do m[#m + 1] = tostring(st.mode) .. ":" .. tostring(st.act) .. ":" .. tostring(st.seat and st.seat.kind) .. ":" .. tostring(st.seat and st.seat.piece and st.seat.piece.key) .. ":" .. tostring(st.last) end
            local taken, cut, now, marks = L.dbg()
            for _, sm in ipairs(marks) do
                if sm.piece.key == "fo4_npcchairvaultsit03" then
                    local r = math.rad(sm.yaw)
                    local fr = {}
                    for _, d in ipairs({ { 0, 0.6 }, { 0.6, 0 }, { -0.6, 0 }, { 0, -0.6 } }) do
                        local fx, fy = -math.sin(r), math.cos(r)
                        local px, py = sm.x + d[1] * fy + d[2] * fx, sm.y - d[1] * fx + d[2] * fy
                        fr[#fr + 1] = tostring(L.backend().free(px, py, sm.z))
                    end
                    m[#m + 1] = string.format("chair %s taken=%s cut=%s now=%.0f ways=%s at %.1f,%.1f,%.2f", sm.kind, tostring(taken[sm.key]), tostring(cut[sm.key]), now, table.concat(fr, ","), sm.x, sm.y, sm.z)
                end
            end
            for _, st in L.people() do st.like = nil end
            L.trace = nil
            m[#m + 1] = string.format("allow w%s f%s t%s", tostring(L.allow.walk), tostring(L.allow.furniture), tostring(L.allow.talk))
            for h, st in L.people() do
                local e = SIM.ents[tonumber(h)] or SIM.ents[h]
                local q = e and e.pos
                m[#m + 1] = string.format("person set=%s like.relax=%s at=%s", tostring(st.set), tostring(st.like and st.like.relax), q and string.format("%.1f,%.1f,%.1f", q.x, q.y, q.z) or "?")
            end
            m[#m + 1] = "trace: " .. table.concat(tr, " | ")
            local clear = from and L.backend().free(from.x, from.y, from.z)
            return blocked, sat, clear and math.sqrt((from.x - x) ^ 2 + (from.y - y) ^ 2) or -1, table.concat(m, " ") end''')(fwd[0], fwd[1], c0.o.z)
        Tb = [p for p in pieces('fo4_metaltableround01') if (p.o.x - fwd[0]) ** 2 + (p.o.y - fwd[1]) ** 2 < 4]
        check(bl[0] and bl[1] and bl[2] >= 0, "a chair with a table across its front: they come at it from free ground and sit (front blocked %s, sat %s, came %.2f m off the front; %s)" % (bl[0], bl[1], bl[2], bl[3]))
        for p in Tb:                                                                                  # (gone again)
            lua('function(p) local S = SIM.mod.state if not S.build then SIM.mod.build() end S.level, S.hold = 0, nil S.target = p end')(p); SIM.key('IK_R'); SIM.release('IK_R'); SIM.tick(2)
        lua('function() SIM.mod.exit() end')(); SIM.tick(2)
    lfile = open(os.path.join(ROOT, 'bin/x64/plugins/cyber_engine_tweaks/mods/Homestead/modules/life.lua'), encoding='utf-8').read()
    import re
    wsn = re.findall(r'"([a-z_]+)\\\\([a-z0-9_]+__[a-z0-9_]+)"', lfile)
    miss = [f + '/' + n for f, n in wsn if not os.path.exists(os.path.join(ROOT, 'source/json/homestead/workspots', f, n + '.workspot.json'))]
    check(str(res[1]).startswith('homestead\\workspots\\') and wsn and not miss,
          "workspots are our looping copies (the game's play once and get up): %d, none missing %s" % (len(wsn), miss[:3]))
    scenario(103)
    # a day's rhythm: things done for a while (not up and down every few seconds), and two people meeting to talk
    rh = lua('''function()
        local L = SIM.mod.life
        local n, used, chats, faced, last = 0, 0, 0, false, {}
        for i = 1, 1800 do
            L.tick(1)
            for h, st in L.people() do
                if st.mode == "use" and last[h] ~= st.seat then n = n + 1; last[h] = st.seat end
                if st.mode == "use" then used = used + 1 end
                if st.mode == "use" and st.act == "chat" and st.partner then
                    local o = L.state()[st.partner]
                    if o and o.mode == "use" and o.act == "chat" then
                        chats = chats + 1
                        local d = math.abs(((st.seat.yaw - o.seat.yaw) % 360) - 180)
                        if d < 20 then faced = true end
                    end
                end
            end
        end
        return n, used / math.max(n, 1), chats, faced end''')()
    check(rh[0] > 0 and rh[1] >= 45, 'a day: each thing done for a while (%d things in 30 min, %.0f s each on average)' % (rh[0], rh[1]))
    ch = lua('''function()
        local L = SIM.mod.life
        local first
        for _, st in L.people() do
            st.like = { relax = 0, work = 0, look = 0, chat = 50, idle = 0.01, wander = 0 }
            if st.mode == "use" then st.t = 0 end                  -- (everyone up)
            local e = SIM.ents[st.id.hash]
            if e and not first then first = e.pos elseif e then e.pos = Vector4.new(first.x + 4, first.y, first.z, 1) end
        end
        local chats, faced = 0, false
        for i = 1, 400 do
            L.tick(1)
            for h, st in L.people() do
                if st.mode == "use" and st.act == "chat" and st.partner then
                    local o = L.state()[st.partner]
                    if o and o.mode == "use" and o.act == "chat" and o.partner == h then
                        chats = chats + 1
                        if math.abs(((st.seat.yaw - o.seat.yaw) % 360) - 180) < 20 then faced = true end
                    end
                end
            end
        end
        for _, st in L.people() do st.like = nil end
        return chats, faced end''')()
    check(ch[0] > 0 and ch[1], 'two people meet to talk, standing facing each other (%d s of talk)' % ch[0])
    pc = lua('''function()                                      -- (what people cost: their tick, once a second; walkers,
        local L, n = SIM.mod.life, 0                            -- four times a second - Lua time, per person)
        for _ in L.people() do n = n + 1 end
        for _, st in L.people() do st.like = { relax = 0, work = 0, look = 0, chat = 0, idle = 0.01, wander = 50 } end
        local t0, tt, tf = os.clock(), 0, 0
        for i = 1, 300 do
            local a = os.clock(); L.tick(1); tt = tt + os.clock() - a
            for _ = 1, 4 do local b = os.clock(); L.frame(0.25); tf = tf + os.clock() - b end
        end
        for _, st in L.people() do st.like = nil end
        return n, tt / 300 * 1000 / math.max(n, 1), tf / 1200 * 1000 / math.max(n, 1) end''')()
    check(pc[0] >= 2 and pc[1] < 0.5 and pc[2] < 0.1,
          'people are cheap: %d people wandering, %.3f ms each a second (their tick) + %.3f ms each a quarter second walking (Lua)' % (pc[0], pc[1], pc[2]))
    scenario(104)
    # nobody stands in anybody: a standing spot where someone already is (or is going) is turned down
    cr = lua('''function()
        local L = SIM.mod.life
        local a, b
        for _, st in L.people() do if not a then a = st elseif not b then b = st end end
        if not (a and b) then return "fewer than two people" end
        local e = SIM.ents[a.id.hash]
        for _, st in L.people() do st.like = { relax = 0, work = 0, look = 0, chat = 0, idle = 50, wander = 0 } end
        local bad = 0
        for i = 1, 300 do
            L.tick(1)
            local ea, eb = SIM.ents[a.id.hash], SIM.ents[b.id.hash]
            local ga, gb = a.mode ~= "use" and a.seat, b.mode ~= "use" and b.seat
            if a.seat and b.seat and not a.seat.key and not b.seat.key and a.partner ~= b.h
               and (a.seat.x - b.seat.x) ^ 2 + (a.seat.y - b.seat.y) ^ 2 < 0.49 then bad = bad + 1 end
            if i == 50 and eb and ea then eb.pos = Vector4.new(ea.pos.x + 0.2, ea.pos.y, ea.pos.z, 1) end   -- (one walks into the other)
        end
        for _, st in L.people() do st.like = nil end
        return bad end''')()
    check(cr == 0, 'two people never take standing spots within a body of each other (%s s overlapping)' % (cr,))
    scenario(105)
    # a seat scrapped (or picked up) while someone sits on it: they get up at once, in workshop mode too
    sc = lua('''function()
        local L, M = SIM.mod.life, SIM.mod
        local user
        if M.state.build then M.exit() end                      -- (people only act outside workshop mode)
        L.tick(1)                                               -- (everyone known again after workshop mode: their likes stick)
        local chair, k = nil, 0
        for _, p in ipairs(M.state.pieces) do if p.key == "fo4_npcchairvaultsit03" then chair = p end end
        for _, st in L.people() do                              -- (a few steps from a chair: where the day before left
            local e = SIM.ents[st.id.hash]                      -- them isn't this check's business)
            if e and chair then k = k + 1; e.pos = Vector4.new(chair.o.x + 2 + k, chair.o.y + 2.5, chair.o.z, 1) end
            st.goal, st.mode, st.t = nil, "idle", 0
            local taken = L.dbg()                               -- (whatever seat the day before had them on the
            for k, h in pairs(taken) do if h == st.h then taken[k] = nil end end   -- way to: let go)
            st.seat = nil
        end
        for _, st in L.people() do st.like = { relax = 50, work = 0, look = 0, chat = 0, idle = 0.01, wander = 0 } end
        for i = 1, 1500 do
            L.tick(1)
            for _, st in L.people() do if st.mode == "use" and st.seat and st.seat.piece then user = st end end
            if user then break end
        end
        for _, st in L.people() do st.like = nil end
        if not user then
            local m = {}
            for _, st in L.people() do m[#m + 1] = tostring(st.mode) .. ":" .. tostring(st.act) .. ":" .. tostring(st.seat and st.seat.kind) end
            return "nobody sat (" .. table.concat(m, " ") .. ")"
        end
        local p = user.seat.piece
        M.build()
        local S = M.state
        S.level, S.hold, S.target = 0, nil, p
        SIM.key("IK_R"); SIM.release("IK_R"); SIM.tick(2)
        local scrapped = true
        for _, q in ipairs(S.pieces) do if q == p then scrapped = false end end
        local r = string.format("%s %s %s", tostring(scrapped), user.mode, tostring(user.seat == nil))
        M.exit()
        for _, st in L.people() do st.goal, st.mode, st.t = nil, "idle", 30 end   -- (settled again for what follows)
        return r end''')()
    SIM.tick(2)
    check(sc.startswith('true idle true'), 'a seat scrapped in workshop mode while someone sits on it: they get up at once (scrapped, mode, seat let go: %s)' % (sc,))
    scenario(106)
    # a person who walked off is where they are now: aimed at there, scrapped
    J = pieces('npc_judy')
    if J:
        lua('function(h, x, y, z) SIM.ents[h].pos = Vector4.new(x, y, z, 1) end')(J[-1].id.hash, ZX + 24, ZY - 24, Z)
        lua('function() SIM.mod.exit() end')(); SIM.tick(70)
        stand(ZX + 24, ZY - 28); look_at(ZX + 24, ZY - 24, Z + 1.0)
        lua('function() local S = SIM.mod.state if not S.build then SIM.mod.build() end S.level, S.hold = 0, nil end')(); SIM.tick(3)
        tgt = st.target.key if st.target else None
        SIM.key('IK_R'); SIM.release('IK_R'); SIM.tick(2)
        left = [p for p in pieces('npc_judy') if p.id.hash == J[-1].id.hash]
        check(tgt == 'npc_judy' and not left, 'a person who walked off is aimed at where they are and scrapped (%s, %d left)' % (tgt, len(left)))
    else: check(False, 'a placed person for the scrap check')
    lua('function() SIM.mod.build() end')(); SIM.tick(1)
    scenario(107)
    # a closed door opens for a person walking up to it, and stays open behind them - near its span, not only its middle:
    # the walker comes up lx m along the door from its middle, 1 m in front of it
    door_walk = lua('''function(key, lx)
        local M, S = SIM.mod, SIM.mod.state
        if S.build then M.exit() end
        local door, who
        for _, p in ipairs(S.pieces) do
            if p.key == key then door = p end
            if p.it.npc then who = p end
        end
        if not (door and who) then return "no door or person" end
        if M.anim.label(door) ~= "Open" then M.anim.use(door) for _ = 1, 60 do M.anim.tick(1 / 15) end end
        M.life.tick(0)
        local st = M.life.state()[tostring(who.id.hash)]
        local e = SIM.ents[who.id.hash]
        local a = SIM.axes(door.yaw)
        local function at(ly) local x, y = door.it.cx + lx, door.it.cy + ly
            return Vector4.new(door.o.x + a[1] * x + a[3] * y, door.o.y + a[2] * x + a[4] * y, door.o.z, 1) end
        e.pos = at(-1.0)
        local far = at(3)
        st.goal, st.best, st.stuck, st.mode = { x = far.x, y = far.y, z = far.z }, math.huge, 0, "walk"   -- (walking there)
        M.life.frame(0.3)
        for _ = 1, 60 do M.anim.tick(1 / 15) end
        local was = tostring(M.anim.label(door))
        e.pos = at(4)
        M.life.frame(0.3)
        for _ = 1, 60 do M.anim.tick(1 / 15) end
        st.goal, st.mode = nil, "idle"
        local now = tostring(M.anim.label(door))
        if now == "Close" then M.anim.use(door) for _ = 1, 60 do M.anim.tick(1 / 15) end end   -- (left shut for the checks after)
        return was .. " then " .. now end''')
    dr = door_walk('fo4_workshop_utilmetaldoor01', 1.2)
    check(dr == 'Close then Close', 'a closed door opens for a person walking up to it 1.2 m off its middle (by its span) and stays open behind them (%s)' % dr)
    GD = 'fo4_dlc05workshopwarehousegaragedoor01'               # (the 7.3 m Rolling Metal Door: walked up to 3 m off its middle)
    lua('function() SIM.mod.build() end')(); SIM.tick(1)
    stand(ZX + 2, ZY - 26); fo4_hold(GD); look_at(ZX + 2, ZY - 20, Z); SIM.tick(3); SIM.key('IK_E'); SIM.release('IK_E'); SIM.tick(2)
    dr = door_walk(GD, 3.0) if pieces(GD) else 'not placed'
    check(dr == 'Close then Close', 'the rolling garage door opens for a person walking up to it near one end, and stays open behind them (%s)' % dr)
    scenario(108)
    # Command mode (hold C): a person selected, assigned to a chair - they go and sit, and stay; R releases them
    stand(ZX + 12, ZY - 20); fo4_hold(CH); look_at(ZX + 12, ZY - 16, Z); SIM.tick(3); SIM.key('IK_E'); SIM.release('IK_E'); SIM.tick(3)   # (a chair of its own: the
    look_at(ZX + 15, ZY - 16, Z); SIM.tick(3); SIM.key('IK_E'); SIM.release('IK_E'); SIM.tick(3)                                             # earlier one was scrapped;
                                                                                                                                             # another 3 m east)
    lua('function() SIM.mod.exit() end')(); SIM.tick(2)                                                                                        # earlier one was scrapped)
    cm = lua('''function()
        local M, S = SIM.mod, SIM.mod.state
        if S.build then M.exit() end
        M.refresh(); M.life.sync()
        local who, chair
        for _, p in ipairs(S.pieces) do if p.it.npc and not who then who = p end if p.key == "fo4_npcchairvaultsit03" and not chair then chair = p end end
        if not (who and chair) then return nil end
        local e = SIM.ents[who.id.hash]                      -- (the person a few steps from the chair: both in reach)
        e.pos = Vector4.new(chair.o.x - 4, chair.o.y, chair.o.z, 1)
        M.life.sync()
        return tostring(who.id.hash), tostring(chair.id.hash), e.pos.x, e.pos.y, e.pos.z, chair.o.x, chair.o.y, chair.o.z end''')()
    if cm:
        wh, ch, wx, wy, wz, cx, cy, cz = cm
        stand(cx - 2, cy - 4); look_at(wx, wy, wz + 1.0)
        SIM.key('IK_R'); SIM.tick(45); SIM.release('IK_R'); SIM.tick(2)
        c1 = (st.cmd is not None, bool(st.target) and str(st.target.id.hash) == wh, 'Select' in hints())
        SIM.key('IK_E'); SIM.release('IK_E'); SIM.tick(1)
        c2 = bool(st.cmd and st.cmd.who and st.cmd.who.h == wh)
        look_at(cx, cy, cz + 0.4); SIM.tick(2)
        c3 = bool(st.target) and str(st.target.id.hash) == ch
        SIM.key('IK_E'); SIM.release('IK_E'); SIM.tick(1)
        job = lua('function(h) return SIM.mod.life.jobOf(h) end')(wh)
        check(all(c1) and c2 and c3 and job == ch, 'Command mode: hold R, E on a person selects them, E on a chair assigns them to it (%s %s %s job %s)' % (c1, c2, c3, job == ch))
        jf = lua('function() return (HS_DIR or "") .. "jobs.txt" end')()
        saved = os.path.exists(jf) and wh in open(jf).read()
        sat = lua('''function(h, ch)
            local L = SIM.mod.life
            for i = 1, 600 do
                L.tick(1)
                local st = L.state()[h]
                if st and st.mode == "use" and st.seat and st.seat.piece and tostring(st.seat.piece.id.hash) == ch then return i end
            end
            local st = L.state()[h]
            return "not sat: " .. tostring(st and st.mode) .. " " .. tostring(st and st.act) end''')(wh, ch)
        check(saved and isinstance(sat, (int, float)), 'assigned: saved to jobs.txt, they go and sit on that chair (%s)' % (sat,))
        held = lua('''function(h) local L = SIM.mod.life for i = 1, 1200 do L.tick(1) end local st = L.state()[h] return st.mode, st.seat and tostring(st.seat.piece.id.hash) end''')(wh)
        check(held[0] == 'use' and held[1] == ch, 'they stay on it for good, 20 minutes on (%s)' % (held,))
        SIM.key('IK_R'); SIM.release('IK_R'); SIM.tick(1)
        rel = lua('function(h) local L = SIM.mod.life local st = L.state()[h] return L.jobOf(h) == nil, st.mode, st.seat == nil end')(wh)
        check(rel[0] and rel[1] == 'idle' and rel[2], 'R releases them: the job gone, up from the chair (%s)' % (rel,))
        # sitting, assigned to another chair: up and on their way at once (user: "they stood up from the seat they were
        # in, then just stood there" - the first try, still in the seat, failed and cut the chair off for a minute)
        mv = lua('''function(h, ch, x2, y2)
            local L, S = SIM.mod.life, SIM.mod.state
            local c1, c2
            for _, p in ipairs(S.pieces) do
                if tostring(p.id.hash) == ch then c1 = p
                elseif p.key == "fo4_npcchairvaultsit03" and (p.o.x - x2) ^ 2 + (p.o.y - y2) ^ 2 < 1 then c2 = p end
            end
            if not (c1 and c2) then return "no chairs" end
            L.job(h, c1)
            local st
            for _ = 1, 600 do L.tick(1); st = L.state()[h]; if st.mode == "use" then break end end
            if st.mode ~= "use" then return "never sat: " .. tostring(st.mode) end
            L.job(h, c2)
            local first, run, most = nil, 0, 0
            for i = 1, 70 do
                L.tick(1)
                if not first and st.seat and st.seat.piece == c2 then first = i end
                run = st.mode == "idle" and run + 1 or 0; most = math.max(most, run)
            end
            local r = string.format("%s %d %s", tostring(first), most, tostring(st.mode))
            L.unjob(h)
            return r end''')(wh, ch, cx + 3, cy)
        mvp = mv.split()
        check(len(mvp) == 3 and mvp[0].isdigit() and int(mvp[0]) <= 10 and int(mvp[1]) < 60 and mvp[2] in ('walk', 'spawn', 'use'),
              'sitting, assigned to another chair: within 10 s on their way to it, never stood idle a minute (tick, longest idle, mode: %s)' % mv)
        # E on the ground: a spot is a job - they walk there and stand by till cleared
        sp = lua('''function(h, x, y, z)
            local L = SIM.mod.life
            if not L.moveTo(h, { x = x, y = y, z = z }) then return "no spot" end
            local st = L.state()[h]
            local function there() local e = SIM.ents[st.id.hash] return math.sqrt((e.pos.x - x) ^ 2 + (e.pos.y - y) ^ 2) end
            for _ = 1, 200 do L.tick(1) end
            local a = string.format("%.2f %s %s", there(), st.mode, tostring(st.seat and st.seat.kind))
            for _ = 1, 1200 do L.tick(1) end
            local b = string.format("%.2f %s %s", there(), st.mode, tostring(st.seat and st.seat.kind))
            local saved = L.jobOf(h)
            L.unjob(h)
            return a .. " | " .. b .. " | " .. tostring(saved) .. " | " .. tostring(L.jobOf(h)) .. " " .. st.mode end''')(wh, cx - 4, cy + 2, cz)
        spp = [x.split() for x in sp.split(' | ')]
        check(len(spp) == 4 and float(spp[0][0]) < 1 and spp[0][1:] == ['use', 'idle'] and float(spp[1][0]) < 1 and spp[1][1:] == ['use', 'idle']
              and spp[2][0].count(',') == 2 and spp[3] == ['nil', 'idle'],
              'E on the ground: they walk there and stand by, still there 20 minutes on, the spot kept as their job; cleared, back to their day (%s)' % sp)
        SIM.key('IK_R'); SIM.tick(45); SIM.release('IK_R'); SIM.tick(2)
        check(st.cmd is None, 'hold R again leaves Command mode')
        # the keys as settings: a row each, the game's own binds on the key in its text; rebound, the handler and the hint follow
        rows = [o for o in lua('function() local t = {} for _, o in ipairs(SIM.ns.opts) do if o.kind == "key" then t[#t + 1] = o end end return t end')().values()]
        labels = [r.label for r in rows]
        cmdrow = next((r for r in rows if r.label.startswith('Command mode')), None)
        scraprow = next((r for r in rows if r.label == 'Scrap'), None)
        check(len(rows) == 7 and cmdrow and cmdrow.args[1] == 'IK_R' and cmdrow.args[3] is True and 'Reload' in cmdrow.desc
              and scraprow and 'Reload' in scraprow.desc and 'blocked in workshop mode' in scraprow.desc,
              'Settings > Keys: 7 rows; Command mode (hold) is R and its text names the game\'s Reload, blocked (%s)' % (labels,))
        cmdrow.args[4]('IK_X'); SIM.tick(1)
        kx = lua('function() return SIM.mod.keys.actionFor("command"), SIM.mod.keys.conflict("command") end')()
        kset = 'key.command=IK_X' in open(os.path.join(SETDIR, 'settings.txt')).read()
        SIM.key('IK_X'); SIM.tick(45); SIM.release('IK_X'); SIM.tick(2)
        on_x = st.cmd is not None
        SIM.key('IK_X'); SIM.tick(45); SIM.release('IK_X'); SIM.tick(2)
        check(kset and on_x and st.cmd is None and kx[0] is None and 'nothing on foot' in kx[1],
              'Command mode rebound to X: kept in settings.txt, hold X toggles it; X has no game action - no hint, and the text says so (%s)' % (kx[1],))
        cmdrow.args[4]('IK_R'); SIM.tick(1)
        check(lua('function() return SIM.mod.keys.actionFor("command") end')() == 'Reload', 'back on R: the hint borrows the game\'s Reload for its icon')
        lua('function() for _, st in SIM.mod.life.people() do st.goal, st.mode, st.t = nil, "idle", 30 end end')()
        # a bed: set onto its device first, then straight into entry 2 - the lie loop (entry 1, the root sequence,
        # had a woman lying diagonally across a bed)
        BED = 'fo4_workshopnpcbedmilitarycottlay01'
        stand(cx + 4, cy - 4); fo4_hold(BED); look_at(cx + 4, cy, cz); SIM.tick(3); SIM.key('IK_E'); SIM.release('IK_E'); SIM.tick(3)
        lua('function() SIM.mod.exit() end')(); SIM.tick(2)
        bd = lua('''function(h, key)
            local L, S = SIM.mod.life, SIM.mod.state
            local bed
            for _, p in ipairs(S.pieces) do if p.key == key then bed = p end end
            if not bed then return "no bed" end
            L.job(h, bed)
            SIM.jumps = {}
            for i = 1, 600 do
                L.tick(1)
                local st = L.state()[h]
                if st and st.mode == "use" and st.seat and st.seat.piece and st.seat.piece.key == key then
                    local e, d = SIM.ents[st.id.hash], SIM.ents[st.dev.hash]
                    local on = e and d and (e.pos.x - d.pos.x) ^ 2 + (e.pos.y - d.pos.y) ^ 2 < 1e-4
                    L.unjob(h)
                    return string.format("jump %s on %s", tostring(SIM.jumps[#SIM.jumps]), tostring(on))
                end
            end
            L.unjob(h)
            return "never lay down" end''')(wh, BED)
        check(bd == 'jump 2 on true', 'a bed: set onto its device, then a jump to entry 2, the lie loop (%s)' % bd)
        lua('function() for _, st in SIM.mod.life.people() do if st.mode ~= "use" then st.goal, st.mode, st.t = nil, "idle", 30 end end end')()
        # stale jobs (user, 2026-10-03: jobs.txt kept 10248651ULL after that person became 10249057ULL): a person with a
        # job picked up and put back (a new entity) takes it along - one entry, under the new id, in jobs.txt too; a
        # session drops a job whose person or piece is none of ours, logged with the count, and keeps the rest
        jm = lua('''function(h, ch)
            local L, S, M = SIM.mod.life, SIM.mod.state, SIM.mod
            local who, chair, before = nil, nil, {}
            for _, p in ipairs(S.pieces) do local k = tostring(p.id.hash) before[k] = true
                if k == h then who = p elseif k == ch then chair = p end end
            if not (who and chair) then return "no person or chair" end
            L.job(h, chair)
            M.build() SIM.tick(1)
            M.startMove(who) SIM.tick(2)
            M.restore() SIM.tick(2)
            M.exit() SIM.tick(2)
            local nh
            for _, p in ipairs(S.pieces) do local k = tostring(p.id.hash) if p.it.npc and not before[k] then nh = k end end
            local n = 0 for _, j in pairs(L.jobs) do if j == ch then n = n + 1 end end
            local f = io.open((HS_DIR or "") .. "jobs.txt", "r") local txt = f and f:read("*a") or "" if f then f:close() end
            local r = string.format("%s %s %d %s", tostring(nh ~= nil and L.jobs[nh] == ch), tostring(L.jobs[h] == nil), n,
                tostring(nh ~= nil and txt:find(nh .. "=" .. ch, 1, true) ~= nil and not txt:find(h .. "=", 1, true)))
            if not nh then return r end
            L.jobs["1ULL"], L.jobs[ch] = ch, "2ULL"           -- (no such person; one of ours on no such piece)
            SIM.said, SIM.print = {}, print
            print = function(s) SIM.said[#SIM.said + 1] = tostring(s) SIM.print(s) end
            return r .. "|" .. nh end''')(wh, ch)
        jmp = jm.split('|')
        SIM.session(); SIM.tick(130)                              # (the second refresh: the first one settles)
        jp = lua('''function(nh, ch) local L = SIM.mod.life
            print = SIM.print
            local logs = 0 for _, s in ipairs(SIM.said) do if s:find("jobs: 2 dropped", 1, true) then logs = logs + 1 end end
            local r = string.format("%s %s %s %d", tostring(L.jobs["1ULL"] == nil), tostring(L.jobs[ch] == nil), tostring(L.jobs[nh] == ch), logs)
            L.unjob(nh)
            return r end''')(jmp[1], ch) if len(jmp) == 2 else 'not run'
        check(jmp[0] == 'true true 1 true' and jp == 'true true true 1',
              'jobs: a person with a job picked up and put back - one entry, under the new id (jobs.txt too), none under the old (%s); a session drops a job whose person or whose piece is gone, keeps theirs, logged once (%s)' % (jmp[0], jp))
    else: check(False, 'a person and a chair for the Command mode check')
    scenario(114)
    # navigation off (Settings > People > Navigation; the backend changes at the next load, never mid-walk), and LiveNav
    # not installed with it on: the null backend - no pathing system touched, no move command, no LiveNav call - people
    # are props (user, 2026-10-04): they stay where they were put, nobody's day runs - a chair whose way in is where
    # someone stands is not sat on (till then it was), no device made, no workspot played, nobody in Life's list;
    # a spot order (Command mode, Life.moveTo) is refused - "Navigation off", no job, nothing asked (2026-10-03: it was
    # kept as the job). Back on with LiveNav there: walking again
    stand(ZX + 8, ZY - 34); fo4_hold('npc_judy'); look_at(ZX + 8, ZY - 30, Z); SIM.tick(3); SIM.key('IK_E'); SIM.release('IK_E'); SIM.tick(3)   # (a second person)
    lua('function() SIM.mod.exit() end')(); stand(ZX, ZY - 10); SIM.tick(2)
    null_day = lua('''function()
        local L, S, E = SIM.mod.life, SIM.mod.state, SIM.mod.calls
        if L.backend() ~= L.backends.null then return "not null" end
        local _, _, _, marks = L.dbg()
        local chair
        for _, s in ipairs(marks) do if s.kind == "chair" and s.piece.key == "fo4_npcchairvaultsit03" then chair = s break end end
        local people = {}
        for _, p in ipairs(S.pieces) do if p.it.npc then people[#people + 1] = p end end
        if not chair or #people < 2 then local k = {} for _, p in ipairs(S.pieces) do k[#k + 1] = p.key end return "no chair or fewer than two people: " .. #marks .. " marks " .. #people .. " people; " .. table.concat(k, " ") end
        local r = math.rad(chair.yaw)
        local a, b = SIM.ents[people[1].id.hash], SIM.ents[people[2].id.hash]
        a.pos = Vector4.new(chair.x - math.sin(r) * 0.6, chair.y + math.cos(r) * 0.6, chair.z, 1)   -- (on its way in)
        b.pos = Vector4.new(chair.x + math.sin(r) * 6, chair.y - math.cos(r) * 6, chair.z, 1)       -- (6 m behind it)
        local at = {}
        for i, p in ipairs(people) do local e = SIM.ents[p.id.hash] at[i] = { e.pos.x, e.pos.y } end
        local function calls() local n = 0 for _, v in pairs(LN.n) do n = n + v end
            local ws = 0 for _ in pairs(SIM.ws) do ws = ws + 1 end
            return { (E.total.move or 0) + (E.n.move or 0), n, (E.total.create or 0) + (E.n.create or 0), ws } end
        local c0 = calls()
        for _, st in L.people() do st.like = { relax = 50, work = 0, look = 1, chat = 1, idle = 0.01, wander = 1 } end
        local sat, busy = nil, 0
        for i = 1, 300 do
            if i % 2 == 0 then L.tick(1) else for _ = 1, 60 do L.step(1 / 60) end end   -- (the sim's turns and the game's)
            for _ = 1, 4 do L.frame(0.25) end
            SIM.step()
            for h, st in L.people() do
                busy = busy + 1
                if st.mode == "use" and st.seat and st.seat.piece == chair.piece then sat = h end
            end
        end
        for _, st in L.people() do st.like = nil end
        local moved = 0
        for i, p in ipairs(people) do local e = SIM.ents[p.id.hash] if math.abs(e.pos.x - at[i][1]) + math.abs(e.pos.y - at[i][2]) > 0.01 then moved = moved + 1 end end
        local who = tostring(people[1].id.hash)
        local ok = L.moveTo(who, { x = chair.x + 5, y = chair.y, z = chair.z })
        local job = L.jobOf(who)
        for i = 1, 30 do L.tick(1) SIM.step() end
        local e = SIM.ents[people[1].id.hash]
        local stayed = math.abs(e.pos.x - at[1][1]) + math.abs(e.pos.y - at[1][2]) < 0.01
        S.cmd = { t = 0, who = { h = who, name = "X", p = people[1] }, point = { x = chair.x + 5, y = chair.y, z = chair.z } }
        S.target = nil
        SIM.key("IK_E"); SIM.release("IK_E")
        local toast = S.toast
        S.cmd = nil
        L.unjob(who)
        local c1, d = calls(), {}                                -- (the orders too: refused without asking anything)
        for i = 1, #c0 do d[i] = c1[i] - c0[i] end
        return string.format("%s|%d|%s|%s|%s|%s|%s|%d", tostring(sat == who), moved, table.concat(d, ","), tostring(ok and job ~= nil), tostring(stayed), tostring(toast), tostring(L.jobOf(who)), busy) end''')
    SIM.press('Navigation')(False); SIM.tick(2)
    still = lua('function() return SIM.mod.life.backend() == SIM.mod.life.backends.livenav end')()
    SIM.session(); SIM.tick(70)
    nl_off = null_day().split('|')
    SIM.press('Navigation')(True); SIM.liveNav(False); SIM.session(); SIM.tick(70)
    nl_none = null_day().split('|')
    for what, nlp in (('navigation off (from the next load)', nl_off), ('LiveNav not installed (navigation on)', nl_none)):
        check(still and len(nlp) == 8 and nlp[0] == 'false' and nlp[1] == '0' and nlp[2] == '0,0,0,0' and nlp[3] == 'false' and nlp[4] == 'true'
              and 'Navigation off' in nlp[5] and nlp[6] == 'nil' and nlp[7] == '0',
              '%s: people are props - no move command, LiveNav call, device or workspot (%s), nobody walks (%s moved), the chair at hand not sat on (%s), nobody in a day (%s); a spot order refused - no job, nobody goes (%s, %s), Command mode says so (%s)' % ((what,) + tuple(nlp[2:3] + nlp[1:2] + nlp[0:1] + nlp[7:8] + nlp[3:6])))
    SIM.liveNav(True); SIM.session(); SIM.tick(70)
    back = lua('''function() local L = SIM.mod.life
        if L.backend() ~= L.backends.livenav then return "not livenav" end
        local n0 = SIM.walks or 0
        for _, st in L.people() do st.like = { relax = 0, work = 0, look = 0, chat = 0, idle = 0.01, wander = 50 } end
        for i = 1, 60 do L.tick(1) SIM.step() end
        for _, st in L.people() do st.like = nil end
        return (SIM.walks or 0) - n0 end''')()
    off = lua('function() return SIM.offNav or 0 end')()
    check(isinstance(back, (int, float)) and back > 0 and off == 0, 'navigation on again with LiveNav there (the next load): people walk again (%s moves), every walk on the navmesh (%d off it)' % (back, off))
    # reachability (LiveNav.Probe): E on the top of a platform with no way up (a foundation reached only by a ladder:
    # an island, LiveNav makes no ladder links) says "No way up there", no job, no move; E on the ground beside it: the
    # job, and they walk there as before
    isl = lua('''function()
        local L, S = SIM.mod.life, SIM.mod.state
        local p
        for _, q in ipairs(S.pieces) do if q.it.npc then p = q break end end
        if not p then return "nobody" end
        local h, e = tostring(p.id.hash), SIM.ents[p.id.hash]
        L.unjob(h)
        local x, y, z = e.pos.x + 6, e.pos.y, Homestead.TerrainBelow(Vector4.new(e.pos.x + 6, e.pos.y, e.pos.z + 1, 1)).z
        LiveNav.AddBoxes("sim:island", { 0, 0, 1.25, 1, 1, 1.25, 0, 0, 0, 1 }, { pos = Vector4.new(x, y, z, 1), q = { i = 0, j = 0, k = 0, r = 1 } }, true)
        local function send(pt)
            S.cmd, S.target = { t = 0, who = { h = h, name = "X", p = p } , point = pt }, nil
            local n0 = LN.probes or 0
            SIM.key("IK_E"); SIM.release("IK_E")
            local toast, job = S.toast, L.jobOf(h)
            S.cmd = nil
            for _, st in L.people() do if st.h == h then st.t = 0 end end
            for i = 1, 10 do L.tick(1) SIM.step() end
            local there = (e.pos.x - pt.x) ^ 2 + (e.pos.y - pt.y) ^ 2 < 0.36 and math.abs(e.pos.z - pt.z) < 0.6
            return string.format("%s;%s;%s;%d", tostring(toast), tostring(job), tostring(there), (LN.probes or 0) - n0)
        end
        local up = send({ x = x, y = y, z = z + 2.5 })
        local down = send({ x = x - 2.5, y = y, z = z })
        L.unjob(h)
        LiveNav.RemoveObject("sim:island")
        return up .. "|" .. down end''')()
    iu, idn = (isl.split('|') + ['', ''])[:2]
    iu, idn = iu.split(';'), idn.split(';')
    check(len(iu) == 4 and len(idn) == 4 and 'No way up there' in iu[0] and iu[1] == 'nil' and iu[2] == 'false' and iu[3] != '0'
          and 'will wait there' in idn[0] and idn[1].count(',') == 2 and idn[2] == 'true',
          'LiveNav.Probe: commanded onto a platform with no way up (an island) - "No way up there", no job, not sent (%s); onto the ground beside it - the job, and they walk there (%s)' % (iu, idn))
    # Command mode up onto a platform by its steps (user, 2026-10-03: "on the ground ... I cant command them to go up
    # onto ... a platform connected by steps ... the spawned npc simply wont move"): aimed at through Cmd.tick, the top
    # of a piece nobody can be given (a platform, a tread) is somewhere to stand - the order logged and toasted, the job
    # set, the probe climbs the steps, they end on the top. Every refusal (the sky, nobody selected) a "command:" line
    # and a toast. (A walk-flagged piece given a 1 m platform and three 0.25 m steps, toward -X.)
    _PK = 'fo4_dlc05scaffstairhalfb'
    _plat = [[0, 0, 0.5, 1, 1, 0.5]] + [[-1.25 - 0.5 * (3 - k), 0, 0.125 * k, 0.25, 1, 0.125 * k] for k in (1, 2, 3)]
    lua('''function(k, bs) local it = SIM.it(k)
        it.saved = { boxes = it.boxes, cboxes = it.cboxes, walk = it.walk, min = it.min, max = it.max, size = it.size, cx = it.cx, cy = it.cy, navfile = it.navfile }
        local b = {} for i = 1, #bs do b[i] = bs[i] end
        it.boxes, it.cboxes, it.walk, it.navfile, it.groups, it.solid, it.bb = b, nil, true, nil, nil, nil, nil
        it.min, it.max, it.size, it.cx, it.cy = { -2.5, -1, 0 }, { 1, 1, 1 }, { 3.5, 2, 1 }, -0.75, 0 end''')(_PK, lua('function(...) local t = {...} for i, v in ipairs(t) do t[i] = { v[1], v[2], v[3], v[4], v[5], v[6] } end return t end')(*[lua('function(...) return {...} end')(*b) for b in _plat]))
    _who = lua('''function() local S = SIM.mod.state
        for _, q in ipairs(S.pieces) do if q.it.npc then local e = SIM.ents[q.id.hash]
            e.pos.x, e.pos.y = 4956.8, 1573.98               -- (a clear spot, whatever their day took them to before)
            return q, e.pos.x, e.pos.y end end end''')()
    _px, _py = _who[1] + 5, _who[2]
    put(_PK, _px, _py, Z); refresh(); SIM.tick(30)
    def order(aim, who=True):                                    # V looks at aim (from 6 m back, 3 m aside), E: toast,
        stand(_px - 6, _py - 3); look_at(*aim)                   # job, log lines, then 10 s of their day: where they are
        return lua('''function(p, who) local L, S, C = SIM.mod.life, SIM.mod.state, SIM.mod.C
            local h, e = tostring(p.id.hash), SIM.ents[p.id.hash]
            L.unjob(h)
            if not who then e.pos.x = e.pos.x - 20; L.sync(); C.Grid.build(S.pieces) end   -- (out of the view: E on them would select them)
            S.cmd, S.target = { t = 0, who = who and { h = h, name = "X", p = p } or nil }, nil
            SIM.tick(2)                                          -- (Cmd.tick: the crosshair's piece and spot)
            local said, log = {}, C.log
            C.log = function(s) said[#said + 1] = s end
            SIM.key("IK_E"); SIM.release("IK_E")
            C.log = log
            local toast, job, tgt = S.toast, L.jobOf(h), S.target and S.target.key
            S.cmd, S.target = nil, nil
            for _, st in L.people() do if st.h == h then st.t = 0 end end
            for i = 1, 10 do L.tick(1) SIM.step() end
            return string.format("%s;%s;%s;%s;%.2f;%.2f;%.2f", tostring(toast), tostring(job), table.concat(said, "/"), tostring(tgt), e.pos.x, e.pos.y, e.pos.z) end''')(_who[0], who).split(';')
    _up = order((_px + 0.3, _py, Z + 1.0))
    _tread = order((_px - 1.75, _py, Z + 0.5))
    _sky = order((_px, _py + 40, Z + 30))
    _none = order((_px + 0.3, _py, Z + 1.0), False)
    lua('function() for _, st in SIM.mod.life.people() do SIM.mod.life.unjob(st.h) end end')()
    _pp = [p for p in pieces(_PK)]
    if _pp: lua('function(p) local S = SIM.mod.state S.level, S.hold, S.target = 0, nil, p end')(_pp[0]); lua('function() SIM.mod.build() end')(); SIM.tick(1); lua('function(p) local S = SIM.mod.state S.level, S.hold, S.target = 0, nil, p end')(_pp[0]); SIM.key('IK_R'); SIM.release('IK_R'); SIM.tick(30); lua('function() SIM.mod.exit() end')(); SIM.tick(2)
    lua('''function(k) local it, s = SIM.it(k), SIM.it(k).saved
        it.boxes, it.cboxes, it.walk, it.min, it.max, it.size, it.cx, it.cy, it.navfile = s.boxes, s.cboxes, s.walk, s.min, s.max, s.size, s.cx, s.cy, s.navfile
        it.groups, it.solid, it.bb, it.saved = nil, nil, nil, nil end''')(_PK)
    def on(r, x, y, z): return len(r) == 7 and abs(float(r[4]) - x) < 0.6 and abs(float(r[5]) - y) < 0.6 and abs(float(r[6]) - z) < 0.1
    check(len(_up) == 7 and _up[3] == _PK and 'will wait there' in _up[0] and _up[1].count(',') == 2 and 'command: X to' in _up[2] and ' ok probe ' in _up[2]
          and float(_up[2].rsplit(' ', 1)[1]) > 0 and on(_up, _px + 0.3, _py, Z + 1.0),
          'Command mode: E aimed at a platform reached by steps (the piece under the crosshair, nothing to assign) - "will wait there", the job, logged with the probe up the steps, and they stand on its top (%s)' % _up)
    check(on(_tread, _px - 1.75, _py, Z + 0.5) and 'will wait there' in _tread[0], 'Command mode: E aimed at a tread - they stand on it (%s)' % _tread)
    check(len(_sky) == 7 and 'somewhere to stand' in _sky[0] and _sky[1] == 'nil' and 'command: X to nothing nowhere to stand there' in _sky[2]
          and len(_none) == 7 and 'Look at someone' in _none[0] and 'command: nobody selected' in _none[2],
          'Command mode: every refusal toasted and logged - the sky (%s), nobody selected (%s)' % (_sky[:3], _none[:3]))
    # Command mode's spot is the navmesh where the crosshair hits (user, 2026-10-03: "the topmost mesh relative to where
    # we are pointing would get priority and be a valid spot"): any surface hit, the navmesh point there from 1 m under it
    # to 0.5 m over it (Life.moveTo) - never the ground or a floor under or beside it. A deck 2.4 m up over walkable
    # ground, by 0.4 m steps: its top; the ground beside it: the ground; a crate's top (1.2 m, no navmesh on it) and a
    # wall's face (2 m up): "no walkable spot there", logged, no job (the faces-up rule sent them to the crate's foot).
    # Points set as the crosshair's (Cmd.tick takes any hit now: the platform and tread checks above go through it)
    _lv = lua('''function()
        local L, S, C = SIM.mod.life, SIM.mod.state, SIM.mod.C
        local p
        for _, q in ipairs(S.pieces) do if q.it.npc then p = q break end end
        local h, e = tostring(p.id.hash), SIM.ents[p.id.hash]
        e.pos.x, e.pos.y = 4950, 1578.9                      -- (a clear spot, whatever their day took them to before)
        local x, y = e.pos.x + 4, e.pos.y + 6
        local z = Homestead.TerrainBelow(Vector4.new(x, y, e.pos.z + 1, 1)).z
        local I = { pos = Vector4.new(x, y, z, 1), q = { i = 0, j = 0, k = 0, r = 1 } }
        local deck = { 0, 0, 2.35, 1, 1, 0.05, 0, 0, 0, 1 }
        for k = 1, 5 do for _, v in ipairs({ -1.25 - 0.5 * (5 - k), 0, 0.2 * k, 0.25, 1, 0.2 * k, 0, 0, 0, 1 }) do deck[#deck + 1] = v end end
        LiveNav.AddBoxes("sim:deck", deck, I, true)
        LiveNav.AddBoxes("sim:crate", { 0, 4, 0.6, 0.5, 0.5, 0.6, 0, 0, 0, 1 }, I, false)
        LiveNav.AddBoxes("sim:wall", { 4, 0, 1.5, 0.05, 2, 1.5, 0, 0, 0, 1 }, I, false)
        local function send(dx, dy, dz)
            L.unjob(h)
            S.cmd, S.target = { t = 0, who = { h = h, name = "X", p = p }, point = { x = x + dx, y = y + dy, z = z + dz } }, nil
            local said, log = {}, C.log
            C.log = function(s) said[#said + 1] = s end
            SIM.key("IK_E"); SIM.release("IK_E")
            C.log = log
            local toast, job, at = S.toast, L.jobOf(h), (table.concat(said, "/"):match("to [-%d.]+, [-%d.]+, ([-%d.]+)"))
            S.cmd = nil
            for _, st in L.people() do if st.h == h then st.t = 0 end end
            for i = 1, 10 do L.tick(1) SIM.step() end
            return string.format("%s;%s;%s;%.2f;%.2f", tostring(toast), tostring(job), table.concat(said, "/"), (tonumber(at) or -99) - z, e.pos.z - z)
        end
        local r = { send(0.2, 0.3, 2.4), send(-0.5, -2.5, 0), send(0, 4, 1.2), send(3.95, 0.5, 2) }
        L.unjob(h)
        for _, id in ipairs({ "sim:deck", "sim:crate", "sim:wall" }) do LiveNav.RemoveObject(id) end
        return table.concat(r, "|") end''')().split('|')
    _lv = [r.split(';') for r in _lv] if len(_lv) == 4 else [[]] * 4
    _dk, _gd, _cr, _wl = _lv
    check(len(_dk) == 5 and 'will wait there' in _dk[0] and _dk[1].count(',') == 2 and ' ok probe ' in _dk[2] and abs(float(_dk[3]) - 2.4) < 0.05 and abs(float(_dk[4]) - 2.4) < 0.1
          and len(_gd) == 5 and 'will wait there' in _gd[0] and abs(float(_gd[3])) < 0.05 and abs(float(_gd[4])) < 0.1,
          "Command mode: aimed at a deck's top over walkable ground - the spot on the deck (logged at +%s m), they climb its steps and stand on it (+%s m); at the ground beside it - the ground (%s, +%s m)" % tuple(_dk[3:5] + _gd[3:5]) if len(_dk) == 5 and len(_gd) == 5 else 'Command mode: deck / ground (%s, %s)' % (_dk, _gd))
    check(all(len(r) == 5 and 'No walkable spot there' in r[0] and r[1] == 'nil' and 'no walkable spot there' in r[2] and 'command: X to' in r[2] for r in (_cr, _wl)),
          'Command mode: aimed at a crate top (no navmesh on it, the ground 1.2 m under) and at a wall face - "No walkable spot there", logged, no job (%s; %s)' % (_cr[:3], _wl[:3]))
    # Command mode's spot from LiveNav.Nearest (591731a: the poly its Probe starts and ends on; half extents 1 m) - a low
    # deck's top aimed at; an older LiveNav without it: the game's query (Homestead.NavPoint), logged once a session -
    # the same spot (ok, spot height, Nearest asked, NavPoint asked, logged in the session)
    spot_src = lua('''function()
        local L, S = SIM.mod.life, SIM.mod.state
        local p
        for _, q in ipairs(S.pieces) do if q.it.npc then p = q break end end
        local h, e = tostring(p.id.hash), SIM.ents[p.id.hash]
        local x, y = e.pos.x + 5, e.pos.y - 5
        local z = Homestead.TerrainBelow(Vector4.new(x, y, e.pos.z, 1)).z
        LiveNav.AddBoxes("sim:deck", { 0, 0, 0.2, 1.5, 1.5, 0.2, 0, 0, 0, 1 }, { pos = Vector4.new(x, y, z, 1), q = { i = 0, j = 0, k = 0, r = 1 } }, true)
        local np, n = Homestead.NavPoint, 0
        Homestead.NavPoint = function(...) n = n + 1 return np(...) end
        local n0 = LN.nearest or 0
        local ok, why, d, f = L.moveTo(h, { x = x + 0.3, y = y, z = z + 0.4 })
        Homestead.NavPoint = np
        L.unjob(h)
        LiveNav.RemoveObject("sim:deck")
        local logs = 0 for _, s in ipairs(SIM.said or {}) do if s:find("no Nearest", 1, true) then logs = logs + 1 end end
        return string.format("%s %.2f %s %s %d", tostring(ok), f and f.z - z or -9, tostring((LN.nearest or 0) > n0), tostring(n > 0), logs) end''')
    sp_new = spot_src()
    lua('''function() SIM.nearest, LiveNav.Nearest, SIM.said, SIM.print = LiveNav.Nearest, nil, {}, print
        print = function(s) SIM.said[#SIM.said + 1] = tostring(s) SIM.print(s) end end''')(); SIM.session(); SIM.tick(70)
    sp_old = spot_src()
    lua('function() LiveNav.Nearest, print, SIM.said = SIM.nearest, SIM.print, nil end')(); SIM.session(); SIM.tick(70)
    check(sp_new == 'true 0.40 true false 0' and sp_old == 'true 0.40 false true 1',
          "Command mode: the spot from LiveNav.Nearest, the game's query not asked (%s); an older LiveNav without Nearest - the game's query, logged once, the same spot (%s)" % (sp_new, sp_old))
    # after a walk (user, 2026-10-03: "my npc sort of tposes after finishing the move"): from the order on, every turn
    # they are under a move command or in a workspot - never neither (a command that ended by itself left them so till the
    # spot's device came) -, one command at a time, and the walk let go before the workspot plays (it would override it)
    _tp = lua('''function() local L, S = SIM.mod.life, SIM.mod.state
        local p
        for _, q in ipairs(S.pieces) do if q.it.npc then p = q break end end
        local h, e, k = tostring(p.id.hash), SIM.ents[p.id.hash], p.id.hash
        L.unjob(h)
        for i = 1, 5 do L.tick(1) SIM.step() end                -- (up from whatever they did)
        local s0, w0, bare, seen, out = SIM.stacked, SIM.walks or 0, {}, false, ""
        L.moveTo(h, { x = e.pos.x + 3, y = e.pos.y, z = e.pos.z })
        for i = 1, 12 do
            L.tick(1) SIM.step()
            local st = L.state()[h]
            seen = seen or (SIM.walks or 0) > w0
            if seen and not SIM.cmds[k] and not SIM.ws[k] then bare[#bare + 1] = i .. ":" .. st.mode end
            out = st.mode
        end
        local r = string.format("%s|%s|%d|%s", out, table.concat(bare, " "), SIM.stacked - s0, tostring(SIM.ws[k] ~= nil and SIM.cmds[k] == nil))
        L.unjob(h)
        return r end''')().split('|')
    check(len(_tp) == 4 and _tp[0] == 'use' and _tp[1] == '' and _tp[2] == '0' and _tp[3] == 'true',
          'after a walk: never without a move command or a workspot (bare at turns: %r), one command at a time (%s over another), the walk let go once the workspot plays (%s; ends %s)' % tuple(_tp[1:4] + _tp[0:1]) if len(_tp) == 4 else 'after a walk: %s' % _tp)
    # LiveNav's removal hand-off (the mock's: a deck taken from under them cancels their move and drops them to the
    # ground): their move is sent again once LiveNav.Probe(at, at) says they're on the navmesh (asked only for them, a
    # turn at a time; LN.down: still falling) - held: the hold again; walking: the walk on to its goal; one command at a time
    _ho = lua('''function() local L, S = SIM.mod.life, SIM.mod.state
        local p
        for _, q in ipairs(S.pieces) do if q.it.npc then p = q break end end
        local h, e, k = tostring(p.id.hash), SIM.ents[p.id.hash], p.id.hash
        L.unjob(h)
        for i = 1, 5 do L.tick(1) SIM.step() end                -- (up from whatever they did)
        for _, o in L.people() do o.t = 1e9 end                 -- (everyone stays at what they do)
        local st, B, npc = L.state()[h], L.backend(), e
        st.mode = "idle"
        local x, y = e.pos.x + 8, e.pos.y
        local z = Homestead.TerrainBelow(Vector4.new(x, y, e.pos.z + 5, 1)).z
        local T, DECK = { pos = Vector4.new(x, y, z, 1), q = { i = 0, j = 0, k = 0, r = 1 } }, { 0, 0, 0.25, 2, 2, 0.25, 0, 0, 0, 1 }
        local function self() return LN.selfProbes or 0 end
        LiveNav.AddBoxes("sim:deck", DECK, T, true)             -- held on a low deck's top
        local sent = B.moveTo(npc, st, { x = x, y = y, z = z + 0.5 })
        B.update(npc, st, 1)
        local held = sent and SIM.cmds[k] ~= nil and st.goal == nil and math.abs(e.pos.z - (z + 0.5)) < 0.05
        local s0, p0, c0 = SIM.stacked, self(), SIM.cmds[k]
        L.tick(1)
        local quiet = self() - p0
        LN.down = 2
        LiveNav.RemoveObject("sim:deck")
        local fell, back = SIM.cmds[k] == nil and math.abs(e.pos.z - z) < 0.05, nil
        for i = 1, 5 do L.tick(1) if not back and SIM.cmds[k] then back = i end end
        local r1 = string.format("%s %s %s %d %s %d %d", tostring(held), tostring(fell), tostring(back), quiet, tostring(SIM.cmds[k] ~= c0), SIM.stacked - s0, self() - p0)
        LiveNav.AddBoxes("sim:deck", DECK, T, true)             -- walking across the deck to the ground past it
        local gz = Homestead.TerrainBelow(Vector4.new(x + 5, y, z + 5, 1)).z
        sent = B.moveTo(npc, st, { x = x + 5, y = y, z = gz })
        st.mode, e.pos = "stroll", Vector4.new(x, y, z + 0.5, 1)  -- (on their way: on the deck)
        s0, p0 = SIM.stacked, self()
        LN.down = 1
        LiveNav.RemoveObject("sim:deck")
        fell, back = SIM.cmds[k] == nil and math.abs(e.pos.z - z) < 0.05, nil
        for i = 1, 4 do L.tick(1) if not back and SIM.cmds[k] then back = i end end
        local there = math.abs(e.pos.x - (x + 5)) < 0.05 and math.abs(e.pos.z - gz) < 0.05
        local r2 = string.format("%s %s %s %s %s %d %d", tostring(sent), tostring(fell), tostring(back), tostring(there), st.mode, SIM.stacked - s0, self() - p0)
        B.stop(npc, st)
        for _, o in L.people() do o.t = 5 end
        return r1 .. "|" .. r2 end''')().split('|')
    check(_ho == ['true true 3 0 true 0 3', 'true true 2 true idle 0 2'],
          'LiveNav hand-off: held on a deck taken away - dropped, no command; sent again on the 3rd turn, once Probe(at, at) >= 0 (asked only once lost: %s) - %s; walking across it - the walk on to its goal on the 2nd turn, arrived - %s (held, fell, back at turn, asks before, new command, stacked, asks)' % (_ho[0].split()[3] if _ho[0].count(' ') == 6 else '?', _ho[0], _ho[1] if len(_ho) > 1 else ''))
    # LiveNav's world edits (modules/livenav.lua): every piece one object, "hs:<entity hash>" (people never; walkable
    # tops for a piece marked walk, else Structures / Structure / Roads / Buildings only); a floor placed: AddBoxes, one Rebuild once edits have
    # settled; scrapped: Release (whoever stands on it handed off), RemoveObject, one Rebuild
    def ln(): return dict(lua('function() local t = {} for k, v in pairs(LN.n) do t[k] = v end return t end')().items())
    def ln_since(a): b = ln(); return {k: b[k] - a.get(k, 0) for k in sorted(b) if b[k] != a.get(k, 0)}
    SIM.tick(400)                                                # (the load's batch: once streamed in, 5 s at most)
    reg = lua('''function() local n, bad, WALK = 0, {}, { Structures = true, Structure = true, Roads = true, Buildings = true }
        for _, p in ipairs(SIM.mod.state.pieces) do
            local o = LN.objs["hs:" .. tostring(p.id.hash)]
            if p.it.npc then if o then bad[#bad + 1] = "person " .. p.key end
            elseif #(p.it.cboxes or p.it.boxes) > 0 then
                if o and o.walk == (p.it.walk or WALK[p.it.cat] or false) then n = n + 1 else bad[#bad + 1] = p.key end
            end
        end
        return n, table.concat(bad, " ") end''')()
    lua('function() SIM.mod.build() end')(); SIM.tick(1)
    ids0 = {p.id.hash for p in pieces()}
    a = ln(); stand(ZX - 14, ZY + 22); fo4_hold('fo4_workshop_shackmidfloor01'); look_at(ZX - 14, ZY + 26, Z); SIM.tick(3); SIM.key('IK_E'); SIM.release('IK_E'); SIM.tick(30)
    placed = ln_since(a)
    nf = [p for p in pieces('fo4_workshop_shackmidfloor01') if p.id.hash not in ids0]
    a = ln()
    if nf: lua('function(p) local S = SIM.mod.state S.level, S.hold, S.target = 0, nil, p end')(nf[0]); SIM.key('IK_R'); SIM.release('IK_R'); SIM.tick(30)
    scrapped = ln_since(a)
    gone = bool(nf) and lua('function(h) return LN.objs["hs:" .. tostring(h)] == nil end')(nf[0].id.hash)
    check(reg[0] > 5 and reg[1] == '' and placed == {'add': 1, 'rebuild': 1} and scrapped == {'release': 1, 'remove': 1, 'rebuild': 1} and gone,
          "LiveNav: after the load every piece in it as hs:<hash>, walkable tops by category, no person (%d; wrong: '%s'); a floor placed %s, scrapped %s" % (reg[0], reg[1], placed, scrapped))
    # LiveNav traffic boxes for doors (modules/livenav.lua "doors"): a shut door's leaves (catalog pcol, as at rest) go as
    # "hs:door:<entity hash>" in the door's own frame - traffic only (the mock keeps them out of its navmesh), no Rebuild;
    # removed as it opens, sent again once it has shut; a pick-up removes them, the put-back's entity sends its own; a
    # scrap removes them; the frame's static object never changes with the door; navigation off: no call at all
    door_traffic = lua('''function() local S, M, n, ok, bad = SIM.mod.state, SIM.mod, 0, 0, {}
        for _, p in ipairs(S.pieces) do
            if M.anim.shut(p) then
                local t, i, good = LN.traffic["hs:door:" .. tostring(p.id.hash)], 0, true
                for _, pb in ipairs(p.it.pcol or {}) do for _, b in ipairs(pb) do
                    for k = 1, 6 do good = good and t ~= nil and t.f[i + k] == b[k] end
                    good = good and t ~= nil and t.f[i + 10] == (b[10] or 1); i = i + 10 end end
                if i > 0 then
                    n = n + 1
                    if good and i == #t.f and t.pos.x == p.o.x and t.pos.y == p.o.y and t.pos.z == p.o.z then ok = ok + 1 else bad[#bad + 1] = p.key end
                elseif t then bad[#bad + 1] = p.key .. " (no leaves)" end
            end
        end
        local all = 0 for _ in pairs(LN.traffic) do all = all + 1 end
        return n, ok, all, table.concat(bad, " ") end''')
    def traffic_of(p): return lua('function(h) return LN.traffic["hs:door:" .. tostring(h)] ~= nil end')(p.id.hash)
    dt0 = door_traffic()
    check(dt0[0] > 0 and dt0[0] == dt0[1] == dt0[2] and dt0[3] == '',
          'door traffic: after the load every shut door\'s leaves are traffic boxes hs:door:<hash>, its catalog pcol boxes in its own frame, nothing else (%d doors, %d right, %d sent; wrong: \'%s\')' % tuple(dt0))
    dcy = lua('''function() local S, M = SIM.mod.state, SIM.mod
        local D
        for _, p in ipairs(S.pieces) do local h = tostring(p.id.hash)
            if M.anim.shut(p) and LN.objs["hs:" .. h] and LN.traffic["hs:door:" .. h] then D = p break end end
        if not D then return "no shut door with a frame" end
        local id, frame = "hs:door:" .. tostring(D.id.hash), LN.objs["hs:" .. tostring(D.id.hash)]
        local function counts() local t = {} for k, v in pairs(LN.n) do t[k] = v end return t end
        local function since(a) local o = {} for k, v in pairs(LN.n) do if v ~= (a[k] or 0) then o[#o + 1] = k .. "=" .. (v - (a[k] or 0)) end end
            table.sort(o) return table.concat(o, ",") end
        local function run() for _ = 1, 60 do M.anim.tick(1 / 15) end end
        local a = counts(); M.anim.use(D); local at = LN.traffic[id] == nil; run()
        local opened = since(a) .. " " .. tostring(at and LN.traffic[id] == nil and M.anim.label(D) == "Close")
        a = counts(); M.anim.use(D); at = LN.traffic[id] == nil; run()
        local shut = since(a) .. " " .. tostring(at and LN.traffic[id] ~= nil and M.anim.label(D) == "Open")
        return opened .. "|" .. shut .. "|" .. tostring(LN.objs["hs:" .. tostring(D.id.hash)] == frame), D end''')()
    dcs = dcy[0].split('|') if isinstance(dcy, tuple) else [str(dcy)]
    check(dcs == ['remove=1 true', 'traffic=1 true', 'true'],
          'door traffic: opened - its traffic boxes removed as it starts to move (%s); shut again - sent once it is at rest, not while it swings (%s); the frame\'s static object untouched, no AddBoxes or Rebuild (%s)' % tuple((dcs + ['', '', ''])[:3]))
    if isinstance(dcy, tuple):
        D = dcy[1]
        a = ln(); lua('function(p) SIM.mod.state.target = p; SIM.mod.startMove(p) end')(D); SIM.tick(2)
        lifted_t, carried = ln_since(a), not traffic_of(D)
        a = ln(); lua('function() SIM.mod.restore() end')(); SIM.tick(30)
        back_t = ln_since(a)
        D2 = [p for p in pieces(D.key) if p.id.hash != D.id.hash and abs(p.o.x - D.o.x) < 1e-6 and abs(p.o.y - D.o.y) < 1e-6]
        check(lifted_t == {'release': 1, 'remove': 1} and carried and back_t == {'traffic': 1} and len(D2) == 1 and traffic_of(D2[0]),
              'door traffic: picked up - removed at once, none while carried (%s); put back (Tab, the same pose: its frame not re-sent) - its new entity\'s leaves sent, shut (%s)' % (lifted_t, back_t))
        if D2:
            a = ln(); lua('function(p) local S = SIM.mod.state S.level, S.hold, S.target = 0, nil, p end')(D2[0]); SIM.key('IK_R'); SIM.release('IK_R'); SIM.tick(30)
            scr_t = ln_since(a)
            check(scr_t == {'release': 1, 'remove': 2, 'rebuild': 1} and not traffic_of(D2[0]),
                  'door traffic: scrapped - its traffic boxes removed with its frame (%s)' % scr_t)
    SIM.press('Navigation')(False); SIM.tick(2)
    off_t = lua('''function() local S, M = SIM.mod.state, SIM.mod
        local n0, D = 0, nil
        for _, v in pairs(LN.n) do n0 = n0 + v end
        for _, p in ipairs(S.pieces) do if M.anim.shut(p) and #(p.it.pcol or {}) > 0 then D = p break end end
        if not D then return "no door" end
        for _, name in ipairs({ "Open", "Close" }) do M.anim.use(D) for _ = 1, 60 do M.anim.tick(1 / 15) end end
        local n1, left = 0, 0
        for _, v in pairs(LN.n) do n1 = n1 + v end
        for _ in pairs(LN.traffic) do left = left + 1 end
        return string.format("%d calls, %d left, %s", n1 - n0, left, tostring(M.anim.shut(D))) end''')()
    SIM.press('Navigation')(True); SIM.tick(2)
    dt1 = door_traffic()
    check(off_t == '0 calls, 0 left, true' and dt1[0] > 0 and dt1[0] == dt1[1] == dt1[2],
          'door traffic: navigation off - a door opened and shut makes no LiveNav call, none left from before (%s); on again - every shut door sent (%d of %d)' % (off_t, dt1[1], dt1[0]))
    lua('function() SIM.mod.exit() end')(); SIM.tick(2)
    lua('function() if SIM.mod.state.build then SIM.mod.exit() end for _, st in SIM.mod.life.people() do st.like = { relax = 20, work = 5, look = 10, chat = 10, idle = 1, wander = 30 } end end')()
    stand(ZX, ZY - 10); perf('to people frames'); SIM.tick(600); perf('people, 10 s of frames')   # (people taking turns)
    lua('function() for _, st in SIM.mod.life.people() do st.like = nil end end')()
    lua('function() for _, st in SIM.mod.life.people() do if st.mode ~= "use" then st.goal, st.mode, st.t = nil, "idle", 30 end end end')()
    lua('function() SIM.mod.build() end')(); SIM.tick(1)
    scenario(110)
    lua('function() SIM.defer = 2 end')()
    # the free-placement gizmo: Ctrl locks the piece and gives a cursor; arrows move it, rings turn it (and tilt it)
    GP = 'fo4_radiofreedomreceiveroff'
    stand(ZX + 5, ZY + 18); fo4_hold(GP); SIM.key('IK_Q'); SIM.tick(1); look_at(ZX + 5, ZY + 24, Z + 1); SIM.tick(3)
    SIM.key('IK_LControl'); SIM.tick(2)
    o0 = dict(x=st.gz.o.x, y=st.gz.o.y, z=st.gz.o.z) if st.gz else None
    check(st.gz is not None and SIM.gizmoOn and SIM.gz and SIM.gz.n > 100 and 'Gizmo off' in hints(),
          'gizmo: Ctrl in free placement locks the piece, holds the camera and draws the handles (%s segments)' % (SIM.gz and SIM.gz.n))
    u0 = ecalls('ui', 'total') + ecalls('ui', 'n'); SIM.tick(60); u1 = ecalls('ui', 'total') + ecalls('ui', 'n')   # (perf: held still)
    PERF.append(('gizmo on, still, 60 frames', 'ui pushes %d' % (u1 - u0)))
    cx0 = st.gz.cx
    SIM.hold('IK_RightMouse'); SIM.tick(1); SIM.mouse(300, 0); SIM.tick(1)
    lk = (SIM.gizmoOn, st.gz.cx == cx0, 'Look around' in hints())
    SIM.release('IK_RightMouse'); SIM.tick(1); SIM.mouse(300, 0); SIM.tick(1)
    check(lk[0] is False and lk[1] and lk[2] and SIM.gizmoOn and st.gz.cx > cx0,
          'gizmo: the right mouse held looks round (camera free, the cursor waits), let go the cursor moves again (%s)' % (lk,))
    SIM.mouse(-300, 0); SIM.tick(1)
    def cursor_to(u, v):                                    # the mouse, in pixels, onto a screen point (whatever its speed)
        for _ in range(6):
            dx, dy = (u - st.gz.cx) * 1920, (v - st.gz.cy) * 1080        # (the game's mouse Y: + down)
            if abs(dx) < 0.05 and abs(dy) < 0.05: break
            k = 1.0 if _ == 0 else k
            before = st.gz.cx
            SIM.mouse(dx * k, dy * k)
            moved = st.gz.cx - before
            k = k * (u - before) / moved if abs(moved) > 1e-9 else k
        SIM.tick(1)
    def handle(kind, axis):
        hs = lua('function() local hs = SIM.mod.gizmoView() local out = {} for _, h in ipairs(hs) do out[#out + 1] = h end return out end')()
        return next(hs[i] for i in hs if hs[i].kind == kind and hs[i].axis == axis)
    hx = handle('move', 1); a, b = hx.pts[1], hx.pts[2]
    cursor_to((a[1] + b[1]) / 2, (a[2] + b[2]) / 2)
    check(st.gz.hover and st.gz.hover.kind == 'move' and st.gz.hover.axis == 1, 'gizmo: the cursor over the X arrow picks it (%s)' % (st.gz.hover and st.gz.hover.kind))
    SIM.hold('IK_LeftMouse'); SIM.tick(1)
    cursor_to((a[1] + b[1]) / 2 + (b[1] - a[1]) * 0.5, (a[2] + b[2]) / 2 + (b[2] - a[2]) * 0.5); SIM.tick(1)
    SIM.release('IK_LeftMouse'); SIM.tick(1)
    L = hx.L
    h2 = handle('move', 1); a2, b2 = h2.pts[1], h2.pts[2]                  # the moved arrow still runs under the cursor
    ax_, ay_2, bx_, by_ = a2[1] * 16 / 9, a2[2], b2[1] * 16 / 9, b2[2]
    off = abs((bx_ - ax_) * (st.gz.cy - ay_2) - (by_ - ay_2) * (st.gz.cx * 16 / 9 - ax_)) / math.hypot(bx_ - ax_, by_ - ay_2)
    check(0.2 * L < st.gz.o.x - o0['x'] < 0.7 * L and abs(st.gz.o.y - o0['y']) < 1e-6 and abs(st.gz.o.z - o0['z']) < 1e-6 and off < 0.004,
          'gizmo: dragging the X arrow moves the piece along X only, the grabbed point staying under the cursor (%.3f m, %.4f off)' % (st.gz.o.x - o0['x'], off))
    zp = SIM.player.z                                        # the rings from above, at a slant (as a player grabs them)
    SIM.player.x, SIM.player.y, SIM.player.z = st.gz.o.x - 1.2, st.gz.o.y - 1.2, zp + 0.8
    look_at(st.gz.o.x, st.gz.o.y, st.gz.o.z + 0.1); SIM.tick(1)
    y0 = st.hold.yaw
    rz = handle('turn', 3); p0 = rz.pts[26]; p1 = rz.pts[32]           # (the far side: clear of the Z arrow)
    cursor_to(p0[1], p0[2]); SIM.hold('IK_LeftMouse'); SIM.tick(1); cursor_to(p1[1], p1[2]); SIM.release('IK_LeftMouse'); SIM.tick(1)
    turned = (st.hold.yaw - y0 + 180) % 360 - 180
    tilt = lua('function() local q = SIM.mod.state.hold.q local x = 2 * (q.i * q.k + q.r * q.j) local y = 2 * (q.j * q.k - q.r * q.i) return math.sqrt(x * x + y * y) end')()
    check(abs(abs(turned) - 45) < 2 and tilt < 1e-6, 'gizmo: dragging an eighth round the Z ring turns it 45 degrees about Z, no tilt (%.1f)' % turned)
    rx = handle('turn', 1); p0 = rx.pts[4]; p1 = rx.pts[10]
    cursor_to(p0[1], p0[2]); SIM.hold('IK_LeftMouse'); SIM.tick(1); cursor_to(p1[1], p1[2]); SIM.release('IK_LeftMouse'); SIM.tick(1)
    tilt = lua('function() local q = SIM.mod.state.hold.q local x = 2 * (q.i * q.k + q.r * q.j) local y = 2 * (q.j * q.k - q.r * q.i) return math.sqrt(x * x + y * y) end')()
    check(tilt > 0.5, 'gizmo: the X ring tilts it (its up axis leans %.2f)' % tilt)
    SIM.player.z = zp; SIM.tick(90)                         # (back down: landed before the fall check below)
    n0 = len(pieces(GP))
    SIM.key('IK_E'); SIM.tick(3)
    placed = [p for p in pieces(GP) if p.q]
    check(len(pieces(GP)) == n0 + 1 and placed and st.gz is None and not SIM.gizmoOn,
          'gizmo: E places it where the gizmo left it, tilt and all, and lets go of the camera (%d tilted placed)' % len(placed))
    SIM.key('IK_LControl'); SIM.tick(1); SIM.key('IK_LControl'); SIM.tick(1)
    check(st.gz is None and not SIM.gizmoOn, 'gizmo: Ctrl turns it on and off again')
    # the lifetime guard under fire (deferred: an entity attaches two frames after it is made): Ctrl edit with the wheel
    # turned every frame, turned again the moment the piece is set down, a handle clicked on and off a frame at a time,
    # Ctrl off - nothing deleted or moved before it settled, nothing left over
    lua('function() SIM.mod.state.hold = nil end')(); SIM.tick(2)
    R = [p for p in pieces(GP) if p.q][-1]
    lua('function(p) SIM.mod.state.target = p end')(R); SIM.key('IK_LControl'); SIM.release('IK_LControl'); SIM.tick(1)
    n0 = len(pieces(GP))
    for _ in range(20): SIM.key('IK_MouseWheelUp'); SIM.tick(1)
    held_ = st.hold is not None and len(pieces(GP)) == n0
    SIM.tick(30)
    set_ = st.hold is None and st.gz is not None and st.gz.piece is not None and len(pieces(GP)) == n0 + 1
    o1 = (st.gz.piece.o.x, st.gz.piece.o.y, st.gz.piece.o.z) if set_ else (0, 0, 0)
    for _ in range(3): SIM.key('IK_MouseWheelDown'); SIM.tick(1)    # (set down a frame ago: not yet takeable)
    SIM.tick(30)
    o2 = (st.gz.piece.o.x, st.gz.piece.o.y, st.gz.piece.o.z) if st.gz and st.gz.piece else o1
    again = math.dist(o1, o2) > 0.05 and st.gz.notches is None
    hx = handle('move', 1); a, b = hx.pts[1], hx.pts[2]
    cursor_to((a[1] + b[1]) / 2, (a[2] + b[2]) / 2)
    for _ in range(5): SIM.hold('IK_LeftMouse'); SIM.tick(1); SIM.release('IK_LeftMouse'); SIM.tick(1)
    SIM.tick(30)
    SIM.key('IK_LControl'); SIM.release('IK_LControl'); SIM.tick(10)
    vio = lua('function() return table.concat(SIM.violations, "; ") end')()
    check(held_ and set_ and again and not vio and st.gz is None and count('Homestead.ghost') == 0 and len(pieces(GP)) == n0 + 1,
          'Ctrl edit hammered (the wheel every frame, again as it is set down, clicks a frame apart): held while it turns, set down once it rests, the late notches kept, nothing touched before it settled, no preview left (%s %s %s; %s)' % (held_, set_, again, vio or 'no violations'))
    SIM.key('IK_Q'); SIM.tick(1)
    lua('function() SIM.mod.state.hold = nil end')(); SIM.tick(1)

scenario(111)
# workshop mode: a fall doesn't hurt - V is made unhurt while dropping, and back to normal a second after landing
lua('function() SIM.unhurt = {} Homestead.Unhurt = function(on) table.insert(SIM.unhurt, on) end local S = SIM.mod.state if not S.build then SIM.mod.build() end end')()
z0 = SIM.player.z
for k in range(10): SIM.player.z = z0 + 5 - k * 0.5; SIM.tick(1)
SIM.player.z = z0; SIM.tick(120)
calls = lua('function() local s = {} for _, v in ipairs(SIM.unhurt) do s[#s + 1] = tostring(v) end return table.concat(s, ",") end')()
check(calls == 'true,false', 'workshop mode: falling makes V unhurt, landing ends it (%s)' % calls)

# as shipped (2026-09-30): Cyberpunk's own pieces are stashed; the menu holds only what the zone needs (and Fallout 4's)
# frame cost (Lua only, like CET's LuaJIT; the game's own calls are stubs here): workshop mode holding a Fallout floor
# in snap mode among the pieces built above, a walk-in shack among them - reported, and a ceiling as a check
for _i, (_dx, _dy) in enumerate([(-6, -2), (0, -2), (6, -2), (-6, 5), (6, 5), (0, 11)]):   # walk-in shacks (600+ boxes each) round the aim
    stand(ZX + 20 + _dx, ZY - 12 + _dy); fo4_hold('fo4_workshop_shackmetalprefabcompletelg01'); SIM.key('IK_Q'); SIM.tick(1)
    look_at(ZX + 20 + _dx, ZY - 6 + _dy, Z); SIM.tick(3); SIM.key('IK_E'); SIM.tick(2); SIM.key('IK_Q'); SIM.tick(1)
stand(ZX + 18, ZY - 14); fo4_hold('fo4_workshop_shackmidfloor01'); look_at(ZX + 20, ZY - 8, Z); SIM.tick(5)
import time as _t
lua('function() for _ = 1, 7 do SIM.mod.life.tick(1, true) end end')()   # (devices people let go: deleted before, not counted here)
SIM.tick(1)
scenario(120)
_n = 0; _t0 = _t.perf_counter()
for _k in range(120):                                       # the camera turning, as when looking round
    look_at(ZX + 20 + 6 * math.sin(_k / 12), ZY - 8 + 6 * math.cos(_k / 12), Z); SIM.tick(1); _n += 1 if st.place and st.place.o else 0
_ms = (_t.perf_counter() - _t0) * 1000 / 120
_shacks = len(pieces('fo4_workshop_shackmetalprefabcompletelg01'))
check(_n == 120 and _shacks >= 3 and _ms < 4.0, 'frame cost: %.2f ms a frame in workshop mode, turning while holding a floor in snap mode by %d walk-in shacks, %d pieces (Lua)' % (_ms, _shacks, len(st.pieces)))
_pk = {k: ecalls(k, 'peak') for k in ('ray', 'terrain', 'ui', 'create', 'delete', 'teleport')}
check(_pk['create'] == 0 and _pk['delete'] == 0 and _pk['ray'] <= 40 and _pk['ui'] <= 16,
      'game calls a frame, turning with the floor held: no spawn or delete, rays and overlay pushes within budget (most in a frame: %s)' % _pk)
# garbage (the collector's pauses are the jank): placement with the floor held by the shacks, counted with the
# collector stopped. It was 60 KB a placement (a closure and tables for every held point, candidate and box tried)
_gb = lua('''function(look) local C, S = SIM.mod.C, SIM.mod.state
    collectgarbage('collect') collectgarbage('stop')
    local kb = 0
    for k = 0, 59 do look(k) S.cam = nil local c0 = collectgarbage('count') C.placement() kb = kb + collectgarbage('count') - c0 end
    collectgarbage('restart') return kb / 60 end''')(lambda k: look_at(ZX + 20 + 6 * math.sin(k / 12), ZY - 8 + 6 * math.cos(k / 12), Z))
check(_gb < 30, 'garbage: %.1f KB a frame placing the floor held by the shacks (snap mode)' % _gb)
lua('function() SIM.mod.state.hold = nil end')(); SIM.tick(1)

scenario(112)
# the in-game scene replayed (tools/fixtures/scene_night.txt: every piece of a real zone as the game had it, the Large
# Shack's 5,353 boxes among them - it made placement cost 16-80 ms a frame in game): the same held floor, the camera
# turning where V stood - a check that big pieces stay cheap
_scene = os.path.join(ROOT, 'tools', 'fixtures', 'scene_night.txt')
if os.path.exists(_scene):
    lua("""function() local S = SIM.mod.state local d = Game.GetDynamicEntitySystem()
        for _, p in ipairs(S.pieces) do if not p.bench then d:DeleteEntity(p.id) end end SIM.mod.refresh() end""")()
    # (big pieces go to LiveNav from the box file the import wrote - build_catalog.py navfiles, here for the Large
    # Shack into the sim's own folder - and a piece whose file can't be read as floats through CET)
    import sys as _sys; _sys.path.insert(0, os.path.join(ROOT, 'tools')); os.environ['HOMESTEAD_WORK'] = SETDIR
    import build_catalog
    _big, _odd = 'fo4_workshop_shackprefabcompletelg01', 'fo4_workbenchcookingfireworkshop'
    _row = {'key': _big, 'cboxes': [[b[k] for k in range(1, len(b) + 1)] for b in (SIM.it(_big).cboxes or SIM.it(_big).boxes).values()]}
    build_catalog.navfiles([_row])
    lua('function(a, f, b, g) SIM.it(a).navfile, SIM.it(b).navfile = f, g end')(_big, _row.get('navfile'), _odd, os.path.join(SETDIR, 'nav', 'none.f32'))
    _ln0 = dict(lua('function() local t = {} for k, v in pairs(LN.n) do t[k] = v end return t end')().items())
    for _l in open(_scene, encoding='utf-8'):
        _k, _a, _x, _y, _z, _yaw = _l.rstrip('\n').split('\t')
        if _k == 'workbench': continue
        lua("""function(k, a, x, y, z, yaw) local spec = { position = Vector4.new(x, y, z, 1), orientation = EulerAngles.new(0, 0, yaw):ToQuat(),
            alwaysSpawned = true, tags = { CName.new("Homestead"), CName.new("hs:" .. k), CName.new("hsapp:" .. a), CName.new("hsas") } } Game.GetDynamicEntitySystem():CreateEntity(spec) end""")(_k, _a, float(_x), float(_y), float(_z), float(_yaw))
    lua('function() SIM.mod.refresh() end')()
    SIM.player.x, SIM.player.y = 4943.5, 1583.5
    fo4_hold('fo4_workshop_shackmidfloor01'); look_at(4943.5 - 3.4, 1583.5 + 9.4, 181.9); SIM.tick(5)
    _t0 = _t.perf_counter()
    for _k in range(120):
        _a = -0.35 + 0.7 * math.sin(_k / 15)
        look_at(4943.5 + 10 * math.sin(_a), 1583.5 + 10 * math.cos(_a), 181.2); SIM.tick(1)
    _ms = (_t.perf_counter() - _t0) * 1000 / 120
    check(_ms < 4.0 and len(st.pieces) >= 54, 'the in-game scene replayed (%d pieces, a 5,353-box shack): %.2f ms a frame holding a floor, turning (Lua)' % (len(st.pieces), _ms))
    bf = lua('''function(a, b) local S, ff, big, odd, most = SIM.mod.state, nil, nil, nil, 0
        local flat = {}                                        -- (what AddBoxes would send: livenav.lua's 10 floats a box)
        for _, x in ipairs(SIM.it(a).cboxes or SIM.it(a).boxes) do for k = 1, 10 do flat[#flat + 1] = x[k] or (k == 10 and 1 or 0) end end
        for _, p in ipairs(S.pieces) do
            local id = "hs:" .. tostring(p.id.hash)
            if p.key == a then big, ff = LN.objs[id], LN.files[id] end
            if p.key == b then odd = LN.objs[id] end
            if LN.objs[id] and not LN.files[id] then most = math.max(most, LN.objs[id].floats) end
        end
        local worst = (ff and #ff == #flat) and 0 or 1
        for i = 1, #flat do worst = math.max(worst, math.abs((ff and ff[i] or 0) - flat[i])) end
        return big ~= nil and ff ~= nil, odd ~= nil and odd.floats > 0, worst, most, ff and #ff or 0 end''')(_big, _odd)
    _ln1 = lua('function() local t = {} for k, v in pairs(LN.n) do t[k] = v end return t end')()
    _d = {k: _ln1[k] - _ln0.get(k, 0) for k in ('file', 'nofile')}
    check(bf[0] and bf[1] and bf[2] < 1e-4 and _d == {'file': 1, 'nofile': 1},
          'LiveNav: the Large Shack from its box file (AddBoxesFile: %d floats, as AddBoxes would send them to %.0e), a piece whose file is missing as floats (%s); most floats through CET %d' % (bf[4], bf[2], _d, bf[3]))
    lua('function() SIM.mod.state.hold = nil end')(); SIM.tick(1)

# turned boxes (Fallout's own collision fitted, tools/colliders.py box_of: braces, sloped roofs, stair ramps as
# oriented boxes, {cx, cy, cz, hx, hy, hz, qi, qj, qk, qr}): a ramp piece (Scaffolding Ramp B given one 45 degree ramp
# box) - a ray down lands on its slope, span (support) reads the slope's height, overlap sees the slope and not the
# box round it, LiveNav gets its turn in the 10 floats; the
# Watchtower's and a Wide Hall's Havok boxes (tools/fixtures/havok_*.json; the Watchtower's 3 ramps last) grouped by
# their bounds; and the frame cost holding each by its twin: the catalog's voxel boxes, then Fallout's
import json
_RK, _WK = 'fo4_dlc05scafframpb', 'fo4_dlc05scaffwatchtowera'
if lua('function(a, b, c) return SIM.it(a) ~= nil and SIM.it(b) ~= nil and SIM.it(c) ~= nil end')(_RK, _WK, 'fo4_vltworkshopwidehall01'):
    _ramp = [0, 0, 0.8, 1.2, 0.8, 0.11, 0, -math.sin(math.radians(22.5)), 0, math.cos(math.radians(22.5))]   # (45 deg: up toward +X)
    lua('''function(k, b) local it = SIM.it(k) it.saved = { boxes = it.boxes }
        it.boxes, it.groups, it.solid = { b }, nil, nil end''')(_RK, lua('function(...) return {...} end')(*_ramp))
    _RX, _RY = ZX - 3, ZY + 20
    clear(_RX, _RY, 4)
    put(_RK, _RX, _RY, Z); refresh(); SIM.tick(30)
    _r = lua('''function(k, x, y, z) local C, S = SIM.mod.C, SIM.mod.state
        local p for _, q in ipairs(S.pieces) do if q.key == k then p = q end end
        local b = p.it.boxes[1]
        local t0, n0 = C.rayBox(p, b, { x = x, y = y, z = z + 5 }, { x = 0, y = 0, z = -1 })
        local t1 = C.rayBox(p, b, { x = x + 0.5, y = y, z = z + 5 }, { x = 0, y = 0, z = -1 })
        local lo, hi = C.span(b, 0.5, 0, 0)
        local cube = { key = "simcube", boxes = { { 0, 0, 0, 0.1, 0.1, 0.1 } }, size = { 0.2, 0.2, 0.2 }, cx = 0, cy = 0, min = { -0.1, -0.1, -0.1 }, max = { 0.1, 0.1, 0.1 } }
        local inside = C.blockedBy(cube, { x = x + 0.5, y = y, z = z + 1.3 }, 0) == p
        local over = C.blockedBy(cube, { x = x - 0.5, y = y, z = z + 1.5 }, 0) == nil
        local o = LN.objs["hs:" .. tostring(p.id.hash)]
        return z + 5 - t0, n0[3], z + 5 - t1, z + hi, z + lo, inside, over, o and o.boxes[1].inv.j or 99, p end''')(_RK, _RX, _RY, Z)
    _top = 0.8 + 0.11 / math.cos(math.radians(45))
    check(abs(_r[0] - (Z + _top)) < 0.005 and abs(_r[1] - math.cos(math.radians(45))) < 0.01 and abs(_r[2] - (Z + _top + 0.5)) < 0.005,
          'a turned box (a 45 degree ramp): a ray down lands on its slope, %.3f and %.3f m up at x 0 and 0.5 (want %.3f, %.3f), the face tilted (normal z %.3f)' % (_r[0] - Z, _r[2] - Z, _top, _top + 0.5, _r[1]))
    check(abs(_r[3] - (Z + _top + 0.5)) < 0.005 and abs(_r[4] - (Z + 1.3 - 0.11 / math.cos(math.radians(45)))) < 0.005,
          'support reads a turned box by the slope: at x 0.5 it spans %.3f..%.3f m' % (_r[4] - Z, _r[3] - Z))
    check(_r[5] and _r[6], 'overlap (snap mode) sees the slope, not the box round it: a cube in the ramp is blocked (%s), one in the air over its low end is not (%s)' % (_r[5], _r[6]))
    check(abs(_r[7] + _ramp[7]) < 1e-3, 'LiveNav: the turn goes in its 10 floats (inverse j %.4f)' % _r[7])
    lua('function(p) local S = SIM.mod.state S.level, S.hold, S.target = 0, nil, p end')(_r[8]); lua('function() SIM.mod.build() end')(); SIM.tick(1)
    lua('function(p) local S = SIM.mod.state S.level, S.hold, S.target = 0, nil, p end')(_r[8]); SIM.key('IK_R'); SIM.release('IK_R'); SIM.tick(30)
    _gone = lua('function(h) return LN.objs["hs:" .. tostring(h)] == nil end')(_r[8].id.hash)
    check(_gone, 'LiveNav: the ramp scrapped, its object goes')
    lua('function() SIM.mod.exit() end')(); SIM.tick(2)
    lua('function(k) local it = SIM.it(k) it.boxes, it.groups, it.solid, it.saved = it.saved.boxes, nil, nil, nil end')(_RK)
    # the Watchtower and a vault Wide Hall each held by its twin, in snap mode: each frame's cost, the catalog's voxel
    # boxes and then Fallout's (tools/fixtures/havok_*.json)
    def _bench(key, label):
        clear(ZX - 14, ZY + 13, 11); put(key, ZX - 14, ZY + 13, Z); refresh()
        stand(ZX - 14, ZY + 3); fo4_hold(key); look_at(ZX - 14, ZY + 9, Z); SIM.tick(3)
        lua('function() SIM.mod.prof(true) end')()
        _f = []
        for _k in range(240):
            look_at(ZX - 14 + 5 * math.sin(_k / 10), ZY + 10 + 3 * math.cos(_k / 13), Z)
            _t0 = _t.perf_counter(); SIM.tick(1); _f.append((_t.perf_counter() - _t0) * 1000)
        _f.sort()
        _p = dict((s.split(' avg ')[0], s.split(' avg ')[1]) for s in lua('function() return SIM.mod.prof() end')().split(' | ') if ' avg ' in s)
        lua('function() SIM.mod.state.hold = nil end')(); SIM.tick(1)
        return '%s: a frame %.2f ms, p95 %.2f, worst %.2f (Lua, wall); blocked %s' % (label, sum(_f) / len(_f), _f[int(0.95 * len(_f))], _f[-1], _p.get('blocked', '-')), sum(_f) / len(_f), _f[-1]
    for _key, _fix, _name in ((_WK, 'havok_watchtowera.json', 'the Watchtower'), ('fo4_vltworkshopwidehall01', 'havok_widehall01.json', 'a Wide Hall')):
        _hk = json.load(open(os.path.join(ROOT, 'tools', 'fixtures', _fix)))['boxes']
        _before = _bench(_key, 'voxel boxes (%d)' % lua('function(k) return #SIM.it(k).boxes end')(_key))[0]
        _g = lua('''function(k, bs) local it = SIM.it(k) it.saved = it.boxes
            it.boxes, it.groups, it.solid = {}, nil, nil
            for i = 1, #bs do local b = {} for j = 1, #bs[i] do b[j] = bs[i][j] end it.boxes[i] = b end
            local g, n, ok = SIM.mod.C.groupsOf(it), 0, true
            for _, x in ipairs(g or {}) do
                for _, b in ipairs(x.boxes) do
                    n = n + 1
                    local a = b[7] and b.t and b.t.box or b
                    for k = 1, 3 do ok = ok and a[k] - a[k + 3] >= x.box[k] - x.box[k + 3] - 1e-6 and a[k] + a[k + 3] <= x.box[k] + x.box[k + 3] + 1e-6 end
                end
            end
            return g and #g or 0, n, ok end''')(_key, lua('function(...) return {...} end')(*[lua('function(...) return {...} end')(*b) for b in _hk]))
        check(_g[0] > 1 and _g[1] == len(_hk) and _g[2], "%s's Havok boxes (%d, %d turned) in %d groups by their bounds, every box in one, inside its group's bounds" % (_name, len(_hk), sum(len(b) == 10 for b in _hk), _g[0]))
        _after, _avg, _worst = _bench(_key, "Fallout's boxes (%d)" % len(_hk))
        # held deep in its twin it was 8.8-10.7 ms at worst: boxHit made two tables and a closure a box pair (run
        # uncompiled, and the collector's pauses on top) - so the garbage an overlap check makes is checked too, at
        # 25 poses in the twin (a frame's wall time alone swings with when the collector runs)
        # (the worst frame was under 4 ms at square turns; held, it turns with the view now: a skew near miss checks
        # every pair, 6-9 ms)
        if _key == _WK:
            _gc = lua('''function(k) local S, C, it, p, n, hit = SIM.mod.state, SIM.mod.C, SIM.it(k), nil, 0, 0
                for _, q in ipairs(S.pieces) do if q.key == k then p = q end end
                collectgarbage('collect') collectgarbage('stop') local c0 = collectgarbage('count')
                for dx = -3, 3, 1.5 do for dy = -3, 3, 1.5 do
                    n = n + 1 if C.blockedBy(it, { x = p.o.x + dx, y = p.o.y + dy, z = p.o.z }, p.yaw) then hit = hit + 1 end
                end end
                local kb = (collectgarbage('count') - c0) / n collectgarbage('restart') return kb, hit, n end''')(_WK)
            check(_worst < 15.0 and _gc[0] < 4, "the Watchtower held by its twin, Fallout's boxes: worst frame %.2f ms of 240, a frame %.2f ms (Lua, wall); the overlap check %.2f KB of garbage a call (%d poses in its twin, %d blocked)" % (_worst, _avg, _gc[0], _gc[2], _gc[1]))
        print('     perf %s held by its twin, %s; %s' % (_name, _before, _after))
        lua('function(k) local it = SIM.it(k) it.boxes, it.groups, it.solid, it.saved = it.saved, nil, nil, nil end')(_key)
    clear(ZX - 14, ZY + 13, 11)

scenario(113)
# settlements: founded anywhere (a workbench whose tags hold its spot), their pieces kept apart, found again from tags
lua('function() local S = SIM.mod.state if S.build then SIM.mod.exit() end S.hold = nil end')(); SIM.tick(2)
FX, FY = ZX + 1000, ZY
stand(FX, FY); look_at(FX, FY + 20, Z + EYE); SIM.tick(3)
ok = lua('function() return SIM.mod.found() end')(); SIM.tick(3)
zk = lua('function() local z = SIM.mod.zone() return z.key, z.site == true, z.x, z.y end')()
check(ok and zk[1] and abs(zk[2] - FX) < 0.5 and abs(zk[3] - (FY + 12)) < 0.5 and st.bench is not None,
      'found: a settlement where V stands - its plot 12 m ahead, its own workbench (%s)' % zk[0])
check(not lua('function() return SIM.mod.found() end')() and 'Too close' in (st.toast or ''), 'another one within 300 m is refused (%s)' % st.toast)
fo4_hold('fo4_metaltableround01'); look_at(FX + 2, FY + 12, Z); SIM.tick(3); SIM.key('IK_E'); SIM.release('IK_E'); SIM.tick(2)
lua('function() SIM.mod.exit() end')(); SIM.tick(2)
there = [p.key for p in st.pieces.values()]
new_ids = {p.id.hash for p in st.pieces.values()}
stand(ZX, ZY - 10); SIM.tick(70)
home = [p.key for p in st.pieces.values()]
check('fo4_metaltableround01' in there and not new_ids & {p.id.hash for p in st.pieces.values()} and lua('function() return SIM.mod.zone().key end')() == FIRST,
      "back at the first settlement: its pieces, not the new one's (%d there, %d at the first)" % (len(there), len(home)))
lua('function() SIM.mod.state.info = {} SIM.mod.sites.forget() SIM.mod.sites.list = { (SIM.mod.zone()) } end')()   # a fresh load
stand(FX, FY); SIM.tick(200)
again = [p.key for p in st.pieces.values()]
zk2 = lua('function() local z = SIM.mod.zone() return z.key end')()
check(zk2 == zk[0] and 'fo4_metaltableround01' in again and st.bench is not None, 'a fresh load finds the settlement again from its workbench tags, and its pieces (%s)' % zk2)
ok = lua('function() return SIM.mod.abandon() end')(); SIM.tick(3)
left = lua('''function(x, y) local n = 0 for _, e in pairs(SIM.ents) do local q = e.spec.position
    if q and (q.x - x) ^ 2 + (q.y - y) ^ 2 < 200 ^ 2 then n = n + 1 end end return n end''')(FX, FY)
check(ok and lua('function() return SIM.mod.zone().key end')() == FIRST and left == 0, 'abandon: its bench and pieces go (%d left), the first settlement is the one V is in again' % left)
stand(ZX, ZY - 10); SIM.tick(70)

scenario(121)
# settlements in and out of the world by distance (sites.lua): a big one 4 km east - 300 pieces, the night scene's
# kinds over and over, with a shut door, a person with a chair job and one piece saved streamed - driven to and from
# at 40 m/s. Out once V is loadDist + 100 m off its edge, in within loadDist, nearest first, BUDGET components (meshes,
# collider boxes) a frame or one bigger alone; the far one all in the world before V is VIEW m off it; along the edge no flip; jobs kept (the same ids);
# LiveNav: out in one batch + one Rebuild, back in one batch + one Rebuild once V is there, nothing with navigation off;
# workshop mode keeps its settlement in; saved out (a fresh load): back in from its hsin tags
import time as _t
VIEW, SPEED, MORE, BUDGET = 400.0, 40.0, 100.0, 100   # (VIEW: why, NOTES.md Settlements)
LD = lua('function() return SIM.mod.state.loadDist end')()
_set = lua('''function() local o = SIM.opt("Settlement load distance") if not o then return "no row" end
    local a = o.args local was = SIM.mod.state.loadDist a[6](1200) local now = SIM.mod.state.loadDist a[6](was)
    return string.format("%s %d-%d by %d, default %d: %d then %d", o.kind, a[1], a[2], a[3], a[5], now, SIM.mod.state.loadDist) end''')()
check(_set == 'range 200-2000 by 50, default 800: 1200 then 800' and LD == 800 and 'loadDistance=800' in open(os.path.join(SETDIR, 'settings.txt')).read(),
      'Settings > Building > Settlement load distance: %s, kept in settings.txt' % _set)
BX, BY = ZX + 4000, ZY
lua('function() local S = SIM.mod.state if S.build then SIM.mod.exit() end S.hold = nil end')(); SIM.tick(2)
stand(BX, BY - 12); look_at(BX, BY, Z + EYE); SIM.tick(3)
lua('function() SIM.mod.found() end')(); SIM.tick(3)
BK = lua('function() return SIM.mod.zone().key end')()
_rows = [l.rstrip('\n').split('\t') for l in open(os.path.join(ROOT, 'tools', 'fixtures', 'scene_night.txt'), encoding='utf-8')]
_rows = [r for r in _rows if r[0] not in ('boundary', 'workbench')]
_spawn = lua('''function(k, a, x, y, z, yaw) local _, _, p = SIM.mod.C.spawnPiece(k, a, { x = x, y = y, z = z }, yaw, false) return p end''')
_n = 0
for _copy in range(6):                                       # (six copies of the scene 60 m apart: 300 pieces)
    for _r in _rows:
        if _n == 296: break
        _spawn(_r[0], _r[1], BX + (_copy % 3 - 1) * 60 + float(_r[2]) - 4938, BY + 12 + (_copy // 3) * 60 - 30 + float(_r[3]) - 1594, Z + float(_r[4]) - 180.4, float(_r[5]))
        _n += 1
_DOOR = lua('''function() for _, it in ipairs(require("catalog").items) do
    if it.anim and it.cat == "Structures" and not it.stash and it.pcol and #it.pcol > 0 and it.anim.seqs and it.anim.seqs.Open and it.anim.seqs.Close then return it.key end end end''')()
_spawn(_DOOR, 'default', BX + 8, BY + 4, Z, 0)
_chair = _spawn('fo4_npcchairvaultsit03', 'default', BX - 6, BY + 2, Z, 0)
_judy = _spawn('npc_judy', 'default', BX - 4, BY, Z, 0)
lua('function(p, c) SIM.mod.life.job(tostring(p.id.hash), c) end')(_judy, _chair)
_OLD = lua("""function(x, y) return Game.GetDynamicEntitySystem():CreateEntity({ position = Vector4.new(x, y, 180.4, 1),
    orientation = EulerAngles.new(0, 0, 90):ToQuat(), tags = { CName.new("Homestead"), CName.new("hs:floor"), CName.new("hsapp:default") } }).hash end""")(BX + 12, BY - 6)
SIM.mod.C.index(); SIM.tick(600)                             # (everything attached, refresh's looks, LiveNav's batch)
def ln_now(): return dict(lua('function() local t = {} for k, v in pairs(LN.n) do t[k] = v end return t end')().items())
def ln_diff(a, b): return {k: b[k] - a.get(k, 0) for k in sorted(b) if b[k] != a.get(k, 0)}
def site(key):
    return lua('''function(k) local M = SIM.mod for _, s in ipairs(M.sites.list) do if s.key == k then
        local p, off = SIM.player, 0 for _, h in ipairs(s.hs or {}) do if M.state.unloaded[h] then off = off + 1 end end
        return s.loaded, M.sites.edge(s, p), #(s.ids or {}), off, M.sites.loading end end end''')(key)
def job_of(p): return lua('function(p) return SIM.mod.life.jobOf(tostring(p.id.hash)) end')(p)
B0 = site(BK)
_lnB, _trB = lua('''function(k) local n, t = 0, 0 for _, s in ipairs(SIM.mod.sites.list) do if s.key == k then
    for _, h in ipairs(s.hs) do if LN.objs["hs:" .. h] then n = n + 1 end if LN.traffic["hs:door:" .. h] then t = t + 1 end end end end return n, t end''')(BK)
_jobs0 = (job_of(_judy), lua('function(c) return tostring(c.id.hash) end')(_chair))
def drive(x0, x1, y, keys):                                  # V from x0 to x1 at SPEED (a frame a tick): each tick's
    out, n = [], max(1, int(abs(x1 - x0) / (SPEED / 60)))    # time (ms), components dressed, enables, disables, the
                                                             # sites' state, LiveNav's counts, entities dressed
    for i in range(n + 1):
        stand(x0 + (x1 - x0) * i / n, y)
        m0, i0 = SIM.meshes, SIM.inits; t0 = _t.perf_counter(); SIM.tick(1); ms = (_t.perf_counter() - t0) * 1000
        out.append((ms, SIM.meshes - m0, ecalls('enable', 'n'), ecalls('disable', 'n'), [site(k) for k in keys], ln_now(), SIM.inits - i0))
    return out
def first(rec, i, f):                                         # the first tick where f(site i's state) holds, or None
    return next((j for j, r in enumerate(rec) if f(r[4][i])), None)
AX = FIRST
# B -> A: B out past loadDist + 100 m off its edge, once, in one LiveNav batch; A in before V is VIEW m off it
_ln0 = ln_now()
R1 = drive(BX, ZX + 200, BY, [BK, AX])
_bo = first(R1, 0, lambda s: s[0] is False)
_ai = first(R1, 1, lambda s: s[0] is True)
_ad = first(R1[_ai:], 1, lambda s: s[4] is False) if _ai is not None else None
_flips = [sum(1 for j in range(1, len(R1)) if R1[j][4][i][0] != R1[j - 1][4][i][0]) for i in (0, 1)]
_lnOut = ln_diff(R1[_bo - 1][5], R1[_bo][5]) if _bo else {}
check(_bo is not None and LD + MORE <= R1[_bo][4][0][1] <= LD + MORE + 1 and R1[_bo][4][0][3] == R1[_bo][4][0][2] == B0[2]
      and _lnOut == {'remove': _lnB + _trB, 'rebuild': 1} and _trB == 1 and _ai is not None and _ad is not None and R1[_ai + _ad][4][1][1] >= VIEW and _flips == [1, 1],
      'by distance: driving off at 40 m/s, the 300-piece settlement goes at %.1f m off its edge (loadDist %d + %d), all %d entities, LiveNav %s in that frame (%d objects of it, %d door); the far one comes in at %.1f m and is all in the world %.1f m off (>= %d); one flip each (%s)' %
      (R1[_bo][4][0][1] if _bo else -1, LD, MORE, B0[2], _lnOut, _lnB, _trB, R1[_ai][4][1][1] if _ai is not None else -1,
       R1[_ai + _ad][4][1][1] if _ad is not None else -1, VIEW, _flips))
_out = lua('''function(k) local S, n, tagged, kept = SIM.mod.state, 0, 0, 0 for _, s in ipairs(SIM.mod.sites.list) do if s.key == k then
    for i, id in ipairs(s.ids) do if SIM.off[id.hash] then n = n + 1
        local sp = SIM.off[id.hash].spec for _, t in ipairs(sp.tags) do if t.hash == "hsin" .. k then tagged = tagged + 1 end end
        if sp.persistSpawn ~= false then kept = kept + 1 end end end end end
    return n, tagged, kept, #Game.GetDynamicEntitySystem():GetTaggedIDs(CName.new("Homestead")) end''')(BK)
check(_out[0] == B0[2] and _out[1] == B0[2] and _out[2] == B0[2],
      'out of the world, the save untouched: all %d of its entities disabled, not deleted - each still tagged and saved (persistSpawn %d), tagged with its settlement for a load (%d), still listed by tag (%d)' % (_out[0], _out[2], _out[1], _out[3]))
# A -> B: the big one comes in, nearest first, a frame's share at a time: all in the world before V is VIEW m off it
R2 = drive(ZX + 200, BX - 30, BY, [BK, AX])
_bi = first(R2, 0, lambda s: s[0] is True)
_bd = first(R2[_bi:], 0, lambda s: s[4] is False) if _bi is not None else None
_ao = first(R2, 1, lambda s: s[0] is False)
_win = R2[_bi:_bi + (_bd or 0) + 1] if _bi is not None else []
_big = lambda r: r[6] == 1 and r[1] > BUDGET                 # (one entity bigger than the budget, alone: a Large Shack's
_worst = max([r[0] for r in _win if not _big(r)] or [99])    # 5,353 boxes can't be spread - its cost is the same at any load)
_lone = max([r[0] for r in _win if _big(r)] or [0])
_most = max([r[1] for r in _win if r[6] > 1] or [0])        # (the most dressed in a frame of more than one entity)
_alone = sum(1 for r in _win if _big(r))
_flips = [sum(1 for j in range(1, len(R2)) if R2[j][4][i][0] != R2[j - 1][4][i][0]) for i in (0, 1)]
_frames = (_bd or 0)
check(_bi is not None and _bd is not None and LD - 1 <= R2[_bi][4][0][1] < LD and R2[_bi + _bd][4][0][1] >= VIEW and R2[_bi + _bd][4][0][3] == 0
      and _most <= BUDGET + 10 and _worst < 6.0 and _ao is not None and LD + MORE <= R2[_ao][4][1][1] <= LD + MORE + 1 and _flips == [1, 1],
      'by distance: driving up at 40 m/s, the 300-piece settlement comes in at %.1f m off its edge and is all in the world after %d frames (%.2f s at 60 fps, %.0f m of road), %.1f m off (>= %d); at most %d components dressed in a frame (budget %d), worst such frame %.2f ms (Lua, wall; the slow-frame log is at 6 ms); %d bigger entities each alone in a frame (worst %.2f ms); the one left goes at %.1f m; one flip each (%s)' %
      (R2[_bi][4][0][1] if _bi is not None else -1, _frames, _frames / 60, _frames * SPEED / 60, R2[_bi + _bd][4][0][1] if _bd is not None else -1, VIEW,
       _most, BUDGET, _worst, _alone, _lone, R2[_ao][4][1][1] if _ao is not None else -1, _flips))
# in it: LiveNav's batch once all of it is listed (one frame, one Rebuild), its shut door's traffic boxes again, the
# person back on their chair (the job under the same id), the piece saved streamed made again always spawned
stand(BX, BY); SIM.tick(900)
_ln2 = ln_diff(R2[_bi][5], ln_now())                    # (from the frame it turned in: the batch came once V was near)
_door = lua('''function(k) for _, p in ipairs(SIM.mod.state.pieces) do if p.key == k then return LN.traffic["hs:door:" .. tostring(p.id.hash)] ~= nil end end end''')(_DOOR)
_sat = lua('''function(p) for k, st in SIM.mod.life.people() do if k == tostring(p.id.hash) then return st.mode .. " " .. tostring(st.seat and st.seat.piece and st.seat.piece.key) end end end''')(_judy)
_old = lua('''function(h, x, y) local n, t = 0, false for _, p in ipairs(SIM.mod.state.pieces) do
    if p.key == "floor" and math.abs(p.o.x - x) < 0.01 and math.abs(p.o.y - y) < 0.01 then n = n + 1 local e = SIM.ents[p.id.hash]
        for _, x in ipairs(e and e.spec.tags or {}) do t = t or x.hash == "hsas" end end end
    return n, t, SIM.ents[h] == nil and SIM.off[h] == nil end''')(_OLD, BX + 12, BY - 6)
check(_ln2.get('add', 0) + _ln2.get('file', 0) >= _lnB and _ln2.get('rebuild') == 1 and _ln2.get('remove', 0) == 0 and _door and _sat == 'use fo4_npcchairvaultsit03'
      and (job_of(_judy), _jobs0[1]) == _jobs0 and _old[0] == 1 and _old[1] and _old[2],
      'back in it: LiveNav %s (%d objects of it before), one Rebuild; its shut door stops traffic again (%s); the person has their chair job still (the same id) and sits on it (%s); the piece saved streamed made again, always spawned (%s)' % (_ln2, _lnB, _door, _sat, _old))
# along the edge, no flip: out and in only past the band's far side and near side, back and forth across either alone
def hover(e, n=20):                                           # V e m off the settlement's east edge, n frames
    b = site(BK); x1 = lua('function(k) for _, s in ipairs(SIM.mod.sites.list) do if s.key == k then return s.x1 end end end')(BK)
    stand(x1 + e, BY); SIM.tick(n); return site(BK)[0]
_seq = [hover(LD + MORE + 30, 120)]
for _ in range(5): _seq += [hover(LD + 10), hover(LD + MORE + 30)]
_seq += [hover(LD - 10, 240)]
for _ in range(5): _seq += [hover(LD + MORE - 10), hover(LD - 10)]
_x1 = lua('function(k) for _, s in ipairs(SIM.mod.sites.list) do if s.key == k then return s.x1 end end end')(BK)
_bx = lua('function(k) for _, s in ipairs(SIM.mod.sites.list) do if s.key == k then return s.x0, s.y0, s.x1, s.y1 end end end')(BK)
_along, _r = set(), LD + 50                                   # (along its east edge and round the corner, LD + 50 m out:
for _i in range(200):                                         # inside the band all the way)
    _a = _i / 199 * 2.5
    if _a < 1: _p = (_bx[2] + _r, _bx[1] + (_bx[3] - _bx[1]) * _a)
    elif _a < 1.5: _p = (_bx[2] + _r * math.cos((_a - 1) * math.pi), _bx[3] + _r * math.sin((_a - 1) * math.pi))
    else: _p = (_bx[2] - (_bx[2] - _bx[0]) * (_a - 1.5), _bx[3] + _r)
    stand(_p[0], _p[1]); SIM.tick(3); _along.add(site(BK)[0])
check(_seq == [False] * 11 + [True] * 11 and _along == {True},
      'by distance: back and forth across the near side while out and the far side while in - no flip (%s); along the edge and round its corner in the band - none (%s)' % (''.join('1' if x else '0' for x in _seq), _along))
# workshop mode keeps its settlement in whatever the distance; out of it, the rule again
stand(BX, BY); SIM.tick(300)
_gc = lua('''function() local M = SIM.mod                      -- (a look at who belongs where is due once the
    for _ = 1, 150 do M.sites.stream(1 / 60, SIM.player) end   -- pieces have changed: not counted)
    collectgarbage("collect") collectgarbage("stop") local c0 = collectgarbage("count")
    for _ = 1, 110 do M.sites.stream(1 / 60, SIM.player) end
    local kb = (collectgarbage("count") - c0) / 110 collectgarbage("restart") return kb end''')()
check(_gc < 0.1, 'by distance, nothing turning: no garbage a frame (%.4f KB: the JIT compiling this loop)' % _gc)
lua('function() SIM.mod.build() SIM.mod.state.loadDist = -1000 end')(); SIM.tick(30)
_ws = site(BK)
lua('function() SIM.mod.exit() end')(); SIM.tick(30)
_ws2 = site(BK)
lua('function(d) SIM.mod.state.loadDist = d end')(LD); SIM.tick(600)
check(_ws[0] is True and _ws[3] == 0 and _ws2[0] is False and site(BK)[0] is True and site(BK)[3] == 0,
      'workshop mode keeps the settlement it is in, in (asked out: %s, %d out); out of workshop mode it goes (%s), and comes back (%s)' % (_ws[0], _ws[3], _ws2[0], site(BK)[0]))
# navigation off: out and in again without one LiveNav call
SIM.press('Navigation')(False); SIM.tick(60)
_lnA = ln_now()
stand(_x1 + LD + MORE + 30, BY); SIM.tick(200); _no1 = site(BK)[0]
stand(BX, BY); SIM.tick(600); _no2 = site(BK)
_lnB2 = ln_diff(_lnA, ln_now())
SIM.press('Navigation')(True); SIM.tick(600)
check(_no1 is False and _no2[0] is True and _no2[3] == 0 and _lnB2 == {},
      'navigation off: the settlement out and in again (%s, %s) without a LiveNav call (%s)' % (_no1, _no2[0], _lnB2 or 'none'))
# saved out: a fresh load far off finds it disabled (Codeware spawns only what was saved enabled); driving up, it comes
# back from its hsin tags - nothing of it known by place this session
stand(_x1 + LD + MORE + 200, BY); SIM.tick(200)             # (past the band even as far as posts reach: unknown after a load)
SIM.session(); SIM.tick(120)
_sv = site(BK)
R3 = drive(_x1 + LD + MORE + 200, BX, BY, [BK])
_si = first(R3, 0, lambda s: s[0] is True)
_left = lua('function(k) local n = 0 for _, e in pairs(SIM.off) do for _, t in ipairs(e.spec.tags) do if t.hash == "hsin" .. k then n = n + 1 end end end return n end')(BK)
SIM.tick(600)
_b3 = site(BK)
check(_sv[0] is False and _si is not None and _left == 0 and _b3[0] is True and _b3[2] == B0[2] and _b3[3] == 0 and job_of(_judy) == _jobs0[0],
      'saved out: after a fresh load it stays out (%s) and comes in from its tags as V drives up (%.0f m off its edge, as far as posts reach; %d still out), all %d of it back, the job kept (%s)' % (_sv[0], R3[_si][4][0][1] if _si is not None else -1, _left, _b3[2], job_of(_judy) == _jobs0[0]))
_outN = max([j for j in range(len(R1)) if R1[j][3] > 0] or [0]) - (_bo or 0) + 1
print('     perf by distance: the 300-piece settlement in after %d frames (%d components; worst %.2f ms, at most %d components in a frame of several), out over %d frames (worst %.2f ms)' %
      (_frames, sum(r[1] for r in _win), _worst, _most, _outN, max(r[0] for r in R1[(_bo or 0):(_bo or 0) + _outN])))
stand(ZX, ZY - 10); SIM.tick(600)

# reset (CET console): every piece of every settlement, parts, fires and sounds with them
lua('function() SIM.mod.reset() end')(); SIM.tick(240)   # (pieces the sim deleted behind the mod's back: pending three looks)
rs = lua('function() local S, playing = SIM.mod.state, false for _, v in pairs(SIM.mod.state.sfx) do playing = playing or next(v) ~= nil end return next(S.fx) == nil, not playing, next(S.pending) == nil end')()
check(count('Homestead') == 0 and count('Homestead.part') == 0 and all(rs), 'reset: no piece or part left anywhere, no fire or sound kept (%s)' % (rs,))
# the settings: Settings > Mods > Homestead (Native Settings UI) - the importer's news live, Import from the main menu
# only (through the RED4ext plugin), the overwrite switch making it a fresh one (off again after), the People switches
open(os.path.join(SETDIR, 'import_status.txt'), 'w').write(chr(10).join(['state=done', r'fo4=D:\FO4\Data', 'fo4version=1.11.240',
    'drives=C:|300;D:|500', 'finished=2026-10-01 20:00', 'minutes=6.0']) + chr(10))
SIM.importer, SIM.started = r'C:\game\bin\x64\plugins\cyber_engine_tweaks\mods\Homestead\importer\HomesteadImport.exe', None
SIM.tick(140)                                                # (playing, no import running: the status file isn't read)
unread = SIM.opt('Imported 2026-10-01 20:00') is None
SIM.inMenu = True                                            # (the pause menu open: Settings > Mods > Homestead can be looked at)
SIM.tick(140)                                                # (the status file is read every other second when no import runs)
check(unread, 'settings: while V plays (no menu open, no import running) the status file of the importer is not read')
fo4 = SIM.opt('Fallout 4:')
fold = SIM.opt('Import data folder')
names = list(fold.args[1].values()) if fold else []
check(SIM.ns.tab == 'Homestead' and SIM.opt('Imported 2026-10-01 20:00') and fo4 and '1.11.240' in fo4.label
      and names[0].startswith('Default: ...') and names[0].endswith('Homestead' + chr(92) + 'import') and fold.desc.endswith(SIM.importer[:-len('importer' + chr(92) + 'HomesteadImport.exe')] + 'import')
      and len(names) == 2 and names[1].startswith('D:'),
      'settings: Settings > Mods > Homestead shows the last import, Fallout 4 and its version, the default folder (short in the list, in full in its text) and the other drives (%s)' % names)
lua('function() SIM.importRow().args[3]() end')(); SIM.tick(2)
check(SIM.started is None and SIM.opt('Quit to the main menu'), 'settings: in a game, Import says to quit to the main menu first')
SIM.mainMenu = True                                           # (no game loaded: the main menu)
lua('function() SIM.importRow().args[3]() end')(); SIM.tick(2)
check(SIM.started == 0 and SIM.opt('Importing'), 'settings: on the main menu, Import starts the importer (mode %s)' % SIM.started)
SIM.started, SIM.running = None, False                       # (that one done)
SIM.press('Overwrite already imported items')(True); lua('function() SIM.importRow().args[3]() end')()
check(SIM.started == 1 and SIM.opt('Overwrite already imported items').value is False, 'settings: the overwrite switch makes it a fresh import (mode %s), and is off again after' % SIM.started)
open(os.path.join(SETDIR, 'import_status.txt'), 'w').write(chr(10).join(['state=running', "step=Fallout 4's textures", 'pct=46', 'eta=420']) + chr(10))
SIM.running = True
SIM.tick(140)
check(SIM.opt("Importing: Fallout 4's textures  -  46%  -  about 7 min left") is not None and SIM.importRow().args[1] == 'Cancel',
      "settings: while it imports, the status line says what it's on, how far, and about how long is left (no refresh needed), its button Cancel")
lua('function() SIM.importRow().args[3]() end')(); SIM.tick(2)
check(SIM.stopped and SIM.opt('Cancelled') is not None and SIM.importRow().args[1] == 'Import' and 'state=cancelled' in open(os.path.join(SETDIR, 'import_status.txt')).read(),
      'settings: Cancel stops the importer (and what it started); it says so, and the button is Import again')
open(os.path.join(SETDIR, 'import_status.txt'), 'w').write(chr(10).join(['state=running', "step=Fallout 4's models", 'pct=20']) + chr(10))
SIM.running = False
SIM.tick(140)
check(SIM.opt('Stopped before it finished') is not None, "settings: an importer gone without a word (killed, the PC off) isn't shown importing forever")
SIM.importer = ''
lua('function() SIM.importRow().args[3]() end')(); SIM.tick(2)
check(SIM.opt("The importer isn't installed") is not None, 'settings: no importer installed - they say so')
SIM.mainMenu, SIM.inMenu = False, False
SIM.press('People walk around')(False)
walk = lua('function() return SIM.mod.life.allow.walk end')()
check(walk is False and 'peopleWalk=0' in open(os.path.join(SETDIR, 'settings.txt')).read(), 'settings: People walk around off - placed people stay put, and it is kept (settings.txt)')
SIM.press('People walk around')(True)
# without navigation people are props: their three rows are not shown (LiveNav missing: no People rows at all; the
# switch off: the switch alone), and what was set stays in settings.txt
def _rows(livenav, nav):
    return lua('''function(ln, nav) local M = SIM.mod
        M.settings.set("peopleNav", nav and "1" or "0"); M.settings.set("peopleTalk", "0")
        SIM.liveNav(ln); M.life.navClear(true); SIM.ns.opts = {}; M.settings.init()   -- (LiveNav asked again, as at a load)
        local r = {}
        for _, o in ipairs(SIM.ns.opts) do if o.path == "/homestead/people" then r[#r + 1] = o.label end end
        return table.concat(r, "|") .. ";" .. tostring(M.settings.get("peopleTalk")) .. ";" .. tostring(SIM.opt("Command mode") ~= nil) end''')(livenav, nav)
_r = (_rows(False, True), _rows(True, False), _rows(True, True))
lua('function() SIM.mod.settings.set("peopleTalk", "1") SIM.ns.opts = {} SIM.mod.settings.init() end')()
check(_r == (';0;false', 'Navigation;0;false', 'People walk around|People use furniture|People talk to each other|Navigation;0;true'),
      'settings: LiveNav missing - no People rows; navigation off - its switch alone; on - all four (and the Command key row); a hidden one keeps its value (%s)' % (_r,))
import re as _re
tabs = lua('''function() HS_NATIVE = nil local m = dofile(MOD_DIR .. "/init.lua") local _, t = m.zone() local c, bad = {}, 0
    local byKey = {} for _, it in ipairs(require("catalog").items) do byKey[it.key] = it end
    local function walk(n) for _, k in ipairs(n.kids or {}) do if k.key then local it = byKey[k.key]
        if it.stashed or not (it.fo4 or it.npc or it.cat == "Night City") then bad = bad + 1 end else walk(k) end end end
    for k, n in pairs(t) do c[#c + 1] = k walk(n) end table.sort(c) HS_NATIVE = "only" return table.concat(c, ","), bad end''')()
check(tabs[1] == 0 and 'Night City' in tabs[0] and 'Zone' not in tabs[0] and 'People' in tabs[0] and not _re.search(r'(Structure|Buildings|Roads)', tabs[0]),
      "this release: Fallout 4's pieces, Cyberpunk's props, weapons and nature in Night City, people - no Zone tab, no buildings, kits or roads (tabs %s)" % tabs[0])
import re as _re
_src = '\n'.join(open(f, encoding='utf-8').read() for f in [os.path.join(MOD, 'init.lua')] + glob.glob(os.path.join(MOD, 'modules', '*.lua')))   # (and its modules)
check(not _re.search(r'\b_G\b', _src.replace('CET sandboxes _G away', '')), 'init.lua uses no _G (CET sandboxes it away: the mod would fail to load)')
check(not _re.search(r'\bpackage\.', _src), "init.lua uses no package table (CET's sandbox has none: the catalog's data would never load)")
gw = lua('function() return table.concat(SIM.globalWrites, " ") end')()
check(gw == '', 'the mod writes no globals (%s)' % (gw or 'none'))
# a player's first start: no import yet, so no catalog - the mod still loads (its settings work), and workshop mode
# says to import first (a fresh copy of the mod, the catalog made unloadable for it)
first = lua('''function()
    local saved, pre = package.loaded["catalog"], package.preload["catalog"]
    package.loaded["catalog"], package.preload["catalog"] = nil, function() error("no catalog.lua") end
    local ok, m = pcall(dofile, MOD_DIR .. "/init.lua")
    package.loaded["catalog"], package.preload["catalog"] = saved, pre
    if not ok then return "load failed: " .. tostring(m) end
    m.build()
    return tostring(m.state.build) .. " " .. tostring(m.state.toast) end''')()
check(first.startswith('false') and 'import' in first, "a first start without an import: the mod loads, workshop mode won't open (%s)" % first)
first2 = lua('''function()                                   -- (as CET does it: a missing file's require gives nil, no error)
    local saved, pre = package.loaded["catalog"], package.preload["catalog"]
    package.loaded["catalog"], package.preload["catalog"] = nil, function() return nil end
    local ok, m = pcall(dofile, MOD_DIR .. "/init.lua")
    package.loaded["catalog"], package.preload["catalog"] = saved, pre
    if not ok then return "load failed: " .. tostring(m) end
    m.build()
    return tostring(m.state.build) .. " " .. tostring(m.state.toast) end''')()
check(first2.startswith('false') and 'import' in first2, "a first start, CET's way (require gives nil): the mod still loads (%s)" % first2)
tot = lua('function() local t = {} for k, v in pairs(SIM.mod.calls.total) do t[#t + 1] = k .. " " .. v end table.sort(t) return table.concat(t, ", ") end')()
vio = lua('function() return #SIM.violations, table.concat(SIM.violations, "; ") end')()
check(vio[0] == 0, 'the whole run: no entity deleted or moved by the mod before it had settled (%s)' % (vio[1][:300] or 'none'))
perf('to the end')
for _n, _p in PERF: print('     perf %-28s %s' % (_n, _p))
print('     perf steps (avg / worst ms, Lua): ' + SIM.mod.prof())
print('     done, %d entities created in total; game calls in all: %s' % (SIM.created, tot))
