-- Navigation backends: Life (life.lua) asks one of these for everything about moving people, chosen at onInit.
-- livenav (modules/livenav.lua) when the LiveNav addon is installed and Settings > People > Navigation is on, else null (props).
-- Backend contract (st = the person's state in life.lua, npc = their entity):
--   caps()                     -> { walk = bool }; without walk people are props and Command mode refuses ("navigation off")
--   near(x, y, z, within)      -> { x, y, z } or nil: nearest standable spot to x, y (about height z), within m
--   free(x, y, z)              -> bool: room to stand there
--   reach(from, to)            -> nil if reachable (or unknown), else why not ("no way there") and a length when known
--   moveTo(npc, st, to, close) -> true if a walk to `to` started (already there counts), false if none; close ends nearer
--   update(npc, st, dt)        -> nil walking, true arrived, false stuck (Life.tick, once a second while walking)
--   stop(npc, st)              -> stop the walk (npc nil: gone); harmless with none
--   keep(npc, st)              -> resend their move if something else cancelled it (every turn)
return function(C)
    local STILL = { walk = false }
    local null = { caps = function() return STILL end, free = function() return true end, moveTo = function() return false end,
                   update = function() return true end, stop = function() end, reach = function() end, keep = function() end }
    function null.near(x, y, z) return { x = x, y = y, z = z } end

    return { null = null, livenav = require("modules/livenav")(C) }
end
