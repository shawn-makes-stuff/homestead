-- The settlement border in workshop mode: a tall holographic wall round the circle (C.RADIUS) - one entity with one
-- mesh, homestead\border.mesh (tools/make_border.py; colour, opacity and scan lines are set in the mesh material).
-- Depth-tested, so pieces in front hide it. No collider or piece tag: no ray or look-at meets it. Never saved.
-- Made on entering workshop mode, gone on leaving; Settings > Building > Settlement border switches it. M is C.Border.
return function(M, C)
    local S, RADIUS, v4, hashOf, Eng, try = C.S, C.RADIUS, C.v4, C.hashOf, C.Eng, C.try
    local MESH = "homestead\\border.mesh"
    -- The wall spans BELOW m under the centre's ground to ABOVE m over it (so it stands in sloped ground).
    local BELOW, ABOVE = 30, 30
    local RING = {}

    local function show(z)
        local spec = DynamicEntitySpec.new()
        spec.templatePath = C.TEMPLATE
        spec.position = v4(z.x, z.y, z.z - BELOW)
        spec.orientation = Quaternion.new(0, 0, 0, 1)
        spec.persistSpawn, spec.persistState, spec.alwaysSpawned, spec.spawnInView, spec.active = false, false, true, true, true
        spec.tags = { CName.new("Homestead.border") }
        S.creating = RING
        local id = Eng.create(spec, nil, { path = C.TEMPLATE, x = z.x, y = z.y, z = z.z - BELOW, i = 0, j = 0, k = 0, r = 1, tags = { "Homestead.border" }, keep = false })
        S.creating = nil
        S.ring = { id = id, h = hashOf(id), zone = z }
    end

    function M.update()
        local want = S.build and S.showBorder and S.zone or nil
        if (S.ring and S.ring.zone or nil) == want then return end
        if S.ring then Eng.delete(S.ring.id); S.ring = nil end
        if want then show(want) end
    end

    function M.dress(entity, h)
        if S.creating ~= RING and not (S.ring and S.ring.h == h) then return false end
        local c = entMeshComponent.new()
        c.name = CName.new("hs_border")
        c.mesh = ResRef.FromString(MESH)
        c.meshAppearance = CName.new("default")
        c.visualScale = Vector3.new(RADIUS, RADIUS, BELOW + ABOVE)
        try("border shadows", function()
            local never = Enum.new("shadowsShadowCastingMode", "Never")
            c.castShadows, c.castLocalShadows, c.castRayTracedGlobalShadows, c.castRayTracedLocalShadows = never, never, never, never
        end)
        entity:AddComponent(c)
        return true
    end
end
