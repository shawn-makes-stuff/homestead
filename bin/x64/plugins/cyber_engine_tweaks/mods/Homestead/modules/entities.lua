-- Entities: our pieces as the game's dynamic entities. What a piece is rides on its tags (tagInfo, tagsFor: CET
-- reads tags back as bare hashes); spawn makes one (persisted with the save unless it's a preview), del is the one
-- way out (its fire, sounds and records go with it). onEntity dresses an entity as it initialises - meshes,
-- colliders, lights, a stash device's own branch - and afterAttach finishes what needs it standing in the world.
-- refresh reads the zone's pieces (S.pieces: id, key, o, yaw, it, parts) from the tagged entities.
return function(C)
    local S, catalog, byKey, des, hashOf, Eng, try = C.S, C.catalog, C.byKey, C.des, C.hashOf, C.Eng, C.try
    local log, say, v4 = C.log, C.say, C.v4
    local CHUNK, OUTLINE, Q, Grid, Anim, Life = C.CHUNK, C.OUTLINE, C.Q, C.Grid, C.Anim, C.Life
    local local2world, anchorOf, slotsOf, levelKey, RADIUS = C.local2world, C.anchorOf, C.slotsOf, C.levelKey, C.RADIUS

    local TEMPLATE = "homestead\\empty.ent"
    local TEMPLATE_LIT = "homestead\\empty_lit.ent"
    -- Every entity of ours is alwaysSpawned: otherwise Codeware hands it to the game's population system, which despawns pieces V
    -- isn't looking at and respawns them in sight (pop-in). The tag marks an entity made so; one without it (saved before) is made again in place, once (remake).
    local ALWAYS = "hsas"

    -- CET hands tags back as bare hashes (no text), so a piece's tags are matched against the names they can be. With
    -- thousands of items that can't be a walk through the catalog: a piece also carries its key's 12-bit hash as one tag
    -- per set bit ("hsb0".."hsb11") plus "hsv2", so 13 checks find the few keys it can be. Pieces from before (no "hsv2")
    -- were all kit items and are matched against those. Cached: an entity's tags never change (a move respawns it).
    local BITS = 12
    local function keyHash(key)
        local h = 0
        for i = 1, #key do h = (h * 31 + key:byte(i)) % 4096 end
        return h
    end
    local byHash, legacy = {}, {}
    for _, it in ipairs(catalog.items) do
        local h = keyHash(it.key)
        byHash[h] = byHash[h] or {}
        table.insert(byHash[h], it)
        if not it.key:find("^h_") then table.insert(legacy, it) end
    end
    local function tagInfo(id)
        local hid = hashOf(id)
        if S.info[hid] ~= nil then return S.info[hid] or nil end
        local function has(name) return des():IsTagged(id, name) end
        local cands = legacy
        if has("hsv2") then
            local h = 0
            for b = 0, BITS - 1 do if has("hsb" .. b) then h = h + 2 ^ b end end
            cands = byHash[h] or {}
        end
        local info = false
        for _, it in ipairs(cands) do
            if has("hs:" .. it.key) then
                info = { key = it.key, app = it.apps[1], ghost = has("Homestead.ghost") or has("Homestead.ghostpart"), bench = has("Homestead.bench"), chunk = 1 }
                for c = 2, it.chunks do if has("hsc" .. c) then info.chunk = c break end end
                for _, a in ipairs(it.apps) do if has("hsapp:" .. a) then info.app = a break end end
                break
            end
        end
        S.info[hid] = info
        return info or nil
    end

    -- (tags are TEXT in the mod: the game's names are made of them only where a spec is handed to the game - names())
    local function tagsFor(role, key, app)
        local tags = { role, "hs:" .. key, "hsapp:" .. app, "hsv2", ALWAYS }
        local h = keyHash(key)
        for b = 0, BITS - 1 do if math.floor(h / 2 ^ b) % 2 == 1 then table.insert(tags, "hsb" .. b) end end
        return tags
    end
    local function names(tags)
        local out = {}
        for i, t in ipairs(tags) do out[i] = CName.new(t) end
        return out
    end

    local function spawn(key, app, o, yaw, ghost, chunk, q)
        chunk = chunk or 1
        local spec = DynamicEntitySpec.new()
        local rec, tpl = byKey[key] and byKey[key].record, byKey[key] and byKey[key].template
        local own                                             -- (an entity of our own: its template, for modules/world.lua)
        if rec and not ghost then spec.recordID = TweakDBID.new(rec)
        elseif tpl and chunk == 1 then
            spec.templatePath = ResRef.FromString(tpl)
            spec.appearanceName = CName.new(app)
        else
            own = (not ghost and chunk == 1 and byKey[key] and byKey[key].lights) and TEMPLATE_LIT or TEMPLATE
            spec.templatePath = own
        end
        local turn = Q.toQuat(q, yaw)
        spec.position = v4(o.x, o.y, o.z)
        spec.orientation = turn
        spec.persistSpawn = not ghost
        spec.persistState = false
        spec.alwaysSpawned = true
        spec.spawnInView = true
        spec.active = true
        local role = chunk > 1 and (ghost and "Homestead.ghostpart" or "Homestead.part") or (ghost and "Homestead.ghost" or "Homestead")
        local tags = tagsFor(role, key, app)
        if chunk > 1 then table.insert(tags, "hsc" .. chunk) end
        -- its own identity, for what is kept about it across saves (life.lua: an entity's id is a session's)
        if chunk == 1 and not ghost then table.insert(tags, string.format("hsu:%d%05d", os.time(), math.random(0, 99999))) end
        if key == "workbench" and not ghost then
            table.insert(tags, "Homestead.bench")
            for _, t in ipairs(S.zone.tags or {}) do table.insert(tags, t) end
        end
        spec.tags = names(tags)
        -- (ours: described to modules/world.lua in plain values - nothing is read back from the game's spec)
        if own then own = { path = own, x = o.x, y = o.y, z = o.z, i = turn.i, j = turn.j, k = turn.k, r = turn.r, tags = tags, keep = not ghost } end
        local info = { key = key, app = app, ghost = ghost, bench = key == "workbench" and not ghost, o = o, yaw = yaw, q = q, chunk = chunk }
        S.creating = info
        local id = Eng.create(spec, (rec and not ghost) or (tpl and chunk == 1), own)
        if rec and not ghost then S.calm = S.calm or {}; S.calm[#S.calm + 1] = { id = id, t = 0 } end   -- (C.calm: at once)
        S.creating = nil
        if not ghost then S.pending[hashOf(id)] = info end
        return id
    end

    -- one of the game's objects a copied building brings (a door that opens, a lamp that lights), spawned as itself at its
    -- spot in the building: a part of the piece, found again by where it stands
    local function spawnEnt(key, app, e, o, yaw)
        local w = local2world(o, yaw, e.x, e.y, e.z)
        local spec = DynamicEntitySpec.new()
        spec.templatePath = ResRef.FromString(e.path)
        if e.app ~= "default" then spec.appearanceName = CName.new(e.app) end
        spec.position = v4(w.x, w.y, w.z)
        spec.orientation = Q.toQuat(Q.mul(Q.yaw(yaw), { i = e.q[1], j = e.q[2], k = e.q[3], r = e.q[4] }))
        spec.persistSpawn = true
        spec.persistState = false
        spec.alwaysSpawned = true
        spec.spawnInView = true
        spec.active = true
        spec.tags = names(tagsFor("Homestead.part", key, app))
        local id = Eng.create(spec, not e.path:find("stash.ent", 1, true))
        S.pending[hashOf(id)] = { key = key, app = app, ghost = false, bench = false, o = w, yaw = yaw, chunk = 1 }
        return id
    end

    -- a whole piece: its main entity and, for a big one, its parts at the same spot. A real one (not a preview) goes
    -- into the piece list at once - the world changed, no waiting for refresh to list it. -> the main id, all ids, the piece
    local function spawnPiece(key, app, o, yaw, ghost, q)
        local ids = {}
        for c = 1, byKey[key].chunks do table.insert(ids, spawn(key, app, o, yaw, ghost, c, q)) end
        if ghost then return ids[1], ids end
        for _, e in ipairs(byKey[key].ents or {}) do table.insert(ids, spawnEnt(key, app, e, o, yaw)) end
        local it = byKey[key]
        local p = { id = ids[1], key = key, app = app, o = o, yaw = yaw, q = q, it = it, bench = key == "workbench", at = anchorOf(it, o, yaw), always = true }
        if #ids > 1 then p.parts = {} for i = 2, #ids do p.parts[i - 1] = ids[i] end end
        S.pieces[#S.pieces + 1], S.byId[hashOf(p.id)] = p, p
        S.world = S.world + 1
        return ids[1], ids, p
    end

    local function killFx(h) for _, f in ipairs(S.fx[h] or {}) do pcall(function() f:Kill() end) end S.fx[h] = nil end

    local function del(id)
        local h = hashOf(id)
        killFx(h)
        Anim.forget(id)
        S.pending[h], S.info[h], S.unloaded[h] = nil, nil, nil
        Eng.delete(id)
    end
    local function removePiece(p)
        pcall(Life.gone, p)
        Life.pieceRemoved(p)
        del(p.id)
        for _, id in ipairs(p.parts or {}) do del(id) end
        local h, keep = hashOf(p.id), {}
        for _, q in ipairs(S.pieces) do if hashOf(q.id) ~= h then keep[#keep + 1] = q end end
        S.pieces, S.byId[h] = keep, nil
        S.world = S.world + 1
    end

    local IGNORED                                             -- (TrafficGenDynamicImpact.Ignored, made at first use)
    local BOXES_PER = 64          -- boxes per collider component: one with 168 took the game down (a 7-storey prefab)
    local function colliderOf(name, boxes, lo, hi)
        local c = entColliderComponent.new()
        c.name = CName.new(name)
        local actors = {}
        for n = lo, hi do
            local b = boxes[n]
            local box = physicsColliderBox.new()
            box.halfExtents = Vector3.new(b[4], b[5], b[6])
            local t = Transform.new()
            t.position = Vector4.new(b[1], b[2], b[3], 1)
            t.orientation = b[7] and Quaternion.new(b[7], b[8], b[9], b[10]) or Quaternion.new(0, 0, 0, 1)
            box.localToBody = t
            box.material = CName.new("concrete.physmat")
            table.insert(actors, box)
        end
        c.colliders = actors
        local filter = physicsFilterData.new()     -- World Builder's static-world filter (collides with V, NPCs, cars)
        filter.preset = CName.new("World Static")
        local query = physicsQueryFilter.new()
        query.mask1 = 0
        query.mask2 = 70107400
        local sim = physicsSimulationFilter.new()
        sim.mask1 = 114696
        sim.mask2 = 23627
        filter.queryFilter = query
        filter.simulationFilter = sim
        c.filterData = filter
        -- The engine's entColliderComponent has a dynamicTrafficSetting (TrafficGenDynamicImpact: Ignored / Blocking -
        -- RED4ext SDK): ours never block the game's traffic (user, 2026-10-05: no cars or people under a settlement on
        -- an overpass till V left and came back - UNPROVEN that this was it; what a new component's default is isn't known).
        if IGNORED == nil then local ok, e = pcall(Enum.new, "TrafficGenDynamicImpact", "Ignored"); IGNORED = ok and e or false end
        local t = IGNORED and c.dynamicTrafficSetting
        if t then t.impact = IGNORED; c.dynamicTrafficSetting = t end
        return c
    end
    local function addColliders(entity, it, chunk)
        local boxes = it.cboxes or it.boxes
        local per = math.ceil(#boxes / it.chunks)
        local lo, hi = (chunk - 1) * per + 1, math.min(#boxes, chunk * per)
        for first = lo, hi, BOXES_PER do entity:AddComponent(colliderOf("hs_collider" .. first, boxes, first, math.min(hi, first + BOXES_PER - 1))) end
        if chunk == 1 and it.pcol then
            for k, pb in ipairs(it.pcol) do
                if #pb > 0 then entity:AddComponent(colliderOf("hs_pcol" .. k, pb, 1, math.min(#pb, BOXES_PER))) end
            end
        end
    end

    -- A Fallout piece's light (modules/lights.lua). Pieces with lights spawn from empty_lit.ent, whose light components (12; 2 from an import before 2026-10-05: the rest of a piece's lights aren't there) carry the game's
    -- own settings (made here they lit nothing); this sets colour, reach and strength. Fallout's radius is the reach, its fade a strength; strength
    -- counts much less than linearly, so a street lamp lights the street and a poster's glow stays a glow.
    local function lumens(l)
        if l.lm then return l.lm end
        return math.min(800, 140 * math.max(0.4, l.radius) ^ 1.2 * math.max(0.15, math.min(2.5, l.fade or 1)) ^ 0.4)
    end
    -- A spotlight's beam is the game's own two ways (read from its files, NOTES.md "Spotlight beam"): the light scatters
    -- in the fog (scaleVolFog, as the prison's searchlight has it), and a shaft the game's searchlights carry as a mesh
    -- (a cone along +Y: BEAM.r0 m wide at its start, BEAM.len m long), here from the lens (l.beam: its radius) to the
    -- light's reach. modules/turret.lua turns it with the head, Anim's lamp switches it.
    local BEAM = { mesh = "base\\fx\\meshes\\spotlight_a_beam_mesh.mesh", app = "cz_combat_tower", r0 = 0.12, len = 4.795 }
    local function addLight(entity, l, i)
        local t = WorldTransform.new()
        t:SetPosition(Vector4.new(l.pos[1], l.pos[2], l.pos[3], 1))
        if l.spot and l.dir then
            local dx, dy, dz = l.dir[1], l.dir[2], l.dir[3]
            local ax, az = dz, -dx
            local s2 = math.sqrt(ax * ax + az * az)
            local a = math.acos(math.max(-1, math.min(1, dy)))
            if s2 < 1e-6 then ax, az, s2 = 1, 0, 1 end
            local h = math.sin(a / 2) / s2
            t:SetOrientation(Quaternion.new(ax * h, 0, az * h, math.cos(a / 2)))
        end
        if l.beam then
            local b = entMeshComponent.new()
            b.name, b.mesh, b.meshAppearance = CName.new("hs_beam" .. i), ResRef.FromString(BEAM.mesh), CName.new(BEAM.app)
            b.visualScale = Vector3.new(l.beam / BEAM.r0, l.radius / BEAM.len, l.beam / BEAM.r0)
            b.localTransform, b.isEnabled = t, S.dark[hashOf(entity:GetEntityID())] == nil
            pcall(function() b.castShadows = Enum.new("shadowsShadowCastingMode", "Never") end)
            entity:AddComponent(b)
        end
        local c = entity:FindComponentByName(CName.new("hs_light" .. i))
        if not c then return end
        c.color = Color.new({ Red = l.color[1], Green = l.color[2], Blue = l.color[3], Alpha = 255 })
        c.radius = math.max(0.5, l.radius * 1.25)
        c.intensity = lumens(l)
        c.enableLocalShadows = l.radius >= 1                 -- (a poster's or a screen's glow casts none)
        c.shadowFadeDistance, c.shadowFadeRange = 30, 10
        if l.spot and l.dir then
            pcall(function() c.type = Enum.new("ELightType", "LT_Spot") end)
            c.outerAngle, c.innerAngle = l.spot / 2, l.spot / 2 * 0.6
            if l.beam then c.scaleVolFog = 100 end
        end
        c.localTransform = t
        c.isEnabled = true
    end
    local function lightsOn(entity, it)
        for i, l in ipairs(it.lights) do
            local c = entity:FindComponentByName(CName.new("hs_light" .. i))
            if c then c:SetIntensity(lumens(l)); c:ToggleLight(true) end
        end
    end
    local function lightsOff(entity, from)
        for i = from, 12 do local c = entity:FindComponentByName(CName.new("hs_light" .. i)); if c then c.isEnabled = false end end
    end

    -- Fallout's fire and smoke (catalog `fx`) as the game's own effects, spawned in the world at the piece. They don't
    -- belong to the entity, so they are kept by it (S.fx) and killed with it (killFx), or when it streams in again
    local function addFx(entity, fx)
        local h = hashOf(entity:GetEntityID())
        killFx(h)
        local at, q, list = entity:GetWorldPosition(), entity:GetWorldOrientation(), {}
        for _, e in ipairs(fx) do
            local p = q:Transform(Vector4.new(e.pos[1], e.pos[2], e.pos[3], 0))
            local t = WorldTransform.new()
            t:SetPosition(Vector4.new(at.x + p.x, at.y + p.y, at.z + p.z, 1))
            local r = gameFxResource.new()
            r.effect = ResRef.FromString(e.path)
            local inst = Game.GetFxSystem():SpawnEffect(r, t, false)
            if inst then list[#list + 1] = inst end
        end
        S.fx[h] = list
    end

    local function afterAttach(dt)
        local keep = {}
        for _, a in ipairs(S.after) do
            a.t = a.t + dt
            local e = des():GetEntity(a.id)
            local w = e and e:GetWorldPosition()
            if w and a.t > 0.3 and math.abs(w.x) + math.abs(w.y) > 1 then
                if a.stash then
                    for _, c in ipairs(e:GetComponents()) do
                        local cls = c:GetClassName().value
                        if cls:find("Mesh") or cls == "GameplayRoleComponent" or cls == "entColliderComponent" or cls == "gameinteractionsComponent" then
                            pcall(function() c:Toggle(false) end)
                        end
                    end
                elseif a.it.lights and not S.dark[hashOf(a.id)] then try("light", lightsOn, e, a.it) end
                if a.it.fx then try("effect", addFx, e, a.it.fx) end
            elseif a.t < 10 then keep[#keep + 1] = a end
        end
        S.after = keep
    end

    -- a container's stash (catalog `stash`: the game's stash device, part of the piece): its collider becomes the
    -- container's bounds (not its wall rack's, for the moment it's on), and once in the world its meshes, map icon,
    -- collider and interaction go (afterAttach): E on the container opens it (modules/anim.lua). V's own stashes come
    -- through here too: not ours, left alone.
    local function stashPart(entity, it)
        local b = { (it.min[1] + it.max[1]) / 2, (it.min[2] + it.max[2]) / 2, (it.min[3] + it.max[3]) / 2,
                    math.max(0.1, (it.max[1] - it.min[1]) / 2) + 0.03, math.max(0.1, (it.max[2] - it.min[2]) / 2) + 0.03,
                    math.max(0.1, (it.max[3] - it.min[3]) / 2) + 0.03 }
        for _, c in ipairs(entity:GetComponents()) do
            if c:GetClassName().value == "entColliderComponent" then
                local box = physicsColliderBox.new()
                box.halfExtents = Vector3.new(b[4], b[5], b[6])
                local t = Transform.new()
                t.position = Vector4.new(b[1], b[2], b[3], 1)
                box.localToBody = t
                box.material = CName.new("concrete.physmat")
                c.colliders = { box }
            elseif c:GetName().value == "UI_Slots" then           -- (where the game hangs its icon: Cyberpunk's stash is
                local t = WorldTransform.new()                    -- a wall unit, its icon 1.3 m behind and 1.8 m up; ours:
                t:SetPosition(Vector4.new(b[1], b[2], it.max[3] + 0.2, 1))
                c.localTransform = t
            end
        end
        S.after[#S.after + 1] = { id = entity:GetEntityID(), it = it, t = 0, stash = true }
    end

    -- What the importer got wrong, put right here: a fix in the importer would make every player import again
    -- (STATUS.md "Updates"). NOGLOW: Fallout effect shaders that are no lights (glass, water, a fire's sprite sheet)
    -- came out glowing - that glow mesh isn't shown. ONE: lights Fallout shows one at a time (a cycling bulb's
    -- colours, a traffic light's) - one component, all of them kept in it.cycle (anim.lua steps through them).
    local NOGLOW = { "^fo4_dlc05grnhs", "^fo4_wksdisplaycase", "^fo4_dlc06workshopsodastation", "^fo4_workshopartillery$",
                     "^fo4_waterpump01furn$", "^fo4_dlc06vault_sink_01activator$", "^fo4_dlc06workshopvault_waterfountain01$",
                     "^fo4_dlc02_taxidermybloodbug$", "^fo4_mq206beamemitter$" }
    local ONE = { fo4_workshopcyclinglightbulb01 = true, fo4_workshoptrafficlight = true }
    local function fix(it)
        if it.fixed then return end
        it.fixed = true
        if ONE[it.key] and it.lights then
            it.cycle = { unpack(it.lights) }
            for i = #it.lights, 2, -1 do it.lights[i] = nil end
        end
        for _, pat in ipairs(NOGLOW) do if it.glow and it.key:find(pat) then it.noglow = it.glow end end
    end

    -- Someone just placed: friendly from their first frame in the world (every frame till they are there; the refresh's
    -- check a second later would let a drone fire first - user, 2026-10-05)
    local function peace(e)
        local a = e:GetAttitudeAgent()
        a:SetAttitudeGroup(CName.new("friendly"))
        a:SetAttitudeTowards(Game.GetPlayer():GetAttitudeAgent(), EAIAttitude.AIA_Friendly)
    end
    -- The bar droid (q303_droid.ent) has its standing animations (idle_stand: base ...\android\unarmed\
    -- ma_android_unarmed_locomotion_patrolling.anims) only while this animation wrapper is on - its quest's doing, so
    -- placed from its record it stood in a T-pose (user, 2026-10-05). Other androids' templates have the set always.
    local function wake(e) AnimationControllerComponent.SetAnimWrapperWeight(e, CName.new("droidLocomotionUnarmed"), 1) end
    function C.calm(dt)
        local keep = {}
        for _, c in ipairs(S.calm or {}) do
            local e = des():GetEntity(c.id)
            c.t = c.t + dt
            if e then pcall(peace, e); pcall(wake, e) end
            if c.t < 3 then keep[#keep + 1] = c end              -- (again for 3 s: its own start-up sets it back)
        end
        S.calm = #keep > 0 and keep or nil
    end

    local function onEntity(entity)
        if not entity then return end
        local id = entity:GetEntityID()
        Eng.attached(id)
        if C.Border.dress(entity, hashOf(id)) then return end
        if Life.onEntity(entity) then return end
        local info = S.pending[hashOf(id)] or S.creating or tagInfo(id)
        local it = info and byKey[info.key]
        if entity:GetClassName().value == "Stash" then
            if it and it.stash then try("stash", stashPart, entity, it) end
            return
        end
        if not it then return end
        fix(it)
        local chunk = info.chunk or 1
        -- mesh parts: { path, x, y, z, yaw[, app[, qi, qj, qk, qr, sx, sy, sz]] } in the piece's space (a part may carry
        -- its full rotation and scale)
        local ball = C.Ball.is(it)                                 -- (a ball: no collider - modules/ball.lua rolls it)
        local list = it.meshes
        for i = (chunk - 1) * CHUNK + 1, math.min(#list, chunk * CHUNK) do
            local m = list[i]
            if i == it.noglow then goto skip end
            local c = entMeshComponent.new()
            c.name = CName.new("hs_mesh" .. i)
            c.mesh = ResRef.FromString(m[1])
            local a = m[6]
            c.meshAppearance = CName.new((a and a ~= "") and a or info.app or "default")
            if m[2] ~= 0 or m[3] ~= 0 or m[4] ~= 0 or m[5] ~= 0 or m[7] then
                local t = WorldTransform.new()
                t:SetPosition(Vector4.new(m[2], m[3], m[4], 1))
                if m[7] then t:SetOrientation(Quaternion.new(m[7], m[8], m[9], m[10]))
                else t:SetOrientationEuler(EulerAngles.new(0, 0, m[5])) end
                c.localTransform = t
            end
            if m[11] then c.visualScale = Vector3.new(m[11], m[12] or 1, m[13] or 1) end
            entity:AddComponent(c)
            ::skip::
        end
        if not info.ghost and #it.boxes > 0 and not ball then addColliders(entity, it, chunk) end
        if chunk == 1 and not info.ghost then
            for i, l in ipairs(it.lights or {}) do try("light", addLight, entity, l, i) end
            if it.lights then try("light", lightsOff, entity, #it.lights + 1) end
            if it.off then
                local c, dark = entMeshComponent.new(), S.dark[hashOf(id)] ~= nil
                c.name = CName.new("hs_off")
                c.mesh = ResRef.FromString(it.meshes[1][1])
                c.meshAppearance = CName.new(it.off)
                c.isEnabled = dark
                entity:AddComponent(c)
                local m = entity:FindComponentByName(CName.new("hs_mesh1"))
                if m then m.isEnabled = not dark end
            end
            -- a light's strength and a piece's fire need it placed in the world first (made now, the fire went to the
            -- world's origin and the light's strength was reset): done a moment later, from onUpdate (afterAttach)
            if it.lights or it.fx then S.after[#S.after + 1] = { id = id, it = it, t = 0 } end
        end
    end

    local function outline(id, index)
        local e = id and des():GetEntity(id)
        if e then e:QueueEvent(entRenderHighlightEvent.new({ seeThroughWalls = true, outlineIndex = index, opacity = 1 })) end
    end

    local function outlinePiece(p, index)
        outline(p.id, index)
        for _, id in ipairs(p.parts or {}) do outline(id, index) end
    end

    local function retarget(t, rest, pick)
        if t ~= S.target and (t and hashOf(t.id)) ~= (S.target and hashOf(S.target.id)) then
            if S.target then outlinePiece(S.target, rest and rest(S.target) or OUTLINE.off) end
            if t and (not pick or pick(t)) then outlinePiece(t, OUTLINE.target) end
        end
        S.target = t
    end

    -- the world version (S.world): bumped whenever the zone's built pieces change - one spawned or removed by us, or
    -- refresh finding one new, gone or moved (people walking aren't a change). What is made from the pieces keys off
    -- it instead of looking at them all: LiveNav's sweep (livenav.lua), the snap points, the cheap refresh.

    local function index()
        S.occupied, S.levels, S.bench, S.cost = {}, {}, nil, 0
        for _, p in ipairs(S.pieces) do
            local it = p.it
            if p.bench then S.bench = p end
            if it.kind and it.kind ~= "road" and it.kind ~= "prefab" then
                p.slots = p.slots or slotsOf(it, p.o, p.yaw)
                for _, k in ipairs(p.slots) do S.occupied[k] = p end
                S.levels[levelKey(p.o.z)] = p.o.z
            end
            S.cost = S.cost + it.cost
        end
        Grid.build(S.pieces)
        if S.pointsWorld ~= S.world then S.pointsWorld = S.world; Eng.count("points"); Grid.buildPoints(S.pieces) end
    end

    -- periodic (once a second, onUpdate): with the same entities as last time, the world as refresh left it and nothing
    -- half done (a piece still streaming in, an orphan or a stash under watch, a placement pending), only the people's
    -- places are read anew (Life.sync) - the piece list, its slots, cells and snap points stand as they are
    local function sameIds(ids, parts)
        local seen = S.seenIds
        if #ids + #parts ~= #seen then return false end
        for i, id in ipairs(ids) do if seen[i] ~= id.hash then return false end end
        for i, id in ipairs(parts) do if seen[#ids + i] ~= id.hash then return false end end
        return true
    end
    local function alive(tag)
        local out = {}
        for _, id in ipairs(des():GetTaggedIDs(tag) or {}) do if not Eng.dying(id) then out[#out + 1] = id end end
        return out
    end
    local function here(o)
        return (o.x - S.zone.x) ^ 2 + (o.y - S.zone.y) ^ 2 <= (RADIUS + 500) ^ 2 and C.Sites.nearest(o) == S.zone
    end
    local function refresh(periodic)
        if not des() or not des():IsReady() then
            if next(S.byId) then S.pieces, S.byId, S.world = {}, {}, S.world + 1 end
            index() return
        end
        local ids, partIds = alive("Homestead"), alive("Homestead.part")
        if periodic and S.settled and S.refreshWorld == S.world and not next(S.pending) and sameIds(ids, partIds) then
            local arrived = false
            for _, id in ipairs(S.waitIds or {}) do if des():GetEntity(id) then arrived = true break end end
            if not arrived then
                if Life.sync() then Grid.build(S.pieces) end
                return
            end
        end
        Eng.count("refresh")
        local seen = {}
        for _, id in ipairs(ids) do seen[#seen + 1] = id.hash end
        for _, id in ipairs(partIds) do seen[#seen + 1] = id.hash end
        S.seenIds = seen
        local old, pieces, byId, bench, changed = S.byId, {}, {}, nil, false
        local waiting, waitIds = {}, {}
        for _, id in ipairs(ids) do
            local h = hashOf(id)
            local info = not S.unloaded[h] and (S.pending[h] or tagInfo(id)) or nil
            if S.pending[h] and info then S.info[h], S.pending[h] = info, nil end
            local it = info and byKey[info.key]
            local o, yaw, q = info and info.o, info and info.yaw, info and info.q
            if it and not o then
                local e = des():GetEntity(id)
                if e then
                    local p = e:GetWorldPosition()
                    o = { x = p.x, y = p.y, z = p.z }
                    local w = e:GetWorldOrientation()
                    local wq = { i = w.i, j = w.j, k = w.k, r = w.r }
                    yaw = (math.floor(Q.yawOf(wq) * 10 + 0.5) / 10) % 360
                    if Q.tilted(wq) then q = wq end
                    if o.x ~= 0 or o.y ~= 0 then info.o, info.yaw, info.q = o, yaw, q end
                end
            end
            if it and not o then waiting[info.key] = true; waitIds[#waitIds + 1] = id end
            if o and not here(o) then o = nil end
            if o then
                if info.bench and bench then
                    del(id)
                    log("removed an extra workbench")
                else
                    local p = old[h]
                    if not (p and p.key == info.key and (it.npc or (p.o.x == o.x and p.o.y == o.y and p.o.z == o.z and p.yaw == yaw))) then
                        p = { id = id, key = info.key, app = info.app, o = o, yaw = yaw, q = q, it = it, bench = info.bench, at = anchorOf(it, o, yaw) }
                        changed = changed or not it.npc
                    end
                    p.parts = nil
                    if p.bench then bench = p end
                    pieces[#pieces + 1], byId[h] = p, p
                end
            end
        end
        for h, p in pairs(old) do
            if not byId[h] then
                if S.pending[h] and here(p.o) then pieces[#pieces + 1], byId[h] = p, p
                elseif not p.it.npc then changed = true end
            end
        end
        S.pieces, S.byId = pieces, byId
        if changed then S.world = S.world + 1 end
        local hostile = {}
        for _, p in ipairs(S.pieces) do
            if p.it.npc and not S.checked[hashOf(p.id)] then
                local e = des():GetEntity(p.id)
                local ok, att = pcall(function() return e and e:GetAttitudeTowards(Game.GetPlayer()) end)
                if ok and att then
                    S.checked[hashOf(p.id)] = true
                    pcall(wake, e)                                -- (after a load: nobody is placed anew, C.calm doesn't run)
                    -- (anyone can be placed - a ganger, a mech: they keep the peace, with V and with each other; one that
                    -- can't be made to is removed, as all hostile ones were before 2026-10-05)
                    if tostring(att):find("Hostile") and not pcall(peace, e) then hostile[#hostile + 1] = p end
                end
            end
        end
        for _, p in ipairs(hostile) do removePiece(p); say(p.it.name .. " won't keep the peace: removed"); log("removed hostile " .. p.key) end
        local function near(a, b, d) return (a.x - b.x) ^ 2 + (a.y - b.y) ^ 2 + (a.z - b.z) ^ 2 < d end
        local me = Game.GetPlayer() and Game.GetPlayer():GetWorldPosition()
        for _, id in ipairs(partIds) do
            local h = hashOf(id)
            local info = not S.unloaded[h] and (S.pending[h] or tagInfo(id)) or nil
            if S.pending[h] and info then S.info[h], S.pending[h] = info, nil end
            local e = des():GetEntity(id)
            local q = info and (info.o or (e and e:GetWorldPosition()))
            local owner
            if q then
                for _, p in ipairs(S.pieces) do
                    if p.key == info.key then
                        if near(p.o, q, 0.01) then owner = p break end
                        for _, en in ipairs(p.it.ents or {}) do
                            if near(local2world(p.o, p.yaw, en.x, en.y, en.z), q, 0.04) then owner = p break end
                        end
                        if owner then break end
                    end
                end
            end
            if not q and info then waiting[info.key] = true; waitIds[#waitIds + 1] = id end
            if owner then
                owner.parts = owner.parts or {}
                local dup = false
                for _, x in ipairs(owner.parts) do dup = dup or hashOf(x) == h end
                if not dup then owner.parts[#owner.parts + 1] = id end
                S.orphan[h] = nil
            elseif q and me and near(me, q, 40 ^ 2) and not waiting[info.key] and not C.Sites.loading then
                S.orphan[h] = (S.orphan[h] or 0) + 1
                if S.orphan[h] >= 3 then del(id); S.orphan[h] = nil end
            end
        end
        for _, p in ipairs(S.pieces) do
            local h = hashOf(p.id)
            if p.it.stash and not p.parts and me and near(me, p.o, 40 ^ 2) and not waiting[p.key] and not C.Sites.loading then
                S.nostash[h] = (S.nostash[h] or 0) + 1
                if S.nostash[h] >= 3 then S.nostash[h] = nil; spawnEnt(p.key, p.app, p.it.ents[1], p.o, p.yaw) end
            else S.nostash[h] = nil end
        end
        for h, info in pairs(S.pending) do
            info.miss = (info.miss or 0) + 1
            if info.miss >= 3 then S.pending[h] = nil end
        end
        Life.sync()
        index()
        S.tagged = #ids
        S.waitIds = waitIds
        S.settled = not next(S.orphan) and not next(S.nostash)
        S.refreshWorld = S.world
    end

    C.spawnPiece, C.killFx, C.del, C.removePiece, C.lumens = spawnPiece, killFx, del, removePiece, lumens
    C.afterAttach, C.onEntity, C.outline, C.outlinePiece, C.retarget, C.refresh = afterAttach, onEntity, outline, outlinePiece, retarget, refresh
    C.index, C.TEMPLATE = index, TEMPLATE
    function C.ready(p)
        if not Eng.ready(p.id) then return false end
        for _, id in ipairs(p.parts or {}) do if not Eng.ready(id) then return false end end
        return true
    end

    -- a piece saved before ALWAYS (streamed by the population system: it popped in) made again where it stands, always
    -- spawned, as a pick-up and put-back does (its people's jobs follow it). Every frame outside workshop and Command
    -- mode, two a frame; a piece is asked once, once it has settled (the lifetime guard), and a list all asked isn't
    -- gone through again (S.asked: spawnPiece adds to it only pieces made so). Logged once a batch.
    local AS                                                  -- (made at first use: no game types while the mod loads)
    function C.remake()
        if S.build or S.cmd or S.hold or S.asked == S.pieces then return end
        local n, open = 0, false
        for _, p in ipairs(S.pieces) do
            -- (and one still in the game's population, from a save made before our pieces were static: modules/world.lua)
            if p.always == nil and C.ready(p) then p.always = des():IsTagged(p.id, ALWAYS) and des().static(p.id) == des().wants(p.it) end
            open = open or p.always == nil
            if p.always == false then
                removePiece(p)
                local id = spawnPiece(p.key, p.app, p.o, p.yaw, false, p.q)
                C.Life.rejob(hashOf(p.id), hashOf(id))
                n = n + 1
                if n == 2 then break end
            end
        end
        if n > 0 then S.remade = (S.remade or 0) + n; index() return end
        if not open then S.asked = S.pieces end
        if S.remade then log(string.format("made %d pieces again, always spawned (they were saved streamed: the pop-in)", S.remade)); S.remade = nil end
    end
end
