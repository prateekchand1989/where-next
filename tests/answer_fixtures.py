"""Adapt legacy test narratives into the new structured provider contract."""
import re
from html import unescape
from interpretation import render_answer_markdown


def structured_answer(markdown):
    sections = []
    for block in markdown.strip().split('\n\n'):
        lines = block.splitlines()
        heading = lines.pop(0).strip('*# ') if len(lines) > 1 else 'Evidence'
        bullets = [line.removeprefix('- ').removeprefix('* ') for line in lines] or [block]
        sections.append({'heading': heading, 'bullets': bullets})
    if len(sections) == 1:
        sections.append({'heading': 'Scope', 'bullets': ['Use the supplied county screening evidence.']})
    return {'headline': 'County screening answer', 'sections': sections}


def expected_answer(markdown):
    return render_answer_markdown(structured_answer(markdown))


def card_html(app):
    return next(item.proto.body for item in app.get('html') if 'wn-summary-grid' in item.proto.body)


def card_values(app):
    return [unescape(text) for text in re.findall(r'<div class="wn-summary-value">(.*?)</div>', card_html(app))]
