-- Command mode (Fallout's Command): people given jobs - a seat, a bed, a work spot, a spot on the ground to wait at -
-- outside workshop mode, with people living on meanwhile. Cmd.enter / exit, Cmd.tick (the piece looked at, outlines),
-- Cmd.act (select, assign, send), Cmd.clear, Cmd.unselect. init.lua requires this after ui.lua; Cmd goes into C.
return function(C)
    local S, hashOf, say, SFX, OUTLINE, Eng, Gizmo = C.S, C.hashOf, C.say, C.SFX, C.OUTLINE, C.Eng, C.Gizmo
    local Life, sfx, Lines, timed, aim, outlinePiece = C.Life, C.sfx, C.Lines, C.timed, C.aim, C.outlinePiece
    local retarget, refresh = C.retarget, C.refresh

    -- KEYS.command (R by default; Settings > Keys) toggles it in the zone, outside workshop mode; everything assignable is outlined.
    -- E on a person selects them; E on an outlined piece gives them that job (Life.job, saved in jobs.txt); E on standable ground
    -- sends them to wait there (Life.moveTo; refused with navigation off). R clears a job, Tab unselects / leaves.
    local Cmd = {}
    function Cmd.rest(p)
        if S.cmd and S.cmd.who and hashOf(p.id) == S.cmd.who.h then return OUTLINE.selected end
        return Life.usable(p) and OUTLINE.usable or OUTLINE.off
    end
    function Cmd.pickable(p) return p.it.npc or Life.usable(p) end
    function Cmd.exit()
        if not S.cmd then return end
        for _, p in ipairs(S.pieces) do if Cmd.pickable(p) then outlinePiece(p, OUTLINE.off) end end
        S.target, S.cmd = nil, nil
        Homestead.Restrict(false)
        Lines.set("cmd", nil)
        Eng.ui("Target", ""); S.targetShown = ""
        sfx(SFX.exit)
    end
    function Cmd.tick(dt)
        local c = S.cmd
        if not S.inZone then Cmd.exit() return end
        local a = timed("aim", aim)
        local t = a.piece
        retarget(t, Cmd.rest, Cmd.pickable)
        -- Somewhere to stand ("Wait here"): whatever the crosshair hits that is nobody and nothing assignable; Life.moveTo
        -- finds the navmesh there (a wall face or a crate top: none).
        c.point = not (t and Cmd.pickable(t)) and a.point or nil
        c.t = c.t + dt
        if c.t >= 1 then
            c.t = 0
            for _, p in ipairs(S.pieces) do if p ~= t and Cmd.pickable(p) then outlinePiece(p, Cmd.rest(p)) end end
        end
    end
    local function off() return Life.walks() and "" or "  -  navigation off" end
    local function told(what, why, d)
        C.log(string.format("command: %s %s probe %s", what, why or "ok", tostring(d)))
    end
    local function no(what, why, toast) told(what, why); say(toast); sfx(SFX.refuse) end
    function Cmd.act()
        local c, t = S.cmd, S.target
        if t and t.it.npc then
            local old = c.who and c.who.p
            c.who = { h = hashOf(t.id), name = t.it.name, p = t }
            if old then outlinePiece(old, Cmd.rest(old)) end
            say(t.it.name .. ": now look at a seat, a bed, a work spot or somewhere to stand and press E")
            sfx(SFX.open)
        elseif not c.who then no("nobody selected", "look at someone first", "Look at someone and press E")
        elseif t and Life.usable(t) then  -- no way to it now: the job is kept, said once, retried as the navmesh changes
            local _, why, d = Life.job(c.who.h, t)
            told(c.who.name .. " to " .. t.it.name, why, d)
            say(c.who.name .. " assigned to " .. t.it.name .. (why and "  -  " .. why or off())); sfx(why and SFX.refuse or SFX.build)
        elseif c.point then
            local ok, why, d, f = Life.moveTo(c.who.h, c.point)
            local at = f or c.point
            told(string.format("%s to %.1f, %.1f, %.1f", c.who.name, at.x, at.y, at.z), why, d)
            if ok then say(c.who.name .. " will wait there"); sfx(SFX.drop) else say((why:gsub("^%l", string.upper))); sfx(SFX.refuse) end
        else no(c.who.name .. " to " .. (t and t.it.name or "nothing"), "nowhere to stand there", "Look at a seat, a bed, a work spot, or somewhere to stand") end
    end
    function Cmd.clear()
        local c, t = S.cmd, S.target
        local h, name = c.who and c.who.h, c.who and c.who.name
        if t and t.it.npc then h, name = hashOf(t.id), t.it.name end
        if h and Life.unjob(h) then say(name .. " released"); sfx(SFX.scrap) else no("clear " .. (name or "nobody"), "no assignment", "No assignment to clear") end
    end
    function Cmd.unselect()
        local c = S.cmd
        if not c.who then Cmd.exit() return end
        local p = c.who.p
        c.who = nil
        outlinePiece(p, Cmd.rest(p))
        say("Nobody selected"); sfx(SFX.back)
    end
    function Cmd.enter()
        if S.cmd then return end
        if S.build then C.exitBuild() end
        S.cmd = { t = 1 }
        Homestead.Restrict(true)
        refresh(true)
        local a, d = Gizmo.cam().aspect, 0.004  -- a dot mid-screen: the game draws no crosshair here
        Lines.set("cmd", { 0.5 - d, 0.5, 0.5 + d, 0.5, 4, 5, 0.5, 0.5 - d * a, 0.5, 0.5 + d * a, 4, 5 })
        say("Command mode: look at someone and press E")
        sfx(SFX.enter)
    end

    C.Cmd = Cmd
end
