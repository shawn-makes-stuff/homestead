-- Fallout's turrets (modules/turret.lua): range (m), rate (shots a second), dmg (percent of the target's health a hit),
-- turn (degrees a second), muzzle { forward, up } in m from the head's pivot, flash (the game's own muzzle effect) and
-- sound (the game's own event). No rate: it has no gun and only follows its target (a spotlight).
local HMG = "base\\fx\\weapons\\firearms\\special\\militech_hmg\\w_special_hmg_muzzle_tpp.effect"
local TECH = "base\\fx\\weapons\\tech\\rifles\\corporate\\tech_riffle_muzzle_tpp.effect"
local FIRE = "dev_security_turret_fire"
return {
    fo4_workshopturrettripod = { range = 35, rate = 4, dmg = 1.5, turn = 120, muzzle = { 0.8, 0.5 }, flash = HMG, sound = FIRE },          -- Machinegun Turret
    fo4_workshopturrettripodmounted = { range = 40, rate = 5, dmg = 2, turn = 120, muzzle = { 0.8, 0.45 }, flash = HMG, sound = FIRE },  -- Heavy Machinegun Turret
    fo4_workshopturretlaserheavy = { range = 40, rate = 2, dmg = 3.5, turn = 150, muzzle = { 0.5, 0.35 }, flash = TECH, sound = FIRE },    -- Turret (laser)
    fo4_workshopturretspotlight = { range = 40, turn = 90 },                                                                            -- Spotlight
    fo4_dlc01_workshopturretspotlight = { range = 40, turn = 90 },                                                                      -- Wall Spotlight
}
