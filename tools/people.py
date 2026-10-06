"""The placeable people: every named character, from the game's Character records (source/survey/chars.txt, dumped in
game by tools/dev/chars.lua: id, display name, template, crowd, attitude group). One record per name - the plain
`Character.<Name>` one where it exists, else the one with the fewest quest / scene marks - leaving out crowds,
role names (vendors, cops, drones, gangers), V, and variants that aren't the person (hallucinations, holograms,
mirrors, corpses). Writes <work>/survey/people.json (<work>: paths.work(), ours source/) and tools/dev/people_list.lua;
build_catalog.py reads people.json, tools/dev/people_check.lua spawns each in game and marks the ones that come up
hostile or broken (<work>/survey/people_check.txt: record, verdict, attitude).
  python tools/people.py
"""
import collections, json, os, re
import paths
from npc_looks import templates
ROOT = paths.ROOT
SURVEY = os.path.join(paths.work(), 'survey')

ROLES = re.compile(r'\b(vendor|drone|mech|soldier|officer|cop|guard|operator|unit|netrunner|ganger|bartender|driver|'
                   r'resident|guest|worker|robot|bouncer|receptionist|technician|civilian|citizen|tourist|security|'
                   r'agent|trooper|squad|thug|merc|mercenary|scav|scavenger|nomad|corpo|employee|patron|client|'
                   r'customer|dancer|doll|joytoy|medic|doctor|nurse|mechanic|cook|chef|waiter|waitress|janitor|'
                   r'passenger|pilot|guest|boss|lieutenant|sergeant|captain|commander|leader|member|fixer|dealer|'
                   r'bodyguard|assassin|sniper|hacker|runner|voodoo|wraith|maelstrom|tyger|valentino|animal|'
                   r'mox|militech|arasaka|kang tao|ncpd|maxtac|barghest|prevention|biotechnica|trauma|'
                   r'homeless|junkie|prisoner|inmate|hostage|victim|corpse|body|dummy|target|test|voice|'
                   r'\?|unknown|man|woman|kid|child|boy|girl|punk|gangoon|gonk|raffen|6th street|aldecaldos|'
                   r'wraiths|inquisitor|lookout|sentry|reaper|butcher|thief|bum|drunk|reporter|crew|staff|'
                   r'monk|priest|preacher|dj|vip|shopkeeper|clerk|barber|ripperdoc|attendant|announcer|host)\b', re.I)
NOT_PERSON = re.compile(r'hallucin|vision|holo|mirror|replacer|dead|corpse|body|bd_|_bd|braindance|puppet|'
                        r'dream|memory|ghost|flashback|cutscene|_cs_|scene|fake|dummy|test|debug|voice|photo|'
                        r'screen|tv_|_tv|video|call|phone|avatar|terminal', re.I)


# records seen in game where the plain one doesn't show the person: Character.Silverhand is the engram (only V sees
# him), invisible when placed; the q115 one is Johnny in the flesh (2026-09-30, tools/dev/spawn_row.lua)
PREFER = {'Johnny': 'Character.q115_suicide_johnny'}


# People the game's records name by their role: the real character, under their own name (user, 2026-10-05: "all
# characters in photo mode have a real world counterpart" - found by their looks: the photo mode's puppet and the record
# here wear the same appearance; Wade Bleecker is Mr. Hands, who is listed). Record -> name.
NAMED = {'Character.lizzies_bouncer': 'Rita Wheeler', 'Character.q105_yakuza_manager': 'Cheri Nowlin', 'Character.Stout': 'Meredith Stout',
         'Character.myers': 'President Myers', 'Character.reed': 'Solomon Reed',
         'Character.q105_voodoo_queen': 'Brigitte'}      # (named "[Data Encrypted]": Brigitte in the flesh - the plain
# record, Voodoo_Queen, is her cyberspace self, see `what`)
# The photo mode's puppets were listed for a day (2026-10-05, never released): they take no animation. Kept out of the
# menu (`old`: build_catalog hides the row), so one placed then still loads and can be scrapped.
OLD = {'Cheri': 'Cheri Nowlin', 'Meredith': 'Meredith Stout', 'Myers': 'President Myers', 'Reed': 'Solomon Reed',
       'RitaWheeler': 'Rita Wheeler', 'Wade': 'Wade'}


# Animals the name filters above let through only as one (the four ue_ cats share the name "Cat", the plain one wins),
# or not at all (Nibbles is flagged a crowd record, the cow's record says "fake"). One row each (user, 2026-10-06:
# "add animals"). Record -> name.
ANIMALS = {'Character.ue_cat_black': 'Cat (black)', 'Character.ue_cat_pink': 'Cat (pink)', 'Character.ue_cat_tricolor': 'Cat (tricolor)',
           'Character.ue_cat_white': 'Cat (white)', 'Character.q003_cat': 'Nibbles', 'Character.sq021_fake_cow_npc': 'Cow'}


