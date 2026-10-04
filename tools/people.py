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


def score(rid):
    """lower is more the person themself: Character.<Name> plain, then fewer quest marks"""
    tail = rid.split('.', 1)[-1]
    return (bool(re.match(r'(mq|sq|q|ma|ep1|dlc|minor|story|side|job)\d*_', tail, re.I)), tail.count('_'), len(tail))


def main():
    rows = [l.rstrip('\n').split('\t') for l in open(os.path.join(SURVEY, 'chars.txt'), encoding='utf-8') if l.strip()]
    rows = [r + [''] * (5 - len(r)) for r in rows]
    by = collections.defaultdict(list)
    for rid, name, _tpl, crowd, att in rows:
        name = name.strip()
        if not name or crowd == 'true' or name == 'V' or name.startswith('!') or ROLES.search(name) or NOT_PERSON.search(rid): continue
        if not rid.startswith('Character.') or len(name) > 28: continue
        by[name].append((rid, att))
    people = []
    for name, recs in sorted(by.items()):
        if len(recs) > 12: continue                                  # a name on many records is a role, not a person
        rid, att = min(recs, key=lambda x: score(x[0]))
        if name in PREFER: rid, att = next((r for r in recs if r[0] == PREFER[name]), (rid, att))
        people.append(dict(name=name, record=rid, attitude=att, variants=len(recs), **({'main': True} if name in PREFER else {})))
    json.dump(people, open(os.path.join(SURVEY, 'people.json'), 'w'), indent=0)
    print(len(people), 'people')
    # for the in-game check (tools/dev/people_check.lua): the records as a Lua list
    lua = 'HS_PEOPLE = {' + chr(10) + ''.join('  "%s",' % p['record'] + chr(10) for p in people) + '}' + chr(10)
    open(os.path.join(ROOT, 'tools', 'dev', 'people_list.lua'), 'w', encoding='utf-8').write(lua)


if __name__ == '__main__':
    main()
