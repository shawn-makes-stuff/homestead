-- The lights of Fallout's workshop pieces: ours to edit (the importer's are used only for a piece not listed here - a
-- piece a player's Fallout mod adds). Per light: Fallout's colour, radius (m: its reach) and fade (a strength),
-- where it is in the piece's space, and for a spotlight its cone (degrees) and direction. A piece shows as many as
-- its template has components for (entities.lua addLight). These replace the import's at load (init.lua OWN).
return {
    fo4_dlc02workshopgeneratorfusion = {   -- Generator - Fusion
        { color = { 0, 94, 94 }, radius = 0.37, fade = 1, pos = { -1.592, -0.937, 0.956 } },
        { color = { 0, 94, 94 }, radius = 0.37, fade = 1, pos = { -0.748, -0.497, 0.956 } },
        { color = { 252, 120, 1 }, radius = 1.83, fade = 0.4, pos = { -0.748, -0.497, 0.956 } },
        { color = { 131, 218, 209 }, radius = 0.91, fade = 1, pos = { -1.161, -0.501, 1.049 }, spot = 90, dir = { -1, 0, 0 } },
        { color = { 101, 254, 154 }, radius = 1.37, fade = 6, pos = { -0.816, -0.915, 0.886 }, spot = 90, dir = { -1, 0, 0 } },
    },
    fo4_dlc02workshopnixietubelight01 = { { color = { 254, 161, 94 }, radius = 0.91, fade = 1, pos = { 0, -0.111, 0.371 } } },   -- Oversized Nixie Tube
    fo4_dlc02workshoprelaxsiren = {   -- Quitting Time Siren
        { color = { 243, 211, 63 }, radius = 1.83, fade = 1, pos = { 0.353, -0.816, 3.739 } },
        { color = { 141, 214, 131 }, radius = 1.83, fade = 1.2, pos = { 0.374, -0.766, 3.375 } },
        { color = { 237, 35, 35 }, radius = 1.83, fade = 0.6, pos = { 0.363, -0.606, 4.089 } },
        { color = { 237, 35, 35 }, radius = 1.83, fade = 0.6, pos = { -0.589, -0.36, 4.089 } },
        { color = { 237, 35, 35 }, radius = 1.83, fade = 0.6, pos = { -0.576, 0.644, 4.089 } },
        { color = { 237, 35, 35 }, radius = 1.83, fade = 0.6, pos = { 0.585, 0.614, 4.089 } },
        { color = { 243, 211, 63 }, radius = 1.83, fade = 1, pos = { 0.585, 0.484, 3.701 } },
        { color = { 243, 211, 63 }, radius = 1.83, fade = 1, pos = { -0.576, 0.644, 3.722 } },
        { color = { 243, 211, 63 }, radius = 1.83, fade = 1, pos = { -0.589, -0.402, 3.666 } },
        { color = { 141, 214, 131 }, radius = 1.83, fade = 1.2, pos = { 0.585, 0.484, 3.383 } },
        { color = { 141, 214, 131 }, radius = 1.83, fade = 1.2, pos = { -0.576, 0.653, 3.326 } },
        { color = { 141, 214, 131 }, radius = 1.83, fade = 1.2, pos = { -0.589, -0.402, 3.243 } },
    },
    fo4_dlc02workshoptamesiren = {   -- Beta Wave Emitter
        { color = { 191, 139, 64 }, radius = 3.43, fade = 1, pos = { 0, 0, 2.444 } },
        { color = { 191, 139, 64 }, radius = 3.43, fade = 1, pos = { 0, 0, 4.11 } },
    },
    fo4_dlc03workshoplanternbottle01 = { { color = { 160, 115, 0 }, radius = 1.83, fade = 1, pos = { 0, 0, 0.267 } } },   -- Bottle Lantern
    fo4_dlc03workshoplanternbottle02 = { { color = { 160, 115, 0 }, radius = 1.83, fade = 1, pos = { 0, 0, 0.243 } } },   -- Bottle Lantern
    fo4_dlc03workshoplanternbottle03 = { { color = { 160, 115, 0 }, radius = 1.83, fade = 1, pos = { 0, 0, 0.222 } } },   -- Bottle Lantern
    fo4_dlc03workshoplanternbottle04 = { { color = { 160, 115, 0 }, radius = 1.83, fade = 1, pos = { 0, 0, 0.206 } } },   -- Bottle Lantern
    fo4_dlc03workshoplanternbottlehanging03 = { { color = { 160, 115, 0 }, radius = 1.83, fade = 1, pos = { 0, 0, -0.64 } } },   -- Bottle Lantern
    fo4_dlc03workshoplanternbottlehanging06 = {   -- Bottle Lantern
        { color = { 160, 115, 0 }, radius = 1.83, fade = 1, pos = { 0.12, 0.085, -0.867 } },
        { color = { 160, 115, 0 }, radius = 1.83, fade = 1, pos = { -0.058, -0.129, -0.725 } },
    },
    fo4_dlc03workshoplanternbulbhanging02 = { { color = { 160, 115, 0 }, radius = 1.83, fade = 1, pos = { 0.01, -0.003, -0.586 } } },   -- Bulb Lantern
    fo4_dlc04workshop_lightbox_starportart01 = { { color = { 209, 188, 167 }, radius = 1.79, fade = 0.5, pos = { 0, -0.362, 0 } } },   -- Poster
    fo4_dlc04workshop_lightbox_starportart02 = { { color = { 209, 188, 167 }, radius = 1.79, fade = 0.5, pos = { 0, -0.362, 0 } } },   -- Poster
    fo4_dlc04workshop_lightbox_starportart03 = { { color = { 209, 188, 167 }, radius = 1.79, fade = 0.5, pos = { 0, -0.362, 0 } } },   -- Poster
    fo4_dlc04workshop_streetlamp02 = { { color = { 220, 213, 163 }, radius = 14.63, fade = 1, pos = { -0.01, 0.001, 6.426 }, spot = 75, dir = { 0, 0, 1 } } },   -- Street Light
    fo4_dlc04workshop_streetlampbanner02a = { { color = { 220, 213, 163 }, radius = 14.63, fade = 1, pos = { 0, 0.001, 6.426 }, spot = 75, dir = { 0, 0, 1 } } },   -- Street Light
    fo4_dlc04workshop_streetlamptilingremap01 = { { color = { 220, 213, 163 }, radius = 14.63, fade = 1, pos = { 0, 1.558, 6.426 }, spot = 75, dir = { 0, 0, 1 } } },   -- Street Light
    fo4_dlc04workshop_streetlamptilingremapbanner01a = { { color = { 220, 213, 163 }, radius = 14.63, fade = 1, pos = { 0, 1.558, 6.426 }, spot = 75, dir = { 0, 0, 1 } } },   -- Street Light
    fo4_dlc05_posteraframe01 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { -0.003, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe02 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe03 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe04 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe05 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe06 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe07 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { -0.003, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe08 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe09 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe10 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe11 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe12 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe13 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { -0.003, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe14 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe15 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe16 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe17 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe18 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { -0.003, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe19 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe20 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe21 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe22 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe23 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { -0.003, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe24 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe25 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe26 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe27 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe28 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe29 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { -0.003, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe30 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe31 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe32 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe33 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe34 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe35 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe36 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe37 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe38 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe39 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe40 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posteraframe41 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.436, -0.079 } } },   -- Poster
    fo4_dlc05_posterbframe01 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe02 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe03 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe04 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe05 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe06 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe07 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe08 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe09 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe10 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe11 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe12 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe13 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe14 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe15 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe16 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe17 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe18 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe19 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe20 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe21 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe22 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe23 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe24 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe25 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe26 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe27 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe28 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe29 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe30 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe31 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe32 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe33 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe34 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe35 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe36 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe37 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe38 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe39 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe40 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05_posterbframe41 = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, -0.242, 0.294 } } },   -- Poster
    fo4_dlc05conduitceilinglight01a = { { color = { 255, 248, 206 }, radius = 3.66, fade = 1, pos = { 0, 0, -0.179 } } },   -- Conduit Light
    fo4_dlc05conduitceilingradiator01 = { { color = { 255, 183, 34 }, radius = 0.29, fade = 2, pos = { 0, 0, -0.129 } } },   -- Conduit - Power Radiator
    fo4_dlc05conduitfloorlight01a = { { color = { 255, 248, 206 }, radius = 3.66, fade = 1, pos = { 0, 0, 0.293 } } },   -- Conduit Light
    fo4_dlc05conduitfloorradiator01 = { { color = { 255, 183, 34 }, radius = 0.29, fade = 2, pos = { 0, 0, 0.243 } } },   -- Conduit - Power Radiator
    fo4_dlc05elevatorcar2 = { { color = { 250, 238, 190 }, radius = 2.14, fade = 0.75, pos = { 0, 0, 1.929 } } },   -- 2 Floor Elevator
    fo4_dlc05elevatorcar3 = { { color = { 250, 238, 190 }, radius = 2.14, fade = 0.75, pos = { 0, 0.004, 1.929 } } },   -- 3 Floor Elevator
    fo4_dlc05elevatorcar4 = { { color = { 250, 238, 190 }, radius = 2.14, fade = 0.75, pos = { 0, 0.03, 1.929 } } },   -- 4 Floor Elevator
    fo4_dlc05marqueearrowdownstraight01 = { { color = { 192, 192, 182 }, radius = 1.83, fade = 1, pos = { 0, -0.311, -0.35 } } },   -- Marquee Arrow
    fo4_dlc05marqueearrowdownturnleft01 = {   -- Marquee Arrow
        { color = { 192, 192, 182 }, radius = 1.83, fade = 1, pos = { 0.041, -0.115, -0.35 } },
        { color = { 192, 192, 182 }, radius = 1.83, fade = 1, pos = { -0.493, -0.115, -0.877 } },
    },
    fo4_dlc05marqueearrowdownturnright01 = {   -- Marquee Arrow
        { color = { 192, 192, 182 }, radius = 1.83, fade = 1, pos = { 0.041, -0.115, -0.35 } },
        { color = { 192, 192, 182 }, radius = 1.83, fade = 1, pos = { 0.574, -0.115, -0.877 } },
    },
    fo4_dlc05marqueearrowleftstraight01 = { { color = { 192, 192, 182 }, radius = 1.83, fade = 1, pos = { -0.35, -0.311, 0 } } },   -- Marquee Arrow
    fo4_dlc05marqueearrowrightstraight01 = { { color = { 192, 192, 182 }, radius = 1.83, fade = 1, pos = { 0.35, -0.311, 0 } } },   -- Marquee Arrow
    fo4_dlc05marqueearrowturnleftdown01 = {   -- Marquee Arrow
        { color = { 192, 192, 182 }, radius = 1.83, fade = 1, pos = { -0.35, -0.115, -0.041 } },
        { color = { 192, 192, 182 }, radius = 1.83, fade = 1, pos = { -0.877, -0.115, -0.574 } },
    },
    fo4_dlc05marqueearrowturnleftup01 = {   -- Marquee Arrow
        { color = { 192, 192, 182 }, radius = 1.83, fade = 1, pos = { -0.35, -0.115, -0.041 } },
        { color = { 192, 192, 182 }, radius = 1.83, fade = 1, pos = { -0.877, -0.115, 0.493 } },
    },
    fo4_dlc05marqueearrowturnrightdown01 = {   -- Marquee Arrow
        { color = { 192, 192, 182 }, radius = 1.83, fade = 1, pos = { 0.877, -0.115, -0.493 } },
        { color = { 192, 192, 182 }, radius = 1.83, fade = 1, pos = { 0.35, -0.115, 0.041 } },
    },
    fo4_dlc05marqueearrowturnrightup01 = {   -- Marquee Arrow
        { color = { 192, 192, 182 }, radius = 1.83, fade = 1, pos = { 0.35, -0.115, 0.041 } },
        { color = { 192, 192, 182 }, radius = 1.83, fade = 1, pos = { 0.877, -0.115, 0.574 } },
    },
    fo4_dlc05marqueearrowupstraight01 = { { color = { 192, 192, 182 }, radius = 1.83, fade = 1, pos = { 0, -0.311, 0.35 } } },   -- Marquee Arrow
    fo4_dlc05marqueearrowupturnleft01 = {   -- Marquee Arrow
        { color = { 192, 192, 182 }, radius = 1.83, fade = 1, pos = { -0.574, -0.115, 0.877 } },
        { color = { 192, 192, 182 }, radius = 1.83, fade = 1, pos = { -0.041, -0.115, 0.35 } },
    },
    fo4_dlc05marqueearrowupturnright01 = {   -- Marquee Arrow
        { color = { 192, 192, 182 }, radius = 1.83, fade = 1, pos = { 0.493, -0.115, 0.877 } },
        { color = { 192, 192, 182 }, radius = 1.83, fade = 1, pos = { -0.041, -0.115, 0.35 } },
    },
    fo4_dlc05marqueesign01 = { { color = { 192, 192, 182 }, radius = 2.74, fade = 2, pos = { 0.149, 0.001, 2.841 } } },   -- Marquee Sign
    fo4_dlc05workshoppowerarmordisplay01 = {   -- Power Armor Display
        { color = { 250, 238, 190 }, radius = 2.14, fade = 0.75, pos = { -0.007, -0.544, 2.355 } },
        { color = { 255, 255, 255 }, radius = 1.83, fade = 6, pos = { -0.433, 1.301, 0.495 }, spot = 55, dir = { -0.294, 0.648, -0.703 } },
        { color = { 255, 255, 255 }, radius = 1.83, fade = 6, pos = { 0.494, 1.055, 0.495 }, spot = 55, dir = { 0, 0.707, -0.707 } },
        { color = { 232, 241, 242 }, radius = 1.43, fade = 0.15, pos = { -0.007, 0.362, 0.151 } },
    },
    fo4_dlc05workshoppowerarmordisplayblue01 = {   -- Power Armor Display
        { color = { 250, 238, 190 }, radius = 2.14, fade = 0.75, pos = { -0.007, -0.544, 2.355 } },
        { color = { 255, 255, 255 }, radius = 1.83, fade = 6, pos = { -0.433, 1.301, 0.495 }, spot = 55, dir = { -0.294, 0.648, -0.703 } },
        { color = { 255, 255, 255 }, radius = 1.83, fade = 6, pos = { 0.494, 1.055, 0.495 }, spot = 55, dir = { 0, 0.707, -0.707 } },
        { color = { 232, 241, 242 }, radius = 1.43, fade = 0.15, pos = { -0.007, 0.362, 0.151 } },
    },
    fo4_dlc05workshoppowerarmordisplayred01 = {   -- Power Armor Display
        { color = { 250, 238, 190 }, radius = 2.14, fade = 0.75, pos = { -0.007, -0.544, 2.355 } },
        { color = { 255, 255, 255 }, radius = 1.83, fade = 6, pos = { -0.433, 1.301, 0.495 }, spot = 55, dir = { -0.294, 0.648, -0.703 } },
        { color = { 255, 255, 255 }, radius = 1.83, fade = 6, pos = { 0.494, 1.055, 0.495 }, spot = 55, dir = { 0, 0.707, -0.707 } },
        { color = { 232, 241, 242 }, radius = 1.43, fade = 0.15, pos = { -0.007, 0.362, 0.151 } },
    },
    fo4_dlc05workshoppowerarmordisplayyellow01 = {   -- Power Armor Display
        { color = { 250, 238, 190 }, radius = 2.14, fade = 0.75, pos = { -0.007, -0.544, 2.355 } },
        { color = { 255, 255, 255 }, radius = 1.83, fade = 6, pos = { -0.433, 1.301, 0.495 }, spot = 55, dir = { -0.294, 0.648, -0.703 } },
        { color = { 255, 255, 255 }, radius = 1.83, fade = 6, pos = { 0.494, 1.055, 0.495 }, spot = 55, dir = { 0, 0.707, -0.707 } },
        { color = { 232, 241, 242 }, radius = 1.43, fade = 0.15, pos = { -0.007, 0.362, 0.151 } },
    },
    fo4_dlc06vaultworkshopgenerator02 = { { color = { 115, 237, 255 }, radius = 2.8, fade = 1, pos = { 0, 0, 0.343 } } },   -- Vault-Tec Super-Reactor
    fo4_dlc06vltlightcagewallmountedgreen = { { color = { 18, 238, 0 }, radius = 1.43, fade = 0.7, pos = { 0, -0.102, 0.203 } } },   -- Wall Light - Green
    fo4_dlc06vltlightcagewallmountedred = { { color = { 209, 56, 56 }, radius = 1.43, fade = 0.6, pos = { 0, -0.102, 0.203 } } },   -- Wall Light - Red
    fo4_dlc06vltlightcagewallmountedwhite = { { color = { 255, 255, 255 }, radius = 1.43, fade = 0.7, pos = { 0, -0.102, 0.203 } } },   -- Wall Light - White
    fo4_dlc06vltlightceiling = { { color = { 255, 255, 255 }, radius = 2.34, fade = 1.25, pos = { 0, 0, -0.1 } } },   -- Fluorescent Ceiling Light
    fo4_dlc06vltlightfluorbox = { { color = { 255, 255, 255 }, radius = 3.66, fade = 0.8, pos = { 0, 0, -0.1 } } },   -- Fluorescent Ceiling Light
    fo4_dlc06vltlightfluorbox02 = { { color = { 255, 255, 255 }, radius = 3.66, fade = 1.25, pos = { 0, 0, 0.009 } } },   -- Fluorescent Ceiling Light
    fo4_dlc06vltlightfluorreshallhalflight = { { color = { 255, 255, 255 }, radius = 3.66, fade = 0.8, pos = { 0, 0, -0.1 } } },   -- Fluorescent Ceiling Light
    fo4_dlc06vltlightfluorreshalllight = { { color = { 255, 255, 255 }, radius = 3.66, fade = 0.8, pos = { 0, 0, -0.1 } } },   -- Fluorescent Ceiling Light
    fo4_dlc06vltlightfluorreswalllight = { { color = { 255, 255, 255 }, radius = 3.66, fade = 1.25, pos = { 0, -0.441, -0.014 } } },   -- Fluorescent Wall Light
    fo4_dlc06vltlightfluorreswalllight02 = { { color = { 255, 255, 255 }, radius = 3.66, fade = 1.25, pos = { 0, -0.435, -0.082 } } },   -- Fluorescent Wall Light
    fo4_dlc06workshophightechtelevision01clean = { { color = { 131, 218, 209 }, radius = 0.91, fade = 1, pos = { 0, -0.235, 0.917 }, spot = 90, dir = { 0.087, 0.996, 0 } } },   -- Television
    fo4_dlc06workshopjukebox01clean = { { color = { 143, 157, 255 }, radius = 0.91, fade = 8, pos = { 0, 0.103, 1.306 } } },   -- Jukebox
    fo4_dlc06workshoptelevision01clean = { { color = { 131, 218, 209 }, radius = 0.91, fade = 1, pos = { -0.007, -0.155, 1.218 }, spot = 90, dir = { 0.087, 0.996, 0 } } },   -- Television
    fo4_dlc06workshoptelevision01tableclean = { { color = { 131, 218, 209 }, radius = 0.91, fade = 1, pos = { -0.007, -0.177, 0.599 }, spot = 90, dir = { 0.087, 0.996, 0 } } },   -- Television
    fo4_dlc06workshopvaultexteriorgeardoor01 = { { color = { 255, 124, 0 }, radius = 10.97, fade = 1, pos = { 0.145, -4.572, 3.429 }, spot = 80, dir = { 0, 0, -1 } } },   -- Vault Door
    fo4_mq206beamemitter = {   -- Molecular Beam Emitter
        { color = { 35, 149, 241 }, radius = 7.32, fade = 10, pos = { 1.864, -0.034, 6.522 } },
        { color = { 35, 149, 241 }, radius = 7.32, fade = 10, pos = { -0.739, 0.014, 5.82 } },
        { color = { 86, 122, 248 }, radius = 3.66, fade = 0.75, pos = { 0.065, 0.098, 4.022 } },
    },
    fo4_mq206reflectorplatform = { { color = { 86, 122, 248 }, radius = 3.66, fade = 0.75, pos = { 0.041, 0.093, 1.586 } } },   -- Stabilized Reflector Platform
    fo4_mq206relaydish = {   -- Relay Dish
        { color = { 217, 209, 193 }, radius = 3.66, fade = 1, pos = { 0.212, 0.264, 4.328 } },
        { color = { 252, 120, 1 }, radius = 1.83, fade = 0.4, pos = { 0.151, 1.232, 4.359 } },
        { color = { 252, 120, 1 }, radius = 1.83, fade = 0.4, pos = { 0.151, 1.067, 2.248 } },
        { color = { 252, 120, 1 }, radius = 1.83, fade = 0.4, pos = { 0.693, 1.067, 3.125 } },
        { color = { 252, 120, 1 }, radius = 1.83, fade = 0.4, pos = { -0.819, 1.067, 3.125 } },
    },
    fo4_wksdisplaycasewall02a = { { color = { 217, 209, 193 }, radius = 3.66, fade = 1, pos = { 0.42, 0, 1.15 } } },   -- Display Case
    fo4_wksdisplaycasewall03a = { { color = { 217, 209, 193 }, radius = 3.66, fade = 1, pos = { 0.376, 0, 1.641 } } },   -- Display Case
    fo4_workbencharmora = { { color = { 237, 168, 122 }, radius = 1.83, fade = 1, pos = { -0.775, 0.195, 0.284 } } },   -- Armor Workbench
    fo4_workbenchcookingfireworkshop = { { color = { 237, 168, 122 }, radius = 1.83, fade = 1, pos = { -0.224, 0.716, 0.283 } } },   -- Cooking Station
    fo4_workshop_hightechlightceiling04_dirty_cream_on = { { color = { 234, 228, 219 }, radius = 1.83, fade = 2, pos = { 0, 0, -0.624 } } },   -- Lamp
    fo4_workshop_hightechlightceiling04_dirty_orange_on = { { color = { 255, 204, 153 }, radius = 1.83, fade = 2, pos = { -0.005, 0, -0.575 } } },   -- Lamp
    fo4_workshop_hightechlightceiling06_dirty_cream_on = { { color = { 234, 228, 219 }, radius = 1.83, fade = 2, pos = { -0.004, 0, -1.045 } } },   -- Lamp
    fo4_workshop_hightechlightceiling06_dirty_orange_on = { { color = { 255, 204, 153 }, radius = 1.83, fade = 2, pos = { -0.004, 0, -1.055 } } },   -- Lamp
    fo4_workshop_hightechlightfloor01_dirty_cream_on = { { color = { 234, 228, 219 }, radius = 1.83, fade = 2, pos = { 0, 0, 1.104 } } },   -- Lamp
    fo4_workshop_hightechlightfloor01_dirty_orange_on = { { color = { 255, 204, 153 }, radius = 1.83, fade = 2, pos = { 0, 0, 1.104 } } },   -- Lamp
    fo4_workshop_hightechlightfloor02_dirty_cream_on = { { color = { 234, 228, 219 }, radius = 1.83, fade = 2, pos = { 0, 0, 0.992 } } },   -- Lamp
    fo4_workshop_hightechlightfloor02_dirty_orange_on = { { color = { 255, 204, 153 }, radius = 1.83, fade = 2, pos = { 0, 0, 1.105 } } },   -- Lamp
    fo4_workshop_hightechlightfloor03_dirty_cream_on = { { color = { 234, 228, 219 }, radius = 1.83, fade = 2, pos = { 0, 0, 1.478 } } },   -- Lamp
    fo4_workshop_hightechlightfloor03_dirty_orange_on = { { color = { 255, 204, 153 }, radius = 1.83, fade = 2, pos = { 0, 0, 1.6 } } },   -- Lamp
    fo4_workshop_hightechlightfloor05_on = { { color = { 255, 204, 153 }, radius = 0.57, fade = 2, pos = { 0, 0, 0.19 } } },   -- Lamp
    fo4_workshop_hightechlightfloor07_on = { { color = { 234, 228, 219 }, radius = 1.93, fade = 10, pos = { 0, -0.296, 1.568 }, spot = 75, dir = { 0, 0, 1 } } },   -- Lamp
    fo4_workshopbar02counter = { { color = { 205, 205, 204 }, radius = 1.37, fade = 4, pos = { 0, -0.271, 0.943 } } },   -- Bar
    fo4_workshopbar03counter = { { color = { 205, 205, 204 }, radius = 1.37, fade = 4, pos = { -0.914, -0.271, 0.943 } } },   -- Restaurant
    fo4_workshopcagebulbwalllight = { { color = { 223, 218, 187 }, radius = 3.66, fade = 1, pos = { 0, -0.294, -0.1 } } },   -- Cage Wall Light
    fo4_workshopcampfire01 = { { color = { 237, 168, 122 }, radius = 1.83, fade = 1, pos = { -0.004, 0.018, 0.81 } } },   -- Camp Fire
    fo4_workshopceilingfanlight01 = {   -- Ceiling Fan
        { color = { 217, 209, 193 }, radius = 3.66, fade = 1, pos = { 0, 0, -0.376 } },
        { color = { 234, 228, 219 }, radius = 1.83, fade = 2, pos = { 0, 0, -0.482 } },
    },
    fo4_workshopconstructionlight01 = { { color = { 235, 222, 192 }, radius = 7.86, fade = 6, pos = { 0.008, -0.105, 1.588 }, spot = 50, dir = { 0, 0.966, 0.259 } } },   -- Construction Light
    fo4_workshopcyclinglightbulb01 = {   -- Cycling Light
        { color = { 255, 255, 255 }, radius = 3.66, fade = 1.5, pos = { 0, 0, -0.622 } },
        { color = { 243, 112, 112 }, radius = 3.66, fade = 1.7, pos = { 0, 0, -0.622 } },
        { color = { 141, 214, 131 }, radius = 3.66, fade = 2.1, pos = { 0, 0, -0.622 } },
        { color = { 47, 149, 251 }, radius = 3.66, fade = 2, pos = { 0, 0, -0.622 } },
        { color = { 160, 129, 235 }, radius = 3.66, fade = 2, pos = { 0, 0, -0.622 } },
        { color = { 255, 153, 0 }, radius = 3.66, fade = 2, pos = { 0, 0, -0.622 } },
        { color = { 243, 211, 63 }, radius = 3.66, fade = 2, pos = { 0, 0, -0.622 } },
        { color = { 115, 176, 232 }, radius = 3.66, fade = 1.25, pos = { 0, 0, -0.622 } },
        { color = { 30, 123, 208 }, radius = 3.66, fade = 0.85, pos = { 0, 0, -0.622 } },
        { color = { 71, 159, 62 }, radius = 3.66, fade = 1.3, pos = { 0, 0, -0.622 } },
        { color = { 114, 173, 122 }, radius = 3.66, fade = 0.85, pos = { 0, 0, -0.622 } },
        { color = { 255, 167, 19 }, radius = 3.66, fade = 1.25, pos = { 0, 0, -0.622 } },
        { color = { 188, 100, 20 }, radius = 3.66, fade = 0.85, pos = { 0, 0, -0.622 } },
        { color = { 133, 118, 214 }, radius = 3.66, fade = 1.55, pos = { 0, 0, -0.622 } },
        { color = { 94, 78, 203 }, radius = 3.66, fade = 1.1, pos = { 0, 0, -0.622 } },
        { color = { 227, 121, 121 }, radius = 3.66, fade = 1, pos = { 0, 0, -0.622 } },
        { color = { 187, 72, 72 }, radius = 3.66, fade = 0.75, pos = { 0, 0, -0.622 } },
        { color = { 231, 203, 107 }, radius = 3.66, fade = 1.2, pos = { 0, 0, -0.622 } },
        { color = { 202, 172, 70 }, radius = 3.66, fade = 0.75, pos = { 0, 0, -0.622 } },
        { color = { 219, 215, 193 }, radius = 3.66, fade = 1.1, pos = { 0, 0, -0.622 } },
        { color = { 167, 158, 126 }, radius = 3.66, fade = 0.75, pos = { 0, 0, -0.622 } },
    },
    fo4_workshopfancywalllight01 = { { color = { 251, 249, 227 }, radius = 3.66, fade = 1, pos = { 0, -0.162, 0.182 } } },   -- Fancy Wall Light
    fo4_workshopfancywalllight02 = { { color = { 251, 249, 227 }, radius = 3.66, fade = 1, pos = { 0, -0.223, 0.196 } } },   -- Fancy Wall Light
    fo4_workshopfluorescentlight = { { color = { 218, 214, 173 }, radius = 3.66, fade = 2.5, pos = { 0, -0.001, 0.502 } } },   -- Fluorescent Light
    fo4_workshopgeneratorlarge = { { color = { 217, 209, 193 }, radius = 3.66, fade = 1, pos = { 0.116, -2.005, 1.586 } } },   -- Generator - Large
    fo4_workshophightechceilinglight = { { color = { 226, 235, 233 }, radius = 3.66, fade = 1, pos = { 0, 0, -0.1 } } },   -- Ceiling Light
    fo4_workshophightechtelevision01 = { { color = { 131, 218, 209 }, radius = 0.91, fade = 1, pos = { 0, -0.235, 0.917 }, spot = 90, dir = { 0.087, 0.996, 0 } } },   -- Television
    fo4_workshophightechwalllight = { { color = { 226, 235, 233 }, radius = 3.66, fade = 1, pos = { 0, -0.077, 0.098 } } },   -- Wall Light
    fo4_workshophightechwalllight02 = { { color = { 226, 235, 233 }, radius = 3.66, fade = 1, pos = { 0, -0.077, 0.133 } } },   -- Wall Light
    fo4_workshopindcatlight = { { color = { 255, 248, 206 }, radius = 3.66, fade = 1, pos = { 0, -0.146, 0.214 } } },   -- Industrial Wall Light
    fo4_workshopjukebox01 = { { color = { 143, 157, 255 }, radius = 0.91, fade = 8, pos = { 0, 0.103, 1.306 } } },   -- Jukebox
    fo4_workshoplightbulblight = { { color = { 228, 203, 182 }, radius = 7.32, fade = 1, pos = { 0, 0, -0.1 } } },   -- Lightbulb
    fo4_workshopmetalfirebarrel = { { color = { 218, 145, 109 }, radius = 3.66, fade = 1.5, pos = { 0, 0, 0.998 } } },   -- Fire Barrel
    fo4_workshopmirrorball01 = {   -- Mirror Ball
        { color = { 217, 209, 193 }, radius = 3.66, fade = 1, pos = { 0, 0, -0.29 } },
        { color = { 234, 228, 219 }, radius = 0.51, fade = 10, pos = { 0, 0, -0.6 }, spot = 90, dir = { 0, 0, -1 } },
    },
    fo4_workshopoillamp01 = { { color = { 237, 168, 122 }, radius = 1.83, fade = 1, pos = { 0, 0, 0.35 } } },   -- Oil Lamp
    fo4_workshoppowerpylon02 = { { color = { 255, 183, 34 }, radius = 0.69, fade = 2, pos = { -0.048, -0.142, 4.294 } } },   -- Power Pylon - Large
    fo4_workshoppowerpylonswitch02 = { { color = { 255, 183, 34 }, radius = 0.69, fade = 2, pos = { -0.048, -0.142, 4.294 } } },   -- Switched Power Pylon - Large
    fo4_workshopstorearmor02counter = { { color = { 205, 205, 204 }, radius = 1.37, fade = 4, pos = { 0, -0.271, 0.943 } } },   -- Armor Shop
    fo4_workshopstorearmor03counter = { { color = { 205, 205, 204 }, radius = 1.37, fade = 4, pos = { -0.914, -0.271, 0.943 } } },   -- Armor Emporium
    fo4_workshopstoreclinic02counter = { { color = { 205, 205, 204 }, radius = 1.37, fade = 4, pos = { 0, -0.271, 0.943 } } },   -- Clinic
    fo4_workshopstoreclinic03counter = { { color = { 205, 205, 204 }, radius = 1.37, fade = 4, pos = { -0.914, -0.271, 0.943 } } },   -- Surgery Center
    fo4_workshopstoreclothing02counter = { { color = { 205, 205, 204 }, radius = 1.37, fade = 4, pos = { 0, -0.271, 0.943 } } },   -- Clothing Shop
    fo4_workshopstoreclothing03counter = { { color = { 205, 205, 204 }, radius = 1.37, fade = 4, pos = { -0.914, -0.271, 0.943 } } },   -- Clothing Emporium
    fo4_workshopstoremisc02counter = { { color = { 205, 205, 204 }, radius = 1.37, fade = 4, pos = { 0, -0.271, 0.943 } } },   -- Trading Shop
    fo4_workshopstoremisc03counter = { { color = { 205, 205, 204 }, radius = 1.37, fade = 4, pos = { -0.914, -0.271, 0.943 } } },   -- Trading Emporium
    fo4_workshopstoreweapon02counter = { { color = { 205, 205, 204 }, radius = 1.37, fade = 4, pos = { 0, -0.271, 0.943 } } },   -- Weapons Shop
    fo4_workshopstoreweapon03counter = { { color = { 205, 205, 204 }, radius = 1.37, fade = 4, pos = { -0.914, -0.271, 0.943 } } },   -- Weapons Emporium
    fo4_workshopstreetlamp01 = { { color = { 226, 235, 233 }, radius = 7.32, fade = 1.3, pos = { 0.001, -1.058, 8.451 } } },   -- Street Light
    fo4_workshopstreetlamp02 = { { color = { 226, 235, 233 }, radius = 7.32, fade = 1.3, pos = { 0.126, -0.708, 8.38 } } },   -- Street Light
    fo4_workshopstreetlamp03 = { { color = { 226, 235, 233 }, radius = 7.32, fade = 1.3, pos = { 0.001, 0, 4.764 } } },   -- Street Light
    fo4_workshopstreetoillamppost = { { color = { 233, 175, 97 }, radius = 3.66, fade = 1, pos = { 0, 0, 2.516 } } },   -- Oil Lamp Post
    fo4_workshopstringoflights = { { color = { 228, 203, 182 }, radius = 7.32, fade = 1, pos = { 0, 0, -0.554 } } },   -- String of Lights
    fo4_workshopstrobelight01 = { { color = { 175, 175, 175 }, radius = 7.32, fade = 1, pos = { 0, 0, -0.076 } } },   -- Strobe Light
    fo4_workshopsubwaylight = { { color = { 226, 235, 233 }, radius = 3.66, fade = 1, pos = { 0, -0.144, 0.129 } } },   -- Subway Light
    fo4_workshoptablelightblue01 = { { color = { 251, 249, 227 }, radius = 3.66, fade = 1, pos = { 0, 0, 0.421 } } },   -- Table Lamp Blue
    fo4_workshoptablelightyellow01 = { { color = { 251, 249, 227 }, radius = 3.66, fade = 1, pos = { 0, 0, 0.562 } } },   -- Yellow Table Lamp
    fo4_workshoptelevision01 = { { color = { 131, 218, 209 }, radius = 0.91, fade = 1, pos = { -0.007, -0.155, 1.218 }, spot = 90, dir = { 0.087, 0.996, 0 } } },   -- Television
    fo4_workshoptelevision01table = { { color = { 131, 218, 209 }, radius = 0.91, fade = 1, pos = { -0.007, -0.177, 0.599 }, spot = 90, dir = { 0.087, 0.996, 0 } } },   -- Television
    fo4_workshopterminal = { { color = { 237, 168, 122 }, radius = 0.23, fade = 3, pos = { -0.044, -0.105, 0.965 } } },   -- Terminal
    fo4_workshoptracklighting01 = { { color = { 226, 235, 233 }, radius = 3.66, fade = 1, pos = { 0.014, -0.038, -0.1 } } },   -- Track Light
    fo4_workshoptracklighting02 = { { color = { 235, 235, 226 }, radius = 3.66, fade = 3.5, pos = { 0.014, -0.045, -0.1 } } },   -- Track Light
    fo4_workshoptracklightingground = { { color = { 226, 235, 233 }, radius = 1.83, fade = 3, pos = { -0.014, -0.038, 0.075 } } },   -- Track Light Ground
    fo4_workshoptrafficlight = {   -- Traffic Light
        { color = { 237, 35, 35 }, radius = 1.83, fade = 0.6, pos = { 0, -0.648, -0.487 } },
        { color = { 141, 214, 131 }, radius = 1.83, fade = 1.2, pos = { 0, -0.648, -1.202 } },
        { color = { 243, 211, 63 }, radius = 1.83, fade = 1, pos = { 0, -0.648, -0.837 } },
    },
    fo4_workshoptrapelectricalarc01 = { { color = { 79, 132, 255 }, radius = 5.71, fade = 2, pos = { 0, 0, 0.266 } } },   -- Tesla Arc
    fo4_workshopwaterpurifier = { { color = { 255, 183, 34 }, radius = 1.37, fade = 2, pos = { -0.126, -0.592, 1.438 } } },   -- Water Purifier
    fo4_workshopwaterpurifierlarge = { { color = { 255, 183, 34 }, radius = 1.37, fade = 2, pos = { -2.168, 0.163, 1.929 } } },   -- Water Purifier - Industrial
    fo4_workshopwaxcandles01 = { { color = { 237, 168, 122 }, radius = 1.83, fade = 1, pos = { 0, 0, 0.328 } } },   -- Candles
    fo4_workshopwaxcandleswallsconce01 = { { color = { 237, 168, 122 }, radius = 1.83, fade = 1, pos = { 0, -0.634, 0.237 } } },   -- Wall Sconce
    -- The spotlights' light is Fallout's own: it hangs on the turret's skin as an art object (ARMA ONAM -> ARTO, its
    -- AddOnNode 201 -> LIGH WorkshopTurretSpotlightLight01: colour 235 222 192, radius 1024 units, fade 4, a 70 degree
    -- spot), which the importer's lights.py doesn't follow - so its values are here. Where: the art's node on the
    -- head's bone (the floor one's gun at 0, 0, 0.737 + 0, 0, 0.36; the wall one's lamp at 0, 0.357, 0 + 0, 0.19, -0.19,
    -- shining down its lamp's 45 degrees), a little out of the lens. lm: its strength as it is - the 800 every other
    -- light is held to lit nothing at a spotlight's reach (user, 2026-10-05). modules/turret.lua turns the floor one's.
    -- beam: a visible shaft from the lens to the light's reach, its radius at its start in metres; at its end it is
    -- 5.17 times that (the game's mesh: entities.lua BEAM - one number widens both). 0.24: 0.5 m wide at the lamp,
    -- 2.5 m at 14.6 m; Fallout's lens ring, 0.139, "looks more like a flashlight beam" (user, 2026-10-06, who also
    -- wanted "the start a touch lower": pos z 6 cm under the lens's middle, 1.10 and -0.26). Fallout's own beam is a
    -- flat smoke card as long as the light reaches.
    fo4_workshopturretspotlight = { { color = { 235, 222, 192 }, radius = 14.63, fade = 4, lm = 8000, pos = { 0, 0.12, 1.04 }, spot = 70, dir = { 0, 1, 0 }, beam = 0.24 } },   -- Spotlight
    fo4_dlc01_workshopturretspotlight = { { color = { 235, 222, 192 }, radius = 14.63, fade = 4, lm = 8000, pos = { 0, 0.62, -0.32 }, spot = 70, dir = { 0, 0.707, -0.707 }, beam = 0.24 } },   -- Wall Spotlight
}