# "holo" in the record, no hologram to look at (user, 2026-10-05): calls and plain people
NOT_HOLO = {'Character.q001_holo_coroner', 'Character.q001_tbug_holocall', 'Character.Tbug_holo', 'Character.q001_holo_tech_02', 'Character.q001_holo_tech_01',
            'Character.Holocall_Placide', 'Character.q305_songbird_blackwall_holo', 'Character.q001_holo_police_officer'}


# Entity templates with no mesh in them: a voice, an AI, a thing the quest shows by other means (read 2026-10-06 -
# Skippy, Erebus and the Canto share the invisible speaker; Brendan and the fortune teller are props of the world,
# their records spawn nothing to see)
NO_BODY = re.compile(r'invisible|q005_penthouse_siri|q001_biomonitor|mq037_brendan', re.I)


# See-through, and nothing in the record or the look's name says so: its skin's material does (read 2026-10-06 with
# WolvenKit - blackwall_blendable_skin.mt, the figures of Songbird's memory; Johnny's skin_blendable.mt is solid)
SEE_THROUGH = {'Character.BrainhackNPC_wa'}


def what(parts):
    """What an entity is by its meshes (survey/people_looks.json, tools/npc_looks.py: [[mesh, look, mask], ...]), where
    its name and record don't say (user, 2026-10-06: "robots and holograms in the general list (characters that were
    see through or mechs)"): 'Drones and Mechs' - a droid's head (the casino's staff: six named people share one
    template whose default look is the droid, and their records name no look), or no part of a character at all (a
    chopper); 'Holograms' - skin in a cyberspace / hologram look (silverhand_overlay.mt: Brigitte)."""
    names = [(m.replace('/', '\\').split('\\')[-1].lower(), l.lower()) for m, l, _ in parts]
    if not names: return None
    if any(re.match(r'h0_\d+_\w*droid', n) for n, _ in names) or not any('\\characters\\' in m.lower() for m, _, _ in parts): return 'Drones and Mechs'
    if any(re.match(r'(h0|t0)_', n) and re.search(r'cyberspace|holo', l) for n, l in names): return 'Holograms'


def score(rid):
    """lower is more the person themself: Character.<Name> plain, then fewer quest marks"""
    tail = rid.split('.', 1)[-1]
    return (bool(re.match(r'(mq|sq|q|ma|ep1|dlc|minor|story|side|job)\d*_', tail, re.I)), tail.count('_'), len(tail))


