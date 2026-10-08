"""Deterministic county targeting from the current Python ranking and known names."""
import re

STATE_NAMES = {'MD': 'Maryland', 'NJ': 'New Jersey', 'NY': 'New York',
               'OH': 'Ohio', 'PA': 'Pennsylvania'}


def requested_rank(question):
    text = question.casefold()
    if re.search(r'\bnext[ -]best\b', text):
        return 2
    for rank, word in enumerate(('first', 'second', 'third', 'fourth', 'fifth'), 1):
        number = ('one', 'two', 'three', 'four', 'five')[rank - 1]
        ordinal_word = word + (r'(?:[ -]best|\s+county)' if rank == 1 else r'(?:[ -]best)?')
        if re.search(r'\b' + ordinal_word + r'\b|\bnumber\s+(?:' + number + '|' + str(rank) + r')\b|#\s*' + str(rank) + r'\b', text):
            return rank
    return None


def explicit_screening_states(question):
    """Only screening/scope requests override controls, not named-county risk context."""
    if requested_rank(question) is None and not re.search(
            r'\b(best\s+(?:county|location)|where|warehouse|only|candidate states)\b', question, re.I):
        return None
    aliases = {alias.casefold(): code for code, name in STATE_NAMES.items() for alias in (code, name)}
    token = '(?:' + '|'.join(re.escape(alias) for alias in sorted(aliases, key=len, reverse=True)) + r')\b(?!\s+County)'
    found = []
    for match in re.finditer(r'\b(?:in|within|across|from)\s+(' + token + r'(?:\s*(?:,|and|or|&|\+)\s*' + token + ')*)', question, re.I):
        found.extend(aliases[item.group().casefold()] for item in re.finditer(token, match.group(1), re.I))
    return sorted(set(found)) or None


def question_targets(question, scored, ranked, selected, states, highlighted_fips=None):
    """Names take precedence; otherwise shortlist, comparison, then current leader."""
    text = question.casefold()
    ordinal = requested_rank(question)
    explicit_scope = explicit_screening_states(question)
    matches = []
    ambiguous = []
    mentions = []
    for name, group in scored.groupby('county', sort=False):
        short = re.sub(r'\s+county$', '', name, flags=re.I)
        pattern = r'(?<!\w)' + re.escape(short.casefold()) + r'(?:\s+county)?(?!\w)'
        mentions.extend((mention, name, group) for mention in re.finditer(pattern, text))
    for mention, name, group in mentions:
        # "in New York" is a state constraint; "New York County" remains explicit.
        if (explicit_scope is not None and not re.search(r'\bcounty$', mention.group(), re.I)
                and mention.group().casefold() in {name.casefold() for name in STATE_NAMES.values()}
                and re.search(r'\b(?:in|within|across|from)\s*$', text[:mention.start()])):
            continue
        # "York" inside "New York County" must not resolve to a second county.
        if any(other.start() <= mention.start() and other.end() >= mention.end()
               and other.end() - other.start() > mention.end() - mention.start()
               for other, _, _ in mentions):
            continue
        # State immediately following the county disambiguates duplicate county names.
        suffix = text[mention.end():]
        named_states = [code for code, full in STATE_NAMES.items()
                        if re.match(r'\s*(?:,|in)?\s*' +
                                    r'(?:' + re.escape(code.casefold()) + '|' + full.casefold() + r')\b', suffix)]
        candidates = group[group.state.isin(named_states)] if named_states else group
        if len(candidates) > 1 and not named_states:
            candidates = candidates[candidates.state.isin(states)]
        if len(candidates) == 1:
            matches.append((mention.start(), candidates.iloc[0].fips))
        else:
            ambiguous.append(name)
    if matches or ambiguous:
        fips = list(dict.fromkeys(fips for _, fips in sorted(matches)))
        return {'kind': 'explicit_counties', 'fips': fips, 'unresolved_names': ambiguous}
    if ordinal is not None:
        targets = list(ranked.iloc[ordinal - 1:ordinal].fips)
        if re.search(r'\b(compare|compared|comparison|trade[- ]?offs)\b', text):
            subjects = [highlighted_fips] if highlighted_fips in set(scored.fips) else list(selected.head(1).fips)
            return {'kind': 'highlighted_comparison', 'fips': list(dict.fromkeys(subjects + targets)),
                    'requested_rank': ordinal, 'unresolved_names': []}
        return {'kind': 'ranked_county', 'fips': targets, 'requested_rank': ordinal, 'unresolved_names': []}
    unknown = re.findall(r'\b([a-z-]+)\s+county\b', text)
    if any(name not in {'current', 'recommended', 'best', 'top', 'selected', 'the', 'a', 'each', 'any'}
           for name in unknown):
        return {'kind': 'unresolved_county', 'fips': [], 'unresolved_names': ['County name could not be resolved']}
    if re.search(r'\b(shortlist|top (?:five|5|options|locations|counties)|top-ranked|best options)\b', text):
        return {'kind': 'current_shortlist', 'fips': list(ranked.head(5).fips), 'unresolved_names': []}
    if re.search(r'\b(compare|comparison|trade[- ]?offs|between these counties)\b', text):
        return {'kind': 'selected_comparison', 'fips': list(selected.fips), 'unresolved_names': []}
    return {'kind': 'current_leader', 'fips': list(ranked.head(1).fips), 'unresolved_names': []}