def main():
    rows = [l.rstrip('\n').split('\t') for l in open(os.path.join(SURVEY, 'chars.txt'), encoding='utf-8') if l.strip()]
    rows = [r + [''] * (5 - len(r)) for r in rows]
    # Who has a body (user, 2026-10-06: "they should all have bodies unless they dont have anything at all when I
    # spawn them"): the record's entity template, from the game's tweakdb. A name goes to a record that has one; a
    # record without stays in the list as `old` (not offered; one placed still loads).
    tpl = templates([r[0] for r in rows])
    body = lambda rid: bool(tpl[rid][0]) and not NO_BODY.search(tpl[rid][0])
    pick = lambda recs: min([x for x in recs if body(x[0])] or recs, key=lambda x: score(x[0]))
    by = collections.defaultdict(list)
    for rid, name, _tpl, crowd, att in rows:
        name = name.strip()
        if not name or crowd == 'true' or name == 'V' or name.startswith('!') or ROLES.search(name) or NOT_PERSON.search(rid): continue
        if not rid.startswith('Character.') or len(name) > 28: continue
        by[name].append((rid, att))
    people = []
    for name, recs in sorted(by.items()):
        if len(recs) > 12: continue                                  # a name on many records is a role, not a person
        rid, att = pick(recs)
        if name in PREFER: rid, att = next((r for r in recs if r[0] == PREFER[name]), (rid, att))
        people.append(dict(name=name, record=rid, attitude=att, variants=len(recs), **({'main': True} if name in PREFER else {})))
    ids = {r[0]: r[4] for r in rows}
    people = [p for p in people if p['record'] not in NAMED and p['record'] not in ANIMALS]
    people += [dict(name=name, record=rid, attitude=ids[rid], variants=1, main=True) for rid, name in sorted(NAMED.items()) if rid in ids]
    people += [dict(name=name, record=rid, attitude=ids[rid], variants=1, group='Animals') for rid, name in sorted(ANIMALS.items()) if rid in ids]
    people += [dict(name=name, record='Character.%s_Puppet_Photomode' % who, attitude='friendly', variants=1, old=True)
               for who, name in sorted(OLD.items()) if 'Character.%s_Puppet_Photomode' % who in ids]
    # Those a role's name stands for (user, 2026-10-05): one of each name - a Voodoo Boy, a Wraith, a Food Vendor - the
    # record with the fewest marks; drones, mechs and robots in a folder of their own; and holograms (named, or by their
    # record). Hostile ones too: the mod makes whoever is placed keep the peace (entities.lua).
    # Machines and animals by their name or record, named ones too (user, 2026-10-06: "some mechs and holograms hiding
    # out in the general user list", "an animals category": Lars is q003_spiderbot, a Camera q112_camera_drone); a
    # person's cyberspace self goes with the holograms.
    MACHINE = re.compile(r'drone|mech\b|robot|android|droid|turret|\bbot\b|_bot\b|minotaur|spiderbot|chimera|cerberus|_exo\b', re.I)
    ANIMAL = re.compile(r'(?<![a-z])(cat|chicken|iguana)(?![a-z])', re.I)
    roles, holo = collections.defaultdict(list), []
    for rid, name, _tpl, crowd, att in rows:
        name = name.strip()
        if not rid.startswith('Character.') or crowd == 'true' or name.startswith('!') or 'photomode' in rid.lower() or rid in NAMED: continue
        if rid in NOT_HOLO: continue
        if 'holo' in rid.lower():
            holo.append(dict(name=(name if name and name != 'Hologram' else 'Hologram: ' + re.sub(r'(?i)^(q|sq|mq|sts|ep1)\d*_|_?holo(gram|call)?_?', ' ', rid.split('.', 1)[1]).replace('_', ' ').strip().title())[:28],
                             record=rid, attitude=att, variants=1, group='Holograms'))
        elif name and ROLES.search(name) and not NOT_PERSON.search(rid) and len(name) <= 28 and name.lower() != 'drone':   # (a bare "Drone": a quest's
            # stand-in that comes up in a T-pose - user, 2026-10-05)
            roles[name.title() if name.isupper() else name].append((rid, att))
    extra = []
    for name, recs in sorted(roles.items()):
        rid, att = pick(recs)                                        # ("Robot": the bar droid, Character.cz_con_foodshop_01 -
        # the user's pick, 2026-10-06; it stood in a T-pose until entities.lua `wake`)
        extra.append(dict(name=name, record=rid, attitude=att, variants=len(recs)))
        was = min(recs, key=lambda x: score(x[0]))                   # (listed until 2026-10-06: the role's base record,
        if was[0] != rid: extra.append(dict(name=name, record=was[0], attitude=was[1], variants=1))   # no body)
    seen = collections.Counter()
    for p in holo:
        seen[p['name']] += 1
        if seen[p['name']] > 1: p['name'] = ('%s %d' % (p['name'][:25], seen[p['name']]))
    have = {p['record'] for p in people}
    extra = [p for p in extra + holo if p['record'] not in have]
    people += extra
    lp = os.path.join(SURVEY, 'people_looks.json')              # (dev time, after npc_looks.py: without it nobody is told by
    looks = json.load(open(lp)) if os.path.exists(lp) else {}   # their meshes; someone new: people.py, npc_looks.py, people.py)
    if not looks: print('no people_looks.json: folders by name and record only')
    for p in people:
        s = p['name'] + ' ' + p['record'].split('.', 1)[1]
        if p.get('group') or p.get('old'): continue
        if ANIMAL.search(s): p['group'] = 'Animals'
        elif MACHINE.search(s): p['group'] = 'Drones and Mechs'
        elif 'cyberspace' in s.lower() or p['record'] in SEE_THROUGH: p['group'] = 'Holograms'
        elif what(looks.get(p['record']) or []):
            p['group'] = what(looks[p['record']])
            print('by its meshes: %s (%s) -> %s' % (p['name'], p['record'], p['group']))
    for p in people:
        if not body(p['record']): p['old'] = True
    print('no body, not offered:', sorted(p['name'] for p in people if p.get('old') and 'Photomode' not in p['record']))
    print('by role: %d, machines: %d, animals: %d, holograms: %d' % (len(extra) - len(holo), *(sum(1 for p in people if p.get('group') == g) for g in ('Drones and Mechs', 'Animals', 'Holograms'))))
    json.dump(people, open(os.path.join(SURVEY, 'people.json'), 'w'), indent=0)
    print(len(people), 'people')
    # for the in-game check (tools/dev/people_check.lua): the records as a Lua list
    lua = 'HS_PEOPLE = {\n' + ''.join('  "%s",\n' % p['record'] for p in people) + '}\n'
    open(os.path.join(ROOT, 'tools', 'dev', 'people_list.lua'), 'w', encoding='utf-8').write(lua)


if __name__ == '__main__':
    main()
